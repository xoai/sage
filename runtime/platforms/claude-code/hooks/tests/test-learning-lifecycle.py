from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.learning_contracts import RecallRecord, RecallResult
from sage_runtime.lifecycle_adapter import observe_context


CLAUDE_HOOKS = ROOT / "runtime" / "platforms" / "claude-code" / "hooks"
HERMES_HOOKS = ROOT / "runtime" / "platforms" / "hermes" / "hooks"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLAUDE_RECALL = _load(CLAUDE_HOOKS / "sage-learning-recall.py", "claude_learning_recall")
CLAUDE_OBSERVE = _load(CLAUDE_HOOKS / "sage-learning-observe.py", "claude_learning_observe")
CLAUDE_REFLECT = _load(CLAUDE_HOOKS / "sage-reflect-stop.py", "claude_reflect_stop")
HERMES_RECALL = _load(HERMES_HOOKS / "sage-learning-recall.py", "hermes_learning_recall")
HERMES_OBSERVE = _load(HERMES_HOOKS / "sage-learning-observe.py", "hermes_learning_observe")
HERMES_REFLECT = _load(HERMES_HOOKS / "sage-reflect-checkpoint.py", "hermes_reflect_checkpoint")


class FakeBackend:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search_learnings(self, query, context, limit):
        self.queries.append(query)
        return RecallResult(
            query=query,
            backend="fake",
            records=(
                RecallRecord(
                    id="map-command",
                    title="Map command correction",
                    scope="global",
                    prevention="Use /map; sage:map is not a command.",
                    rationale="The correction was verified in a prior session.",
                ),
            ),
        )


class BrokenBackend:
    def search_learnings(self, query, context, limit):
        raise RuntimeError("memory service unavailable")


def _context(payload: dict) -> str:
    hook_output = payload.get("hookSpecificOutput")
    if isinstance(hook_output, dict):
        return str(hook_output.get("additionalContext", ""))
    return str(payload.get("context", payload.get("message", payload.get("reason", ""))))


def _claude(project: Path, event: str, **values) -> dict:
    return {"hook_event_name": event, "cwd": str(project), "session_id": "session-1", **values}


def _hermes(project: Path, event: str, **values) -> dict:
    extra = values.pop("extra", {})
    return {
        "hook_event_name": event,
        "cwd": str(project),
        "session_id": "session-1",
        "extra": extra,
        **values,
    }


def test_recall_is_scoped_once_and_has_platform_native_envelopes(tmp_path: Path) -> None:
    claude_backend = FakeBackend()
    hermes_backend = FakeBackend()
    project = tmp_path / "project"
    claude = CLAUDE_RECALL.handle(
        _claude(project, "UserPromptSubmit", prompt="fix the map command"),
        backend=claude_backend,
    )
    hermes = HERMES_RECALL.handle(
        _hermes(
            project,
            "pre_llm_call",
            extra={"user_message": "fix the map command"},
        ),
        backend=hermes_backend,
    )

    assert claude_backend.queries == hermes_backend.queries
    assert len(claude_backend.queries) == 1
    assert "Use /map" in _context(claude)
    assert _context(claude) == _context(hermes)
    assert claude["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "context" in hermes


def test_backend_outage_never_blocks_either_platform(tmp_path: Path) -> None:
    claude = CLAUDE_RECALL.handle(
        _claude(tmp_path / "claude", "UserPromptSubmit", prompt="continue"),
        backend=BrokenBackend(),
    )
    hermes = HERMES_RECALL.handle(
        _hermes(tmp_path / "hermes", "pre_llm_call", extra={"user_message": "continue"}),
        backend=BrokenBackend(),
    )
    assert _context(claude) == ""
    assert _context(hermes) == ""


def test_external_recall_owner_makes_sage_hooks_stand_down(tmp_path: Path) -> None:
    project = tmp_path / "project"
    config = project / ".sage" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "learning:\n  backend: sage-memory\n  recall_owner: hermes-native\n",
        encoding="utf-8",
    )
    backend = FakeBackend()

    output = CLAUDE_RECALL.handle(
        _claude(project, "UserPromptSubmit", prompt="fix the map command"),
        backend=backend,
    )

    assert _context(output) == ""
    assert backend.queries == []


def test_claude_recall_delivers_candidates_persisted_by_observer_only_hooks(
    tmp_path: Path,
) -> None:
    project = tmp_path / "claude"
    envelope = _claude(
        project,
        "PostToolUse",
        tool_name="terminal",
        tool_use_id="call-1",
        tool_response={"success": False, "error": "exit 127"},
    )
    observe_context(envelope, occurred_at="2026-07-10T16:00:00Z", dispatch=False)
    observe_context(
        dict(envelope, tool_use_id="call-2"),
        occurred_at="2026-07-10T16:01:00Z",
        dispatch=False,
    )

    first = CLAUDE_RECALL.handle(
        _claude(project, "UserPromptSubmit", prompt="continue"),
        backend=BrokenBackend(),
    )
    second = CLAUDE_RECALL.handle(
        _claude(project, "UserPromptSubmit", prompt="continue"),
        backend=BrokenBackend(),
    )

    assert "Trigger type: repeated-failure" in _context(first)
    assert _context(second) == ""


def test_failure_and_correction_create_same_candidates_on_both_platforms(tmp_path: Path) -> None:
    claude_project = tmp_path / "claude"
    hermes_project = tmp_path / "hermes"
    first_claude = _claude(
        claude_project,
        "PostToolUse",
        tool_name="terminal",
        tool_use_id="call-1",
        tool_response={"success": False, "error": "exit 127"},
    )
    first_hermes = _hermes(
        hermes_project,
        "post_tool_call",
        tool_name="terminal",
        extra={"tool_call_id": "call-1", "result": '{"error":"exit 127"}'},
    )
    assert _context(CLAUDE_OBSERVE.handle(first_claude, occurred_at="2026-07-10T16:00:00Z")) == ""
    assert _context(HERMES_OBSERVE.handle(first_hermes, occurred_at="2026-07-10T16:00:00Z")) == ""

    second_claude = dict(first_claude, tool_use_id="call-2")
    second_hermes = _hermes(
        hermes_project,
        "post_tool_call",
        tool_name="terminal",
        extra={"tool_call_id": "call-2", "result": '{"error":"exit 127"}'},
    )
    claude_failure = _context(
        CLAUDE_OBSERVE.handle(second_claude, occurred_at="2026-07-10T16:01:00Z")
    )
    hermes_failure = _context(
        HERMES_OBSERVE.handle(second_hermes, occurred_at="2026-07-10T16:01:00Z")
    )
    assert claude_failure == hermes_failure
    assert "Trigger type: repeated-failure" in claude_failure
    assert "canonical `sage-self-learning`" in claude_failure
    hermes_pending = _context(
        HERMES_RECALL.handle(
            _hermes(
                hermes_project,
                "pre_llm_call",
                extra={"user_message": "continue after the tool failure"},
            ),
            backend=BrokenBackend(),
        )
    )
    assert hermes_pending == hermes_failure
    assert _context(
        HERMES_RECALL.handle(
            _hermes(
                hermes_project,
                "pre_llm_call",
                extra={"user_message": "continue after the tool failure"},
            ),
            backend=BrokenBackend(),
        )
    ) == ""

    correction = {
        "type": "user.correction",
        "explicit": True,
        "observation_id": "correction-1",
        "message": "The command is /map, not sage:map.",
    }
    claude_correction = _context(
        CLAUDE_OBSERVE.handle(
            _claude(claude_project, "UserCorrection", sage_event=correction),
            occurred_at="2026-07-10T16:02:00Z",
        )
    )
    hermes_correction = _context(
        HERMES_OBSERVE.handle(
            _hermes(hermes_project, "user_correction", sage_event=correction),
            occurred_at="2026-07-10T16:02:00Z",
        )
    )
    assert claude_correction == hermes_correction
    assert "Trigger type: user-correction" in claude_correction

    failed_verification = {
        "type": "verification.recorded",
        "verification_id": "unit-tests",
        "passed": False,
        "observation_id": "verification-1",
    }
    passed_verification = dict(
        failed_verification, passed=True, observation_id="verification-2"
    )
    assert _context(
        CLAUDE_OBSERVE.handle(
            _claude(claude_project, "PostToolUse", sage_event=failed_verification),
            occurred_at="2026-07-10T16:03:00Z",
        )
    ) == ""
    assert _context(
        HERMES_OBSERVE.handle(
            _hermes(hermes_project, "post_tool_call", sage_event=failed_verification),
            occurred_at="2026-07-10T16:03:00Z",
        )
    ) == ""
    claude_recovery = _context(
        CLAUDE_OBSERVE.handle(
            _claude(claude_project, "PostToolUse", sage_event=passed_verification),
            occurred_at="2026-07-10T16:04:00Z",
        )
    )
    hermes_recovery = _context(
        HERMES_OBSERVE.handle(
            _hermes(hermes_project, "post_tool_call", sage_event=passed_verification),
            occurred_at="2026-07-10T16:04:00Z",
        )
    )
    assert claude_recovery == hermes_recovery
    assert "Trigger type: fail-to-pass" in claude_recovery


def test_completion_requests_evidence_reflection_exactly_once(tmp_path: Path) -> None:
    claude_project = tmp_path / "claude"
    hermes_project = tmp_path / "hermes"
    correction = {
        "type": "user.correction",
        "explicit": True,
        "observation_id": "correction-1",
        "message": "Use /map.",
    }
    CLAUDE_OBSERVE.handle(
        _claude(claude_project, "UserCorrection", sage_event=correction),
        occurred_at="2026-07-10T16:00:00Z",
    )
    HERMES_OBSERVE.handle(
        _hermes(hermes_project, "user_correction", sage_event=correction),
        occurred_at="2026-07-10T16:00:00Z",
    )

    claude_first = CLAUDE_REFLECT.handle(
        _claude(claude_project, "Stop", stop_hook_active=False),
        occurred_at="2026-07-10T16:05:00Z",
    )
    hermes_first = HERMES_REFLECT.handle(
        _hermes(hermes_project, "pre_verify"),
        occurred_at="2026-07-10T16:05:00Z",
    )
    assert claude_first["decision"] == "block"
    assert hermes_first["action"] == "continue"
    normalized_claude = _context(claude_first).replace(str(claude_project), "<project>")
    normalized_hermes = _context(hermes_first).replace(str(hermes_project), "<project>")
    assert normalized_claude == normalized_hermes
    assert "canonical `reflect` skill exactly once" in _context(claude_first)
    assert "Do not require user feedback" in _context(claude_first)

    assert CLAUDE_REFLECT.handle(
        _claude(claude_project, "Stop", stop_hook_active=True),
        occurred_at="2026-07-10T16:06:00Z",
    ) == {}
    assert HERMES_REFLECT.handle(
        _hermes(hermes_project, "pre_verify"),
        occurred_at="2026-07-10T16:06:00Z",
    ) == {}
