from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.catalog import compile_route_catalog
from sage_runtime.contracts import RunState
from sage_runtime.router import route


def write_workflow(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.workflow.md").write_text(
        f"---\nname: {name}\nversion: \"1.0.0\"\n---\n# {name}\n",
        encoding="utf-8",
    )


@pytest.fixture
def catalog(tmp_path: Path) -> dict[str, object]:
    workflow_dir = tmp_path / "workflows"
    for name in ("map", "build", "fix"):
        write_workflow(workflow_dir, name)
    return compile_route_catalog(
        workflow_dir,
        "hermes",
        {"map": "/map", "build": "/sage-build", "fix": "/fix"},
    )


@pytest.fixture
def active_run() -> RunState:
    return RunState.from_dict(
        {
            "schema": "run-state/v1",
            "run_id": "run-001",
            "status": "active",
            "explicit_intent": True,
            "workflow_owner": "sage:build",
            "active_capability": "change.implement",
            "active_provider": "sage:implement",
            "strict": False,
            "composition_hash": "composition-sha",
            "route_catalog_hash": "catalog-sha",
            "artifacts": {},
            "verification": {},
            "dirty": False,
            "updated_at": "2026-07-10T00:00:00Z",
        }
    )


def test_explicit_catalog_command_is_authoritative_without_arming_gate(catalog: dict) -> None:
    decision = route("/map this repository", catalog, active_run=None)

    assert decision.to_dict() == {
        "schema": "route-decision/v1",
        "kind": "explicit",
        "target": "/map",
        "authoritative": True,
        "arm_gate": False,
        "reason": "validated explicit command",
        "diagnostics": [],
    }


def test_wrong_namespace_is_a_corrected_suggestion_not_authority(catalog: dict) -> None:
    decision = route("sage:map", catalog, active_run=None)

    assert decision.kind == "suggestion"
    assert decision.target == "/map"
    assert decision.authoritative is False
    assert decision.arm_gate is False
    assert any("/map" in diagnostic for diagnostic in decision.diagnostics)


@pytest.mark.parametrize(
    "prompt",
    [
        "Hermes memory setup",
        "the docs said 'ship it'",
        "public IP address",
        "decode this value",
        "update dependencies",
        "> /build was used in the old transcript",
        "```text\n/map this repository\n```",
    ],
)
def test_non_authoritative_mentions_do_not_route(prompt: str, catalog: dict) -> None:
    decision = route(prompt, catalog, active_run=None)

    assert decision.kind == "none"
    assert decision.target is None
    assert decision.authoritative is False
    assert decision.arm_gate is False


def test_idle_unique_workflow_word_is_advisory_only(catalog: dict) -> None:
    decision = route("Please map the spaces in this repository", catalog, active_run=None)

    assert decision.kind == "advisory"
    assert decision.target == "/map"
    assert decision.authoritative is False
    assert decision.arm_gate is False


def test_active_run_suppresses_natural_language_inference(catalog: dict, active_run: RunState) -> None:
    decision = route("Please map the spaces in this repository", catalog, active_run=active_run)

    assert decision.kind == "none"
    assert decision.target is None
    assert decision.reason == "active run suppresses inferred routing"


def test_active_run_suppresses_wrong_namespace_suggestion(
    catalog: dict, active_run: RunState
) -> None:
    decision = route("sage:fix", catalog, active_run=active_run)

    assert decision.kind == "none"
    assert decision.target is None
    assert decision.reason == "active run suppresses inferred routing"


def test_explicit_command_during_active_run_is_an_explicit_switch(
    catalog: dict, active_run: RunState
) -> None:
    decision = route("/map this repository", catalog, active_run=active_run)

    assert decision.kind == "switch"
    assert decision.target == "/map"
    assert decision.authoritative is True
    assert decision.arm_gate is False


def test_explicit_cancel_is_authoritative_only_when_run_is_active(
    catalog: dict, active_run: RunState
) -> None:
    active = route("/cancel", catalog, active_run=active_run)
    idle = route("/cancel", catalog, active_run=None)

    assert active.kind == "cancel"
    assert active.authoritative is True
    assert active.target is None
    assert idle.kind == "none"
    assert idle.authoritative is False


def test_other_plugin_directive_does_not_fall_through_to_sage_inference(catalog: dict) -> None:
    decision = route("/superpowers:brainstorming build a feature", catalog, active_run=None)

    assert decision.kind == "none"
    assert decision.target is None
    assert any("not installed" in diagnostic for diagnostic in decision.diagnostics)


def test_two_idle_workflow_matches_do_not_choose_silently(catalog: dict) -> None:
    decision = route("Map the project and build the feature", catalog, active_run=None)

    assert decision.kind == "ambiguous"
    assert decision.target is None
    assert decision.authoritative is False
    assert decision.arm_gate is False


def test_route_cli_reads_prompt_from_stdin(catalog: dict, tmp_path: Path) -> None:
    catalog_path = tmp_path / "route-catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "sage_runtime_cli.py"),
            "route",
            "decide",
            "--catalog",
            str(catalog_path),
            "--project",
            str(tmp_path),
        ],
        input="/map this repository",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["target"] == "/map"
