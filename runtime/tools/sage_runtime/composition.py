"""Compile skill metadata and layered overlays into one provider catalog."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Collection, Mapping, Sequence

import yaml

from .composition_contracts import (
    COMPOSITION_CONTRACT,
    CompositionError,
    CompositionPolicy,
    Provider,
)
from .io import atomic_write_json
from .metadata import extract_sage_metadata


COMPOSITION_CATALOG_SCHEMA = "composition-catalog/v1"
_OVERLAY_KEYS = frozenset({"contract", "bindings", "policy", "workflow_defaults"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _stable_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _read_overlay(path: Path | None) -> dict[str, Any]:
    if path is None or not Path(path).is_file():
        return {}
    source = Path(path)
    try:
        loaded = yaml.safe_load(source.read_text(encoding="utf-8-sig")) or {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 1 if mark is not None else 1
        raise CompositionError(f"malformed composition overlay {source}:{line}: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise CompositionError(f"composition overlay must be a mapping: {source}")
    unknown = sorted(set(loaded) - _OVERLAY_KEYS)
    if unknown:
        raise CompositionError(f"unsupported composition overlay field: {unknown[0]}")
    contract = loaded.get("contract")
    if contract not in {None, COMPOSITION_CONTRACT, "composition-overlay/v1"}:
        raise CompositionError(f"unsupported composition overlay contract: {contract}")
    for field in ("bindings", "policy", "workflow_defaults"):
        value = loaded.get(field, {})
        if not isinstance(value, Mapping):
            raise CompositionError(f"overlay {field} must be a mapping: {source}")
    return dict(loaded)


def _provider_material(provider: Provider) -> dict[str, Any]:
    return provider.to_dict()


def _provider_is_installed(provider_id: str, installed: Collection[str]) -> bool:
    if provider_id in installed:
        return True
    if ":" not in provider_id:
        return False
    return provider_id.rsplit(":", 1)[-1] in installed


def _discover_providers(skill_roots: Sequence[Path]) -> dict[str, dict[str, Any]]:
    providers: dict[str, dict[str, Any]] = {}
    for root in sorted((Path(path) for path in skill_roots), key=lambda item: str(item)):
        if not root.is_dir():
            continue
        for skill_path in sorted(root.rglob("SKILL.md")):
            try:
                marker_probe = skill_path.read_bytes()
            except OSError as exc:
                raise CompositionError(f"cannot read installed skill: {skill_path}: {exc}") from exc
            if b"sage-metadata" not in marker_probe:
                continue
            metadata = extract_sage_metadata(skill_path)
            composition = metadata.get("composition")
            if composition is None:
                continue
            if not isinstance(composition, Mapping):
                raise CompositionError(f"composition metadata must be a mapping: {skill_path}")
            contract = composition.get("contract")
            if contract != COMPOSITION_CONTRACT:
                raise CompositionError(
                    f"unsupported composition contract {contract!r}: {skill_path}"
                )
            provider_id = composition.get("id", skill_path.parent.name)
            raw = {
                "id": provider_id,
                "atomic": composition.get("atomic", False),
                "provides": composition.get("provides", []),
            }
            provider = Provider.from_dict(raw)
            material = _provider_material(provider)
            existing = providers.get(provider.id)
            source = {"kind": "skill-metadata", "path": str(skill_path.resolve())}
            if existing is not None:
                if existing["raw"] != material:
                    raise CompositionError(
                        f"conflicting composition metadata for provider: {provider.id}"
                    )
                existing["sources"].append(source)
            else:
                providers[provider.id] = {"raw": material, "sources": [source]}
    return providers


def _apply_bindings(
    providers: dict[str, dict[str, Any]],
    overlay: Mapping[str, Any],
    kind: str,
    path: Path,
    installed: Collection[str],
) -> None:
    bindings = overlay.get("bindings", {})
    for provider_id, binding_raw in bindings.items():
        if not isinstance(provider_id, str) or not provider_id:
            raise CompositionError(f"overlay provider id must be a non-empty string: {path}")
        if not isinstance(binding_raw, Mapping):
            raise CompositionError(f"overlay binding for {provider_id} must be a mapping")
        if kind == "base-overlay" and not _provider_is_installed(
            provider_id, installed
        ):
            continue
        existing = providers.get(provider_id, {"raw": {"id": provider_id}, "sources": []})
        merged = _deep_merge(existing["raw"], dict(binding_raw))
        merged["id"] = provider_id
        provider = Provider.from_dict(merged)
        providers[provider_id] = {
            "raw": _provider_material(provider),
            "sources": [*existing["sources"], {"kind": kind, "path": str(path.resolve())}],
        }


def _provider_supports(
    providers: Mapping[str, dict[str, Any]], provider_id: str, capability: str, role: str
) -> bool:
    provider = providers.get(provider_id)
    if provider is None:
        return False
    return any(
        item["capability"] == capability and item["role"] == role
        for item in provider["raw"]["provides"]
    )


def _validate_policy(
    policy: CompositionPolicy, providers: Mapping[str, dict[str, Any]], label: str
) -> None:
    for capability, selection in policy.capabilities.items():
        owner = selection.get("owner")
        if isinstance(owner, str) and not _provider_supports(
            providers, owner, capability, "owner"
        ):
            raise CompositionError(
                f"{label} owner {owner!r} does not provide {capability} as owner"
            )
        for plural, role in (
            ("augmenters", "augmenter"),
            ("validators", "validator"),
            ("observers", "observer"),
        ):
            for provider_id in selection.get(plural, ()):
                if not _provider_supports(providers, provider_id, capability, role):
                    raise CompositionError(
                        f"{label} {role} {provider_id!r} does not provide {capability}"
                    )


def compile_composition(
    skill_roots: Sequence[Path],
    user_overlay: Path | None,
    project_overlay: Path | None,
    installed_ids: Collection[str],
    *,
    base_overlay: Path | None = None,
) -> dict[str, Any]:
    """Compile installed providers and overlays into ``composition-catalog/v1``."""

    providers = _discover_providers(skill_roots)
    installed = set(installed_ids)
    layers = (
        ("base", base_overlay, _read_overlay(base_overlay)),
        ("user", user_overlay, _read_overlay(user_overlay)),
        ("project", project_overlay, _read_overlay(project_overlay)),
    )
    for kind, path, overlay in layers:
        if path is not None and overlay:
            _apply_bindings(
                providers,
                overlay,
                f"{kind}-overlay",
                Path(path),
                installed,
            )

    missing = sorted(
        provider_id
        for provider_id in providers
        if not _provider_is_installed(provider_id, installed)
    )
    if missing:
        raise CompositionError(f"provider {missing[0]!r} is not installed")

    policy_layers: dict[str, CompositionPolicy] = {}
    effective_policy_raw: dict[str, Any] = {}
    workflow_defaults_raw: dict[str, Any] = {}
    sources: list[dict[str, str]] = []
    for kind, path, overlay in layers:
        raw_policy = overlay.get("policy", {})
        policy_layers[kind] = CompositionPolicy.from_dict(raw_policy)
        effective_policy_raw = _deep_merge(effective_policy_raw, raw_policy)
        layer_defaults = overlay.get("workflow_defaults", {})
        if kind == "base":
            layer_defaults = {
                workflow: selection
                for workflow, selection in layer_defaults.items()
                if workflow.rsplit(":", 1)[-1] in installed
            }
        workflow_defaults_raw = _deep_merge(
            workflow_defaults_raw, layer_defaults
        )
        if path is not None and overlay:
            sources.append({"kind": f"{kind}-overlay", "path": str(Path(path).resolve())})
    effective_policy = CompositionPolicy.from_dict(effective_policy_raw)
    for kind, policy in policy_layers.items():
        _validate_policy(policy, providers, f"{kind} policy")
    _validate_policy(effective_policy, providers, "effective policy")

    workflow_defaults: dict[str, Any] = {}
    for workflow, raw_policy in workflow_defaults_raw.items():
        if not isinstance(workflow, str) or not isinstance(raw_policy, Mapping):
            raise CompositionError("workflow defaults must map workflow IDs to policies")
        parsed = CompositionPolicy.from_dict(raw_policy)
        _validate_policy(parsed, providers, f"workflow default {workflow}")
        workflow_defaults[workflow] = parsed.to_dict()

    rendered_providers: dict[str, Any] = {}
    for provider_id in sorted(providers):
        material = providers[provider_id]["raw"]
        rendered_providers[provider_id] = {
            **material,
            "hash": _stable_hash(material),
            "sources": providers[provider_id]["sources"],
        }
    policy_output = {
        "base": policy_layers["base"].to_dict(),
        "user": policy_layers["user"].to_dict(),
        "project": policy_layers["project"].to_dict(),
        "effective": effective_policy.to_dict(),
    }
    claimed_installed_ids = set(rendered_providers)
    claimed_installed_ids.update(
        provider_id.rsplit(":", 1)[-1]
        for provider_id in rendered_providers
        if ":" in provider_id
    )
    direct_skills = sorted(installed - claimed_installed_ids)
    hash_material = {
        "schema": COMPOSITION_CATALOG_SCHEMA,
        "providers": {
            provider_id: {
                key: value
                for key, value in provider.items()
                if key not in {"sources"}
            }
            for provider_id, provider in rendered_providers.items()
        },
        "policy": policy_output,
        "workflow_defaults": workflow_defaults,
        "direct_skills": direct_skills,
    }
    return {
        "schema": COMPOSITION_CATALOG_SCHEMA,
        "providers": rendered_providers,
        "policy": policy_output,
        "workflow_defaults": workflow_defaults,
        "direct_skills": direct_skills,
        "sources": sources,
        "generated_at": _utc_now(),
        "hash": _stable_hash(hash_material),
    }


def compile_composition_to_path(
    output: Path,
    skill_roots: Sequence[Path],
    user_overlay: Path | None,
    project_overlay: Path | None,
    installed_ids: Collection[str],
    *,
    base_overlay: Path | None = None,
) -> dict[str, Any]:
    catalog = compile_composition(
        skill_roots,
        user_overlay,
        project_overlay,
        installed_ids,
        base_overlay=base_overlay,
    )
    atomic_write_json(Path(output), catalog)
    return catalog
