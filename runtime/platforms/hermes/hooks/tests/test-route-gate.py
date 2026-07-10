from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.adapter import operation_from_envelope
from sage_runtime.hook_config import (
    HookConfigError,
    install_claude_hooks,
    install_hermes_hooks,
    validate_hook_config,
)


HERMES_ROUTE = ROOT / "runtime/platforms/hermes/hooks/sage-pre-llm.py"
HERMES_GATE = ROOT / "runtime/platforms/hermes/hooks/sage-pre-tool.py"
CLAUDE_ROUTE = ROOT / "runtime/platforms/claude-code/hooks/sage-route-context.py"
CLAUDE_GATE = ROOT / "runtime/platforms/claude-code/hooks/sage-strict-gate.py"


def write_catalog(project: Path) -> None:
    runtime_dir = project / ".sage" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "route-catalog.json").write_text(
        json.dumps(
            {
                "schema": "route-catalog/v1",
                "platform": "test",
                "routes": {
                    "map": {"workflow": "map", "target": "/map", "source": "map"},
                    "build": {
                        "workflow": "build",
                        "target": "/build",
                        "source": "build",
                    },
                },
                "generated_at": "2026-07-10T12:00:00Z",
                "hash": "catalog-sha",
            }
        ),
        encoding="utf-8",
    )


def write_gate_policy(project: Path) -> Path:
    path = project / "gate-modes.yaml"
    path.write_text(
        """strict_runtime:
  ttl_seconds: 0
  lane_roots: []
  scopes:
    full:
      stages:
        pre-write:
          required_artifacts: [approved-plan]
          required_approvals: []
          required_verifications: []
""",
        encoding="utf-8",
    )
    return path


def write_active_state(project: Path, *, strict: bool = False) -> None:
    runtime_dir = project / ".sage" / "runtime"
    state_dir = runtime_dir / "runs" / "run-001"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "schema": "run-state/v1",
        "run_id": "run-001",
        "status": "active",
        "explicit_intent": True,
        "workflow_owner": "sage:build",
        "active_capability": "change.implement",
        "active_provider": "sage:implement",
        "strict": strict,
        "composition_hash": "composition-sha",
        "route_catalog_hash": "catalog-sha",
        "artifacts": {},
        "verification": {},
        "dirty": False,
        "updated_at": "2026-07-10T12:00:00Z",
    }
    (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (runtime_dir / "active-run.json").write_text(
        json.dumps(
            {
                "schema": "active-run/v1",
                "active": True,
                "run_id": "run-001",
                "state_path": "runs/run-001/state.json",
                "bound_at": "2026-07-10T12:00:00Z",
                "updated_at": "2026-07-10T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write_catalog(tmp_path)
    return tmp_path


def adapter_env(project: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_BIN": sys.executable,
            "SAGE_PROJECT": str(project),
            "SAGE_RUNTIME_CLI": str(ROOT / "runtime/tools/sage_runtime_cli.py"),
            "SAGE_GATE_POLICY": str(write_gate_policy(project)),
        }
    )
    return env


def run_hook(script: Path, envelope: dict, project: Path) -> tuple[int, dict, str]:
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        cwd=project,
        env=adapter_env(project),
        check=False,
    )
    parsed = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, parsed, result.stderr


def test_idle_advisory_context_is_equivalent_and_bounded(project: Path) -> None:
    hermes_envelope = {
        "hook_event_name": "pre_llm_call",
        "cwd": str(project),
        "extra": {"user_message": "Please map the spaces in this repository"},
    }
    claude_envelope = {
        "hook_event_name": "UserPromptSubmit",
        "cwd": str(project),
        "prompt": "Please map the spaces in this repository",
    }

    hermes_code, hermes, hermes_stderr = run_hook(HERMES_ROUTE, hermes_envelope, project)
    claude_code, claude, claude_stderr = run_hook(CLAUDE_ROUTE, claude_envelope, project)
    claude_context = claude["hookSpecificOutput"]["additionalContext"]

    assert hermes_code == 0, hermes_stderr
    assert claude_code == 0, claude_stderr
    assert hermes["context"] == claude_context
    assert "/map" in hermes["context"]
    assert "advisory" in hermes["context"].lower()
    assert len(hermes["context"].encode("utf-8")) <= 2048


def test_active_run_suppresses_inferred_advisory(project: Path) -> None:
    write_active_state(project)
    envelope = {
        "hook_event_name": "pre_llm_call",
        "cwd": str(project),
        "extra": {"user_message": "Please map the spaces in this repository"},
    }

    code, output, stderr = run_hook(HERMES_ROUTE, envelope, project)

    assert code == 0, stderr
    assert "advisory" not in output["context"].lower()
    assert "active run" in output["context"].lower()


def test_explicit_strict_run_denies_one_concrete_invariant(project: Path) -> None:
    write_active_state(project, strict=True)
    envelope = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "write_file",
        "tool_input": {"path": "src/app.py", "content": "changed"},
        "cwd": str(project),
        "extra": {},
    }

    hermes_code, hermes, hermes_stderr = run_hook(HERMES_GATE, envelope, project)
    claude_code, claude, claude_stderr = run_hook(
        CLAUDE_GATE,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "src/app.py", "content": "changed"},
            "cwd": str(project),
        },
        project,
    )

    assert hermes_code == 0, hermes_stderr
    assert claude_code == 0, claude_stderr
    assert hermes["action"] == "block"
    assert "approved-plan" in hermes["message"]
    decision = claude["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "approved-plan" in decision["permissionDecisionReason"]


def test_read_only_tool_is_allowed_even_during_strict_run(project: Path) -> None:
    write_active_state(project, strict=True)
    envelope = {
        "hook_event_name": "pre_tool_call",
        "tool_name": "read_file",
        "tool_input": {"path": "src/app.py"},
        "cwd": str(project),
        "extra": {},
    }

    code, output, stderr = run_hook(HERMES_GATE, envelope, project)

    assert code == 0, stderr
    assert output == {"action": "allow"}


@pytest.mark.parametrize(
    ("command", "read_only"),
    [
        ("rg TODO src", True),
        ("git status --short", True),
        ("git branch --show-current", True),
        ("git branch -D old-feature", False),
        ("git worktree list", True),
        ("git worktree add ../other feature", False),
        ("python build.py", False),
        ("rg TODO src > report.txt", False),
    ],
)
def test_shell_operation_classification_is_conservative(
    command: str, read_only: bool
) -> None:
    operation = operation_from_envelope(
        {"tool_name": "terminal", "tool_input": {"command": command}}
    )

    assert operation.read_only is read_only


def test_absolute_platform_path_is_normalized_against_project(tmp_path: Path) -> None:
    operation = operation_from_envelope(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "src" / "app.py")},
        },
        tmp_path,
    )

    assert operation.paths == ("src/app.py",)


def test_missing_catalog_or_runtime_fails_open(tmp_path: Path) -> None:
    route_code, route_output, route_stderr = run_hook(
        HERMES_ROUTE,
        {
            "hook_event_name": "pre_llm_call",
            "cwd": str(tmp_path),
            "extra": {"user_message": "Please map this repository"},
        },
        tmp_path,
    )
    gate_code, gate_output, gate_stderr = run_hook(
        HERMES_GATE,
        {
            "hook_event_name": "pre_tool_call",
            "tool_name": "write_file",
            "tool_input": {"path": "src/app.py"},
            "cwd": str(tmp_path),
            "extra": {},
        },
        tmp_path,
    )

    assert route_code == 0, route_stderr
    assert route_output == {"context": ""}
    assert gate_code == 0, gate_stderr
    assert gate_output == {"action": "allow"}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (HERMES_ROUTE, {"context": ""}),
        (HERMES_GATE, {"action": "allow"}),
        (
            CLAUDE_ROUTE,
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": "",
                }
            },
        ),
        (
            CLAUDE_GATE,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "",
                }
            },
        ),
    ],
)
def test_copied_hook_without_shared_runtime_returns_native_fail_open_output(
    tmp_path: Path, source: Path, expected: dict
) -> None:
    copied = tmp_path / source.name
    shutil.copy2(source, copied)
    env = os.environ.copy()
    for key in (
        "SAGE_PROJECT",
        "SAGE_RUNTIME_CLI",
        "SAGE_ROUTE_CATALOG",
        "SAGE_GATE_POLICY",
    ):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, str(copied)],
        input="{}",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


def test_claude_hook_merge_preserves_unrelated_settings_and_is_idempotent(
    tmp_path: Path,
) -> None:
    settings = tmp_path / "settings.local.json"
    settings.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Read"]},
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "matcher": "",
                            "hooks": [{"type": "command", "command": "python custom.py"}],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    for _ in range(2):
        install_claude_hooks(
            settings,
            session_command="python session.py",
            route_command="python route.py",
            gate_command="python gate.py",
        )

    merged = json.loads(settings.read_text(encoding="utf-8"))
    assert merged["permissions"] == {"allow": ["Read"]}
    prompt_commands = [
        hook["command"]
        for group in merged["hooks"]["UserPromptSubmit"]
        for hook in group["hooks"]
    ]
    assert prompt_commands == ["python custom.py", "python route.py"]
    assert len(merged["hooks"]["PreToolUse"]) == 1
    assert len(merged["hooks"]["SessionStart"]) == 1


def test_hermes_hook_merge_preserves_unrelated_config_without_enabling_auto_accept(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        """model: test-model
hooks:
  pre_llm_call:
    - command: python custom.py
""",
        encoding="utf-8",
    )

    for _ in range(2):
        install_hermes_hooks(
            config,
            route_command="python route.py",
            gate_command="python gate.py",
        )

    merged = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert merged["model"] == "test-model"
    assert "hooks_auto_accept" not in merged
    assert [item["command"] for item in merged["hooks"]["pre_llm_call"]] == [
        "python custom.py",
        "python route.py",
    ]
    assert merged["hooks"]["pre_tool_call"] == [
        {"command": "python gate.py", "matcher": ".*"}
    ]


@pytest.mark.parametrize(
    ("platform", "filename", "malformed"),
    [
        ("claude-code", "settings.local.json", "{not-json"),
        ("hermes", "config.yaml", "hooks: [unterminated"),
    ],
)
def test_malformed_hook_config_is_backed_up_and_rejected_before_merge(
    tmp_path: Path, platform: str, filename: str, malformed: str
) -> None:
    config = tmp_path / filename
    config.write_text(malformed, encoding="utf-8")

    with pytest.raises(HookConfigError, match="malformed"):
        validate_hook_config(config, platform, backup_malformed=True)

    assert config.read_text(encoding="utf-8") == malformed
    backups = list(tmp_path.glob(f"{filename}.malformed-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == malformed
