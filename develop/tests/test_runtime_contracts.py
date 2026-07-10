from __future__ import annotations

import os
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.contracts import ContractError, NormalizedEvent, RunState
from sage_runtime.io import atomic_write_json


VALID_EVENT = {
    "schema": "sage-event/v1",
    "event_id": "evt-001",
    "type": "run.started",
    "occurred_at": "2026-07-10T00:00:00Z",
    "payload": {"run_id": "run-001", "strict": False},
}


@pytest.mark.parametrize("field", ["schema", "event_id", "type", "occurred_at"])
def test_event_requires_stable_identity(field: str) -> None:
    raw = dict(VALID_EVENT)
    del raw[field]

    with pytest.raises(ContractError, match=field):
        NormalizedEvent.from_dict(raw)


def test_event_rejects_unknown_schema() -> None:
    raw = {**VALID_EVENT, "schema": "sage-event/v2"}

    with pytest.raises(ContractError, match="schema"):
        NormalizedEvent.from_dict(raw)


@pytest.mark.parametrize(
    "occurred_at",
    [
        "2026-07-10 00:00:00",
        "2026-07-10T00:00:00",
        "2026-07-10T01:00:00+01:00",
        "not-a-timestamp",
    ],
)
def test_event_requires_a_utc_timestamp(occurred_at: str) -> None:
    raw = {**VALID_EVENT, "occurred_at": occurred_at}

    with pytest.raises(ContractError, match="occurred_at"):
        NormalizedEvent.from_dict(raw)


def test_event_preserves_payload_without_allowing_mutation() -> None:
    event = NormalizedEvent.from_dict(VALID_EVENT)

    assert event.payload == {"run_id": "run-001", "strict": False}
    assert event.to_dict() == VALID_EVENT
    with pytest.raises(TypeError):
        event.payload["strict"] = True
    with pytest.raises(FrozenInstanceError):
        event.type = "run.completed"


def test_run_state_rejects_semantic_narrative_fields() -> None:
    raw = {
        "schema": "run-state/v1",
        "run_id": "run-001",
        "status": "active",
        "explicit_intent": True,
        "workflow_owner": "sage:build",
        "active_capability": "solution.specify",
        "active_provider": "sage:specify",
        "strict": False,
        "composition_hash": "composition-sha",
        "route_catalog_hash": "catalog-sha",
        "artifacts": {},
        "verification": {},
        "dirty": False,
        "updated_at": "2026-07-10T00:00:00Z",
        "rationale": "The model preferred this provider.",
    }

    with pytest.raises(ContractError, match="rationale"):
        RunState.from_dict(raw)


def test_atomic_json_is_stable_and_replaced_from_same_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "nested" / "state.json"
    real_replace = os.replace
    observed: dict[str, Path] = {}

    def capture_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        observed["source"] = source_path
        observed["destination"] = destination_path
        assert source_path.parent == destination_path.parent == path.parent
        real_replace(source_path, destination_path)

    monkeypatch.setattr("sage_runtime.io.os.replace", capture_replace)

    atomic_write_json(path, {"z": 1, "a": 2})

    assert observed["destination"] == path
    assert path.read_text(encoding="utf-8") == '{\n  "a": 2,\n  "z": 1\n}\n'
    assert list(path.parent.glob(".state.json.*.tmp")) == []
