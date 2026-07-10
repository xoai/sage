"""Immutable neutral contracts for deterministic skill composition."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


COMPOSITION_CONTRACT = "composition/v1"
RESOLVED_COMPOSITION_SCHEMA = "resolved-composition/v1"
CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
ROLES = frozenset({"owner", "augmenter", "validator", "observer"})
COMBINE_MODES = frozenset({"exclusive", "compatible"})


class CompositionError(ValueError):
    """Raised when composition metadata cannot be deterministic."""


def validate_capability(value: object) -> str:
    if not isinstance(value, str) or not CAPABILITY_PATTERN.fullmatch(value):
        raise CompositionError(f"invalid capability name: {value!r}")
    return value


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompositionError(f"{field} must be a non-empty string")
    return value.strip()


def _ordered_strings(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise CompositionError(f"{field} must be a list of non-empty strings")
    output: list[str] = []
    for item in value:
        output.append(_nonempty_string(item, field))
    return tuple(output)


@dataclass(frozen=True)
class CapabilityBinding:
    capability: str
    role: str
    combine: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    terminal: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "CapabilityBinding":
        if not isinstance(raw, Mapping):
            raise CompositionError("capability binding must be a mapping")
        unknown = sorted(
            set(raw) - {"capability", "role", "combine", "inputs", "outputs", "terminal"}
        )
        if unknown:
            raise CompositionError(f"unsupported capability binding field: {unknown[0]}")
        capability = validate_capability(raw.get("capability"))
        role = _nonempty_string(raw.get("role"), "role")
        if role not in ROLES:
            raise CompositionError(f"unknown role: {role}")
        combine = _nonempty_string(raw.get("combine"), "combine")
        if combine not in COMBINE_MODES:
            raise CompositionError(f"unknown combine mode: {combine}")
        terminal_raw = raw.get("terminal")
        terminal = None if terminal_raw is None else _nonempty_string(terminal_raw, "terminal")
        return cls(
            capability=capability,
            role=role,
            combine=combine,
            inputs=_ordered_strings(raw.get("inputs"), "inputs"),
            outputs=_ordered_strings(raw.get("outputs"), "outputs"),
            terminal=terminal,
        )

    def to_dict(self) -> dict[str, Any]:
        output: dict[str, Any] = {
            "capability": self.capability,
            "role": self.role,
            "combine": self.combine,
        }
        if self.inputs:
            output["inputs"] = list(self.inputs)
        if self.outputs:
            output["outputs"] = list(self.outputs)
        if self.terminal is not None:
            output["terminal"] = self.terminal
        return output


@dataclass(frozen=True)
class Provider:
    id: str
    atomic: bool
    provides: tuple[CapabilityBinding, ...]

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Provider":
        if not isinstance(raw, Mapping):
            raise CompositionError("provider must be a mapping")
        unknown = sorted(set(raw) - {"id", "atomic", "provides"})
        if unknown:
            raise CompositionError(f"unsupported provider field: {unknown[0]}")
        provider_id = _nonempty_string(raw.get("id"), "provider id")
        atomic = raw.get("atomic", False)
        if not isinstance(atomic, bool):
            raise CompositionError("provider atomic must be a boolean")
        provides_raw = raw.get("provides", [])
        if not isinstance(provides_raw, list):
            raise CompositionError("provider provides must be a list")
        if not provides_raw:
            if atomic:
                raise CompositionError("atomic span must not be empty")
            raise CompositionError("provider must declare at least one capability")
        provides = tuple(CapabilityBinding.from_dict(item) for item in provides_raw)
        seen: set[tuple[str, str]] = set()
        for item in provides:
            key = (item.capability, item.role)
            if key in seen:
                raise CompositionError(
                    f"duplicate provider capability-role tuple: {item.capability}/{item.role}"
                )
            seen.add(key)
            if item.combine == "exclusive" and item.role != "owner":
                raise CompositionError(
                    f"exclusive capability {item.capability} requires an owner role"
                )
        if atomic and not any(item.terminal for item in provides):
            raise CompositionError("atomic provider requires a terminal signal")
        return cls(id=provider_id, atomic=atomic, provides=provides)

    @property
    def terminal(self) -> str | None:
        terminals = [item.terminal for item in self.provides if item.terminal is not None]
        return terminals[-1] if terminals else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "atomic": self.atomic,
            "provides": [item.to_dict() for item in self.provides],
        }


_POLICY_KEYS = frozenset({"owner", "augmenters", "validators", "observers"})
_ROLE_TO_POLICY_KEY = {
    "owner": "owner",
    "augmenter": "augmenters",
    "validator": "validators",
    "observer": "observers",
}


@dataclass(frozen=True)
class CompositionPolicy:
    capabilities: Mapping[str, Mapping[str, object]]

    @classmethod
    def from_dict(cls, raw: Mapping[str, object] | None) -> "CompositionPolicy":
        if raw is None:
            raw = {}
        if not isinstance(raw, Mapping):
            raise CompositionError("composition policy must be a mapping")
        capabilities: dict[str, Mapping[str, object]] = {}
        for capability_raw, selection_raw in raw.items():
            capability = validate_capability(capability_raw)
            if not isinstance(selection_raw, Mapping):
                raise CompositionError(f"policy for {capability} must be a mapping")
            unknown = sorted(set(selection_raw) - _POLICY_KEYS)
            if unknown:
                raise CompositionError(f"unsupported policy role for {capability}: {unknown[0]}")
            owner_raw = selection_raw.get("owner")
            owner = None if owner_raw is None else _nonempty_string(owner_raw, "policy owner")
            selection = {
                "owner": owner,
                "augmenters": _ordered_strings(
                    selection_raw.get("augmenters"), "policy augmenters"
                ),
                "validators": _ordered_strings(
                    selection_raw.get("validators"), "policy validators"
                ),
                "observers": _ordered_strings(
                    selection_raw.get("observers"), "policy observers"
                ),
            }
            capabilities[capability] = MappingProxyType(selection)
        return cls(capabilities=MappingProxyType(capabilities))

    def owner_for(self, capability: str) -> str | None:
        selection = self.capabilities.get(capability)
        if selection is None:
            return None
        owner = selection.get("owner")
        return owner if isinstance(owner, str) else None

    def helpers_for(self, capability: str, role: str) -> tuple[str, ...]:
        key = _ROLE_TO_POLICY_KEY.get(role)
        if key is None or role == "owner":
            return ()
        selection = self.capabilities.get(capability)
        if selection is None:
            return ()
        helpers = selection.get(key, ())
        return helpers if isinstance(helpers, tuple) else ()

    def to_dict(self) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for capability in sorted(self.capabilities):
            selection = self.capabilities[capability]
            rendered: dict[str, Any] = {}
            owner = selection.get("owner")
            if isinstance(owner, str):
                rendered["owner"] = owner
            for key in ("augmenters", "validators", "observers"):
                values = selection.get(key, ())
                if isinstance(values, tuple) and values:
                    rendered[key] = list(values)
            output[capability] = rendered
        return output


@dataclass(frozen=True)
class ResolvedBinding:
    capability: str
    provider_id: str
    role: str
    combine: str
    atomic: bool
    terminal: str | None
    provenance: str

    def __post_init__(self) -> None:
        validate_capability(self.capability)
        _nonempty_string(self.provider_id, "resolved provider id")
        if self.role not in ROLES:
            raise CompositionError(f"unknown role: {self.role}")
        if self.combine not in COMBINE_MODES:
            raise CompositionError(f"unknown combine mode: {self.combine}")
        if not isinstance(self.atomic, bool):
            raise CompositionError("resolved atomic must be a boolean")
        _nonempty_string(self.provenance, "resolved provenance")

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "ResolvedBinding":
        return cls(
            capability=validate_capability(raw.get("capability")),
            provider_id=_nonempty_string(raw.get("provider_id"), "resolved provider id"),
            role=_nonempty_string(raw.get("role"), "role"),
            combine=_nonempty_string(raw.get("combine"), "combine"),
            atomic=raw.get("atomic", False),
            terminal=(
                None
                if raw.get("terminal") is None
                else _nonempty_string(raw.get("terminal"), "terminal")
            ),
            provenance=_nonempty_string(raw.get("provenance"), "resolved provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "provider_id": self.provider_id,
            "role": self.role,
            "combine": self.combine,
            "atomic": self.atomic,
            "terminal": self.terminal,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ResolvedComposition:
    catalog_hash: str
    selected_workflow: str | None
    bindings: tuple[ResolvedBinding, ...]
    hash: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "ResolvedComposition":
        if raw.get("schema") != RESOLVED_COMPOSITION_SCHEMA:
            raise CompositionError("unsupported resolved composition schema")
        bindings_raw = raw.get("bindings", [])
        if not isinstance(bindings_raw, list):
            raise CompositionError("resolved bindings must be a list")
        workflow = raw.get("selected_workflow")
        if workflow is not None and not isinstance(workflow, str):
            raise CompositionError("selected_workflow must be a string or null")
        return cls(
            catalog_hash=_nonempty_string(raw.get("catalog_hash"), "catalog_hash"),
            selected_workflow=workflow,
            bindings=tuple(ResolvedBinding.from_dict(item) for item in bindings_raw),
            hash=_nonempty_string(raw.get("hash"), "resolved composition hash"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESOLVED_COMPOSITION_SCHEMA,
            "catalog_hash": self.catalog_hash,
            "selected_workflow": self.selected_workflow,
            "bindings": [item.to_dict() for item in self.bindings],
            "hash": self.hash,
        }
