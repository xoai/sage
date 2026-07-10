from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.composition_contracts import (
    CapabilityBinding,
    CompositionError,
    CompositionPolicy,
    Provider,
    ResolvedBinding,
    ResolvedComposition,
)


def binding(
    capability: str = "requirements.elicit",
    role: str = "owner",
    combine: str = "exclusive",
    **extra: object,
) -> dict[str, object]:
    return {
        "capability": capability,
        "role": role,
        "combine": combine,
        **extra,
    }


@pytest.mark.parametrize("role", ["owner", "augmenter", "validator", "observer"])
def test_all_neutral_roles_round_trip(role: str) -> None:
    combine = "exclusive" if role == "owner" else "compatible"
    item = CapabilityBinding.from_dict(binding(role=role, combine=combine))

    assert item.to_dict() == binding(role=role, combine=combine)


@pytest.mark.parametrize("combine", ["exclusive", "compatible"])
def test_combine_modes_are_explicit(combine: str) -> None:
    item = CapabilityBinding.from_dict(binding(combine=combine))

    assert item.combine == combine


@pytest.mark.parametrize(
    "capability",
    ["Requirements.elicit", "requirements", "requirements_elicit", ".requirements"],
)
def test_capability_names_are_stable_dotted_identifiers(capability: str) -> None:
    with pytest.raises(CompositionError, match="capability"):
        CapabilityBinding.from_dict(binding(capability=capability))


def test_inputs_outputs_and_terminal_are_optional_and_ordered() -> None:
    item = CapabilityBinding.from_dict(
        binding(
            inputs=["request", "codebase-context"],
            outputs=["acceptance-criteria", "problem-frame"],
            terminal="design-approved",
        )
    )

    assert item.inputs == ("request", "codebase-context")
    assert item.outputs == ("acceptance-criteria", "problem-frame")
    assert item.terminal == "design-approved"
    assert list(item.to_dict()) == [
        "capability",
        "role",
        "combine",
        "inputs",
        "outputs",
        "terminal",
    ]


def test_atomic_provider_preserves_declared_capability_span_order() -> None:
    provider = Provider.from_dict(
        {
            "id": "external:brainstorm",
            "atomic": True,
            "provides": [
                binding("requirements.elicit", terminal="requirements-complete"),
                binding("solution.specify", terminal="design-approved"),
            ],
        }
    )

    assert tuple(item.capability for item in provider.provides) == (
        "requirements.elicit",
        "solution.specify",
    )
    assert provider.terminal == "design-approved"


def test_atomic_provider_requires_a_nonempty_span() -> None:
    with pytest.raises(CompositionError, match="atomic span"):
        Provider.from_dict({"id": "x", "atomic": True, "provides": []})


def test_atomic_provider_requires_a_terminal_signal() -> None:
    with pytest.raises(CompositionError, match="terminal"):
        Provider.from_dict(
            {"id": "x", "atomic": True, "provides": [binding("change.implement")]}
        )


def test_exclusive_capability_requires_owner() -> None:
    with pytest.raises(CompositionError, match="owner"):
        Provider.from_dict(
            {
                "id": "x",
                "provides": [
                    binding("change.implement", role="augmenter", combine="exclusive")
                ],
            }
        )


def test_duplicate_provider_capability_role_tuple_is_rejected() -> None:
    with pytest.raises(CompositionError, match="duplicate"):
        Provider.from_dict(
            {
                "id": "x",
                "provides": [
                    binding("change.implement"),
                    binding("change.implement"),
                ],
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("role", "helper"), ("combine", "merge")],
)
def test_unknown_role_or_combine_mode_is_rejected(field: str, value: str) -> None:
    raw = binding()
    raw[field] = value

    with pytest.raises(CompositionError, match=field):
        CapabilityBinding.from_dict(raw)


def test_policy_preserves_declared_helper_order_and_is_immutable() -> None:
    policy = CompositionPolicy.from_dict(
        {
            "requirements.elicit": {
                "owner": "external:brainstorm",
                "augmenters": ["sage:context", "external:research"],
                "validators": ["sage:review"],
                "observers": ["learning:observer"],
            }
        }
    )

    assert policy.owner_for("requirements.elicit") == "external:brainstorm"
    assert policy.helpers_for("requirements.elicit", "augmenter") == (
        "sage:context",
        "external:research",
    )
    with pytest.raises(TypeError):
        policy.capabilities["requirements.elicit"] = {}  # type: ignore[index]


def test_resolved_composition_serializes_with_stable_keys() -> None:
    resolved = ResolvedComposition(
        catalog_hash="catalog-sha",
        selected_workflow="sage:build",
        bindings=(
            ResolvedBinding(
                capability="requirements.elicit",
                provider_id="external:brainstorm",
                role="owner",
                combine="exclusive",
                atomic=True,
                terminal="design-approved",
                provenance="explicit",
            ),
        ),
        hash="resolved-sha",
    )

    serialized = resolved.to_dict()
    assert list(serialized) == [
        "schema",
        "catalog_hash",
        "selected_workflow",
        "bindings",
        "hash",
    ]
    assert serialized["schema"] == "resolved-composition/v1"
    assert json.loads(json.dumps(serialized, sort_keys=True))["hash"] == "resolved-sha"
