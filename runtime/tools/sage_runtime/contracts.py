"""Versioned data contracts shared by Sage runtime components."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping, Optional


EVENT_SCHEMA = "sage-event/v1"
RUN_STATE_SCHEMA = "run-state/v1"


class ContractError(ValueError):
    """Raised when a runtime document violates its versioned contract."""


def _require_string(raw: Mapping[str, Any], field_name: str) -> str:
    if field_name not in raw:
        raise ContractError(f"missing required field: {field_name}")
    value = raw[field_name]
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field_name} must be a non-empty string")
    return value


def _validate_utc_timestamp(value: str, field_name: str) -> str:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ContractError(f"{field_name} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ContractError(f"{field_name} must be an ISO-8601 UTC timestamp")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class NormalizedEvent:
    """An immutable, append-only event accepted by the run-state reducer."""

    schema: str
    event_id: str
    type: str
    occurred_at: str
    payload: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "NormalizedEvent":
        if not isinstance(raw, Mapping):
            raise ContractError("event must be a mapping")
        schema = _require_string(raw, "schema")
        if schema != EVENT_SCHEMA:
            raise ContractError(f"unsupported schema: {schema}")
        event_id = _require_string(raw, "event_id")
        event_type = _require_string(raw, "type")
        occurred_at = _validate_utc_timestamp(
            _require_string(raw, "occurred_at"), "occurred_at"
        )
        payload = raw.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ContractError("payload must be a mapping")
        return cls(
            schema=schema,
            event_id=event_id,
            type=event_type,
            occurred_at=occurred_at,
            payload=_freeze(payload),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "event_id": self.event_id,
            "type": self.type,
            "occurred_at": self.occurred_at,
            "payload": _thaw(self.payload),
        }


_RUN_STATE_FIELDS = frozenset(
    {
        "schema",
        "run_id",
        "status",
        "explicit_intent",
        "workflow_owner",
        "active_capability",
        "active_provider",
        "strict",
        "composition_hash",
        "route_catalog_hash",
        "artifacts",
        "verification",
        "dirty",
        "atomic_span",
        "provider_terminal",
        "reflection_status",
        "reflection_requested_at",
        "updated_at",
    }
)


@dataclass(frozen=True)
class RunState:
    """Machine-owned state derived exclusively from normalized events."""

    schema: str
    run_id: str
    status: str
    explicit_intent: bool
    workflow_owner: Optional[str]
    active_capability: Optional[str]
    active_provider: Optional[str]
    strict: bool
    composition_hash: str
    route_catalog_hash: str
    artifacts: Mapping[str, Any]
    verification: Mapping[str, Any]
    dirty: bool
    atomic_span: Optional[str]
    provider_terminal: Optional[str]
    updated_at: str
    reflection_status: str = "not-requested"
    reflection_requested_at: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RunState":
        if not isinstance(raw, Mapping):
            raise ContractError("run state must be a mapping")
        unknown = sorted(set(raw) - _RUN_STATE_FIELDS)
        if unknown:
            raise ContractError(f"unsupported run-state field: {unknown[0]}")
        schema = _require_string(raw, "schema")
        if schema != RUN_STATE_SCHEMA:
            raise ContractError(f"unsupported schema: {schema}")
        run_id = _require_string(raw, "run_id")
        status = _require_string(raw, "status")
        updated_at = _validate_utc_timestamp(
            _require_string(raw, "updated_at"), "updated_at"
        )
        artifacts = raw.get("artifacts", {})
        verification = raw.get("verification", {})
        if not isinstance(artifacts, Mapping):
            raise ContractError("artifacts must be a mapping")
        if not isinstance(verification, Mapping):
            raise ContractError("verification must be a mapping")
        for boolean_field in ("explicit_intent", "strict", "dirty"):
            if not isinstance(raw.get(boolean_field, False), bool):
                raise ContractError(f"{boolean_field} must be a boolean")
        for optional_string in ("atomic_span", "provider_terminal"):
            value = raw.get(optional_string)
            if value is not None and (not isinstance(value, str) or not value):
                raise ContractError(f"{optional_string} must be a non-empty string or null")
        reflection_status = raw.get("reflection_status", "not-requested")
        if reflection_status not in {"not-requested", "requested", "completed", "skipped"}:
            raise ContractError("reflection_status is unsupported")
        requested_at_raw = raw.get("reflection_requested_at")
        reflection_requested_at = (
            None
            if requested_at_raw is None
            else _validate_utc_timestamp(
                _require_string(raw, "reflection_requested_at"),
                "reflection_requested_at",
            )
        )
        return cls(
            schema=schema,
            run_id=run_id,
            status=status,
            explicit_intent=raw.get("explicit_intent", False),
            workflow_owner=raw.get("workflow_owner"),
            active_capability=raw.get("active_capability"),
            active_provider=raw.get("active_provider"),
            strict=raw.get("strict", False),
            composition_hash=str(raw.get("composition_hash", "")),
            route_catalog_hash=str(raw.get("route_catalog_hash", "")),
            artifacts=_freeze(artifacts),
            verification=_freeze(verification),
            dirty=raw.get("dirty", False),
            atomic_span=raw.get("atomic_span"),
            provider_terminal=raw.get("provider_terminal"),
            updated_at=updated_at,
            reflection_status=reflection_status,
            reflection_requested_at=reflection_requested_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "run_id": self.run_id,
            "status": self.status,
            "explicit_intent": self.explicit_intent,
            "workflow_owner": self.workflow_owner,
            "active_capability": self.active_capability,
            "active_provider": self.active_provider,
            "strict": self.strict,
            "composition_hash": self.composition_hash,
            "route_catalog_hash": self.route_catalog_hash,
            "artifacts": _thaw(self.artifacts),
            "verification": _thaw(self.verification),
            "dirty": self.dirty,
            "atomic_span": self.atomic_span,
            "provider_terminal": self.provider_terminal,
            "reflection_status": self.reflection_status,
            "reflection_requested_at": self.reflection_requested_at,
            "updated_at": self.updated_at,
        }
