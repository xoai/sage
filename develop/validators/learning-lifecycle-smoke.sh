#!/usr/bin/env bash
# End-to-end smoke for backend-neutral recall, candidate detection, and reflection.
set -euo pipefail

resolve_root() {
  if [ -n "${1:-}" ]; then printf '%s' "$1"; return; fi
  cd "$(dirname "$0")/../.." && pwd
}

SAGE_ROOT="$(resolve_root "${1:-}")"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "learning lifecycle smoke: Python 3 is required" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import yaml' >/dev/null 2>&1; then
  echo "learning lifecycle smoke: PyYAML is required" >&2
  exit 1
fi

"$PYTHON_BIN" - "$SAGE_ROOT" <<'PY'
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "runtime" / "tools"))

from sage_runtime.hook_config import install_claude_hooks, install_hermes_hooks
from sage_runtime.learning import LearningConfigError, resolve_learning_config
from sage_runtime.learning_contracts import RecallRecord, RecallResult


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


claude_hooks = root / "runtime" / "platforms" / "claude-code" / "hooks"
hermes_hooks = root / "runtime" / "platforms" / "hermes" / "hooks"
claude_recall = load(claude_hooks / "sage-learning-recall.py", "smoke_claude_recall")
claude_observe = load(claude_hooks / "sage-learning-observe.py", "smoke_claude_observe")
claude_reflect = load(claude_hooks / "sage-reflect-stop.py", "smoke_claude_reflect")
hermes_recall = load(hermes_hooks / "sage-learning-recall.py", "smoke_hermes_recall")
hermes_observe = load(hermes_hooks / "sage-learning-observe.py", "smoke_hermes_observe")
hermes_reflect = load(hermes_hooks / "sage-reflect-checkpoint.py", "smoke_hermes_reflect")


class Backend:
    def __init__(self, broken: bool = False) -> None:
        self.broken = broken
        self.calls = 0

    def search_learnings(self, query, context, limit):
        self.calls += 1
        if self.broken:
            raise RuntimeError("offline")
        return RecallResult(
            query=query,
            backend="smoke",
            records=(
                RecallRecord(
                    id="map-command",
                    title="Map command correction",
                    prevention="Use /map; sage:map is not a command.",
                    rationale="A prior correction was verified.",
                    scope="global",
                ),
            ),
        )


def context(payload: dict) -> str:
    native = payload.get("hookSpecificOutput")
    if isinstance(native, dict):
        return str(native.get("additionalContext", ""))
    return str(payload.get("context", payload.get("message", payload.get("reason", ""))))


def claude(project: Path, event: str, **values) -> dict:
    return {"cwd": str(project), "session_id": "smoke", "hook_event_name": event, **values}


def hermes(project: Path, event: str, **values) -> dict:
    return {"cwd": str(project), "session_id": "smoke", "hook_event_name": event, **values}


with tempfile.TemporaryDirectory(prefix="sage-learning-lifecycle-") as raw:
    temporary = Path(raw)
    recall_project = temporary / "recall"
    left = Backend()
    right = Backend()
    claude_context = context(
        claude_recall.handle(
            claude(recall_project, "UserPromptSubmit", prompt="fix map"), backend=left
        )
    )
    hermes_context = context(
        hermes_recall.handle(
            hermes(recall_project, "pre_llm_call", extra={"user_message": "fix map"}),
            backend=right,
        )
    )
    assert left.calls == right.calls == 1
    assert claude_context == hermes_context and "Use /map" in claude_context
    assert context(
        claude_recall.handle(
            claude(recall_project, "UserPromptSubmit", prompt="continue"),
            backend=Backend(broken=True),
        )
    ) == ""

    projects = {"claude": temporary / "claude", "hermes": temporary / "hermes"}
    correction = {
        "type": "user.correction",
        "explicit": True,
        "observation_id": "correction-1",
        "message": "Use /map.",
    }
    candidate_contexts = {
        "claude": context(
            claude_observe.handle(
                claude(projects["claude"], "UserCorrection", sage_event=correction),
                occurred_at="2026-07-10T16:00:00Z",
            )
        ),
        "hermes": context(
            hermes_observe.handle(
                hermes(projects["hermes"], "user_correction", sage_event=correction),
                occurred_at="2026-07-10T16:00:00Z",
            )
        ),
    }
    assert candidate_contexts["claude"] == candidate_contexts["hermes"]
    assert "canonical `sage-self-learning`" in candidate_contexts["claude"]
    pending = context(
        hermes_recall.handle(
            hermes(
                projects["hermes"],
                "pre_llm_call",
                extra={"user_message": "continue"},
            ),
            backend=Backend(broken=True),
        )
    )
    assert pending == candidate_contexts["hermes"]
    assert context(
        hermes_recall.handle(
            hermes(
                projects["hermes"],
                "pre_llm_call",
                extra={"user_message": "continue"},
            ),
            backend=Backend(broken=True),
        )
    ) == ""

    claude_result = claude_reflect.handle(
        claude(projects["claude"], "Stop", stop_hook_active=False),
        occurred_at="2026-07-10T16:05:00Z",
    )
    hermes_result = hermes_reflect.handle(
        hermes(projects["hermes"], "pre_verify"),
        occurred_at="2026-07-10T16:05:00Z",
    )
    assert claude_result.get("decision") == "block"
    assert hermes_result.get("action") == "continue"
    assert "canonical `reflect` skill exactly once" in context(claude_result)
    assert claude_reflect.handle(
        claude(projects["claude"], "Stop"), occurred_at="2026-07-10T16:06:00Z"
    ) == {}
    assert hermes_reflect.handle(
        hermes(projects["hermes"], "pre_verify"), occurred_at="2026-07-10T16:06:00Z"
    ) == {}

    claude_config = temporary / "settings.json"
    hermes_config = temporary / "config.yaml"
    install_claude_hooks(
        claude_config,
        session_command="session",
        route_command="route",
        gate_command="gate",
        learning_recall_command="recall",
        learning_observe_command="observe",
        reflect_command="reflect",
    )
    install_hermes_hooks(
        hermes_config,
        route_command="route",
        gate_command="gate",
        learning_recall_command="recall",
        learning_observe_command="observe",
        reflect_command="reflect",
    )
    claude_loaded = json.loads(claude_config.read_text(encoding="utf-8"))
    assert set(("UserPromptSubmit", "PostToolUse", "Stop")) <= set(claude_loaded["hooks"])
    hermes_text = hermes_config.read_text(encoding="utf-8")
    for event in (
        "pre_llm_call:",
        "post_tool_call:",
        "pre_verify:",
        "on_session_end:",
        "on_session_finalize:",
    ):
        assert event in hermes_text

    try:
        resolve_learning_config(
            temporary,
            {"SAGE_LEARNING_BACKEND": "sage-memory,openviking"},
        )
    except LearningConfigError:
        pass
    else:
        raise AssertionError("multiple active learning backends must be rejected")

print("learning lifecycle smoke: PASS")
PY
