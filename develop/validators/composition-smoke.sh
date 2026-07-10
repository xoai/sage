#!/usr/bin/env bash
# Golden end-to-end scenarios for neutral skill ownership.
set -euo pipefail

resolve_root() {
  if [ -n "${1:-}" ]; then printf '%s' "$1"; return; fi
  cd "$(dirname "$0")/../.." && pwd
}

SAGE_ROOT="$(resolve_root "${1:-}")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONPATH="$SAGE_ROOT/runtime/tools${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON_BIN" - "$SAGE_ROOT" <<'PY'
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import yaml

from sage_runtime.composition import compile_composition
from sage_runtime.catalog import discover_workflows
from sage_runtime.composition_contracts import ResolvedComposition
from sage_runtime.resolver import CompositionCatalog, CompositionRequest, resolve


root = Path(__file__).resolve() if False else Path(__import__("sys").argv[1]).resolve()
builtin_roots = [root / "core" / "capabilities", root / "skills"]
base_overlay = root / "core" / "composition" / "defaults.yaml"
builtin_ids = {
    path.parent.name for skill_root in builtin_roots for path in skill_root.rglob("SKILL.md")
}
builtin_ids.update(discover_workflows(root / "core" / "workflows"))


def write_overlay(path: Path, value: dict) -> Path:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def compile_for(platform_root: Path, overlay: Path | None = None) -> CompositionCatalog:
    installed = set(builtin_ids)
    installed.update(path.parent.name for path in platform_root.rglob("SKILL.md"))
    compiled = compile_composition(
        [*builtin_roots, platform_root],
        None,
        overlay,
        installed,
        base_overlay=base_overlay,
    )
    return CompositionCatalog.from_dict(compiled)


def require_resolved(result) -> ResolvedComposition:
    assert isinstance(result, ResolvedComposition), result
    return result


def normalized(catalog: CompositionCatalog) -> dict:
    raw = catalog.to_dict()
    return {
        "providers": {
            provider_id: {
                key: value
                for key, value in provider.items()
                if key != "sources"
            }
            for provider_id, provider in raw["providers"].items()
        },
        "policy": raw["policy"],
        "workflow_defaults": raw["workflow_defaults"],
    }


with tempfile.TemporaryDirectory(prefix="sage-composition-") as raw_temp:
    temp = Path(raw_temp)
    claude_skills = temp / "claude-skills"
    hermes_skills = temp / "hermes-skills"
    claude_skills.mkdir()
    hermes_skills.mkdir()

    # 1. Sage build owns its declared default capabilities.
    sage_catalog = compile_for(claude_skills)
    sage_required = (
        "context.orient",
        "requirements.elicit",
        "solution.specify",
        "work.decompose",
        "change.implement",
        "evidence.verify",
        "output.review",
        "learning.capture",
        "work.handoff",
    )
    sage = require_resolved(
        resolve(
            sage_catalog,
            CompositionRequest(
                explicit={},
                selected_workflow="sage:build",
                required_capabilities=sage_required,
            ),
        )
    )
    assert len([item for item in sage.bindings if item.role == "owner"]) == len(
        sage_required
    )

    # Install one unmodified external skill in both platform stores.
    for platform_root in (claude_skills, hermes_skills):
        skill = platform_root / "external-brainstorm"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: external-brainstorm\ndescription: External method\n---\n",
            encoding="utf-8",
        )

    # 2. External atomic design method + Sage implementation and verification.
    mixed_overlay = write_overlay(
        temp / "mixed.yaml",
        {
            "contract": "composition-overlay/v1",
            "bindings": {
                "external-brainstorm": {
                    "atomic": True,
                    "provides": [
                        {
                            "capability": "requirements.elicit",
                            "role": "owner",
                            "combine": "exclusive",
                            "outputs": ["problem-frame"],
                        },
                        {
                            "capability": "solution.specify",
                            "role": "owner",
                            "combine": "exclusive",
                            "inputs": ["problem-frame"],
                            "outputs": ["specification"],
                            "terminal": "design-approved",
                        },
                    ],
                }
            },
            "policy": {
                "requirements.elicit": {"owner": "external-brainstorm"},
                "solution.specify": {"owner": "external-brainstorm"},
            },
        },
    )
    claude_mixed = compile_for(claude_skills, mixed_overlay)
    hermes_mixed = compile_for(hermes_skills, mixed_overlay)
    assert normalized(claude_mixed) == normalized(hermes_mixed)
    mixed = require_resolved(
        resolve(
            claude_mixed,
            CompositionRequest(
                explicit={},
                selected_workflow="sage:build",
                required_capabilities=(
                    "requirements.elicit",
                    "solution.specify",
                    "change.implement",
                    "evidence.verify",
                ),
            ),
        )
    )
    owners = {
        item.capability: item.provider_id for item in mixed.bindings if item.role == "owner"
    }
    assert owners == {
        "requirements.elicit": "external-brainstorm",
        "solution.specify": "external-brainstorm",
        "change.implement": "implement",
        "evidence.verify": "verify-completion",
    }

    # 3. External workflow owns every requested capability; no Sage role resolves.
    external_capabilities = sage_required
    external_provides = [
        {
            "capability": capability,
            "role": "owner",
            "combine": "exclusive",
            **(
                {"terminal": "external-workflow-complete"}
                if capability == external_capabilities[-1]
                else {}
            ),
        }
        for capability in external_capabilities
    ]
    external_overlay = write_overlay(
        temp / "external.yaml",
        {
            "bindings": {
                "external-brainstorm": {
                    "atomic": True,
                    "provides": external_provides,
                }
            },
            "workflow_defaults": {
                "external:workflow": {
                    capability: {"owner": "external-brainstorm"}
                    for capability in external_capabilities
                }
            },
        },
    )
    external_catalog = compile_for(claude_skills, external_overlay)
    external = require_resolved(
        resolve(
            external_catalog,
            CompositionRequest(
                explicit={},
                selected_workflow="external:workflow",
                required_capabilities=external_capabilities,
            ),
        )
    )
    assert {item.provider_id for item in external.bindings} == {"external-brainstorm"}

    # 4. Direct work selects learning independently without selecting a workflow.
    observer_dir = claude_skills / "run-observer"
    observer_dir.mkdir()
    (observer_dir / "SKILL.md").write_text(
        "---\nname: run-observer\ndescription: Run evidence observer\n---\n",
        encoding="utf-8",
    )
    observer_overlay = write_overlay(
        temp / "observer.yaml",
        {
            "bindings": {
                "run-observer": {
                    "atomic": False,
                    "provides": [
                        {
                            "capability": "learning.capture",
                            "role": "observer",
                            "combine": "compatible",
                        }
                    ],
                }
            }
        },
    )
    direct_catalog = compile_for(claude_skills, observer_overlay)
    direct = require_resolved(
        resolve(
            direct_catalog,
            CompositionRequest(
                explicit={
                    "learning.capture": {
                        "owner": "sage-self-learning",
                        "observers": ["run-observer"],
                    }
                },
                selected_workflow=None,
                required_capabilities=("learning.capture",),
            ),
        )
    )
    assert direct.selected_workflow is None
    assert [(item.role, item.provider_id) for item in direct.bindings] == [
        ("owner", "sage-self-learning"),
        ("observer", "run-observer"),
    ]

print("composition smoke: PASS")
PY
