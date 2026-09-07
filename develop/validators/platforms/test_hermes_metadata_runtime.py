#!/usr/bin/env python3
"""Behavioral contract for Task 16: goal/subagent/autonomous/quality metadata
at the plugin's runtime consumers.

The installed plugin must consume the BOUND workspace's active-cycle metadata
— never a sibling profile's, never collection-global state — and must report
unsupported autonomous execution honestly instead of treating a persisted
flag as proof the capability exists. The Kanban worker bridge is a separate
initiative and must never be claimed by this surface.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import subprocess
import sys

import pytest

import test_hermes_plugin_lifecycle as harness


REPO_ROOT = harness.REPO_ROOT

CONTRACT_PATH = pathlib.PurePath(
    "runtime", "platforms", "community", "hermes", "platform.yaml"
)
README_PATH = REPO_ROOT / "runtime" / "platforms" / "community" / "hermes" / "README.md"
PLATFORM_PATH = REPO_ROOT / CONTRACT_PATH
STATUS_PATH = REPO_ROOT / "runtime" / "platforms" / "community" / "hermes" / "STATUS.md"
TOPOLOGY_PATH = REPO_ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup" / "topology.json"
DOCTOR_PATH = REPO_ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup" / "doctor.py"


def _literal_assignment(path: pathlib.Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=os.fspath(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing literal assignment {name} in {path}")


def test_public_install_metadata_names_the_profile_bound_artifacts() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    contract = PLATFORM_PATH.read_text(encoding="utf-8")

    assert "- `.hermes.md` — the workspace instructions Hermes reads" in readme
    assert "- `<profile>/config.yaml` — registers the profile shell hooks" in readme
    for command in ("init", "update", "doctor", "uninstall"):
        assert (
            f"sage {command} --platform hermes --hermes-home <collection> "
            "--hermes-profile <name>"
        ) in readme
    assert (
        "sage recover hermes-profile <operation-id> --platform hermes "
        "--hermes-home <collection> --hermes-profile <name>"
    ) in readme
    assert (
        "sage migrate hermes-profile --platform hermes --hermes-home <collection> "
        "--hermes-profile <name>"
    ) in readme
    assert (
        "sage migrate hermes-profile --rollback --platform hermes "
        "--hermes-home <collection> --hermes-profile <name>"
    ) in readme
    assert f"{len(harness.SUPPORTED_SKILLS)} bound runtime skills" in readme
    assert f"{len(harness.EXPECTED_COMMANDS)} slash commands" in readme
    assert f"{len(harness.EXPECTED_TOOLS)} Sage tools" in readme
    assert "7 fail-closed blockers and 4 observers" in readme
    assert "SAGE_HERMES_COMMAND" in readme
    assert "hermes --profile <name> hooks activation-proof" in readme
    assert "cp -r . ~/.hermes" not in readme
    assert '`pre_tool_call` returns' not in readme
    assert '`post_tool_call` writes' not in readme
    assert "`SOUL.md` — the instructions file" not in readme
    assert "instructions: .hermes.md" in contract
    assert "hooks-config: <profile>/config.yaml" in contract
    for key, path in {
        "activation": "setup/activation.py",
        "doctor": "setup/doctor.py",
        "doctor-probe": "setup/doctor_probe.py",
        "hook-config": "setup/hook_config.py",
        "profile-binding": "setup/profile_binding.py",
        "profile-installer": "setup/profile_installer.py",
        "profile-migration": "setup/profile_migration.py",
        "receipts": "setup/receipts.py",
        "topology": "setup/topology.json",
        "workspace-layout": "setup/workspace_layout.py",
    }.items():
        assert f"{key}: {path}" in contract
    assert 'host-proof-command: "hermes --profile <name> hooks activation-proof' in contract
    assert "instructions: SOUL.md" not in contract


def test_status_topology_and_doctor_vocabulary_match_runtime() -> None:
    status = STATUS_PATH.read_text(encoding="utf-8")
    readme = README_PATH.read_text(encoding="utf-8")
    topology = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
    doctor_states = tuple(_literal_assignment(DOCTOR_PATH, "_STATE_RANK"))

    for hook in harness.EXPECTED_HOOKS:
        assert f"`{hook}`" in status
    assert "registers `pre_tool_call`" not in status
    assert "registers `post_tool_call`" not in status
    assert "hooks/sage-session/" not in status

    topology_hooks = set(topology["plugin_callbacks"]["required"])
    topology_hooks.update(topology["plugin_callbacks"]["optional"])
    assert topology_hooks == harness.EXPECTED_HOOKS
    for record in [*topology["subsystems"], *topology["hooks"]]:
        assert record["support_status"] == "verified", record.get("id")
        acceptance = record.get("acceptance_test")
        assert acceptance, record.get("id")
        assert (REPO_ROOT / acceptance).exists(), acceptance

    documented_states = ", ".join(f"`{state}`" for state in doctor_states)
    assert f"Doctor states: {documented_states}." in " ".join(readme.split())
    assert "executed, blocked, context-delivered" not in readme


@pytest.fixture()
def artifact(tmp_path: pathlib.Path) -> pathlib.Path:
    output = tmp_path / "artifact"
    subprocess.run(
        [
            sys.executable,
            os.fspath(harness.BUILD_PLUGIN),
            "--target",
            "hermes",
            "--out",
            os.fspath(output),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return output


@pytest.fixture()
def profiles(tmp_path: pathlib.Path, artifact: pathlib.Path):
    collection = (tmp_path / "hermes").resolve()
    (collection / "profiles").mkdir(parents=True)
    alpha = harness._install_profile(artifact, collection, "alpha", "ALPHA")
    beta = harness._install_profile(artifact, collection, "beta", "BETA")
    return collection, alpha, beta


def _write_cycle(
    binding: dict[str, str],
    cycle: str,
    *,
    flags: dict[str, bool],
    goal: str,
    status: str = "in-progress",
) -> None:
    work = pathlib.Path(binding["workspace_root"]) / ".sage" / "work" / cycle
    work.mkdir(parents=True, exist_ok=True)
    flag_lines = "\n".join("  %s: %s" % (k, str(v).lower()) for k, v in flags.items())
    (work / "manifest.md").write_text(
        "---\n"
        'cycle_id: "%s"\n'
        "workflow: build\n"
        "phase: implement\n"
        "status: %s\n"
        "gate_state: building\n"
        "execution_mode: subagent\n"
        "flags:\n"
        "%s\n"
        "goal: %s\n"
        "---\n\n# Cycle %s\n" % (cycle, status, flag_lines, goal, cycle),
        encoding="utf-8",
    )


def _write_platform_contract(binding: dict[str, str], *, subagent_dispatch) -> None:
    workspace = pathlib.Path(binding["workspace_root"])
    target = workspace / "sage" / CONTRACT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    value = (
        "attested"
        if subagent_dispatch == "attested"
        else str(subagent_dispatch).lower()
    )
    target.write_text(
        "---\nname: hermes\ncontract-version: 2\ncapabilities:\n"
        "  subagent-dispatch: %s\n" % value,
        encoding="utf-8",
    )


def _register(monkeypatch: pytest.MonkeyPatch, binding: dict[str, str]):
    return harness._register_alpha(monkeypatch, binding)


def test_cycle_metadata_consumes_bound_workspace_manifest(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    _collection, alpha, _beta = profiles
    _write_cycle(
        alpha,
        "20260810-alpha-cycle",
        flags={"quality_locked": True, "autonomous": True, "subagents": False},
        goal="Ship the alpha thing",
    )
    module, _ctx = _register(monkeypatch, alpha)

    metadata = module.cycle_metadata()
    assert metadata["cycle"] == "20260810-alpha-cycle"
    assert metadata["goal"] == "Ship the alpha thing"
    assert metadata["quality_locked"] is True
    assert metadata["autonomous"] is True
    assert metadata["subagents"] is False
    assert metadata["execution_mode"] == "inline"
    assert metadata["degraded"] is False
    assert metadata["announcement"] is None


def test_cycle_metadata_ignores_sibling_and_global_state(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    collection, alpha, beta = profiles
    _write_cycle(
        alpha,
        "20260810-alpha-cycle",
        flags={"quality_locked": True, "autonomous": False, "subagents": False},
        goal="ALPHA GOAL",
    )
    _write_cycle(
        beta,
        "20260810-beta-cycle",
        flags={"quality_locked": False, "autonomous": True, "subagents": True},
        goal="BETA GOAL",
    )
    global_work = collection / ".sage" / "work" / "20260810-global-cycle"
    global_work.mkdir(parents=True)
    (global_work / "manifest.md").write_text(
        "---\nstatus: in-progress\ngoal: GLOBAL GOAL\n---\n", encoding="utf-8"
    )
    module, _ctx = _register(monkeypatch, alpha)

    metadata = module.cycle_metadata()
    assert metadata["cycle"] == "20260810-alpha-cycle"
    assert metadata["goal"] == "ALPHA GOAL"
    assert metadata["quality_locked"] is True
    assert metadata["autonomous"] is False
    for value in metadata.values():
        assert "BETA" not in str(value)
        assert "GLOBAL" not in str(value)


def test_subagents_requested_without_contract_degrades_loudly(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    _collection, alpha, _beta = profiles
    _write_cycle(
        alpha,
        "20260810-alpha-cycle",
        flags={"quality_locked": True, "autonomous": True, "subagents": True},
        goal="Needs subagents",
    )
    module, _ctx = _register(monkeypatch, alpha)

    metadata = module.cycle_metadata()
    assert metadata["subagents"] is True
    assert metadata["execution_mode"] == "inline (subagents-unavailable)"
    assert metadata["degraded"] is True
    assert metadata["announcement"] is not None
    assert "Subagent execution is unavailable" in metadata["announcement"]


def test_subagents_honored_when_contract_attests_dispatch(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    _collection, alpha, _beta = profiles
    _write_platform_contract(alpha, subagent_dispatch="attested")
    _write_cycle(
        alpha,
        "20260810-alpha-cycle",
        flags={"quality_locked": False, "autonomous": True, "subagents": True},
        goal="Subagent run",
    )
    module, _ctx = _register(monkeypatch, alpha)

    metadata = module.cycle_metadata()
    assert metadata["execution_mode"] == "subagent"
    assert metadata["degraded"] is False
    assert metadata["announcement"] is None


def test_pre_verify_surfaces_quality_locked_policy(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    _collection, alpha, beta = profiles
    _write_cycle(
        alpha,
        "20260810-alpha-cycle",
        flags={"quality_locked": True, "autonomous": True, "subagents": False},
        goal="Locked work",
    )
    module, ctx = _register(monkeypatch, alpha)
    verdict = ctx.hooks["pre_verify"]()
    assert verdict is not None
    assert "quality_locked" in str(verdict)

    _write_cycle(
        beta,
        "20260810-beta-cycle",
        flags={"quality_locked": False, "autonomous": False, "subagents": False},
        goal="Unlocked work",
    )
    beta_module, beta_ctx = harness._register_alpha(monkeypatch, beta)
    assert beta_module is not None
    assert beta_ctx.hooks["pre_verify"]() is None


def test_pre_verify_appends_degradation_announcement(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    _collection, alpha, _beta = profiles
    _write_cycle(
        alpha,
        "20260810-alpha-cycle",
        flags={"quality_locked": True, "autonomous": True, "subagents": True},
        goal="Locked and degraded",
    )
    module, ctx = _register(monkeypatch, alpha)
    verdict = ctx.hooks["pre_verify"]()
    assert verdict is not None
    assert "quality_locked" in str(verdict)
    assert "Subagent execution is unavailable" in str(verdict)


def test_no_active_cycle_reports_empty_metadata(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    _collection, alpha, _beta = profiles
    module, ctx = _register(monkeypatch, alpha)

    metadata = module.cycle_metadata()
    assert metadata["cycle"] is None
    assert metadata["goal"] is None
    assert metadata["quality_locked"] is False
    assert metadata["autonomous"] is False
    assert metadata["subagents"] is False
    assert metadata["execution_mode"] == "inline"
    assert metadata["degraded"] is False
    assert ctx.hooks["pre_verify"]() is None


def test_runtime_inventory_never_claims_kanban_bridge(
    monkeypatch: pytest.MonkeyPatch, profiles,
) -> None:
    _collection, alpha, _beta = profiles
    module, _ctx = _register(monkeypatch, alpha)

    inventory = module.runtime_inventory()
    assert inventory["delegation"]["kanban_registered"] is False
    quality = inventory["quality"]
    assert quality.get("kanban_worker_bridge") is not True
    assert "implementation_task" not in quality
