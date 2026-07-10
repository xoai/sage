from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime import catalog as catalog_module
from sage_runtime.catalog import CatalogError, compile_route_catalog, validate_route_target


def write_workflow(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.workflow.md"
    path.write_text(
        f"---\nname: {name}\nversion: \"1.0.0\"\n---\n\n# {name.title()} Workflow\n",
        encoding="utf-8",
    )
    return path


def test_catalog_discovers_workflows_and_records_real_platform_targets(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    write_workflow(workflows, "map")
    write_workflow(workflows, "build")

    catalog = compile_route_catalog(
        workflows,
        "hermes",
        {"map": "map", "build": " /sage:build "},
    )

    assert catalog["schema"] == "route-catalog/v1"
    assert catalog["platform"] == "hermes"
    assert catalog["routes"] == {
        "build": {
            "workflow": "build",
            "target": "/sage:build",
            "source": str((workflows / "build.workflow.md").resolve()),
        },
        "map": {
            "workflow": "map",
            "target": "/map",
            "source": str((workflows / "map.workflow.md").resolve()),
        },
    }
    assert len(catalog["hash"]) == 64
    assert catalog["generated_at"].endswith("Z")


def test_catalog_hash_ignores_generation_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflows = tmp_path / "workflows"
    write_workflow(workflows, "map")
    monkeypatch.setattr(catalog_module, "_utc_now", lambda: "2026-07-10T00:00:00Z")
    first = compile_route_catalog(workflows, "claude-code", {"map": "/map"})
    monkeypatch.setattr(catalog_module, "_utc_now", lambda: "2026-07-11T00:00:00Z")
    second = compile_route_catalog(workflows, "claude-code", {"map": "/map"})

    assert first["generated_at"] != second["generated_at"]
    assert first["hash"] == second["hash"]


def test_catalog_rejects_duplicate_platform_targets(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    write_workflow(workflows, "map")
    write_workflow(workflows, "build")

    with pytest.raises(CatalogError, match="duplicate.*target"):
        compile_route_catalog(workflows, "hermes", {"map": "/work", "build": "/work"})


def test_catalog_rejects_workflow_without_installed_target(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    write_workflow(workflows, "map")
    write_workflow(workflows, "build")

    with pytest.raises(CatalogError, match="missing.*build"):
        compile_route_catalog(workflows, "hermes", {"map": "/map"})


def test_catalog_rejects_target_for_missing_workflow(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    write_workflow(workflows, "map")

    with pytest.raises(CatalogError, match="unknown workflow.*ghost"):
        compile_route_catalog(workflows, "hermes", {"map": "/map", "ghost": "/ghost"})


@pytest.mark.parametrize("target", ["/map now", "//map", "/", "sage map"])
def test_catalog_rejects_unloadable_target(tmp_path: Path, target: str) -> None:
    workflows = tmp_path / "workflows"
    write_workflow(workflows, "map")

    with pytest.raises(CatalogError, match="invalid.*target"):
        compile_route_catalog(workflows, "hermes", {"map": target})


def test_validate_target_resolves_platform_identifier_not_guessed_namespace(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    write_workflow(workflows, "map")
    catalog = compile_route_catalog(workflows, "hermes", {"map": "/map"})

    assert validate_route_target(catalog, "/map") == "/map"
    assert validate_route_target(catalog, "sage:map") == "/map"
    with pytest.raises(CatalogError, match="unloadable route target"):
        validate_route_target(catalog, "/ghost")


def test_catalog_cli_discovers_command_files_and_writes_stable_json(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    commands = tmp_path / "commands"
    output = tmp_path / ".sage" / "runtime" / "route-catalog.json"
    write_workflow(workflows, "map")
    write_workflow(workflows, "build")
    commands.mkdir()
    (commands / "map.md").write_text("map", encoding="utf-8")
    (commands / "sage-build.md").write_text("build", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "catalog",
            "compile",
            "--workflow-dir",
            str(workflows),
            "--platform",
            "hermes",
            "--command-dir",
            str(commands),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["routes"]["map"]["target"] == "/map"
    assert written["routes"]["build"]["target"] == "/sage-build"
