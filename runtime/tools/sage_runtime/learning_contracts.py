"""Backend-neutral contracts for deterministic learning lifecycle hooks."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


RECALL_SCHEMA = "learning-recall/v1"
TRIGGER_TYPES = frozenset(
    {
        "user-correction",
        "repeated-failure",
        "fail-to-pass",
        "behavior-contradiction",
        "better-method",
    }
)
RECORD_STATUSES = frozenset({"active", "superseded", "invalidated"})
RECORD_SCOPES = frozenset({"project", "global"})

MAX_CONTEXT_REQUEST_BYTES = 4096
MAX_ID_BYTES = 512
MAX_TITLE_BYTES = 512
MAX_PREVENTION_BYTES = 2048
MAX_RATIONALE_BYTES = 1024
MAX_DIAGNOSTIC_BYTES = 512
MAX_SELECTOR_BYTES = 1024
MAX_PROVIDERS = 32
MAX_PATHS = 64
MAX_RECALL_RECORDS = 10

_OPAQUE_ID = re.compile(r"^\S+$")
_DEDUPE_KEY = re.compile(r"^[0-9a-f]{64}$")


class LearningContractError(ValueError):
    """Raised when learning data cannot be normalized deterministically."""


def _text(
    value: object,
    field: str,
    *,
    max_bytes: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise LearningContractError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized and not allow_empty:
        raise LearningContractError(f"{field} must be a non-empty string")
    if len(normalized.encode("utf-8")) > max_bytes:
        raise LearningContractError(f"{field} exceeds {max_bytes} UTF-8 bytes")
    return normalized


def _opaque_id(value: object, field: str) -> str:
    result = _text(value, field, max_bytes=MAX_ID_BYTES)
    if not _OPAQUE_ID.fullmatch(result):
        raise LearningContractError(f"{field} must not contain whitespace")
    return result


def _optional_text(value: object, field: str, max_bytes: int) -> str | None:
    if value is None:
        return None
    return _text(value, field, max_bytes=max_bytes)


def _ordered_strings(
    value: object,
    field: str,
    *,
    limit: int,
    item_bytes: int = MAX_SELECTOR_BYTES,
    opaque_ids: bool = False,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise LearningContractError(f"{field} must be a sequence of strings")
    if len(value) > limit:
        raise LearningContractError(f"{field} exceeds item limit {limit}")
    output: list[str] = []
    for item in value:
        normalized = (
            _opaque_id(item, field)
            if opaque_ids
            else _text(item, field, max_bytes=item_bytes)
        )
        if normalized in output:
            raise LearningContractError(f"{field} contains a duplicate value")
        output.append(normalized)
    return tuple(output)


def _dedupe_part(value: object) -> str:
    return " ".join(str(value).split()).casefold()


def stable_dedupe_key(*parts: object) -> str:
    """Return a stable content key independent of backend record IDs."""
    normalized = "\0".join(_dedupe_part(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LearningContext:
    current_request: str
    project_root: str
    repo_name: str
    platform: str
    active_capability: str | None = None
    selected_providers: tuple[str, ...] = ()
    touched_subsystem: str | None = None
    touched_paths: tuple[str, ...] = ()
    seen_record_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "current_request",
            _text(
                self.current_request,
                "current_request",
                max_bytes=MAX_CONTEXT_REQUEST_BYTES,
            ),
        )
        object.__setattr__(
            self,
            "project_root",
            _text(self.project_root, "project_root", max_bytes=MAX_SELECTOR_BYTES),
        )
        object.__setattr__(
            self,
            "repo_name",
            _text(self.repo_name, "repo_name", max_bytes=MAX_TITLE_BYTES),
        )
        object.__setattr__(
            self,
            "platform",
            _text(self.platform, "platform", max_bytes=MAX_TITLE_BYTES),
        )
        object.__setattr__(
            self,
            "active_capability",
            _optional_text(
                self.active_capability, "active_capability", MAX_SELECTOR_BYTES
            ),
        )
        object.__setattr__(
            self,
            "selected_providers",
            _ordered_strings(
                self.selected_providers,
                "selected_providers",
                limit=MAX_PROVIDERS,
                opaque_ids=True,
            ),
        )
        object.__setattr__(
            self,
            "touched_subsystem",
            _optional_text(
                self.touched_subsystem, "touched_subsystem", MAX_SELECTOR_BYTES
            ),
        )
        object.__setattr__(
            self,
            "touched_paths",
            _ordered_strings(
                self.touched_paths,
                "touched_paths",
                limit=MAX_PATHS,
            ),
        )
        object.__setattr__(
            self,
            "seen_record_ids",
            _ordered_strings(
                self.seen_record_ids,
                "seen_record_ids",
                limit=64,
                opaque_ids=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_request": self.current_request,
            "project_root": self.project_root,
            "repo_name": self.repo_name,
            "platform": self.platform,
            "active_capability": self.active_capability,
            "selected_providers": list(self.selected_providers),
            "touched_subsystem": self.touched_subsystem,
            "touched_paths": list(self.touched_paths),
            "seen_record_ids": list(self.seen_record_ids),
        }


@dataclass(frozen=True)
class RecallRecord:
    id: str
    title: str
    prevention: str
    rationale: str
    score: float = 0.0
    tags: tuple[str, ...] = ("self-learning",)
    status: str = "active"
    scope: str = "project"
    project: str | None = None
    platforms: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    providers: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    dedupe_key: str = ""
    superseded_by: str | None = None
    corrects: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _opaque_id(self.id, "id"))
        object.__setattr__(
            self, "title", _text(self.title, "title", max_bytes=MAX_TITLE_BYTES)
        )
        object.__setattr__(
            self,
            "prevention",
            _text(
                self.prevention,
                "prevention",
                max_bytes=MAX_PREVENTION_BYTES,
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "rationale",
            _text(
                self.rationale,
                "rationale",
                max_bytes=MAX_RATIONALE_BYTES,
                allow_empty=True,
            ),
        )
        if not isinstance(self.score, (int, float)) or isinstance(self.score, bool):
            raise LearningContractError("score must be a finite number")
        score = float(self.score)
        if not math.isfinite(score) or score < 0:
            raise LearningContractError("score must be a finite non-negative number")
        object.__setattr__(self, "score", score)

        tags = _ordered_strings(self.tags, "tags", limit=32, item_bytes=128)
        if "self-learning" not in tags:
            raise LearningContractError("tags must include self-learning")
        object.__setattr__(self, "tags", tags)
        if self.status not in RECORD_STATUSES:
            raise LearningContractError(f"unsupported status: {self.status}")
        if self.scope not in RECORD_SCOPES:
            raise LearningContractError(f"unsupported scope: {self.scope}")
        object.__setattr__(
            self,
            "project",
            _optional_text(self.project, "project", MAX_TITLE_BYTES),
        )
        for field_name, value, limit in (
            ("platforms", self.platforms, 16),
            ("capabilities", self.capabilities, 32),
            ("providers", self.providers, MAX_PROVIDERS),
            ("paths", self.paths, MAX_PATHS),
        ):
            object.__setattr__(
                self,
                field_name,
                _ordered_strings(value, field_name, limit=limit),
            )

        superseded_by = (
            None
            if self.superseded_by is None
            else _opaque_id(self.superseded_by, "superseded_by")
        )
        corrects = (
            None if self.corrects is None else _opaque_id(self.corrects, "corrects")
        )
        if self.status == "superseded" and superseded_by is None:
            raise LearningContractError("superseded status requires superseded_by")
        if self.status != "superseded" and superseded_by is not None:
            raise LearningContractError("superseded_by requires superseded status")
        if superseded_by == self.id or corrects == self.id:
            raise LearningContractError("correction links cannot reference the same record")
        object.__setattr__(self, "superseded_by", superseded_by)
        object.__setattr__(self, "corrects", corrects)

        key = self.dedupe_key or stable_dedupe_key(
            self.prevention, self.rationale
        )
        if not isinstance(key, str) or not _DEDUPE_KEY.fullmatch(key):
            raise LearningContractError("dedupe_key must be a lowercase SHA-256 hex digest")
        object.__setattr__(self, "dedupe_key", key)

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "RecallRecord":
        if not isinstance(raw, Mapping):
            raise LearningContractError("recall record must be a mapping")
        return cls(
            id=raw.get("id"),  # type: ignore[arg-type]
            title=raw.get("title"),  # type: ignore[arg-type]
            prevention=raw.get("prevention", ""),  # type: ignore[arg-type]
            rationale=raw.get("rationale", ""),  # type: ignore[arg-type]
            score=raw.get("score", 0.0),  # type: ignore[arg-type]
            tags=raw.get("tags", ("self-learning",)),  # type: ignore[arg-type]
            status=raw.get("status", "active"),  # type: ignore[arg-type]
            scope=raw.get("scope", "project"),  # type: ignore[arg-type]
            project=raw.get("project"),  # type: ignore[arg-type]
            platforms=raw.get("platforms", ()),  # type: ignore[arg-type]
            capabilities=raw.get("capabilities", ()),  # type: ignore[arg-type]
            providers=raw.get("providers", ()),  # type: ignore[arg-type]
            paths=raw.get("paths", ()),  # type: ignore[arg-type]
            dedupe_key=raw.get("dedupe_key", ""),  # type: ignore[arg-type]
            superseded_by=raw.get("superseded_by"),  # type: ignore[arg-type]
            corrects=raw.get("corrects"),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "prevention": self.prevention,
            "rationale": self.rationale,
            "score": self.score,
            "tags": list(self.tags),
            "status": self.status,
            "scope": self.scope,
            "project": self.project,
            "platforms": list(self.platforms),
            "capabilities": list(self.capabilities),
            "providers": list(self.providers),
            "paths": list(self.paths),
            "dedupe_key": self.dedupe_key,
            "superseded_by": self.superseded_by,
            "corrects": self.corrects,
        }


@dataclass(frozen=True)
class RecallResult:
    query: str
    records: tuple[RecallRecord, ...] = ()
    backend: str = ""
    diagnostics: tuple[str, ...] = ()
    ok: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "query",
            _text(
                self.query,
                "query",
                max_bytes=MAX_CONTEXT_REQUEST_BYTES,
                allow_empty=True,
            ),
        )
        if isinstance(self.records, list):
            object.__setattr__(self, "records", tuple(self.records))
        if not isinstance(self.records, tuple) or not all(
            isinstance(item, RecallRecord) for item in self.records
        ):
            raise LearningContractError("records must contain RecallRecord values")
        if len(self.records) > MAX_RECALL_RECORDS:
            raise LearningContractError(
                f"records exceeds item limit {MAX_RECALL_RECORDS}"
            )
        object.__setattr__(
            self,
            "backend",
            _text(
                self.backend,
                "backend",
                max_bytes=MAX_TITLE_BYTES,
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "diagnostics",
            _ordered_strings(
                self.diagnostics,
                "diagnostic",
                limit=10,
                item_bytes=MAX_DIAGNOSTIC_BYTES,
            ),
        )
        if not isinstance(self.ok, bool):
            raise LearningContractError("ok must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RECALL_SCHEMA,
            "ok": self.ok,
            "backend": self.backend,
            "query": self.query,
            "records": [record.to_dict() for record in self.records],
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class LearningCandidate:
    id: str
    trigger: str
    evidence_refs: tuple[str, ...]
    dedupe_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _opaque_id(self.id, "candidate id"))
        if self.trigger not in TRIGGER_TYPES:
            raise LearningContractError(f"unsupported candidate trigger: {self.trigger}")
        evidence = _ordered_strings(
            self.evidence_refs,
            "evidence_refs",
            limit=32,
            opaque_ids=True,
        )
        if not evidence:
            raise LearningContractError("evidence_refs must not be empty")
        object.__setattr__(self, "evidence_refs", evidence)
        if not isinstance(self.dedupe_key, str) or not _DEDUPE_KEY.fullmatch(
            self.dedupe_key
        ):
            raise LearningContractError("dedupe_key must be a lowercase SHA-256 hex digest")

    @classmethod
    def create(
        cls, *, trigger: str, evidence_refs: Sequence[str]
    ) -> "LearningCandidate":
        evidence = tuple(evidence_refs)
        key = stable_dedupe_key(trigger, *sorted(evidence))
        return cls(
            id=f"candidate-{key[:20]}",
            trigger=trigger,
            evidence_refs=evidence,
            dedupe_key=key,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "evidence_refs": list(self.evidence_refs),
            "dedupe_key": self.dedupe_key,
        }
