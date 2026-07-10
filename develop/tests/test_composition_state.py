from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.composition_contracts import ResolvedBinding, ResolvedComposition
from sage_runtime.contracts import NormalizedEvent
from sage_runtime.state import StateError, append_event, reduce_events


def event(index: int, event_type: str, **payload: object) -> NormalizedEvent:
    return NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": f"composition-{index:03d}",
            "type": event_type,
            "occurred_at": f"2026-07-10T13:{index:02d}:00Z",
            "payload": payload,
        }
    )


def resolved_composition() -> ResolvedComposition:
    return ResolvedComposition(
        catalog_hash="catalog-sha",
        selected_workflow="sage:build",
        bindings=(
            ResolvedBinding(
                capability="requirements.elicit",
                provider_id="external:brainstorm",
                role="owner",
                combine="exclusive",
                atomic=True,
                terminal=None,
                provenance="explicit",
            ),
            ResolvedBinding(
                capability="solution.specify",
                provider_id="external:brainstorm",
                role="owner",
                combine="exclusive",
                atomic=True,
                terminal="design-approved",
                provenance="explicit",
            ),
            ResolvedBinding(
                capability="change.implement",
                provider_id="sage:implement",
                role="owner",
                combine="exclusive",
                atomic=False,
                terminal="implementation-complete",
                provenance="workflow-default",
            ),
        ),
        hash="resolved-sha",
    )


def started() -> NormalizedEvent:
    return event(
        1,
        "run.started",
        run_id="run-composed",
        explicit_intent=True,
        strict=False,
        workflow_owner="sage:build",
        route_catalog_hash="route-sha",
        composition_hash="resolved-sha",
        resolved_composition=resolved_composition().to_dict(),
    )


def test_run_started_persists_resolved_composition_hash() -> None:
    state = reduce_events([started()])

    assert state.composition_hash == "resolved-sha"
    assert state.active_capability is None
    assert state.active_provider is None
    assert state.atomic_span is None
    assert state.provider_terminal is None


def test_capability_entry_selects_resolved_owner_and_locks_atomic_span() -> None:
    state = reduce_events(
        [started(), event(2, "capability.entered", capability="requirements.elicit")]
    )

    assert state.active_capability == "requirements.elicit"
    assert state.active_provider == "external:brainstorm"
    assert state.atomic_span == "external:brainstorm"
    assert state.provider_terminal == "design-approved"


def test_unrelated_provider_selection_is_rejected_during_atomic_span() -> None:
    events = [
        started(),
        event(2, "capability.entered", capability="requirements.elicit"),
        event(3, "provider.selected", provider="sage:implement"),
    ]

    with pytest.raises(StateError, match="atomic"):
        reduce_events(events)


def test_terminal_signal_unlocks_atomic_span() -> None:
    state = reduce_events(
        [
            started(),
            event(2, "capability.entered", capability="requirements.elicit"),
            event(3, "capability.entered", capability="solution.specify"),
            event(4, "provider.terminal", signal="design-approved"),
        ]
    )

    assert state.atomic_span is None
    assert state.provider_terminal is None
    assert state.active_capability is None
    assert state.active_provider is None


def test_explicit_provider_switch_can_unlock_atomic_span() -> None:
    state = reduce_events(
        [
            started(),
            event(2, "capability.entered", capability="requirements.elicit"),
            event(
                3,
                "provider.switched",
                provider="manual:override",
                explicit=True,
            ),
        ]
    )

    assert state.atomic_span is None
    assert state.provider_terminal is None
    assert state.active_provider == "manual:override"


def test_cancel_unlocks_provider_and_ends_run() -> None:
    state = reduce_events(
        [
            started(),
            event(2, "capability.entered", capability="requirements.elicit"),
            event(3, "run.cancelled", reason="user requested cancel"),
        ]
    )

    assert state.status == "cancelled"
    assert state.atomic_span is None
    assert state.active_provider is None


def test_restart_replay_preserves_identical_atomic_lock() -> None:
    events = [started(), event(2, "capability.entered", capability="requirements.elicit")]

    first = json.dumps(reduce_events(events).to_dict(), sort_keys=True)
    replayed = json.dumps(reduce_events(events + events).to_dict(), sort_keys=True)

    assert replayed == first


def test_missing_resolved_provider_records_diagnostic_instead_of_bad_transition(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / ".sage" / "runtime" / "runs" / "run-composed"
    append_event(run_dir, started())

    with pytest.raises(StateError, match="no resolved owner"):
        append_event(
            run_dir,
            event(2, "capability.entered", capability="problem.investigate"),
        )

    lines = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert [item["type"] for item in lines] == ["run.started", "runtime.diagnostic"]
    assert lines[-1]["payload"]["rejected_event_id"] == "composition-002"
    assert lines[-1]["payload"]["code"] == "missing-resolved-provider"
