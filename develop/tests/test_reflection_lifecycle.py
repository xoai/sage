from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.contracts import NormalizedEvent
from sage_runtime.reflection import (
    ReflectionQuestion,
    complete_reflection,
    render_reflection_context,
    request_reflection,
    skip_reflection,
)
from sage_runtime.state import append_event, read_events, reconcile_run


def event(index: int, event_type: str, **payload: object) -> NormalizedEvent:
    return NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": f"evt-{index:03d}",
            "type": event_type,
            "occurred_at": f"2026-07-10T01:{index:02d}:00Z",
            "payload": payload,
        }
    )


@pytest.fixture
def completed_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / ".sage" / "runtime" / "runs" / "run-reflect"
    events = (
        event(
            0,
            "run.started",
            run_id="run-reflect",
            explicit_intent=True,
            workflow_owner="external:build",
        ),
        event(1, "tool.outcome", observation_id="call-1", tool_name="terminal", success=True),
        event(2, "user.correction", explicit=True, message="Use /map"),
        event(3, "artifact.observed", artifact_id="spec", path=".sage/work/x/spec.md"),
        event(4, "verification.recorded", verification_id="tests", passed=True),
        event(
            5,
            "learning.candidate",
            candidate_id="candidate-example",
            trigger="user-correction",
            evidence_refs=["evt-002"],
            dedupe_key="a" * 64,
        ),
        event(6, "learning.recalled", record_ids=["lrn-map"]),
        event(7, "run.completed"),
    )
    for item in events:
        append_event(run_dir, item)
    return run_dir


def test_completed_run_requests_evidence_reflection_exactly_once(
    completed_run: Path,
) -> None:
    first = request_reflection(
        completed_run,
        mode="evidence",
        source="stop",
        transcript_path="session/transcript.jsonl",
        occurred_at="2026-07-10T01:08:00Z",
    )
    second = request_reflection(
        completed_run,
        mode="evidence",
        source="stop",
        occurred_at="2026-07-10T01:09:00Z",
    )

    assert first.requested is True
    assert second.requested is False
    assert second.status == "requested"
    requested_events = [
        item for item in read_events(completed_run) if item.type == "reflection.requested"
    ]
    assert len(requested_events) == 1
    state = reconcile_run(completed_run)
    assert state.reflection_status == "requested"
    assert state.reflection_requested_at == "2026-07-10T01:08:00Z"


def test_requested_or_completed_reflection_is_a_noop(completed_run: Path) -> None:
    request_reflection(
        completed_run,
        occurred_at="2026-07-10T01:08:00Z",
    )
    active = request_reflection(
        completed_run,
        occurred_at="2026-07-10T01:09:00Z",
    )
    completed = complete_reflection(
        completed_run,
        stored=1,
        novel_candidates=1,
        occurred_at="2026-07-10T01:10:00Z",
    )
    after = request_reflection(
        completed_run,
        occurred_at="2026-07-10T01:11:00Z",
    )

    assert active.requested is False
    assert completed.completed is True
    assert after.requested is False
    assert after.status == "completed"


def test_evidence_mode_does_not_require_user_feedback(completed_run: Path) -> None:
    request = request_reflection(
        completed_run,
        mode="evidence",
        occurred_at="2026-07-10T01:08:00Z",
    )
    context = render_reflection_context(request)

    assert request.requested is True
    assert request.unresolved_questions == ()
    assert "Do not require user feedback" in context
    assert "transcript" in context.casefold()
    assert "events.jsonl" in context
    assert "tool outcomes" in context.casefold()
    assert "corrections" in context.casefold()
    assert "artifacts" in context.casefold()
    assert "verification" in context.casefold()
    assert "prior learnings" in context.casefold()


@pytest.mark.parametrize(
    "kind",
    ["external-outcome", "personal-preference", "stakeholder-signal"],
)
def test_only_external_question_kinds_are_rendered(
    completed_run: Path, kind: str
) -> None:
    request = request_reflection(
        completed_run,
        mode="evidence",
        unresolved_questions=(ReflectionQuestion(kind=kind, question="Need outside input?"),),
        occurred_at="2026-07-10T01:08:00Z",
    )
    assert "Need outside input?" in render_reflection_context(request)


def test_observable_question_kind_is_rejected(completed_run: Path) -> None:
    with pytest.raises(ValueError, match="question kind"):
        ReflectionQuestion(kind="tool-output", question="What did the command say?")


def test_no_novel_learning_is_a_valid_completion(completed_run: Path) -> None:
    request_reflection(completed_run, occurred_at="2026-07-10T01:08:00Z")
    result = complete_reflection(
        completed_run,
        stored=0,
        novel_candidates=0,
        occurred_at="2026-07-10T01:09:00Z",
    )

    assert result.completed is True
    assert result.stored == 0
    assert reconcile_run(completed_run).reflection_status == "completed"


def test_requested_reflection_can_be_durably_skipped(completed_run: Path) -> None:
    request_reflection(completed_run, occurred_at="2026-07-10T01:08:00Z")

    first = skip_reflection(
        completed_run,
        reason="No evidence-backed reflection is applicable.",
        occurred_at="2026-07-10T01:09:00Z",
    )
    second = skip_reflection(
        completed_run,
        reason="Repeated finalize callback.",
        occurred_at="2026-07-10T01:10:00Z",
    )

    assert first.skipped is True
    assert second.skipped is False
    assert reconcile_run(completed_run).reflection_status == "skipped"
    assert len(
        [item for item in read_events(completed_run) if item.type == "reflection.skipped"]
    ) == 1


def test_stop_and_finalize_sources_cannot_loop(completed_run: Path) -> None:
    stop = request_reflection(
        completed_run,
        source="stop",
        occurred_at="2026-07-10T01:08:00Z",
    )
    finalize = request_reflection(
        completed_run,
        source="finalize",
        occurred_at="2026-07-10T01:09:00Z",
    )

    assert stop.requested is True
    assert finalize.requested is False
    assert len(
        [item for item in read_events(completed_run) if item.type == "reflection.requested"]
    ) == 1


def test_incomplete_run_does_not_request_reflection(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "active-run"
    append_event(
        run_dir,
        event(0, "run.started", run_id="active-run", explicit_intent=True),
    )
    result = request_reflection(run_dir, occurred_at="2026-07-10T01:01:00Z")
    assert result.requested is False
    assert result.status == "not-requested"


def test_render_requests_reflect_and_self_learning_without_invented_answers(
    completed_run: Path,
) -> None:
    request = request_reflection(
        completed_run,
        occurred_at="2026-07-10T01:08:00Z",
    )
    context = render_reflection_context(request, max_bytes=4096)

    assert "canonical `reflect` skill" in context
    assert "Reinforce, Prevent, and Improve" in context
    assert "WHEN / CHECK / BECAUSE" in context
    assert "canonical `sage-self-learning` skill" in context
    assert "candidate-example" in context
    assert "Do not invent" in context
    assert "reflection complete" in context
    assert "reflection skip" in context
    assert str(completed_run) in context
    assert len(context.encode("utf-8")) <= 4096


def test_cli_can_complete_requested_reflection(completed_run: Path) -> None:
    request_reflection(completed_run, occurred_at="2026-07-10T01:08:00Z")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "reflection",
            "complete",
            "--run-dir",
            str(completed_run),
            "--stored",
            "0",
            "--novel-candidates",
            "0",
            "--occurred-at",
            "2026-07-10T01:09:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "completed"
    assert reconcile_run(completed_run).reflection_status == "completed"


def test_cli_can_skip_requested_reflection(completed_run: Path) -> None:
    request_reflection(completed_run, occurred_at="2026-07-10T01:08:00Z")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "reflection",
            "skip",
            "--run-dir",
            str(completed_run),
            "--reason",
            "No evidence-backed reflection is applicable.",
            "--occurred-at",
            "2026-07-10T01:09:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "skipped"
    assert reconcile_run(completed_run).reflection_status == "skipped"
