"""Facts-only strict gate evaluation for explicitly bound Sage runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from .contracts import RunState


GATE_VERDICT_SCHEMA = "gate-verdict/v1"


class GateError(ValueError):
    """Raised when an operation or strict policy is malformed."""


def _timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise GateError(f"{field} must be an ISO-8601 UTC timestamp")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise GateError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise GateError(f"{field} must be an ISO-8601 UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise GateError(f"{field} must be a list of non-empty strings")
    return tuple(value)


@dataclass(frozen=True)
class Operation:
    """Observable facts about one pending platform operation."""

    kind: str
    read_only: bool
    stage: str
    scope: str
    paths: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Operation":
        if not isinstance(raw, Mapping):
            raise GateError("operation must be a mapping")
        kind = raw.get("kind")
        stage = raw.get("stage")
        scope = raw.get("scope", "full")
        read_only = raw.get("read_only")
        if not isinstance(kind, str) or not kind:
            raise GateError("operation.kind must be a non-empty string")
        if not isinstance(stage, str) or not stage:
            raise GateError("operation.stage must be a non-empty string")
        if not isinstance(scope, str) or not scope:
            raise GateError("operation.scope must be a non-empty string")
        if not isinstance(read_only, bool):
            raise GateError("operation.read_only must be a boolean")
        return cls(
            kind=kind,
            read_only=read_only,
            stage=stage,
            scope=scope,
            paths=_string_tuple(raw.get("paths", []), "operation.paths"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "read_only": self.read_only,
            "stage": self.stage,
            "scope": self.scope,
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class StageRequirements:
    artifacts: tuple[str, ...] = ()
    approvals: tuple[str, ...] = ()
    verifications: tuple[str, ...] = ()


@dataclass(frozen=True)
class GatePolicy:
    """Immutable policy whose expiry remains anchored to explicit bind time."""

    bound_at: datetime
    ttl_seconds: int
    lane_roots: tuple[str, ...]
    scopes: Mapping[str, Mapping[str, StageRequirements]]

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "GatePolicy":
        if not isinstance(raw, Mapping):
            raise GateError("gate policy must be a mapping")
        bound_at = _timestamp(raw.get("bound_at"), "bound_at")
        ttl_seconds = raw.get("ttl_seconds", 3600)
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds < 0:
            raise GateError("ttl_seconds must be a non-negative integer")
        lane_roots = _string_tuple(raw.get("lane_roots", []), "lane_roots")
        scopes_raw = raw.get("scopes", {})
        if not isinstance(scopes_raw, Mapping):
            raise GateError("scopes must be a mapping")
        scopes: dict[str, Mapping[str, StageRequirements]] = {}
        for scope, scope_raw in scopes_raw.items():
            if not isinstance(scope, str) or not isinstance(scope_raw, Mapping):
                raise GateError("each scope must be a named mapping")
            stages_raw = scope_raw.get("stages", {})
            if not isinstance(stages_raw, Mapping):
                raise GateError(f"scope {scope} stages must be a mapping")
            stages: dict[str, StageRequirements] = {}
            for stage, requirements_raw in stages_raw.items():
                if not isinstance(stage, str) or not isinstance(requirements_raw, Mapping):
                    raise GateError(f"scope {scope} has an invalid stage")
                stages[stage] = StageRequirements(
                    artifacts=_string_tuple(
                        requirements_raw.get("required_artifacts", []),
                        f"{scope}.{stage}.required_artifacts",
                    ),
                    approvals=_string_tuple(
                        requirements_raw.get("required_approvals", []),
                        f"{scope}.{stage}.required_approvals",
                    ),
                    verifications=_string_tuple(
                        requirements_raw.get("required_verifications", []),
                        f"{scope}.{stage}.required_verifications",
                    ),
                )
            scopes[scope] = MappingProxyType(stages)
        return cls(
            bound_at=bound_at,
            ttl_seconds=ttl_seconds,
            lane_roots=lane_roots,
            scopes=MappingProxyType(scopes),
        )

    @property
    def expires_at(self) -> datetime | None:
        if self.ttl_seconds == 0:
            return None
        return self.bound_at + timedelta(seconds=self.ttl_seconds)

    def requirements(self, scope: str, stage: str) -> StageRequirements:
        stages = self.scopes.get(scope)
        if stages is None:
            return StageRequirements()
        return stages.get(stage, StageRequirements())


@dataclass(frozen=True)
class GateVerdict:
    allowed: bool
    invariant: str
    evidence: Mapping[str, Any]
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": GATE_VERDICT_SCHEMA,
            "allowed": self.allowed,
            "invariant": self.invariant,
            "evidence": dict(self.evidence),
            "remediation": self.remediation,
        }


def _verdict(
    allowed: bool,
    invariant: str,
    evidence: Mapping[str, Any] | None = None,
    remediation: str = "",
) -> GateVerdict:
    return GateVerdict(
        allowed=allowed,
        invariant=invariant,
        evidence=MappingProxyType(dict(evidence or {})),
        remediation=remediation,
    )


def _artifact_exists(state: RunState, artifact: str) -> bool:
    observed = state.artifacts.get(artifact)
    return isinstance(observed, Mapping) and observed.get("exists") is True


def _approval_exists(state: RunState, checkpoint: str) -> bool:
    approvals = state.artifacts.get("approvals")
    if not isinstance(approvals, Mapping):
        return False
    observed = approvals.get(checkpoint)
    return isinstance(observed, Mapping) and observed.get("approved") is True


def _verification_passed(state: RunState, verification: str) -> bool:
    observed = state.verification.get(verification)
    return isinstance(observed, Mapping) and observed.get("passed") is True


def _normalized_path(value: str) -> str | None:
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        return None
    return path.as_posix().lstrip("./")


def _inside_lane(path: str, lane_roots: tuple[str, ...]) -> bool:
    normalized = _normalized_path(path)
    if normalized is None:
        return False
    for root_value in lane_roots:
        root = _normalized_path(root_value)
        if root in {"", "."}:
            return True
        if root is not None and (normalized == root or normalized.startswith(f"{root}/")):
            return True
    return False


def evaluate(
    operation: Operation,
    state: RunState | None,
    policy: GatePolicy,
    now: datetime,
) -> GateVerdict:
    """Evaluate only declared machine-observable strict invariants."""

    if state is None or state.status != "active":
        return _verdict(True, "active-run-required")
    if not state.explicit_intent:
        return _verdict(True, "explicit-route-required")
    if operation.read_only:
        return _verdict(True, "read-only")
    if not state.strict:
        return _verdict(True, "strict-disabled")
    if not isinstance(state.workflow_owner, str) or not state.workflow_owner.startswith(
        "sage:"
    ):
        return _verdict(True, "sage-workflow-inactive")
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise GateError("now must be timezone-aware UTC")
    expires_at = policy.expires_at
    if expires_at is not None and now > expires_at:
        return _verdict(
            True,
            "binding-expired",
            {"expired_at": expires_at.isoformat().replace("+00:00", "Z")},
        )

    requirements = policy.requirements(operation.scope, operation.stage)
    for artifact in requirements.artifacts:
        if not _artifact_exists(state, artifact):
            return _verdict(
                False,
                "required-artifact",
                {"artifact": artifact, "observed": False},
                f"Create and observe the declared artifact: {artifact}",
            )
    for checkpoint in requirements.approvals:
        if not _approval_exists(state, checkpoint):
            return _verdict(
                False,
                "required-approval",
                {"checkpoint": checkpoint, "approved": False},
                f"Record explicit approval for checkpoint: {checkpoint}",
            )
    for verification in requirements.verifications:
        if not _verification_passed(state, verification):
            return _verdict(
                False,
                "required-verification",
                {"verification": verification, "passed": False},
                f"Pass and record the required verification: {verification}",
            )
    if policy.lane_roots:
        if not operation.paths:
            return _verdict(
                False,
                "locked-lane",
                {
                    "path": None,
                    "lane_roots": list(policy.lane_roots),
                    "reason": "mutating operation has no deterministic path evidence",
                },
                "Use a structured file tool or declare paths inside the locked lane",
            )
        for path in operation.paths:
            if not _inside_lane(path, policy.lane_roots):
                return _verdict(
                    False,
                    "locked-lane",
                    {"path": path, "lane_roots": list(policy.lane_roots)},
                    "Write only inside the run's explicitly locked lane",
                )
    return _verdict(True, "strict-invariants-satisfied")


def load_gate_policy(path: Path, bound_at: str) -> GatePolicy:
    """Load the strict runtime section of a gate-modes YAML document."""

    try:
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise GateError(f"malformed gate policy: {path}: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise GateError("gate policy document must be a mapping")
    strict_runtime = loaded.get("strict_runtime")
    if not isinstance(strict_runtime, Mapping):
        raise GateError("gate policy has no strict_runtime mapping")
    raw = dict(strict_runtime)
    raw["bound_at"] = bound_at
    return GatePolicy.from_dict(raw)
