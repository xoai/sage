"""Pure deterministic resolution of neutral composition ownership."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .composition import COMPOSITION_CATALOG_SCHEMA
from .composition_contracts import (
    CapabilityBinding,
    CompositionError,
    CompositionPolicy,
    Provider,
    ResolvedBinding,
    ResolvedComposition,
    validate_capability,
)


CHOICE_REQUIRED_SCHEMA = "choice-required/v1"
_HELPER_ROLES = ("augmenter", "validator", "observer")


def _stable_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CompositionCatalog:
    providers: Mapping[str, Provider]
    provider_metadata: Mapping[str, Mapping[str, object]]
    policy: Mapping[str, CompositionPolicy]
    workflow_defaults: Mapping[str, CompositionPolicy]
    hash: str
    raw: Mapping[str, object]

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "CompositionCatalog":
        if not isinstance(raw, Mapping) or raw.get("schema") != COMPOSITION_CATALOG_SCHEMA:
            raise CompositionError("unsupported composition catalog schema")
        providers_raw = raw.get("providers", {})
        if not isinstance(providers_raw, Mapping):
            raise CompositionError("composition catalog providers must be a mapping")
        providers: dict[str, Provider] = {}
        metadata: dict[str, Mapping[str, object]] = {}
        for provider_id, provider_raw in providers_raw.items():
            if not isinstance(provider_id, str) or not isinstance(provider_raw, Mapping):
                raise CompositionError("composition provider entries must be mappings")
            provider = Provider.from_dict(
                {
                    "id": provider_raw.get("id", provider_id),
                    "atomic": provider_raw.get("atomic", False),
                    "provides": provider_raw.get("provides", []),
                }
            )
            if provider.id != provider_id:
                raise CompositionError(f"provider key does not match id: {provider_id}")
            providers[provider_id] = provider
            metadata[provider_id] = MappingProxyType(
                {
                    "hash": provider_raw.get("hash", ""),
                    "sources": tuple(provider_raw.get("sources", [])),
                }
            )
        policy_raw = raw.get("policy", {})
        if not isinstance(policy_raw, Mapping):
            raise CompositionError("composition catalog policy must be a mapping")
        policy = {
            layer: CompositionPolicy.from_dict(policy_raw.get(layer, {}))
            for layer in ("base", "user", "project", "effective")
        }
        defaults_raw = raw.get("workflow_defaults", {})
        if not isinstance(defaults_raw, Mapping):
            raise CompositionError("workflow_defaults must be a mapping")
        workflow_defaults: dict[str, CompositionPolicy] = {}
        for workflow, selection in defaults_raw.items():
            if not isinstance(workflow, str) or not isinstance(selection, Mapping):
                raise CompositionError("workflow default entries must be mappings")
            workflow_defaults[workflow] = CompositionPolicy.from_dict(selection)
        catalog_hash = raw.get("hash")
        if not isinstance(catalog_hash, str) or not catalog_hash:
            raise CompositionError("composition catalog requires a hash")
        return cls(
            providers=MappingProxyType(providers),
            provider_metadata=MappingProxyType(metadata),
            policy=MappingProxyType(policy),
            workflow_defaults=MappingProxyType(workflow_defaults),
            hash=catalog_hash,
            raw=MappingProxyType(dict(raw)),
        )

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(dict(self.raw)))


@dataclass(frozen=True)
class CompositionRequest:
    explicit: Mapping[str, Mapping[str, object]]
    selected_workflow: str | None
    required_capabilities: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "CompositionRequest":
        if not isinstance(raw, Mapping):
            raise CompositionError("composition request must be a mapping")
        explicit = raw.get("explicit", {})
        if not isinstance(explicit, Mapping):
            raise CompositionError("composition request explicit must be a mapping")
        workflow = raw.get("selected_workflow")
        if workflow is not None and (not isinstance(workflow, str) or not workflow):
            raise CompositionError("selected_workflow must be a non-empty string or null")
        required = raw.get("required_capabilities", [])
        if not isinstance(required, list):
            raise CompositionError("required_capabilities must be a list")
        normalized: list[str] = []
        for capability in required:
            normalized.append(validate_capability(capability))
        if len(set(normalized)) != len(normalized):
            raise CompositionError("required_capabilities contains duplicates")
        return cls(
            explicit=explicit,
            selected_workflow=workflow,
            required_capabilities=tuple(normalized),
        )


@dataclass(frozen=True)
class ChoiceRequired:
    capability: str
    candidates: tuple[Mapping[str, object], ...]
    reason: str = "multiple exclusive owners require explicit selection"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CHOICE_REQUIRED_SCHEMA,
            "capability": self.capability,
            "candidates": [dict(item) for item in self.candidates],
            "reason": self.reason,
        }


def _binding(provider: Provider, capability: str, role: str) -> CapabilityBinding | None:
    return next(
        (
            item
            for item in provider.provides
            if item.capability == capability and item.role == role
        ),
        None,
    )


def _selected_provider(
    catalog: CompositionCatalog,
    capability: str,
    role: str,
    provider_id: str,
    provenance: str,
) -> ResolvedBinding:
    provider = catalog.providers.get(provider_id)
    if provider is None:
        raise CompositionError(f"selected provider is missing: {provider_id}")
    binding = _binding(provider, capability, role)
    if binding is None:
        raise CompositionError(
            f"provider {provider_id!r} does not provide {capability} as {role}"
        )
    return ResolvedBinding(
        capability=capability,
        provider_id=provider_id,
        role=role,
        combine=binding.combine,
        atomic=provider.atomic,
        terminal=binding.terminal,
        provenance=provenance,
    )


def _selection(
    policies: tuple[tuple[str, CompositionPolicy], ...], capability: str, role: str
) -> tuple[tuple[str, ...], str] | None:
    for provenance, policy in policies:
        if role == "owner":
            owner = policy.owner_for(capability)
            if owner is not None:
                return (owner,), provenance
        else:
            helpers = policy.helpers_for(capability, role)
            if helpers:
                return helpers, provenance
    return None


def _owner_candidates(catalog: CompositionCatalog, capability: str) -> list[str]:
    return [
        provider_id
        for provider_id, provider in catalog.providers.items()
        if _binding(provider, capability, "owner") is not None
    ]


def _choice(catalog: CompositionCatalog, capability: str, candidates: list[str]) -> ChoiceRequired:
    rendered: list[Mapping[str, object]] = []
    for provider_id in candidates:
        metadata = catalog.provider_metadata.get(provider_id, {})
        rendered.append(
            MappingProxyType(
                {
                    "provider_id": provider_id,
                    "provenance": "unresolved",
                    "sources": list(metadata.get("sources", ())),
                }
            )
        )
    return ChoiceRequired(capability=capability, candidates=tuple(rendered))


def _check_io_compatibility(
    catalog: CompositionCatalog, owner: ResolvedBinding, helper: ResolvedBinding
) -> None:
    if helper.role != "augmenter":
        return
    owner_binding = _binding(
        catalog.providers[owner.provider_id], owner.capability, owner.role
    )
    helper_binding = _binding(
        catalog.providers[helper.provider_id], helper.capability, helper.role
    )
    if owner_binding is None or helper_binding is None:
        return
    if owner_binding.outputs and helper_binding.inputs:
        if set(owner_binding.outputs).isdisjoint(helper_binding.inputs):
            raise CompositionError(
                f"incompatible augmenter {helper.provider_id!r} for owner "
                f"{owner.provider_id!r} on {owner.capability}"
            )


def _validate_atomic_spans(
    catalog: CompositionCatalog, bindings: tuple[ResolvedBinding, ...]
) -> None:
    selected: dict[str, set[tuple[str, str]]] = {}
    for item in bindings:
        selected.setdefault(item.provider_id, set()).add((item.capability, item.role))
    for provider_id, chosen in selected.items():
        provider = catalog.providers[provider_id]
        if not provider.atomic:
            continue
        declared = {(item.capability, item.role) for item in provider.provides}
        if chosen != declared:
            missing = sorted(declared - chosen)
            raise CompositionError(
                f"atomic provider partial selection: {provider_id}; missing {missing}"
            )


def resolve(
    catalog: CompositionCatalog, request: CompositionRequest
) -> ResolvedComposition | ChoiceRequired:
    """Resolve owners and compatible helpers without lexical inference."""

    explicit = CompositionPolicy.from_dict(request.explicit)
    workflow = CompositionPolicy.from_dict({})
    if request.selected_workflow is not None:
        workflow = catalog.workflow_defaults.get(request.selected_workflow)
        if workflow is None:
            raise CompositionError(
                f"selected workflow has no composition defaults: {request.selected_workflow}"
            )
    policies = (
        ("explicit", explicit),
        ("project-policy", catalog.policy["project"]),
        ("user-policy", catalog.policy["user"]),
        ("workflow-default", workflow),
    )
    resolved: list[ResolvedBinding] = []
    for capability in request.required_capabilities:
        chosen = _selection(policies, capability, "owner")
        if chosen is None:
            candidates = _owner_candidates(catalog, capability)
            if len(candidates) > 1:
                return _choice(catalog, capability, candidates)
            if not candidates:
                raise CompositionError(f"no owner provides required capability: {capability}")
            chosen = ((candidates[0],), "unique-provider")
        owner = _selected_provider(
            catalog, capability, "owner", chosen[0][0], chosen[1]
        )
        resolved.append(owner)

        for role in _HELPER_ROLES:
            selected_helpers = _selection(policies, capability, role)
            ordered: list[tuple[str, str]] = []
            if selected_helpers is not None:
                ordered.extend((item, selected_helpers[1]) for item in selected_helpers[0])
            for provider_id, provenance in ordered:
                helper = _selected_provider(
                    catalog, capability, role, provider_id, provenance
                )
                if helper.combine != "compatible":
                    raise CompositionError(
                        f"incompatible {role} {provider_id!r} for {capability}"
                    )
                _check_io_compatibility(catalog, owner, helper)
                resolved.append(helper)

    bindings = tuple(resolved)
    _validate_atomic_spans(catalog, bindings)
    material = {
        "catalog_hash": catalog.hash,
        "selected_workflow": request.selected_workflow,
        "bindings": [item.to_dict() for item in bindings],
    }
    return ResolvedComposition(
        catalog_hash=catalog.hash,
        selected_workflow=request.selected_workflow,
        bindings=bindings,
        hash=_stable_hash(material),
    )
