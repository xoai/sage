"""Exactly-once, evidence-based reflection lifecycle."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import NormalizedEvent
from .learning_contracts import LearningContractError
from .state import append_event, read_events, reconcile_run


QUESTION_KINDS = frozenset(
    {"external-outcome", "personal-preference", "stakeholder-signal"}
)
REFLECTION_MODES = frozenset({"evidence", "interactive"})
DEFAULT_CONTEXT_BYTES = 4096


def _bounded(value: object, max_bytes: int) -> str:
    text = " ".join(str(value or "").split())
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def _timestamp(value: str | None) -> str:
    if value is not None:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ReflectionQuestion:
    kind: str
    question: str

    def __post_init__(self) -> None:
        if self.kind not in QUESTION_KINDS:
            raise ValueError(f"unsupported reflection question kind: {self.kind}")
        question = _bounded(self.question, 512)
        if not question:
            raise ValueError("reflection question must not be empty")
        object.__setattr__(self, "question", question)

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "question": self.question}


@dataclass(frozen=True)
class ReflectionRequest:
    requested: bool
    status: str
    mode: str
    source: str
    run_id: str
    run_dir: str = ""
    evidence_paths: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    unresolved_questions: tuple[ReflectionQuestion, ...] = ()
    event_id: str | None = None


@dataclass(frozen=True)
class ReflectionCompletion:
    completed: bool
    status: str
    stored: int
    novel_candidates: int
    event_id: str | None = None


@dataclass(frozen=True)
class ReflectionSkip:
    skipped: bool
    status: str
    reason: str
    event_id: str | None = None


def _candidate_ids(events: Sequence[NormalizedEvent]) -> tuple[str, ...]:
    output: list[str] = []
    for event in events:
        if event.type != "learning.candidate":
            continue
        candidate_id = event.payload.get("candidate_id")
        if isinstance(candidate_id, str) and candidate_id and candidate_id not in output:
            output.append(candidate_id)
    return tuple(output)


def _evidence_paths(
    run_dir: Path, state_artifacts: Mapping[str, Any], transcript_path: str | None
) -> tuple[str, ...]:
    output = [str(run_dir / "events.jsonl"), str(run_dir / "state.json")]
    if transcript_path:
        output.insert(0, _bounded(transcript_path, 2048))
    for value in state_artifacts.values():
        if not isinstance(value, Mapping):
            continue
        path = value.get("path")
        if isinstance(path, str) and path and path not in output:
            output.append(path)
    return tuple(output)


def _no_request(run_id: str, status: str, mode: str, source: str) -> ReflectionRequest:
    return ReflectionRequest(
        requested=False,
        status=status,
        mode=mode,
        source=source,
        run_id=run_id,
    )


def request_reflection(
    run_dir: Path,
    *,
    mode: str = "evidence",
    source: str = "completion",
    transcript_path: str | None = None,
    unresolved_questions: Sequence[ReflectionQuestion] = (),
    occurred_at: str | None = None,
) -> ReflectionRequest:
    """Persist one reflection request after a completed run."""
    if mode not in REFLECTION_MODES:
        raise LearningContractError(f"unsupported reflection mode: {mode}")
    directory = Path(run_dir)
    state = reconcile_run(directory)
    if state.status != "completed":
        return _no_request(state.run_id, state.reflection_status, mode, source)
    if state.reflection_status in {"requested", "completed", "skipped"}:
        return _no_request(state.run_id, state.reflection_status, mode, source)

    questions = tuple(unresolved_questions)
    if not all(isinstance(item, ReflectionQuestion) for item in questions):
        raise LearningContractError(
            "unresolved_questions must contain ReflectionQuestion values"
        )
    events = read_events(directory)
    evidence_paths = _evidence_paths(directory, state.artifacts, transcript_path)
    candidate_ids = _candidate_ids(events)
    timestamp = _timestamp(occurred_at)
    event_id = f"reflection-requested-{state.run_id}"
    event = NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": event_id,
            "type": "reflection.requested",
            "occurred_at": timestamp,
            "payload": {
                "run_id": state.run_id,
                "mode": mode,
                "source": _bounded(source, 128),
                "evidence_paths": list(evidence_paths),
                "candidate_ids": list(candidate_ids),
                "unresolved_questions": [item.to_dict() for item in questions],
            },
        }
    )
    appended = append_event(directory, event)
    return ReflectionRequest(
        requested=appended,
        status="requested",
        mode=mode,
        source=source,
        run_id=state.run_id,
        run_dir=str(directory),
        evidence_paths=evidence_paths,
        candidate_ids=candidate_ids,
        unresolved_questions=questions,
        event_id=event_id,
    )


def complete_reflection(
    run_dir: Path,
    *,
    stored: int,
    novel_candidates: int,
    occurred_at: str | None = None,
) -> ReflectionCompletion:
    """Mark a requested reflection complete, including a zero-learning result."""
    if stored < 0 or novel_candidates < 0:
        raise LearningContractError("reflection counts must be non-negative")
    directory = Path(run_dir)
    state = reconcile_run(directory)
    if state.reflection_status == "completed":
        return ReflectionCompletion(False, "completed", stored, novel_candidates)
    if state.reflection_status != "requested":
        return ReflectionCompletion(False, state.reflection_status, stored, novel_candidates)
    event_id = f"reflection-completed-{state.run_id}"
    event = NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": event_id,
            "type": "reflection.completed",
            "occurred_at": _timestamp(occurred_at),
            "payload": {
                "run_id": state.run_id,
                "stored": stored,
                "novel_candidates": novel_candidates,
            },
        }
    )
    appended = append_event(directory, event)
    return ReflectionCompletion(
        completed=appended,
        status="completed" if appended else state.reflection_status,
        stored=stored,
        novel_candidates=novel_candidates,
        event_id=event_id,
    )


def skip_reflection(
    run_dir: Path,
    *,
    reason: str,
    occurred_at: str | None = None,
) -> ReflectionSkip:
    """Terminate one requested reflection without creating a learning."""
    bounded_reason = _bounded(reason, 512)
    if not bounded_reason:
        raise LearningContractError("reflection skip reason must not be empty")
    directory = Path(run_dir)
    state = reconcile_run(directory)
    if state.reflection_status == "skipped":
        return ReflectionSkip(False, "skipped", bounded_reason)
    if state.reflection_status != "requested":
        return ReflectionSkip(False, state.reflection_status, bounded_reason)
    event_id = f"reflection-skipped-{state.run_id}"
    event = NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": event_id,
            "type": "reflection.skipped",
            "occurred_at": _timestamp(occurred_at),
            "payload": {
                "run_id": state.run_id,
                "reason": bounded_reason,
            },
        }
    )
    appended = append_event(directory, event)
    return ReflectionSkip(
        skipped=appended,
        status="skipped" if appended else state.reflection_status,
        reason=bounded_reason,
        event_id=event_id,
    )


def _truncate_context(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    suffix = "\n[reflection context truncated]\n"
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) >= max_bytes:
        return suffix_bytes[:max_bytes].decode("utf-8", errors="ignore")
    prefix = encoded[: max_bytes - len(suffix_bytes)].decode(
        "utf-8", errors="ignore"
    ).rstrip()
    return prefix + suffix


def _render_command(parts: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def render_reflection_context(
    request: ReflectionRequest, max_bytes: int = DEFAULT_CONTEXT_BYTES
) -> str:
    if not request.requested:
        return ""
    evidence = "\n".join(f"- {path}" for path in request.evidence_paths)
    candidates = (
        ", ".join(request.candidate_ids) if request.candidate_ids else "none detected"
    )
    questions = ""
    if request.unresolved_questions:
        rendered_questions = "\n".join(
            f"- [{item.kind}] {item.question}" for item in request.unresolved_questions
        )
        questions = (
            "\nAsk the user only for these unresolved external signals:\n"
            f"{rendered_questions}\n"
        )
    elif request.mode == "evidence":
        questions = (
            "\nDo not require user feedback: all current claims must come from "
            "observable evidence.\n"
        )

    cli_path = Path(__file__).resolve().parent.parent / "sage_runtime_cli.py"
    complete_command = _render_command(
        (
            sys.executable,
            str(cli_path),
            "reflection",
            "complete",
            "--run-dir",
            request.run_dir,
            "--stored",
            "<stored-count>",
            "--novel-candidates",
            "<novel-candidate-count>",
        )
    )
    skip_command = _render_command(
        (
            sys.executable,
            str(cli_path),
            "reflection",
            "skip",
            "--run-dir",
            request.run_dir,
            "--reason",
            "<evidence-based reason>",
        )
    )

    text = (
        "Activate the installed canonical `reflect` skill exactly once for this "
        f"completed run. Mode: {request.mode}.\n"
        "Gather the transcript and normalized event log, including tool outcomes, "
        "corrections, artifacts, verification outcomes, and prior learnings recalled "
        "or created during the run.\n"
        f"Evidence paths:\n{evidence}\n"
        f"Existing learning candidate IDs: {candidates}.\n"
        f"{questions}"
        "Extract Reinforce, Prevent, and Improve candidates using WHEN / CHECK / "
        "BECAUSE. For each candidate, invoke the canonical `sage-self-learning` "
        "skill and follow its full classify, four-part author, search-before-store, "
        "enrich/correct/invalidate/link method. A valid reflection may conclude "
        "that there is no novel learning to store. Do not invent outcomes, user "
        "preferences, stakeholder signals, causes, or answers absent from evidence.\n"
        "After the canonical skills finish, durably acknowledge this request. Run "
        f"`{complete_command}` with the actual non-negative counts, including zero. "
        "If reflection is deliberately inapplicable or cannot proceed, run "
        f"`{skip_command}` instead. Do not leave the request pending.\n"
    )
    return _truncate_context(text, max(1, int(max_bytes)))
