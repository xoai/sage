from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.contracts import NormalizedEvent
from sage_runtime.state import (
    StateBusyError,
    append_event,
    load_active_run,
    reconcile_run,
    reduce_events,
)


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


def complete_run_events() -> list[NormalizedEvent]:
    return [
        event(
            1,
            "run.started",
            run_id="run-001",
            explicit_intent=True,
            strict=True,
            workflow_owner="sage:build",
            route_catalog_hash="catalog-sha",
            composition_hash="composition-sha",
        ),
        event(2, "workflow.selected", workflow_owner="sage:build"),
        event(3, "capability.entered", capability="solution.specify"),
        event(4, "provider.selected", provider="external:brainstorm"),
        event(
            5,
            "artifact.observed",
            artifact_id="spec",
            path=".sage/work/feature/spec.md",
            sha256="abc123",
            rationale="The model considers this specification complete.",
        ),
        event(6, "approval.recorded", checkpoint="design-approved", approved=True),
        event(7, "verification.recorded", verification_id="tests", passed=True),
        event(8, "learning.candidate", candidate_id="candidate-1"),
        event(9, "reflection.completed", stored=0),
        event(10, "run.completed"),
    ]


def test_reducer_derives_only_observable_state() -> None:
    state = reduce_events(complete_run_events())

    assert state.to_dict() == {
        "schema": "run-state/v1",
        "run_id": "run-001",
        "status": "completed",
        "explicit_intent": True,
        "workflow_owner": "sage:build",
        "active_capability": None,
        "active_provider": None,
        "strict": True,
        "composition_hash": "composition-sha",
        "route_catalog_hash": "catalog-sha",
        "artifacts": {
            "spec": {
                "artifact_id": "spec",
                "path": ".sage/work/feature/spec.md",
                "sha256": "abc123",
            },
            "approvals": {
                "design-approved": {"checkpoint": "design-approved", "approved": True}
            },
        },
        "verification": {
            "tests": {"verification_id": "tests", "passed": True}
        },
        "dirty": False,
        "atomic_span": None,
        "provider_terminal": None,
        "reflection_status": "completed",
        "reflection_requested_at": None,
        "updated_at": "2026-07-10T00:10:00Z",
    }


def test_replaying_duplicate_event_ids_is_byte_identical() -> None:
    events = complete_run_events()
    once = json.dumps(reduce_events(events).to_dict(), sort_keys=True)
    replayed = json.dumps(reduce_events(events + events).to_dict(), sort_keys=True)

    assert replayed == once


def test_append_is_idempotent_and_reconcile_restores_state(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".sage" / "runtime"
    run_dir = runtime_dir / "runs" / "run-001"
    started = complete_run_events()[0]

    assert append_event(run_dir, started) is True
    assert append_event(run_dir, started) is False
    assert len((run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert load_active_run(runtime_dir).run_id == "run-001"
    (run_dir / "state.json").unlink()

    restored = reconcile_run(run_dir)

    assert restored.run_id == "run-001"
    assert (run_dir / "state.json").is_file()


def test_unknown_event_is_preserved_without_mutating_state(tmp_path: Path) -> None:
    run_dir = tmp_path / ".sage" / "runtime" / "runs" / "run-001"
    append_event(run_dir, complete_run_events()[0])
    before = (run_dir / "state.json").read_bytes()

    append_event(run_dir, event(11, "platform.telemetry", summary="model-authored text"))

    assert len((run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert (run_dir / "state.json").read_bytes() == before
    assert "summary" not in json.loads(before)


def test_completed_run_is_not_loaded_as_active(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".sage" / "runtime"
    run_dir = runtime_dir / "runs" / "run-001"
    for item in complete_run_events():
        append_event(run_dir, item)

    assert load_active_run(runtime_dir) is None
    pointer = json.loads((runtime_dir / "active-run.json").read_text(encoding="utf-8"))
    assert pointer == {
        "schema": "active-run/v1",
        "active": False,
        "run_id": "run-001",
        "state_path": "runs/run-001/state.json",
        "bound_at": "2026-07-10T00:01:00Z",
        "updated_at": "2026-07-10T00:10:00Z",
    }


def test_append_times_out_when_another_writer_holds_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run-001"
    run_dir.mkdir()
    (run_dir / ".state.lock").write_text("held", encoding="utf-8")
    monkeypatch.setattr("sage_runtime.state.LOCK_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(StateBusyError, match="250 ms|busy"):
        append_event(run_dir, complete_run_events()[0])


def test_state_active_cli_fails_open_when_no_run_exists(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "state",
            "active",
            "--project",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"active": False}


def test_event_append_cli_reads_normalized_json_from_stdin(tmp_path: Path) -> None:
    started = complete_run_events()[0]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "event",
            "append",
            "--project",
            str(tmp_path),
        ],
        input=json.dumps(started.to_dict()),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["appended"] is True
    assert output["state"]["run_id"] == "run-001"


def test_state_reconcile_cli_restores_projection(tmp_path: Path) -> None:
    run_dir = tmp_path / ".sage" / "runtime" / "runs" / "run-001"
    append_event(run_dir, complete_run_events()[0])
    (run_dir / "state.json").unlink()

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "state",
            "reconcile",
            "--project",
            str(tmp_path),
            "--run-id",
            "run-001",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"]["status"] == "active"
    assert (run_dir / "state.json").is_file()


def test_reconciling_completed_history_does_not_clear_another_active_run(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / ".sage" / "runtime"
    old_run = runtime / "runs" / "run-old"
    current_run = runtime / "runs" / "run-current"
    append_event(
        old_run,
        NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": "old-start",
                "type": "run.started",
                "occurred_at": "2026-07-10T01:00:00Z",
                "payload": {"run_id": "run-old", "explicit_intent": True},
            }
        ),
    )
    append_event(
        old_run,
        NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": "old-done",
                "type": "run.completed",
                "occurred_at": "2026-07-10T01:01:00Z",
                "payload": {"run_id": "run-old"},
            }
        ),
    )
    append_event(
        current_run,
        NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": "current-start",
                "type": "run.started",
                "occurred_at": "2026-07-10T01:02:00Z",
                "payload": {"run_id": "run-current", "explicit_intent": True},
            }
        ),
    )

    reconcile_run(old_run)

    active = load_active_run(runtime)
    assert active is not None
    assert active.run_id == "run-current"
