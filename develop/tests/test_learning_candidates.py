from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.contracts import NormalizedEvent
from sage_runtime.learning_candidates import (
    detect_learning_candidates,
    load_candidate,
    render_candidate_context,
)
from sage_runtime.state import append_event, read_events


def event(index: int, event_type: str, **payload: object) -> NormalizedEvent:
    return NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": f"evt-{index:03d}",
            "type": event_type,
            "occurred_at": f"2026-07-10T00:{index:02d}:00Z",
            "payload": payload,
        }
    )


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs" / "run-learning"
    append_event(
        directory,
        event(
            0,
            "run.started",
            run_id="run-learning",
            explicit_intent=True,
            workflow_owner="sage:build",
        ),
    )
    return directory


def append(run_dir: Path, *events: NormalizedEvent) -> None:
    for item in events:
        assert append_event(run_dir, item) is True


def test_explicit_user_correction_creates_evidence_only_candidate(run_dir: Path) -> None:
    append(
        run_dir,
        event(
            1,
            "user.correction",
            explicit=True,
            message="Use /map, not sage:map.",
        ),
    )

    result = detect_learning_candidates(run_dir)

    assert result.appended == 1
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.trigger == "user-correction"
    assert candidate.evidence_refs == ("evt-001",)
    assert len(candidate.dedupe_key) == 64
    candidate_events = [item for item in read_events(run_dir) if item.type == "learning.candidate"]
    assert len(candidate_events) == 1
    payload = candidate_events[0].to_dict()["payload"]
    assert payload["candidate_id"] == candidate.id
    assert payload["evidence_refs"] == ["evt-001"]
    assert "message" not in payload
    assert "learning" not in payload


def test_detection_is_idempotent_with_stable_candidate_key(run_dir: Path) -> None:
    append(run_dir, event(1, "user.correction", explicit=True, message="Correction"))

    first = detect_learning_candidates(run_dir)
    second = detect_learning_candidates(run_dir)

    assert first.appended == 1
    assert second.appended == 0
    assert second.candidates[0].id == first.candidates[0].id
    assert second.candidates[0].dedupe_key == first.candidates[0].dedupe_key


def test_same_normalized_failure_twice_creates_one_candidate(run_dir: Path) -> None:
    append(
        run_dir,
        event(
            1,
            "tool.outcome",
            observation_id="call-1",
            tool_name="terminal",
            success=False,
            failure_fingerprint=" Exit 127: COMMAND not found ",
        ),
        event(
            2,
            "tool.outcome",
            observation_id="call-2",
            tool_name="terminal",
            success=False,
            failure_fingerprint="exit   127: command NOT found",
        ),
    )

    result = detect_learning_candidates(run_dir)

    assert result.appended == 1
    assert result.candidates[0].trigger == "repeated-failure"
    assert result.candidates[0].evidence_refs == ("evt-001", "evt-002")


def test_one_failure_alone_does_not_create_candidate(run_dir: Path) -> None:
    append(
        run_dir,
        event(
            1,
            "tool.outcome",
            observation_id="call-1",
            tool_name="terminal",
            success=False,
            failure_fingerprint="exit 127",
        ),
    )
    result = detect_learning_candidates(run_dir)
    assert result.candidates == ()
    assert result.appended == 0


def test_replayed_identical_post_tool_envelopes_do_not_fake_repetition(
    run_dir: Path,
) -> None:
    common = {
        "observation_id": "call-replayed",
        "tool_name": "terminal",
        "success": False,
        "failure_fingerprint": "exit 127",
    }
    append(
        run_dir,
        event(1, "tool.outcome", **common),
        event(2, "tool.outcome", **common),
    )

    result = detect_learning_candidates(run_dir)
    assert result.candidates == ()


def test_fail_to_pass_for_same_target_creates_recovery_candidate(run_dir: Path) -> None:
    append(
        run_dir,
        event(
            1,
            "verification.recorded",
            verification_id="tests:router",
            passed=False,
            exit_code=1,
        ),
        event(
            2,
            "verification.recorded",
            verification_id="tests:other",
            passed=True,
            exit_code=0,
        ),
        event(
            3,
            "verification.recorded",
            verification_id="tests:router",
            passed=True,
            exit_code=0,
        ),
    )

    result = detect_learning_candidates(run_dir)

    assert len(result.candidates) == 1
    assert result.candidates[0].trigger == "fail-to-pass"
    assert result.candidates[0].evidence_refs == ("evt-001", "evt-003")


def test_verified_tool_contradiction_references_prior_evidence(run_dir: Path) -> None:
    append(
        run_dir,
        event(1, "assumption.recorded", subject="api command", claim="sage:map"),
        event(
            2,
            "tool.outcome",
            observation_id="call-map",
            tool_name="skill",
            success=True,
            verified=True,
            contradicts_event_id="evt-001",
        ),
    )

    result = detect_learning_candidates(run_dir)

    assert len(result.candidates) == 1
    assert result.candidates[0].trigger == "behavior-contradiction"
    assert result.candidates[0].evidence_refs == ("evt-001", "evt-002")


@pytest.mark.parametrize(
    "payload",
    [
        {"verified": False, "contradicts_event_id": "evt-001"},
        {"verified": True, "contradicts_event_id": "missing-event"},
        {"verified": True},
    ],
)
def test_unverified_or_unreferenced_hunch_does_not_create_candidate(
    run_dir: Path, payload: dict[str, object]
) -> None:
    append(
        run_dir,
        event(1, "assumption.recorded", subject="api"),
        event(2, "behavior.observed", **payload),
    )
    assert detect_learning_candidates(run_dir).candidates == ()


def test_candidate_context_requests_canonical_skill_without_authored_lesson(
    run_dir: Path,
) -> None:
    append(
        run_dir,
        event(1, "user.correction", explicit=True, message="SECRET CORRECTION PROSE"),
    )
    candidate = detect_learning_candidates(run_dir).candidates[0]

    rendered = render_candidate_context(candidate, max_bytes=2048)

    assert "canonical `sage-self-learning` skill" in rendered
    assert "classify" in rendered
    assert "What happened" in rendered
    assert "Why wrong" in rendered
    assert "What's correct" in rendered
    assert "Prevention rule" in rendered
    assert "search before store" in rendered
    assert "enrich" in rendered
    assert "invalidate" in rendered
    assert "link" in rendered
    assert candidate.id in rendered
    assert "evt-001" in rendered
    assert "SECRET CORRECTION PROSE" not in rendered
    assert len(rendered.encode("utf-8")) <= 2048


def test_load_candidate_round_trips_persisted_event(run_dir: Path) -> None:
    append(run_dir, event(1, "user.correction", explicit=True, message="Correction"))
    created = detect_learning_candidates(run_dir).candidates[0]
    assert load_candidate(run_dir, created.id) == created


def test_learning_candidate_cli_detect_and_render(run_dir: Path) -> None:
    append(run_dir, event(1, "user.correction", explicit=True, message="Correction"))
    cli = ROOT / "runtime" / "tools" / "sage_runtime_cli.py"

    detected = subprocess.run(
        [sys.executable, str(cli), "learning", "detect", "--run-dir", str(run_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert detected.returncode == 0, detected.stderr
    payload = json.loads(detected.stdout)
    assert payload["appended"] == 1
    candidate_id = payload["candidates"][0]["id"]

    rendered = subprocess.run(
        [
            sys.executable,
            str(cli),
            "learning",
            "candidate-context",
            "--run-dir",
            str(run_dir),
            "--id",
            candidate_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "sage-self-learning" in rendered.stdout
    assert candidate_id in rendered.stdout
