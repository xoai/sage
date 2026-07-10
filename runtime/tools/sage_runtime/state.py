"""Append normalized events and derive deterministic machine-owned run state."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from .composition_contracts import CompositionError, ResolvedBinding, ResolvedComposition
from .contracts import ContractError, NormalizedEvent, RunState
from .io import atomic_write_json


ACTIVE_POINTER_SCHEMA = "active-run/v1"
LOCK_TIMEOUT_SECONDS = 0.25
_LOCK_POLL_SECONDS = 0.01


class StateError(ValueError):
    """Raised when an event stream cannot produce a valid run state."""


class StateBusyError(StateError):
    """Raised when another hook owns the short-lived run-state lock."""


class ProviderTransitionError(StateError):
    """A rejected provider transition that should leave a diagnostic event."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


@contextmanager
def _state_lock(run_dir: Path) -> Iterator[None]:
    lock_path = run_dir / ".state.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise StateBusyError("run state busy after 250 ms; platform hook should fail open") from exc
            time.sleep(min(_LOCK_POLL_SECONDS, LOCK_TIMEOUT_SECONDS))
    try:
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _payload_subset(payload: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key in allowed}


def _resolved_binding(
    resolution: ResolvedComposition, capability: str, role: str = "owner"
) -> ResolvedBinding | None:
    return next(
        (
            item
            for item in resolution.bindings
            if item.capability == capability and item.role == role
        ),
        None,
    )


def _provider_terminal(resolution: ResolvedComposition, provider_id: str) -> str | None:
    terminals = [
        item.terminal
        for item in resolution.bindings
        if item.provider_id == provider_id and item.terminal is not None
    ]
    return terminals[-1] if terminals else None


def reduce_events(events: Iterable[NormalizedEvent]) -> RunState:
    """Replay events in append order, ignoring duplicate IDs and unknown types."""

    state: dict[str, Any] | None = None
    resolution: ResolvedComposition | None = None
    seen: set[str] = set()
    for item in events:
        if item.event_id in seen:
            continue
        seen.add(item.event_id)
        payload = item.to_dict()["payload"]
        mutated = False

        if item.type == "run.started":
            if state is not None:
                raise StateError("event stream contains more than one run.started event")
            run_id = payload.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise StateError("run.started requires payload.run_id")
            resolved_raw = payload.get("resolved_composition")
            if resolved_raw is not None:
                if not isinstance(resolved_raw, Mapping):
                    raise StateError("run.started resolved_composition must be a mapping")
                try:
                    resolution = ResolvedComposition.from_dict(resolved_raw)
                except CompositionError as exc:
                    raise StateError(f"invalid resolved composition: {exc}") from exc
                declared_hash = payload.get("composition_hash")
                if declared_hash not in {None, "", resolution.hash}:
                    raise StateError("run.started composition hash does not match resolution")
            state = {
                "schema": "run-state/v1",
                "run_id": run_id,
                "status": "active",
                "explicit_intent": payload.get("explicit_intent", False) is True,
                "workflow_owner": payload.get("workflow_owner"),
                "active_capability": None,
                "active_provider": None,
                "strict": payload.get("strict", False) is True,
                "composition_hash": (
                    resolution.hash
                    if resolution is not None
                    else str(payload.get("composition_hash", ""))
                ),
                "route_catalog_hash": str(payload.get("route_catalog_hash", "")),
                "artifacts": {},
                "verification": {},
                "dirty": False,
                "atomic_span": None,
                "provider_terminal": None,
                "reflection_status": "not-requested",
                "reflection_requested_at": None,
                "updated_at": item.occurred_at,
            }
            continue

        if state is None:
            if item.type.startswith("run."):
                raise StateError("event stream must begin with run.started")
            continue

        if item.type == "workflow.selected":
            owner = payload.get("workflow_owner")
            if isinstance(owner, str) and owner:
                state["workflow_owner"] = owner
                mutated = True
        elif item.type == "capability.entered":
            capability = payload.get("capability")
            if isinstance(capability, str) and capability:
                if resolution is not None:
                    owner = _resolved_binding(resolution, capability)
                    if owner is None:
                        raise ProviderTransitionError(
                            f"no resolved owner for capability: {capability}",
                            "missing-resolved-provider",
                        )
                    active_span = state.get("atomic_span")
                    if active_span is not None and owner.provider_id != active_span:
                        raise ProviderTransitionError(
                            f"atomic provider {active_span!r} is locked until terminal signal",
                            "atomic-provider-locked",
                        )
                    state["active_provider"] = owner.provider_id
                    if owner.atomic:
                        state["atomic_span"] = owner.provider_id
                        state["provider_terminal"] = _provider_terminal(
                            resolution, owner.provider_id
                        )
                state["active_capability"] = capability
                mutated = True
        elif item.type == "provider.selected":
            provider = payload.get("provider")
            if isinstance(provider, str) and provider:
                active_span = state.get("atomic_span")
                if active_span is not None and provider != active_span:
                    raise ProviderTransitionError(
                        f"atomic provider {active_span!r} rejects selection of {provider!r}",
                        "atomic-provider-locked",
                    )
                if resolution is not None and state.get("active_capability"):
                    allowed = any(
                        binding.capability == state["active_capability"]
                        and binding.provider_id == provider
                        for binding in resolution.bindings
                    )
                    if not allowed:
                        raise ProviderTransitionError(
                            f"provider {provider!r} is not resolved for "
                            f"{state['active_capability']}",
                            "missing-resolved-provider",
                        )
                state["active_provider"] = provider
                mutated = True
        elif item.type == "provider.switched":
            provider = payload.get("provider")
            if payload.get("explicit") is not True:
                raise ProviderTransitionError(
                    "provider switch requires explicit intent", "provider-switch-not-explicit"
                )
            if not isinstance(provider, str) or not provider:
                raise ProviderTransitionError(
                    "provider switch requires a provider", "missing-resolved-provider"
                )
            state["atomic_span"] = None
            state["provider_terminal"] = None
            state["active_provider"] = provider
            mutated = True
        elif item.type == "provider.terminal":
            signal = payload.get("signal")
            if state.get("atomic_span") is not None:
                if signal != state.get("provider_terminal"):
                    raise ProviderTransitionError(
                        f"terminal signal {signal!r} does not unlock active provider",
                        "provider-terminal-mismatch",
                    )
                state["atomic_span"] = None
                state["provider_terminal"] = None
                state["active_capability"] = None
                state["active_provider"] = None
                mutated = True
        elif item.type == "artifact.observed":
            artifact_id = payload.get("artifact_id") or payload.get("path")
            if isinstance(artifact_id, str) and artifact_id:
                state["artifacts"][artifact_id] = _payload_subset(
                    payload,
                    {"artifact_id", "path", "sha256", "exists", "kind", "size", "task_count"},
                )
                mutated = True
        elif item.type == "approval.recorded":
            checkpoint = payload.get("checkpoint")
            if isinstance(checkpoint, str) and checkpoint:
                approvals = state["artifacts"].setdefault("approvals", {})
                approvals[checkpoint] = _payload_subset(
                    payload, {"checkpoint", "approved", "actor", "evidence"}
                )
                mutated = True
        elif item.type == "verification.recorded":
            verification_id = payload.get("verification_id") or payload.get("name")
            if isinstance(verification_id, str) and verification_id:
                state["verification"][verification_id] = _payload_subset(
                    payload,
                    {
                        "verification_id",
                        "name",
                        "passed",
                        "command",
                        "exit_code",
                        "sha256",
                        "observed_at",
                    },
                )
                if payload.get("passed") is True:
                    state["dirty"] = False
                mutated = True
        elif item.type == "learning.candidate":
            # These remain durable in events.jsonl. Their richer projections are
            # added by the learning lifecycle without polluting router state.
            mutated = False
        elif item.type == "reflection.requested":
            if state.get("reflection_status") == "not-requested":
                state["reflection_status"] = "requested"
                state["reflection_requested_at"] = item.occurred_at
                mutated = True
        elif item.type == "reflection.completed":
            state["reflection_status"] = "completed"
            mutated = True
        elif item.type == "reflection.skipped":
            state["reflection_status"] = "skipped"
            mutated = True
        elif item.type == "run.cancelled":
            state["status"] = "cancelled"
            state["active_capability"] = None
            state["active_provider"] = None
            state["atomic_span"] = None
            state["provider_terminal"] = None
            state["dirty"] = False
            mutated = True
        elif item.type == "run.completed":
            state["status"] = "completed"
            state["active_capability"] = None
            state["active_provider"] = None
            state["atomic_span"] = None
            state["provider_terminal"] = None
            state["dirty"] = False
            mutated = True

        if mutated:
            state["updated_at"] = item.occurred_at

    if state is None:
        raise StateError("event stream contains no run.started event")
    return RunState.from_dict(state)


def _read_events(run_dir: Path) -> list[NormalizedEvent]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        raise StateError(f"event log does not exist: {path}")
    events: list[NormalizedEvent] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            events.append(NormalizedEvent.from_dict(raw))
        except (json.JSONDecodeError, ContractError) as exc:
            raise StateError(f"invalid event at {path}:{line_number}: {exc}") from exc
    return events


def read_events(run_dir: Path) -> tuple[NormalizedEvent, ...]:
    """Return the validated append-only event stream for lifecycle observers."""

    return tuple(_read_events(Path(run_dir)))


def _active_pointer(run_dir: Path, state: RunState, bound_at: str) -> None:
    if run_dir.parent.name != "runs":
        return
    runtime_dir = run_dir.parent.parent
    runtime_dir.mkdir(parents=True, exist_ok=True)
    pointer_lock = runtime_dir / ".active-run.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(
                pointer_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise StateBusyError(
                    "active run pointer busy after 250 ms; platform hook should fail open"
                ) from exc
            time.sleep(min(_LOCK_POLL_SECONDS, LOCK_TIMEOUT_SECONDS))
    try:
        existing: dict[str, Any] | None = None
        pointer_path = runtime_dir / "active-run.json"
        if pointer_path.is_file():
            try:
                loaded = json.loads(pointer_path.read_text(encoding="utf-8"))
                existing = loaded if isinstance(loaded, dict) else None
            except (OSError, UnicodeError, json.JSONDecodeError):
                existing = None

        if state.status == "active":
            if (
                existing is not None
                and existing.get("active") is True
                and existing.get("run_id") != state.run_id
            ):
                return
        elif existing is None or existing.get("run_id") != state.run_id:
            return

        relative_state = (run_dir / "state.json").relative_to(runtime_dir).as_posix()
        atomic_write_json(
            pointer_path,
            {
                "schema": ACTIVE_POINTER_SCHEMA,
                "active": state.status == "active",
                "run_id": state.run_id,
                "state_path": relative_state,
                "bound_at": bound_at,
                "updated_at": state.updated_at,
            },
        )
    finally:
        os.close(descriptor)
        pointer_lock.unlink(missing_ok=True)


def _reconcile_locked(run_dir: Path) -> RunState:
    events = _read_events(run_dir)
    state = reduce_events(events)
    bound_at = next(item.occurred_at for item in events if item.type == "run.started")
    atomic_write_json(run_dir / "state.json", state)
    _active_pointer(run_dir, state, bound_at)
    return state


def append_event(run_dir: Path, event: NormalizedEvent) -> bool:
    """Append one unique event and reconcile state under a short-lived lock."""

    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    with _state_lock(directory):
        event_path = directory / "events.jsonl"
        existing = _read_events(directory) if event_path.is_file() else []
        if any(item.event_id == event.event_id for item in existing):
            return False
        if event.type == "run.started" and event.payload.get("run_id") != directory.name:
            raise StateError("run.started payload.run_id must match the run directory")
        try:
            reduce_events([*existing, event])
        except ProviderTransitionError as exc:
            diagnostic_id = f"{event.event_id}:diagnostic"
            if not any(item.event_id == diagnostic_id for item in existing):
                diagnostic = NormalizedEvent.from_dict(
                    {
                        "schema": "sage-event/v1",
                        "event_id": diagnostic_id,
                        "type": "runtime.diagnostic",
                        "occurred_at": event.occurred_at,
                        "payload": {
                            "run_id": directory.name,
                            "rejected_event_id": event.event_id,
                            "code": exc.code,
                            "message": str(exc),
                        },
                    }
                )
                with event_path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(
                        json.dumps(diagnostic.to_dict(), ensure_ascii=False, sort_keys=True)
                    )
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                _reconcile_locked(directory)
            raise StateError(str(exc)) from exc
        with event_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _reconcile_locked(directory)
        return True


def reconcile_run(run_dir: Path) -> RunState:
    """Replay a run's event log and atomically restore its state projection."""

    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    with _state_lock(directory):
        return _reconcile_locked(directory)


def load_active_run(runtime_dir: Path) -> RunState | None:
    """Load the active state pointer, returning no run for missing/stale advice."""

    directory = Path(runtime_dir)
    pointer_path = directory / "active-run.json"
    if not pointer_path.is_file():
        return None
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid active run pointer: {pointer_path}") from exc
    if pointer.get("schema") != ACTIVE_POINTER_SCHEMA:
        raise StateError("invalid active run pointer schema")
    if pointer.get("active") is not True:
        return None
    state_path = pointer.get("state_path")
    if not isinstance(state_path, str) or not state_path:
        raise StateError("active run pointer has no state_path")
    resolved_runtime = directory.resolve()
    resolved_state = (directory / state_path).resolve()
    if resolved_runtime != resolved_state.parent and resolved_runtime not in resolved_state.parents:
        raise StateError("active run pointer escapes runtime directory")
    if not resolved_state.is_file():
        return None
    try:
        return RunState.from_dict(json.loads(resolved_state.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ContractError) as exc:
        raise StateError(f"invalid active run state: {resolved_state}") from exc


def load_active_bound_at(runtime_dir: Path) -> str | None:
    """Return the explicit bind timestamp without deriving it from later events."""

    pointer_path = Path(runtime_dir) / "active-run.json"
    if not pointer_path.is_file():
        return None
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid active run pointer: {pointer_path}") from exc
    if pointer.get("schema") != ACTIVE_POINTER_SCHEMA:
        raise StateError("invalid active run pointer schema")
    if pointer.get("active") is not True:
        return None
    bound_at = pointer.get("bound_at", pointer.get("updated_at"))
    if not isinstance(bound_at, str) or not bound_at:
        raise StateError("active run pointer has no bound_at")
    return bound_at
