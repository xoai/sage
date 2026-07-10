"""Bind authoritative route decisions to replayable run state."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping

from .contracts import NormalizedEvent, RunState
from .composition_contracts import ResolvedComposition
from .io import atomic_write_json
from .resolver import (
    ChoiceRequired,
    CompositionCatalog,
    CompositionRequest,
    resolve as resolve_composition,
)
from .state import StateBusyError, append_event


_EXPLICIT_COMMAND = re.compile(r"^\s*/[A-Za-z0-9][A-Za-z0-9:_-]*\b")
_WORKFLOW_FLAGS = {
    "--strict": ("strict", True),
    "--quality-locked": ("quality_locked", True),
    "--no-quality-locked": ("quality_locked", False),
    "--autonomous": ("autonomous", True),
    "--no-autonomous": ("autonomous", False),
}
_ROUTE_LOCK_TIMEOUT_SECONDS = 0.5
_ROUTE_LOCK_POLL_SECONDS = 0.01


@contextmanager
def _route_allocation_lock(runtime: Path) -> Iterator[None]:
    runtime.mkdir(parents=True, exist_ok=True)
    lock_path = runtime / ".route-allocation.lock"
    deadline = time.monotonic() + _ROUTE_LOCK_TIMEOUT_SECONDS
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(
                lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise StateBusyError(
                    "route allocation busy after 500 ms; platform hook should fail open"
                ) from exc
            time.sleep(_ROUTE_LOCK_POLL_SECONDS)
    try:
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _timestamp(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _active_run_dir(runtime: Path) -> Path | None:
    pointer = _read_json(runtime / "active-run.json")
    if pointer is None or pointer.get("schema") != "active-run/v1":
        return None
    if pointer.get("active") is not True:
        return None
    state_path = pointer.get("state_path")
    if not isinstance(state_path, str) or not state_path:
        return None
    resolved_runtime = runtime.resolve()
    state = (runtime / state_path).resolve()
    if resolved_runtime != state.parent and resolved_runtime not in state.parents:
        return None
    return state.parent if state.is_file() else None


def _state(run_dir: Path) -> RunState | None:
    raw = _read_json(run_dir / "state.json")
    if raw is None:
        return None
    try:
        return RunState.from_dict(raw)
    except Exception:
        return None


def _cancel(run_dir: Path, occurred_at: str, reason: str) -> None:
    current = _state(run_dir)
    if current is None or current.status != "active":
        return
    append_event(
        run_dir,
        NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"run-cancelled-{current.run_id}",
                "type": "run.cancelled",
                "occurred_at": occurred_at,
                "payload": {"run_id": current.run_id, "reason": reason},
            }
        ),
    )


def _receipt_key(session_id: str, prompt: str, target: str) -> str:
    material = "\0".join((session_id, prompt, target))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _next_run_id(runtime: Path, session_id: str) -> str:
    session = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]
    prefix = f"run-{session}-"
    runs = runtime / "runs"
    counters = []
    if runs.is_dir():
        for path in runs.iterdir():
            if not path.is_dir() or not path.name.startswith(prefix):
                continue
            suffix = path.name[len(prefix) :]
            if suffix.isdigit():
                counters.append(int(suffix))
    return f"{prefix}{max(counters, default=0) + 1:04d}"


def _workflow_modes(project: Path, prompt: str) -> dict[str, object]:
    defaults = {"quality_locked": False, "autonomous": False}
    config_path = project / ".sage" / "config.yaml"
    try:
        config_text = config_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        config_text = ""
    for key in defaults:
        defaults[key] = bool(
            re.search(rf"^{re.escape(key)}: true$", config_text, re.MULTILINE)
        )

    match = _EXPLICIT_COMMAND.match(prompt)
    remaining = prompt[match.end() :].strip() if match is not None else ""
    selected: dict[str, bool | None] = {
        "strict": None,
        "quality_locked": None,
        "autonomous": None,
    }
    error: str | None = None
    while remaining.startswith("--"):
        parts = remaining.split(None, 1)
        token = parts[0]
        remaining = parts[1].lstrip() if len(parts) > 1 else ""
        parsed = _WORKFLOW_FLAGS.get(token)
        if parsed is None:
            error = f"unknown workflow flag: {token}"
            break
        key, value = parsed
        previous = selected[key]
        if previous is not None and previous is not value:
            error = f"conflicting workflow flags for {key}"
            break
        selected[key] = value

    if error is not None:
        return {
            "strict": False,
            "quality_locked": False,
            "autonomous": False,
            "sources": {},
            "error": error,
        }
    values: dict[str, object] = {"strict": selected["strict"] is True}
    sources: dict[str, str] = {}
    if selected["strict"] is not None:
        sources["strict"] = "flag"
    for key in ("quality_locked", "autonomous"):
        if selected[key] is not None:
            values[key] = selected[key] is True
            sources[key] = "flag"
        else:
            values[key] = defaults[key]
            if defaults[key]:
                sources[key] = "config"
    values["sources"] = sources
    values["error"] = None
    return values


def _resolve_workflow_composition(
    project: Path, workflow_owner: str, modes: Mapping[str, object]
) -> ResolvedComposition | ChoiceRequired | None:
    raw = _read_json(project / ".sage" / "composition.json")
    if raw is None:
        return None
    catalog = CompositionCatalog.from_dict(raw)
    defaults = catalog.workflow_defaults.get(workflow_owner)
    if defaults is None:
        return None
    explicit: dict[str, object] = {}
    capabilities = list(defaults.capabilities)
    if workflow_owner in {"sage:build", "sage:fix", "sage:architect"}:
        if modes.get("quality_locked") is True:
            explicit["quality.enforce"] = {"owner": "quality-locked"}
            capabilities.append("quality.enforce")
        if modes.get("autonomous") is True:
            explicit["execution.control"] = {"owner": "autonomous"}
            capabilities.append("execution.control")
    return resolve_composition(
        catalog,
        CompositionRequest(
            explicit=explicit,
            selected_workflow=workflow_owner,
            required_capabilities=tuple(capabilities),
        ),
    )


def bind_route_decision(
    project: Path,
    prompt: str,
    decision: Mapping[str, object],
    *,
    session_id: str = "platform",
    occurred_at: str | None = None,
) -> Path | None:
    """Persist only explicit start/switch/cancel decisions; advice is read-only."""
    kind = decision.get("kind")
    if kind not in {"explicit", "switch", "cancel"}:
        return None
    if decision.get("authoritative") is not True:
        return None
    runtime = Path(project) / ".sage" / "runtime"
    with _route_allocation_lock(runtime):
        return _bind_route_decision_locked(
            Path(project),
            runtime,
            prompt,
            decision,
            session_id=session_id,
            occurred_at=occurred_at,
        )


def _bind_route_decision_locked(
    project: Path,
    runtime: Path,
    prompt: str,
    decision: Mapping[str, object],
    *,
    session_id: str,
    occurred_at: str | None,
) -> Path | None:
    kind = decision.get("kind")
    timestamp = _timestamp(occurred_at)
    active = _active_run_dir(runtime)
    if kind == "cancel":
        if active is not None:
            _cancel(active, timestamp, "explicit-cancel")
        return None

    target = decision.get("target")
    if not isinstance(target, str) or not target:
        return None
    workflow_owner = f"sage:{target.removeprefix('/').removeprefix('sage:')}"
    modes = _workflow_modes(project, prompt)
    composition = _resolve_workflow_composition(project, workflow_owner, modes)
    if isinstance(composition, ChoiceRequired):
        atomic_write_json(runtime / "choice-required.json", composition.to_dict())
        return None
    try:
        (runtime / "choice-required.json").unlink()
    except FileNotFoundError:
        pass
    receipt = runtime / "route-receipts" / f"{_receipt_key(session_id, prompt, target)}.json"
    previous = _read_json(receipt)
    if previous is not None:
        prior_id = previous.get("run_id")
        if isinstance(prior_id, str):
            prior_dir = runtime / "runs" / prior_id
            prior_state = _state(prior_dir)
            if (
                prior_state is not None
                and prior_state.status == "active"
                and prior_state.workflow_owner == workflow_owner
            ):
                return prior_dir

    if active is not None:
        _cancel(active, timestamp, "explicit-switch")
    run_id = _next_run_id(runtime, session_id)
    run_dir = runtime / "runs" / run_id
    catalog = _read_json(runtime / "route-catalog.json") or {}
    started_payload: dict[str, object] = {
        "run_id": run_id,
        "explicit_intent": True,
        "strict": modes.get("strict") is True,
        "modes": modes,
        "workflow_owner": workflow_owner,
        "route_catalog_hash": str(catalog.get("hash", "")),
    }
    if isinstance(composition, ResolvedComposition):
        started_payload["composition_hash"] = composition.hash
        started_payload["resolved_composition"] = composition.to_dict()
    append_event(
        run_dir,
        NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"run-started-{run_id}",
                "type": "run.started",
                "occurred_at": timestamp,
                "payload": started_payload,
            }
        ),
    )
    append_event(
        run_dir,
        NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"workflow-selected-{run_id}",
                "type": "workflow.selected",
                "occurred_at": timestamp,
                "payload": {"run_id": run_id, "workflow_owner": workflow_owner},
            }
        ),
    )
    atomic_write_json(
        receipt,
        {
            "schema": "route-receipt/v1",
            "run_id": run_id,
            "target": target,
            "session_id": session_id,
            "recorded_at": timestamp,
        },
    )
    return run_dir
