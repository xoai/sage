from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.composition import compile_composition, compile_composition_to_path
from sage_runtime.composition_contracts import CompositionError


def write_skill(
    root: Path,
    name: str,
    capability: str,
    *,
    terminal: str | None = None,
    atomic: bool = False,
) -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    terminal_line = f"      terminal: {terminal}\n" if terminal else ""
    (directory / "SKILL.md").write_text(
        f"""---
name: {name}
description: Test provider {name}
---

<!-- sage-metadata
composition:
  contract: composition/v1
  atomic: {str(atomic).lower()}
  provides:
    - capability: {capability}
      role: owner
      combine: exclusive
{terminal_line}-->

# {name}
""",
        encoding="utf-8",
    )
    return directory


def write_overlay(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def overlay_binding(capability: str, *, terminal: str | None = None) -> dict:
    binding: dict[str, object] = {
        "capability": capability,
        "role": "owner",
        "combine": "exclusive",
    }
    if terminal:
        binding["terminal"] = terminal
    return {"atomic": terminal is not None, "provides": [binding]}


def test_builtin_skill_metadata_is_discovered_with_provenance(tmp_path: Path) -> None:
    builtins = tmp_path / "builtins"
    write_skill(builtins, "sage-implement", "change.implement")

    catalog = compile_composition(
        [builtins], None, None, installed_ids={"sage-implement"}
    )

    provider = catalog["providers"]["sage-implement"]
    assert provider["provides"][0]["capability"] == "change.implement"
    assert provider["sources"][0]["kind"] == "skill-metadata"
    assert provider["sources"][0]["path"].endswith("SKILL.md")


def test_non_utf8_skill_without_composition_marker_is_ignored(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    write_skill(skills, "valid", "change.implement")
    legacy = skills / "legacy" / "SKILL.md"
    legacy.parent.mkdir()
    legacy.write_bytes(b"---\nname: legacy\n---\n\xff\xfe")

    catalog = compile_composition(
        [skills], None, None, installed_ids={"valid", "legacy"}
    )

    assert set(catalog["providers"]) == {"valid"}
    assert catalog["direct_skills"] == ["legacy"]


def test_catalog_accounts_for_non_provider_skills_as_direct_commands(
    tmp_path: Path,
) -> None:
    skills = tmp_path / "skills"
    write_skill(skills, "method-owner", "change.implement")
    direct = skills / "react" / "SKILL.md"
    direct.parent.mkdir(parents=True)
    direct.write_text("---\nname: react\ndescription: React guidance\n---\n", encoding="utf-8")

    catalog = compile_composition(
        [skills], None, None, installed_ids={"method-owner", "react"}
    )

    assert set(catalog["providers"]) == {"method-owner"}
    assert catalog["direct_skills"] == ["react"]


def test_overlay_can_describe_an_unmodified_installed_skill(tmp_path: Path) -> None:
    installed = tmp_path / "installed"
    (installed / "external-brainstorm").mkdir(parents=True)
    (installed / "external-brainstorm" / "SKILL.md").write_text(
        "---\nname: external-brainstorm\ndescription: Unmodified\n---\n",
        encoding="utf-8",
    )
    user = write_overlay(
        tmp_path / "user.yaml",
        {
            "bindings": {
                "external-brainstorm": overlay_binding(
                    "requirements.elicit", terminal="design-approved"
                )
            }
        },
    )

    catalog = compile_composition(
        [installed], user, None, installed_ids={"external-brainstorm"}
    )

    provider = catalog["providers"]["external-brainstorm"]
    assert provider["atomic"] is True
    assert provider["sources"][-1]["kind"] == "user-overlay"


def test_namespaced_overlay_id_can_bind_installed_leaf(tmp_path: Path) -> None:
    installed = tmp_path / "installed"
    skill = installed / "brainstorming" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: brainstorming\ndescription: External method\n---\n",
        encoding="utf-8",
    )
    project = write_overlay(
        tmp_path / "composition.yaml",
        {
            "contract": "composition-overlay/v1",
            "bindings": {
                "superpowers:brainstorming": overlay_binding(
                    "requirements.elicit", terminal="design-approved"
                )
            },
        },
    )

    catalog = compile_composition(
        [installed],
        None,
        project,
        installed_ids={"brainstorming"},
    )

    assert "superpowers:brainstorming" in catalog["providers"]
    assert "brainstorming" not in catalog["direct_skills"]


def test_project_overlay_replaces_only_matching_user_keys(tmp_path: Path) -> None:
    roots = tmp_path / "skills"
    for name in ("user-owner", "project-owner", "helper-a", "helper-b"):
        (roots / name).mkdir(parents=True)
    user = write_overlay(
        tmp_path / "user.yaml",
        {
            "bindings": {
                "user-owner": overlay_binding("requirements.elicit"),
                "helper-a": {
                    "atomic": False,
                    "provides": [
                        {
                            "capability": "requirements.elicit",
                            "role": "augmenter",
                            "combine": "compatible",
                        }
                    ],
                },
            },
            "policy": {
                "requirements.elicit": {
                    "owner": "user-owner",
                    "augmenters": ["helper-a"],
                }
            },
        },
    )
    project = write_overlay(
        tmp_path / "project.yaml",
        {
            "bindings": {
                "project-owner": overlay_binding("requirements.elicit"),
                "helper-b": {
                    "atomic": False,
                    "provides": [
                        {
                            "capability": "requirements.elicit",
                            "role": "validator",
                            "combine": "compatible",
                        }
                    ],
                },
            },
            "policy": {
                "requirements.elicit": {
                    "owner": "project-owner",
                    "validators": ["helper-b"],
                }
            },
        },
    )

    catalog = compile_composition(
        [roots],
        user,
        project,
        installed_ids={"user-owner", "project-owner", "helper-a", "helper-b"},
    )

    effective = catalog["policy"]["effective"]["requirements.elicit"]
    assert effective == {
        "owner": "project-owner",
        "augmenters": ["helper-a"],
        "validators": ["helper-b"],
    }
    assert set(catalog["providers"]) == {
        "user-owner",
        "project-owner",
        "helper-a",
        "helper-b",
    }


def test_binding_for_missing_installed_skill_fails_validation(tmp_path: Path) -> None:
    overlay = write_overlay(
        tmp_path / "composition.yaml",
        {"bindings": {"missing-skill": overlay_binding("change.implement")}},
    )

    with pytest.raises(CompositionError, match="missing-skill.*installed"):
        compile_composition([], overlay, None, installed_ids=set())


def test_provider_hash_changes_with_capability_or_terminal(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    provider = write_skill(
        skills,
        "external",
        "requirements.elicit",
        terminal="design-approved",
        atomic=True,
    )
    first = compile_composition([skills], None, None, installed_ids={"external"})

    write_skill(
        skills,
        "external",
        "solution.specify",
        terminal="spec-approved",
        atomic=True,
    )
    second = compile_composition([skills], None, None, installed_ids={"external"})

    assert provider.is_dir()
    assert first["hash"] != second["hash"]
    assert first["providers"]["external"]["hash"] != second["providers"]["external"]["hash"]


def test_failed_compilation_does_not_replace_existing_catalog(tmp_path: Path) -> None:
    output = tmp_path / ".sage" / "composition.json"
    skills = tmp_path / "skills"
    write_skill(skills, "valid", "change.implement")
    compile_composition_to_path(
        output, [skills], None, None, installed_ids={"valid"}
    )
    before = output.read_bytes()
    invalid = write_overlay(
        tmp_path / "invalid.yaml",
        {"bindings": {"missing": overlay_binding("requirements.elicit")}},
    )

    with pytest.raises(CompositionError):
        compile_composition_to_path(
            output, [skills], invalid, None, installed_ids={"valid"}
        )

    assert output.read_bytes() == before


def test_repository_defaults_cover_approved_neutral_capabilities() -> None:
    defaults = yaml.safe_load(
        (ROOT / "core/composition/defaults.yaml").read_text(encoding="utf-8")
    )
    provided = {
        item["capability"]
        for provider in defaults["bindings"].values()
        for item in provider["provides"]
    }

    assert {
        "context.orient",
        "requirements.elicit",
        "problem.investigate",
        "solution.specify",
        "work.decompose",
        "change.implement",
        "evidence.verify",
        "output.review",
        "learning.capture",
        "work.handoff",
    } <= provided


def test_composition_compile_cli_writes_atomic_catalog(tmp_path: Path) -> None:
    skill_root = tmp_path / "sage" / "core" / "capabilities"
    write_skill(skill_root, "external", "change.implement")
    installed = tmp_path / ".claude" / "skills" / "external"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text("---\nname: external\n---\n", encoding="utf-8")
    output = tmp_path / ".sage" / "composition.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime/tools/sage_runtime_cli.py"),
            "composition",
            "compile",
            "--project",
            str(tmp_path),
            "--platform",
            "claude-code",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == "composition-catalog/v1"
