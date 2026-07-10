from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.composition_contracts import CompositionError, ResolvedComposition
from sage_runtime.resolver import (
    ChoiceRequired,
    CompositionCatalog,
    CompositionRequest,
    resolve,
)


def provider(
    provider_id: str,
    capability: str,
    *,
    role: str = "owner",
    combine: str | None = None,
    atomic: bool = False,
    terminal: str | None = None,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
) -> dict:
    binding: dict[str, object] = {
        "capability": capability,
        "role": role,
        "combine": combine or ("exclusive" if role == "owner" else "compatible"),
    }
    if terminal:
        binding["terminal"] = terminal
    if inputs:
        binding["inputs"] = inputs
    if outputs:
        binding["outputs"] = outputs
    return {
        "id": provider_id,
        "atomic": atomic,
        "provides": [binding],
        "hash": f"hash-{provider_id}",
        "sources": [{"kind": "test", "path": provider_id}],
    }


def atomic_provider(provider_id: str) -> dict:
    item = provider(
        provider_id,
        "requirements.elicit",
        atomic=True,
        outputs=["problem-frame"],
    )
    item["provides"].append(
        {
            "capability": "solution.specify",
            "role": "owner",
            "combine": "exclusive",
            "inputs": ["problem-frame"],
            "outputs": ["specification"],
            "terminal": "design-approved",
        }
    )
    return item


def catalog(
    providers: list[dict],
    *,
    user: dict | None = None,
    project: dict | None = None,
    workflow_defaults: dict | None = None,
) -> CompositionCatalog:
    return CompositionCatalog.from_dict(
        {
            "schema": "composition-catalog/v1",
            "providers": {item["id"]: item for item in providers},
            "policy": {
                "base": {},
                "user": user or {},
                "project": project or {},
                "effective": {},
            },
            "workflow_defaults": workflow_defaults or {},
            "sources": [],
            "generated_at": "2026-07-10T12:00:00Z",
            "hash": "catalog-sha",
        }
    )


@pytest.mark.parametrize(
    ("explicit", "project_owner", "user_owner", "expected", "provenance"),
    [
        ("explicit-owner", "project-owner", "user-owner", "explicit-owner", "explicit"),
        (None, "project-owner", "user-owner", "project-owner", "project-policy"),
        (None, None, "user-owner", "user-owner", "user-policy"),
        (None, None, None, "workflow-owner", "workflow-default"),
    ],
)
def test_owner_resolution_uses_exact_precedence(
    explicit: str | None,
    project_owner: str | None,
    user_owner: str | None,
    expected: str,
    provenance: str,
) -> None:
    providers = [
        provider(name, "change.implement")
        for name in ("explicit-owner", "project-owner", "user-owner", "workflow-owner")
    ]
    request = CompositionRequest(
        explicit={
            "change.implement": {"owner": explicit}
        }
        if explicit
        else {},
        selected_workflow="sage:build",
        required_capabilities=("change.implement",),
    )
    result = resolve(
        catalog(
            providers,
            project={"change.implement": {"owner": project_owner}}
            if project_owner
            else {},
            user={"change.implement": {"owner": user_owner}} if user_owner else {},
            workflow_defaults={
                "sage:build": {"change.implement": {"owner": "workflow-owner"}}
            },
        ),
        request,
    )

    assert isinstance(result, ResolvedComposition)
    assert result.bindings[0].provider_id == expected
    assert result.bindings[0].provenance == provenance


def test_sage_only_workflow_resolves_defaults() -> None:
    result = resolve(
        catalog(
            [provider("implement", "change.implement")],
            workflow_defaults={
                "sage:build": {"change.implement": {"owner": "implement"}}
            },
        ),
        CompositionRequest(
            explicit={},
            selected_workflow="sage:build",
            required_capabilities=("change.implement",),
        ),
    )

    assert isinstance(result, ResolvedComposition)
    assert result.bindings[0].provider_id == "implement"


def test_external_only_workflow_keeps_sage_inactive() -> None:
    result = resolve(
        catalog(
            [provider("external:workflow", "change.implement")],
            workflow_defaults={
                "external:workflow": {
                    "change.implement": {"owner": "external:workflow"}
                }
            },
        ),
        CompositionRequest(
            explicit={},
            selected_workflow="external:workflow",
            required_capabilities=("change.implement",),
        ),
    )

    assert isinstance(result, ResolvedComposition)
    assert all(not item.provider_id.startswith("sage") for item in result.bindings)


def test_mixed_composition_adds_selected_helpers_in_declared_role_order() -> None:
    providers = [
        provider("external:brainstorm", "requirements.elicit"),
        provider("context-helper", "requirements.elicit", role="augmenter"),
        provider("sage-validator", "requirements.elicit", role="validator"),
        provider("learning-observer", "requirements.elicit", role="observer"),
    ]
    result = resolve(
        catalog(providers),
        CompositionRequest(
            explicit={
                "requirements.elicit": {
                    "owner": "external:brainstorm",
                    "augmenters": ["context-helper"],
                    "validators": ["sage-validator"],
                    "observers": ["learning-observer"],
                }
            },
            selected_workflow=None,
            required_capabilities=("requirements.elicit",),
        ),
    )

    assert isinstance(result, ResolvedComposition)
    assert [(item.role, item.provider_id) for item in result.bindings] == [
        ("owner", "external:brainstorm"),
        ("augmenter", "context-helper"),
        ("validator", "sage-validator"),
        ("observer", "learning-observer"),
    ]


def test_compatible_helpers_are_eligible_not_automatically_activated() -> None:
    providers = [
        provider("external:brainstorm", "requirements.elicit"),
        provider("context-helper", "requirements.elicit", role="augmenter"),
        provider("sage-validator", "requirements.elicit", role="validator"),
    ]

    result = resolve(
        catalog(providers),
        CompositionRequest(
            explicit={"requirements.elicit": {"owner": "external:brainstorm"}},
            selected_workflow=None,
            required_capabilities=("requirements.elicit",),
        ),
    )

    assert isinstance(result, ResolvedComposition)
    assert [(item.role, item.provider_id) for item in result.bindings] == [
        ("owner", "external:brainstorm")
    ]


def test_no_sage_direct_work_can_resolve_an_empty_requirement_set() -> None:
    result = resolve(
        catalog([]),
        CompositionRequest(explicit={}, selected_workflow=None, required_capabilities=()),
    )

    assert isinstance(result, ResolvedComposition)
    assert result.selected_workflow is None
    assert result.bindings == ()


def test_two_unresolved_exclusive_owners_require_a_user_choice() -> None:
    result = resolve(
        catalog(
            [
                provider("owner-a", "requirements.elicit"),
                provider("owner-b", "requirements.elicit"),
            ]
        ),
        CompositionRequest(
            explicit={},
            selected_workflow=None,
            required_capabilities=("requirements.elicit",),
        ),
    )

    assert isinstance(result, ChoiceRequired)
    assert result.to_dict()["schema"] == "choice-required/v1"
    assert [item["provider_id"] for item in result.to_dict()["candidates"]] == [
        "owner-a",
        "owner-b",
    ]


def test_explicit_missing_provider_is_invalid_configuration() -> None:
    with pytest.raises(CompositionError, match="missing"):
        resolve(
            catalog([provider("available", "change.implement")]),
            CompositionRequest(
                explicit={"change.implement": {"owner": "missing"}},
                selected_workflow=None,
                required_capabilities=("change.implement",),
            ),
        )


def test_selected_augmenter_must_be_io_compatible_with_owner() -> None:
    providers = [
        provider(
            "owner",
            "requirements.elicit",
            outputs=["problem-frame"],
        ),
        provider(
            "incompatible",
            "requirements.elicit",
            role="augmenter",
            inputs=["source-code"],
        ),
    ]

    with pytest.raises(CompositionError, match="incompatible"):
        resolve(
            catalog(providers),
            CompositionRequest(
                explicit={
                    "requirements.elicit": {
                        "owner": "owner",
                        "augmenters": ["incompatible"],
                    }
                },
                selected_workflow=None,
                required_capabilities=("requirements.elicit",),
            ),
        )


def test_atomic_provider_cannot_be_partially_selected() -> None:
    with pytest.raises(CompositionError, match="atomic.*partial"):
        resolve(
            catalog([atomic_provider("external:brainstorm")]),
            CompositionRequest(
                explicit={
                    "requirements.elicit": {"owner": "external:brainstorm"}
                },
                selected_workflow=None,
                required_capabilities=("requirements.elicit",),
            ),
        )


def test_resolve_cli_emits_choice_with_exit_four(tmp_path: Path) -> None:
    raw_catalog = catalog(
        [
            provider("owner-a", "requirements.elicit"),
            provider("owner-b", "requirements.elicit"),
        ]
    ).to_dict()
    catalog_path = tmp_path / "composition.json"
    catalog_path.write_text(json.dumps(raw_catalog), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime/tools/sage_runtime_cli.py"),
            "composition",
            "resolve",
            "--catalog",
            str(catalog_path),
        ],
        input=json.dumps(
            {
                "explicit": {},
                "selected_workflow": None,
                "required_capabilities": ["requirements.elicit"],
            }
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 4, result.stderr
    assert json.loads(result.stdout)["schema"] == "choice-required/v1"
