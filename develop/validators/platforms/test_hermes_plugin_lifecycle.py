#!/usr/bin/env python3
"""Behavioral contract for the installed, profile-bound Hermes plugin.

The subject is always the output of ``build_plugin.py --target hermes``.  The
source checkout is not imported as the plugin, because copied source bytes are
not evidence that Hermes can load the package users receive.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap
import uuid
from typing import Dict, Optional, Tuple

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
BUILD_PLUGIN = REPO_ROOT / "runtime" / "tools" / "build_plugin.py"
PROFILE_BINDING_SOURCE = (
    REPO_ROOT
    / "runtime"
    / "platforms"
    / "community"
    / "hermes"
    / "setup"
    / "profile_binding.py"
)
SCOPE_JUDGE_SOURCE = REPO_ROOT / "runtime" / "tools" / "scope_judge.py"
SUPPORTED_SKILLS = {
    "sage",
    "sage-analyst",
    "sage-architect",
    "sage-autoresearch",
    "sage-build",
    "sage-checkpoints",
    "sage-classifier",
    "sage-constitution",
    "sage-continue",
    "sage-debugger",
    "sage-decisions",
    "sage-developer",
    "sage-fix",
    "sage-gates",
    "sage-learn",
    "sage-reflect",
    "sage-review",
    "sage-reviewer",
    "sage-routing",
    "sage-tiers",
    "sage-using-memory",
}
EXPECTED_HOOKS = {
    "on_session_start",
    "pre_llm_call",
    "transform_tool_result",
    "pre_verify",
}
EXPECTED_COMMANDS = {
    "sage",
    "sage-build",
    "sage-fix",
    "sage-architect",
    "sage-analyze",
    "sage-learn",
    "sage-map",
    "sage-qa",
    "sage-reflect",
    "sage-research",
    "sage-review",
    "sage-status",
    "sage-design",
    "sage-design-review",
    "sage-continue",
    "sage-autoresearch",
}
EXPECTED_TOOLS = {
    "sage_run_gates",
    "sage_spec_check",
    "sage_hallucination_check",
    "sage_verify",
    "sage_visual_gate",
    "sage_memory_set_project",
    "sage_memory_store",
    "sage_memory_search",
}


class RecordingContext:
    """Small faithful surface of the public Hermes PluginContext API."""

    def __init__(self) -> None:
        self.hooks = {}
        self.skills = {}
        self.tools = []
        self.commands = []

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_skill(self, name, path, description="", frontmatter=None):
        path = pathlib.Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        self.skills[name] = {
            "path": path,
            "description": description,
            "frontmatter": dict(frontmatter or {}),
        }

    def register_tool(self, *args, **kwargs):
        self.tools.append((args, kwargs))

    def register_command(self, *args, **kwargs):
        self.commands.append((args, kwargs))


def _binding_map(collection: pathlib.Path, profile_id: str) -> dict[str, str]:
    profile = collection / "profiles" / profile_id
    workspace = profile / "workspace"
    state = workspace / ".sage"
    memory = workspace / ".sage-memory"
    return {
        "profile_id": profile_id,
        "collection_root": os.fspath(collection),
        "profile_root": os.fspath(profile),
        "workspace_root": os.fspath(workspace),
        "config_path": os.fspath(profile / "config.yaml"),
        "hooks_root": os.fspath(profile / "hooks"),
        "plugin_root": os.fspath(profile / "plugins" / "sage"),
        "skills_root": os.fspath(profile / "skills"),
        "state_root": os.fspath(state),
        "memory_root": os.fspath(memory),
        "memory_db_path": os.fspath(memory / "memory.db"),
        "receipt_path": os.fspath(state / "receipts" / "install.json"),
        "runs_root": os.fspath(state / "receipts" / "runs"),
        "pack_lock_path": os.fspath(state / "packs.lock"),
    }


def _config_binding(binding: dict[str, str]) -> dict[str, str]:
    return {
        key: binding[key]
        for key in (
            "profile_id",
            "workspace_root",
            "state_root",
            "memory_root",
            "receipt_path",
        )
    }


def _write_profile_authorities(binding: dict[str, str]) -> None:
    config = pathlib.Path(binding["config_path"])
    config.write_text(
        json.dumps(
            {
                "plugins": {"enabled": ["sage"]},
                "sage_profile_binding": _config_binding(binding),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    receipt = pathlib.Path(binding["receipt_path"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps({"schema_version": 1, "binding": binding}, indent=2),
        encoding="utf-8",
    )


def _materialize_runtime(binding: dict[str, str], label: str) -> None:
    workspace = pathlib.Path(binding["workspace_root"])
    runtime = workspace / "sage"
    skills_root = runtime / "skills"
    skills_root.mkdir(parents=True)
    for name in sorted(SUPPORTED_SKILLS):
        source = REPO_ROOT / "skills" / name / "SKILL.md"
        target = skills_root / name / "SKILL.md"
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
    tools = runtime / "runtime" / "tools"
    tools.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "core" / "gates", runtime / "core" / "gates")
    shutil.copy2(SCOPE_JUDGE_SOURCE, tools / "scope_judge.py")
    for name in ("manifest.py", "skill_manager.py", "sage_flags.py", "memory_sync.py"):
        shutil.copy2(REPO_ROOT / "runtime" / "tools" / name, tools / name)
    (runtime / "VERSION").write_text(
        (REPO_ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (workspace / ".hermes.md").write_text(
        "# Bound instructions\n\nPROFILE-CONTEXT-%s\n" % label,
        encoding="utf-8",
    )
    (workspace / ".sage" / "work").mkdir(parents=True, exist_ok=True)


def _install_profile(
    artifact: pathlib.Path,
    collection: pathlib.Path,
    profile_id: str,
    label: str,
) -> dict[str, str]:
    profile = collection / "profiles" / profile_id
    workspace = profile / "workspace"
    workspace.mkdir(parents=True)
    (profile / "hooks").mkdir()
    (profile / "skills").mkdir()
    (profile / "plugins").mkdir()
    shutil.copytree(artifact / "plugins" / "sage", profile / "plugins" / "sage")
    binding = _binding_map(collection, profile_id)
    _materialize_runtime(binding, label)
    _write_profile_authorities(binding)
    return binding


def _load_installed_plugin(plugin_root: pathlib.Path):
    module_name = "task15_sage_%s" % uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(
        module_name,
        plugin_root / "__init__.py",
        submodule_search_locations=[os.fspath(plugin_root)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


@pytest.fixture()
def hermes_artifact(tmp_path: pathlib.Path) -> pathlib.Path:
    output = tmp_path / "artifact"
    subprocess.run(
        [
            sys.executable,
            os.fspath(BUILD_PLUGIN),
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
def installed_profiles(
    tmp_path: pathlib.Path, hermes_artifact: pathlib.Path
) -> tuple[dict[str, str], dict[str, str]]:
    collection = (tmp_path / "hermes").resolve()
    (collection / "profiles").mkdir(parents=True)
    alpha = _install_profile(hermes_artifact, collection, "alpha", "ALPHA")
    beta = _install_profile(hermes_artifact, collection, "beta", "BETA")
    (collection / ".hermes.md").write_text("GLOBAL-CONTEXT\n", encoding="utf-8")
    return alpha, beta


def _register_alpha(
    monkeypatch: pytest.MonkeyPatch,
    alpha: dict[str, str],
    *,
    cwd: pathlib.Path | None = None,
):
    monkeypatch.setenv("HERMES_HOME", alpha["profile_root"])
    monkeypatch.delenv("HERMES_ENABLE_PROJECT_PLUGINS", raising=False)
    monkeypatch.chdir(cwd or pathlib.Path(alpha["workspace_root"]))
    module = _load_installed_plugin(pathlib.Path(alpha["plugin_root"]))
    ctx = RecordingContext()
    module.register(ctx)
    return module, ctx


def test_artifact_contains_a_native_manifest_and_packaged_authority(
    hermes_artifact: pathlib.Path,
) -> None:
    plugin = hermes_artifact / "plugins" / "sage"
    assert (plugin / "plugin.yaml").is_file()
    assert (plugin / "profile_binding.py").read_bytes() == PROFILE_BINDING_SOURCE.read_bytes()


def test_plugin_registers_only_supported_lifecycle_and_bound_runtime_skills(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, beta = installed_profiles
    module, ctx = _register_alpha(
        monkeypatch,
        alpha,
        cwd=pathlib.Path(beta["workspace_root"]),
    )

    assert set(ctx.hooks) == EXPECTED_HOOKS
    assert "pre_tool_call" not in ctx.hooks
    assert "post_tool_call" not in ctx.hooks
    assert set(ctx.skills) == SUPPORTED_SKILLS
    assert ctx.skills["sage-debugger"]["path"] == (
        pathlib.Path(alpha["workspace_root"])
        / "sage"
        / "skills"
        / "sage-debugger"
        / "SKILL.md"
    )
    assert all(
        str(item["path"]).startswith(alpha["workspace_root"])
        for item in ctx.skills.values()
    )
    assert {kwargs["name"] for _args, kwargs in ctx.tools} == EXPECTED_TOOLS
    assert {kwargs["name"] for _args, kwargs in ctx.commands} == EXPECTED_COMMANDS

    inventory = module.runtime_inventory()
    assert inventory["hooks"]["registered"] == sorted(EXPECTED_HOOKS)
    assert inventory["tools"]["registered"] == sorted(EXPECTED_TOOLS)
    assert inventory["commands"]["registered"] == sorted(EXPECTED_COMMANDS)
    assert inventory["memory"]["adapter_registered"] is True
    assert inventory["memory"]["database"] == alpha["memory_db_path"]
    assert inventory["delegation"]["delegate_task_registered"] is False
    assert inventory["delegation"]["kanban_registered"] is False


def _tool_handlers(ctx: RecordingContext):
    return {kwargs["name"]: kwargs["handler"] for _args, kwargs in ctx.tools}


def _command_handlers(ctx: RecordingContext):
    return {kwargs["name"]: kwargs["handler"] for _args, kwargs in ctx.commands}


def test_commands_are_collision_free_bound_handlers_with_exact_inventory(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, beta = installed_profiles
    module, ctx = _register_alpha(
        monkeypatch,
        alpha,
        cwd=pathlib.Path(beta["workspace_root"]),
    )
    handlers = _command_handlers(ctx)

    assert set(handlers) == EXPECTED_COMMANDS
    assert all(
        any(
            isinstance(cell.cell_contents, module.PluginBinding)
            for cell in (handler.__closure__ or ())
        )
        for handler in handlers.values()
    )
    rendered = handlers["sage-build"]("implement alpha-only")
    assert "implement alpha-only" in rendered
    assert "PROFILE-CONTEXT-BETA" not in rendered
    assert beta["workspace_root"] not in rendered


def test_gate_tools_use_only_frozen_workspace_and_reject_authority_overrides(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, beta = installed_profiles
    module, ctx = _register_alpha(
        monkeypatch,
        alpha,
        cwd=pathlib.Path(beta["workspace_root"]),
    )
    calls = []

    class Completed:
        returncode = 0
        stdout = "gate-pass"
        stderr = ""

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Completed()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    handlers = _tool_handlers(ctx)
    assert all(
        any(
            isinstance(cell.cell_contents, module.PluginBinding)
            for cell in (handler.__closure__ or ())
        )
        for handler in handlers.values()
    )
    verify = json.loads(handlers["sage_verify"]({}))
    assert verify["ok"] is True
    assert calls[-1][1]["cwd"] == alpha["workspace_root"]
    assert calls[-1][0][1].endswith("sage-verify.sh")
    assert calls[-1][0][-1] == alpha["workspace_root"]

    before = len(calls)
    escaped = json.loads(
        handlers["sage_hallucination_check"]({"target": beta["workspace_root"]})
    )
    assert escaped["ok"] is False
    assert "bound workspace" in escaped["error"]
    assert len(calls) == before

    overridden = json.loads(
        handlers["sage_verify"]({"cwd": beta["workspace_root"]})
    )
    assert overridden["ok"] is False
    assert "override" in overridden["error"]
    assert len(calls) == before


def test_memory_tools_are_exact_workspace_database_and_project_only(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, beta = installed_profiles
    module, ctx = _register_alpha(
        monkeypatch,
        alpha,
        cwd=pathlib.Path(beta["workspace_root"]),
    )
    handlers = _tool_handlers(ctx)

    selected = json.loads(handlers["sage_memory_set_project"]({}))
    assert selected["ok"] is True
    assert selected["database"] == alpha["memory_db_path"]
    stored = json.loads(
        handlers["sage_memory_store"](
            {
                "title": "Alpha command authority",
                "content": "alpha-only-memory-sentinel",
                "tags": ["hermes", "binding"],
                "scope": "project",
            }
        )
    )
    assert stored["ok"] is True
    found = json.loads(
        handlers["sage_memory_search"](
            {"query": "alpha-only-memory-sentinel", "limit": 5}
        )
    )
    assert found["ok"] is True
    assert [row["content"] for row in found["results"]] == [
        "alpha-only-memory-sentinel"
    ]
    assert all(row["scope"] == "project" for row in found["results"])
    assert pathlib.Path(alpha["memory_db_path"]).is_file()
    assert not pathlib.Path(beta["memory_db_path"]).exists()

    escaped = json.loads(
        handlers["sage_memory_search"](
            {"query": "sentinel", "project_root": beta["workspace_root"]}
        )
    )
    assert escaped["ok"] is False
    assert "override" in escaped["error"]


def test_session_start_initializes_only_and_first_turn_context_is_profile_bound(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, beta = installed_profiles
    module, ctx = _register_alpha(
        monkeypatch,
        alpha,
        cwd=pathlib.Path(beta["workspace_root"]),
    )

    assert ctx.hooks["on_session_start"](
        session_id="session-a", platform="gateway", model="test"
    ) is None
    first = ctx.hooks["pre_llm_call"](
        session_id="session-a",
        platform="gateway",
        is_first_turn=True,
        user_message="hello",
        conversation_history=[],
    )
    assert set(first) == {"context"}
    assert "PROFILE-CONTEXT-ALPHA" in first["context"]
    assert "PROFILE-CONTEXT-BETA" not in first["context"]
    assert "GLOBAL-CONTEXT" not in first["context"]
    assert beta["workspace_root"] not in first["context"]
    assert ctx.hooks["pre_llm_call"](
        session_id="session-a",
        platform="gateway",
        is_first_turn=False,
        user_message="again",
        conversation_history=[{"role": "user", "content": "hello"}],
    ) is None
    # A duplicate host first-turn signal cannot inject twice in one session.
    assert ctx.hooks["pre_llm_call"](
        session_id="session-a", platform="cli", is_first_turn=True
    ) is None
    assert module.binding_snapshot()["workspace_root"] == alpha["workspace_root"]


def test_transform_tool_result_delivers_one_bound_scope_correction(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, beta = installed_profiles
    alpha_workspace = pathlib.Path(alpha["workspace_root"])
    beta_workspace = pathlib.Path(beta["workspace_root"])
    (alpha_workspace / ".sage" / "config.yaml").write_text(
        "scope_judge: true\n", encoding="utf-8"
    )
    alpha_cycle = alpha_workspace / ".sage" / "work" / "alpha-cycle"
    beta_cycle = beta_workspace / ".sage" / "work" / "beta-cycle"
    alpha_cycle.mkdir()
    beta_cycle.mkdir()
    manifest = "---\nstatus: in-progress\ngate_state: building\n---\n"
    (alpha_cycle / "manifest.md").write_text(manifest, encoding="utf-8")
    (beta_cycle / "manifest.md").write_text(manifest, encoding="utf-8")
    alpha_pending = alpha_cycle / ".scope-correction.json"
    beta_pending = beta_cycle / ".scope-correction.json"
    alpha_pending.write_text(
        json.dumps(
            {
                "task": "T15",
                "task_label": "T15 plugin lifecycle",
                "reason": "ALPHA-CORRECTION",
            }
        ),
        encoding="utf-8",
    )
    beta_pending.write_text(
        json.dumps(
            {"task": "T99", "task_label": "T99 sibling", "reason": "BETA-CORRECTION"}
        ),
        encoding="utf-8",
    )

    _, ctx = _register_alpha(monkeypatch, alpha, cwd=beta_workspace)
    transformed = ctx.hooks["transform_tool_result"](
        tool_name="write_file",
        args={"path": "owned.py"},
        result='{"ok": true}',
        session_id="session-a",
        tool_call_id="call-1",
    )
    assert transformed.startswith('{"ok": true}')
    assert "ALPHA-CORRECTION" in transformed
    assert "BETA-CORRECTION" not in transformed
    assert not alpha_pending.exists()
    assert beta_pending.exists()
    assert ctx.hooks["transform_tool_result"](
        tool_name="write_file",
        args={"path": "owned.py"},
        result="second-result",
        session_id="session-a",
        tool_call_id="call-2",
    ) is None


@pytest.mark.parametrize(
    "failure",
    [
        "missing-receipt",
        "mismatched-receipt",
        "missing-config",
        "missing-config-binding",
        "mismatched-config-binding",
        "wrong-active-home",
    ],
)
def test_missing_or_mismatched_authority_fails_registration_visibly(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
    failure: str,
) -> None:
    alpha, beta = installed_profiles
    receipt = pathlib.Path(alpha["receipt_path"])
    config = pathlib.Path(alpha["config_path"])
    if failure == "missing-receipt":
        receipt.unlink()
    elif failure == "mismatched-receipt":
        receipt.write_text(
            json.dumps({"schema_version": 1, "binding": beta}), encoding="utf-8"
        )
    elif failure == "missing-config":
        config.unlink()
    elif failure == "missing-config-binding":
        config.write_text(
            json.dumps({"plugins": {"enabled": ["sage"]}}), encoding="utf-8"
        )
    elif failure == "mismatched-config-binding":
        config.write_text(
            json.dumps(
                {
                    "plugins": {"enabled": ["sage"]},
                    "sage_profile_binding": _config_binding(beta),
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setenv(
        "HERMES_HOME",
        beta["profile_root"] if failure == "wrong-active-home" else alpha["profile_root"],
    )
    monkeypatch.chdir(alpha["workspace_root"])
    module = _load_installed_plugin(pathlib.Path(alpha["plugin_root"]))
    ctx = RecordingContext()
    with pytest.raises(
        module.PluginAuthorityError,
        match="authority|receipt|binding|config|HERMES_HOME|profile",
    ):
        module.register(ctx)
    assert ctx.hooks == {}
    assert ctx.skills == {}


def test_sibling_cwd_project_plugin_is_never_a_registration_authority(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, beta = installed_profiles
    sibling = pathlib.Path(beta["workspace_root"]) / ".hermes" / "plugins" / "sage"
    sibling.mkdir(parents=True)
    (sibling / "plugin.yaml").write_text("name: sage\n", encoding="utf-8")

    monkeypatch.setenv("HERMES_HOME", alpha["profile_root"])
    monkeypatch.setenv("HERMES_ENABLE_PROJECT_PLUGINS", "1")
    monkeypatch.chdir(beta["workspace_root"])
    module = _load_installed_plugin(pathlib.Path(alpha["plugin_root"]))
    ctx = RecordingContext()
    module.register(ctx)
    assert {kwargs["name"] for _args, kwargs in ctx.commands} == EXPECTED_COMMANDS


def test_enabled_project_plugin_collision_is_rejected_before_registration(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    alpha, _ = installed_profiles
    workspace = pathlib.Path(alpha["workspace_root"])
    collision = workspace / ".hermes" / "plugins" / "sage"
    collision.mkdir(parents=True)
    (collision / "plugin.yaml").write_text("name: sage\n", encoding="utf-8")

    monkeypatch.setenv("HERMES_HOME", alpha["profile_root"])
    monkeypatch.setenv("HERMES_ENABLE_PROJECT_PLUGINS", "1")
    monkeypatch.chdir(workspace)
    module = _load_installed_plugin(pathlib.Path(alpha["plugin_root"]))
    ctx = RecordingContext()
    with pytest.raises(module.PluginAuthorityError, match="project plugin collision"):
        module.register(ctx)
    assert ctx.hooks == {}
    assert ctx.skills == {}


def _find_hermes_host() -> Optional[pathlib.Path]:
    override = os.environ.get("SAGE_HERMES_HOST_SOURCE")
    if override:
        candidate = pathlib.Path(override)
        return candidate if (candidate / "hermes_cli" / "plugins.py").is_file() else None
    candidate = REPO_ROOT.parents[1] / "hermes" / "hermes-agent"
    return candidate if (candidate / "hermes_cli" / "plugins.py").is_file() else None


def test_current_hermes_loader_executes_built_plugin_and_discovers_debugger(
    monkeypatch: pytest.MonkeyPatch,
    installed_profiles: tuple[dict[str, str], dict[str, str]],
) -> None:
    host = _find_hermes_host()
    if host is None:
        pytest.skip("current Hermes host source is not available")
    alpha, _ = installed_profiles
    workspace = pathlib.Path(alpha["workspace_root"])
    (workspace / ".sage" / "config.yaml").write_text(
        "scope_judge: true\n", encoding="utf-8"
    )
    cycle = workspace / ".sage" / "work" / "host-cycle"
    cycle.mkdir()
    (cycle / "manifest.md").write_text(
        "---\nstatus: in-progress\ngate_state: building\n---\n",
        encoding="utf-8",
    )
    (cycle / ".scope-correction.json").write_text(
        json.dumps(
            {
                "task": "T15",
                "task_label": "T15 host lifecycle",
                "reason": "HOST-CORRECTION",
            }
        ),
        encoding="utf-8",
    )
    script = textwrap.dedent(
        """
        import json
        from hermes_cli import plugins
        plugins._plugin_manager = plugins.PluginManager()
        manager = plugins._plugin_manager
        manager.discover_and_load()
        plugin = next(item for item in manager.list_plugins() if item["key"] == "sage")
        plugins._plugin_manager = manager
        from tools.skills_tool import skill_view
        debugger = json.loads(skill_view("sage:sage-debugger", preprocess=False))
        manager.invoke_hook("on_session_start", session_id="host-session", platform="gateway")
        first = manager.invoke_hook(
            "pre_llm_call",
            session_id="host-session",
            task_id="host-task",
            user_message="hello",
            conversation_history=[],
            is_first_turn=True,
            model="test",
            platform="gateway",
        )
        from tools.registry import registry
        import model_tools
        registry.dispatch = lambda name, args, **kwargs: "HOST-ORIGINAL"
        model_tools._READ_SEARCH_TOOLS = frozenset()
        transformed = model_tools.handle_function_call(
            "task15_dummy",
            {},
            task_id="host-task",
            session_id="host-session",
            tool_call_id="host-call",
            skip_pre_tool_call_hook=True,
        )
        print(json.dumps({
            "plugin": plugin,
            "hooks": sorted(name for name in plugins.VALID_HOOKS if manager.has_hook(name)),
            "skills": manager.list_plugin_skills("sage"),
            "commands": sorted(plugins.get_plugin_commands()),
            "tools": sorted(registry.get_tool_names_for_toolset("sage")),
            "debugger": debugger,
            "first": first,
            "transformed": transformed,
        }))
        """
    )
    env = os.environ.copy()
    env["HERMES_HOME"] = alpha["profile_root"]
    env["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
    env["PYTHONPATH"] = os.fspath(host)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=alpha["workspace_root"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["plugin"]["enabled"] is True
    assert result["plugin"]["error"] is None
    assert result["plugin"]["tools"] == len(EXPECTED_TOOLS)
    assert result["plugin"]["commands"] == len(EXPECTED_COMMANDS)
    assert set(result["hooks"]) >= EXPECTED_HOOKS
    assert set(result["skills"]) == SUPPORTED_SKILLS
    assert set(result["commands"]) == EXPECTED_COMMANDS
    assert set(result["tools"]) == EXPECTED_TOOLS
    assert result["debugger"]["success"] is True
    assert "Methodical investigator" in result["debugger"]["content"]
    assert result["first"] and "PROFILE-CONTEXT-ALPHA" in result["first"][0]["context"]
    assert result["transformed"].startswith("HOST-ORIGINAL")
    assert "HOST-CORRECTION" in result["transformed"]


def test_manifest_is_honest_about_events_version_and_capabilities(
    hermes_artifact: pathlib.Path,
) -> None:
    import yaml

    manifest = yaml.safe_load(
        (hermes_artifact / "plugins" / "sage" / "plugin.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["name"] == "sage"
    assert manifest["version"] == (REPO_ROOT / "VERSION").read_text().strip()
    assert set(manifest["provides_hooks"]) == EXPECTED_HOOKS
    assert set(manifest["provides_tools"]) == EXPECTED_TOOLS
    assert manifest["provides_slash_commands"] is True
    serialized = json.dumps(manifest).casefold()
    assert "delegate_task" not in serialized
    assert "kanban" not in serialized
