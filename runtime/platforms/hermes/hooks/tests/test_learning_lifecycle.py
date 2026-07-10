from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.hook_config import install_claude_hooks, install_hermes_hooks


def test_claude_learning_hooks_merge_without_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"keep"}]}]}}')
    for _ in range(2):
        install_claude_hooks(
            path,
            session_command="session",
            route_command="route",
            gate_command="gate",
            learning_recall_command="recall",
            learning_observe_command="observe",
            reflect_command="reflect",
        )
    text = path.read_text(encoding="utf-8")
    assert text.count('"command": "keep"') == 1
    assert text.count('"command": "recall"') == 1
    assert text.count('"command": "observe"') == 1
    assert text.count('"command": "reflect"') == 1
    assert '"PostToolUse"' in text
    assert '"Stop"' in text


def test_hermes_learning_hooks_merge_without_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("hooks:\n  pre_llm_call:\n    - command: keep\n")
    for _ in range(2):
        install_hermes_hooks(
            path,
            route_command="route",
            gate_command="gate",
            learning_recall_command="recall",
            learning_observe_command="observe",
            reflect_command="reflect",
        )
    text = path.read_text(encoding="utf-8")
    assert text.count("command: keep") == 1
    assert text.count("command: recall") == 1
    assert text.count("command: observe") == 3
    assert text.count("command: reflect") == 1
    assert "post_tool_call:" in text
    assert "pre_verify:" in text
    assert "on_session_end:" in text
    assert "on_session_finalize:" in text


def test_managed_hook_path_change_replaces_old_command(tmp_path: Path) -> None:
    claude = tmp_path / "settings.json"
    install_claude_hooks(
        claude,
        session_command="bash .claude/hooks/sage-session-init.sh",
        route_command='"python-old" ".claude/hooks/sage-route-context.py"',
        gate_command='"python-old" ".claude/hooks/sage-strict-gate.py"',
        learning_recall_command='"python-old" ".claude/hooks/sage-learning-recall.py"',
    )
    install_claude_hooks(
        claude,
        session_command="bash .claude/hooks/sage-session-init.sh",
        route_command='"python-new" ".claude/hooks/sage-route-context.py"',
        gate_command='"python-new" ".claude/hooks/sage-strict-gate.py"',
        learning_recall_command='"python-new" ".claude/hooks/sage-learning-recall.py"',
    )
    text = claude.read_text(encoding="utf-8")
    assert "python-old" not in text
    assert text.count("sage-route-context.py") == 1
    assert text.count("sage-strict-gate.py") == 1
    assert text.count("sage-learning-recall.py") == 1
