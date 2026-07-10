from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class _Context:
    def __init__(self) -> None:
        self.commands: dict[str, tuple] = {}
        self.skills: dict[str, object] = {}
        self.tools: dict[str, object] = {}

    def register_command(self, name, handler=None, description=None) -> None:
        self.commands[name] = (handler, description)

    def register_skill(self, name, **kwargs) -> None:
        self.skills[name] = kwargs

    def register_tool(self, name, **kwargs) -> None:
        self.tools[name] = kwargs


def test_multi_agent_setup_installs_hermes_build_x_surface(tmp_path: Path) -> None:
    project = tmp_path / "project"
    hermes_home = tmp_path / "hermes-home"
    (project / ".sage").mkdir(parents=True)
    (project / ".sage" / "config.yaml").write_text(
        "platforms:\n  - hermes\n", encoding="utf-8"
    )
    (hermes_home / "plugins" / "sage").mkdir(parents=True)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "multi_agent_setup.py"),
            "install",
            str(ROOT),
            str(project),
            "--yes",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (project / ".sage" / "agents.toml").is_file()
    assert (project / ".sage" / "scripts" / "run-role.sh").is_file()
    assert not (project / ".claude").exists()
    plugin = hermes_home / "plugins" / "sage"
    for name in ("build-x", "review-spec", "review-plan", "implement", "review-code"):
        assert (plugin / "skills" / name / "SKILL.md").is_file()

    spec = importlib.util.spec_from_file_location("sage_hermes_multi_agent", plugin / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    context = _Context()
    module.register(context)
    body = context.commands["build-x"][0]("--kanban ship feature")
    assert "Hermes execution topology" in body
    assert "kanban-orchestrator" in body
    assert "kanban-worker" in body
    assert "delegate_task" in body
    assert "HERMES_KANBAN_TASK" in body
    assert "Selected topology: kanban" in body
    assert "**Task:** ship feature" in body

    unflagged = context.commands["build-x"][0]("make a kanban dashboard")
    assert "Selected topology:" not in unflagged

    conflict = context.commands["build-x"][0](
        "--delegate --kanban ship feature"
    )
    assert "Choose exactly one" in conflict
    assert "# /build-x" not in conflict

    removed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "runtime" / "tools" / "multi_agent_setup.py"),
            "remove",
            str(ROOT),
            str(project),
            "--yes",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert removed.returncode == 0, removed.stderr + removed.stdout
    assert not (project / ".sage" / "agents.toml").exists()
    assert list((project / ".sage").glob(".removed-multi-agent-*/.sage/agents.toml"))
    assert not (plugin / "skills" / "build-x").exists()
    assert "multi_agent:" not in (project / ".sage" / "config.yaml").read_text(
        encoding="utf-8"
    )
