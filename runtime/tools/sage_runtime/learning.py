"""Deterministic, backend-neutral recall orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from .backends.base import LearningBackend
from .learning_contracts import (
    MAX_DIAGNOSTIC_BYTES,
    MAX_RECALL_RECORDS,
    LearningContext,
    LearningContractError,
    RecallRecord,
    RecallResult,
)


MAX_QUERY_BYTES = 4096
DEFAULT_RENDER_BYTES = 4096


class LearningConfigError(ValueError):
    """Raised when a deployment selects ambiguous learning ownership."""


@dataclass(frozen=True)
class LearningConfig:
    backend: str
    recall_owner: str
    openviking: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


def _truncate_utf8(value: object, max_bytes: int, suffix: str = "") -> str:
    text = " ".join(str(value or "").split())
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    suffix_bytes = suffix.encode("utf-8")
    budget = max(0, max_bytes - len(suffix_bytes))
    return encoded[:budget].decode("utf-8", errors="ignore").rstrip() + suffix


def _single_selection(value: object, singular: object, label: str) -> str | None:
    candidates: list[str] = []
    if singular is not None:
        if not isinstance(singular, str) or not singular.strip():
            raise LearningConfigError(f"{label} must be a non-empty string")
        candidates.append(singular.strip())
    if value is not None:
        if not isinstance(value, list):
            raise LearningConfigError(f"{label}s must be a list")
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise LearningConfigError(f"{label}s must contain non-empty strings")
            candidates.append(item.strip())
    unique = tuple(dict.fromkeys(candidates))
    if len(unique) > 1:
        raise LearningConfigError(f"learning requires exactly one active {label}")
    return unique[0] if unique else None


def resolve_learning_config(
    project: Path, environ: Mapping[str, str] | None = None
) -> LearningConfig:
    """Resolve one backend and one recall owner from env over project config."""
    env = os.environ if environ is None else environ
    config_path = Path(project) / ".sage" / "config.yaml"
    learning: Mapping[str, object] = {}
    if config_path.is_file():
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise LearningConfigError(f"invalid learning config: {exc}") from exc
        if not isinstance(loaded, Mapping):
            raise LearningConfigError("project config must be a mapping")
        raw_learning = loaded.get("learning", {})
        if not isinstance(raw_learning, Mapping):
            raise LearningConfigError("learning config must be a mapping")
        learning = raw_learning

    configured_backend = _single_selection(
        learning.get("backends"), learning.get("backend"), "backend"
    )
    env_backend = env.get("SAGE_LEARNING_BACKEND")
    if env_backend is not None:
        parts = [item.strip() for item in env_backend.split(",") if item.strip()]
        if len(tuple(dict.fromkeys(parts))) != 1:
            raise LearningConfigError("learning requires exactly one active backend")
        configured_backend = parts[0]

    configured_owner = _single_selection(
        learning.get("recall_owners"), learning.get("recall_owner"), "recall owner"
    )
    env_owner = env.get("SAGE_LEARNING_RECALL_OWNER")
    if env_owner is not None:
        owners = [item.strip() for item in env_owner.split(",") if item.strip()]
        if len(tuple(dict.fromkeys(owners))) != 1:
            raise LearningConfigError("learning requires exactly one active recall owner")
        configured_owner = owners[0]

    openviking_raw = learning.get("openviking", {})
    if not isinstance(openviking_raw, Mapping):
        raise LearningConfigError("learning.openviking must be a mapping")
    allowed_openviking = {
        "base_url_env",
        "resource_uri_env",
        "user_env",
        "agent_id_env",
    }
    unknown = sorted(set(openviking_raw) - allowed_openviking)
    if unknown:
        raise LearningConfigError(f"unsupported OpenViking config field: {unknown[0]}")
    openviking: dict[str, str] = {}
    for key, value in openviking_raw.items():
        if not isinstance(value, str) or not value.strip():
            raise LearningConfigError(f"learning.openviking.{key} must name an environment variable")
        openviking[str(key)] = value.strip()

    return LearningConfig(
        backend=configured_backend or "sage-memory",
        recall_owner=configured_owner or "sage-learning",
        openviking=MappingProxyType(openviking),
    )


def build_recall_query(context: LearningContext, max_bytes: int = MAX_QUERY_BYTES) -> str:
    """Build a stable query from task and currently selected method context."""
    fields = [
        ("request", context.current_request),
        ("capability", context.active_capability),
        (
            "providers",
            ",".join(context.selected_providers)
            if context.selected_providers
            else None,
        ),
        ("repo", context.repo_name),
        ("subsystem", context.touched_subsystem),
    ]
    query = " | ".join(f"{name}={value}" for name, value in fields if value)
    return _truncate_utf8(query, max(1, min(max_bytes, MAX_QUERY_BYTES)))


def _selector_matches(value: str, selected: tuple[str, ...]) -> bool:
    target = value.casefold()
    return any(item.casefold() == target for item in selected)


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip().removeprefix("./")
    return normalized.rstrip("/").casefold()


def _path_selector_matches(selector: str, context: LearningContext) -> bool:
    expected = _normalize_path(selector)
    candidates = [*context.touched_paths]
    if context.touched_subsystem:
        candidates.append(context.touched_subsystem)
    for candidate_raw in candidates:
        candidate = _normalize_path(candidate_raw)
        if candidate == expected or candidate.startswith(expected + "/"):
            return True
    return False


def _eligible(record: RecallRecord, context: LearningContext) -> bool:
    if record.status != "active" or record.superseded_by is not None:
        return False
    if record.scope == "project" and record.project:
        project_names = {
            context.repo_name.casefold(),
            Path(context.project_root).name.casefold(),
        }
        if record.project.casefold() not in project_names:
            return False
    if record.platforms and not _selector_matches(context.platform, record.platforms):
        return False
    if record.capabilities:
        capability = context.active_capability
        if capability is None or not _selector_matches(capability, record.capabilities):
            return False
    if record.providers and not any(
        _selector_matches(provider, record.providers)
        for provider in context.selected_providers
    ):
        return False
    if record.paths and not any(
        _path_selector_matches(selector, context) for selector in record.paths
    ):
        return False
    return True


def _diagnostic(value: object) -> str:
    return _truncate_utf8(value, MAX_DIAGNOSTIC_BYTES)


def recall_before_work(
    backend: LearningBackend,
    context: LearningContext,
    limit: int = 5,
    max_bytes: int = DEFAULT_RENDER_BYTES,
) -> RecallResult:
    """Attempt one bounded recall without invoking routing, gates, or writes."""
    bounded_limit = min(MAX_RECALL_RECORDS, max(1, int(limit)))
    query = build_recall_query(context)
    try:
        fetched = backend.search_learnings(query, context, bounded_limit)
    except Exception as exc:
        return RecallResult(
            query=query,
            backend=type(backend).__name__,
            diagnostics=(_diagnostic(f"learning recall unavailable: {exc}"),),
            ok=False,
        )
    if not fetched.ok:
        diagnostic = (
            fetched.diagnostics[0]
            if fetched.diagnostics
            else "learning backend reported recall unavailable"
        )
        return RecallResult(
            query=query,
            backend=fetched.backend,
            diagnostics=(_diagnostic(diagnostic),),
            ok=False,
        )

    records: list[RecallRecord] = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for record in fetched.records:
        if not _eligible(record, context):
            continue
        if record.id in seen_ids or record.dedupe_key in seen_keys:
            continue
        records.append(record)
        seen_ids.add(record.id)
        seen_keys.add(record.dedupe_key)
        if len(records) >= bounded_limit:
            break

    # Keep the returned set aligned with the caller's rendering budget.  A
    # single long rule is retained and safely truncated only at render time.
    render_limit = max(1, int(max_bytes))
    while len(records) > 1:
        candidate = RecallResult(query=query, records=tuple(records), backend=fetched.backend)
        if len(render_recall_context(candidate, render_limit).encode("utf-8")) < render_limit:
            break
        records.pop()
    return RecallResult(query=query, records=tuple(records), backend=fetched.backend)


def render_recall_context(
    result: RecallResult, max_bytes: int = DEFAULT_RENDER_BYTES
) -> str:
    """Render only prevention and rationale; never route or authorization data."""
    if not result.ok or not result.records:
        return ""
    lines = ["[Relevant self-learnings: advisory context]"]
    for record in result.records:
        if record.prevention:
            lines.append(f"Prevention: {record.prevention}")
        if record.rationale:
            lines.append(f"Rationale: {record.rationale}")
    text = "\n".join(lines) + "\n"
    max_bytes = max(1, int(max_bytes))
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    suffix = "[learning recall truncated]\n"
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) >= max_bytes:
        return suffix_bytes[:max_bytes].decode("utf-8", errors="ignore")
    budget = max_bytes - len(suffix_bytes)
    prefix = text.encode("utf-8")[:budget].decode("utf-8", errors="ignore").rstrip()
    return prefix + "\n" + suffix


def create_learning_backend(
    name: str,
    *,
    config: LearningConfig | None = None,
    transport: object | None = None,
    environ: Mapping[str, str] | None = None,
) -> LearningBackend:
    if name == "sage-memory":
        from .backends.sage_memory import SageMemoryBackend

        return SageMemoryBackend()
    if name == "openviking":
        from .backends.openviking import OpenVikingBackend, UrllibTransport

        env = os.environ if environ is None else environ
        options = config.openviking if config is not None else {}
        variable_names = {
            "base_url_env": options.get("base_url_env", "OPENVIKING_BASE_URL"),
            "resource_uri_env": options.get(
                "resource_uri_env", "SAGE_LEARNING_RESOURCE_URI"
            ),
            "user_env": options.get("user_env", "OPENVIKING_USER"),
            "agent_id_env": options.get("agent_id_env", "OPENVIKING_AGENT_ID"),
        }
        values: dict[str, str] = {}
        for field_name, variable_name in variable_names.items():
            value = env.get(variable_name, "").strip()
            if not value:
                raise LearningConfigError(
                    f"OpenViking backend requires environment variable {variable_name}"
                )
            values[field_name.removesuffix("_env")] = value
        selected_transport = transport
        if selected_transport is None:
            api_key = env.get("OPENVIKING_API_KEY", "").strip()
            auth_headers = (
                {"X-API-Key": api_key, "Authorization": f"Bearer {api_key}"}
                if api_key
                else {}
            )
            selected_transport = UrllibTransport(default_headers=auth_headers)
        return OpenVikingBackend(
            base_url=values["base_url"],
            resource_uri=values["resource_uri"],
            user=values["user"],
            agent_id=values["agent_id"],
            transport=selected_transport,  # type: ignore[arg-type]
        )
    raise LearningConfigError(f"unsupported learning backend: {name}")
