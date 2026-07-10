"""Shared deterministic learning lifecycle used by thin platform hooks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import NormalizedEvent
from .learning import (
    create_learning_backend,
    recall_before_work,
    render_recall_context,
    resolve_learning_config,
)
from .learning_candidates import (
    detect_learning_candidates,
    load_candidate,
    render_candidate_context,
)
from .learning_contracts import LearningContext
from .reflection import render_reflection_context, request_reflection
from .state import append_event, read_events, reconcile_run


SAGE_RECALL_OWNERS = frozenset({"sage-learning", "sage-lifecycle"})


def utc_now(value: str | None = None) -> str:
    return value or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def project_from_envelope(envelope: Mapping[str, object]) -> Path:
    value = envelope.get("cwd") or envelope.get("project") or "."
    return Path(str(value)).resolve()


def prompt_from_envelope(envelope: Mapping[str, object]) -> str:
    for key in ("prompt", "user_message", "message"):
        value = envelope.get(key)
        if isinstance(value, str) and value.strip():
            return value
    extra = envelope.get("extra")
    if isinstance(extra, Mapping):
        for key in ("user_message", "prompt", "message"):
            value = extra.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _active_run_dir(project: Path) -> Path | None:
    runtime = project / ".sage" / "runtime"
    pointer = _read_json(runtime / "active-run.json")
    if pointer is None or pointer.get("schema") != "active-run/v1":
        return None
    if pointer.get("active") is not True:
        return None
    state_path = pointer.get("state_path")
    if not isinstance(state_path, str) or not state_path:
        return None
    candidate = (runtime / state_path).resolve()
    resolved_runtime = runtime.resolve()
    if resolved_runtime != candidate.parent and resolved_runtime not in candidate.parents:
        return None
    state = _read_json(candidate)
    if state is None or state.get("status") != "active":
        return None
    return candidate.parent


def _session_id(envelope: Mapping[str, object]) -> str:
    for key in ("session_id", "conversation_id", "thread_id"):
        value = envelope.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    extra = envelope.get("extra")
    if isinstance(extra, Mapping):
        value = extra.get("session_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "default"


def lifecycle_run_dir(
    project: Path,
    envelope: Mapping[str, object],
    *,
    create: bool,
    occurred_at: str | None = None,
) -> Path | None:
    active = _active_run_dir(project)
    if active is not None:
        return active
    digest = hashlib.sha256(_session_id(envelope).encode("utf-8")).hexdigest()[:16]
    run_id = f"learning-{digest}"
    run_dir = project / ".sage" / "runtime" / "learning-runs" / run_id
    if (run_dir / "events.jsonl").is_file():
        return run_dir
    if not create:
        return None
    event = NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": f"run-started-{run_id}",
            "type": "run.started",
            "occurred_at": utc_now(occurred_at),
            "payload": {
                "run_id": run_id,
                "explicit_intent": False,
                "strict": False,
            },
        }
    )
    append_event(run_dir, event)
    return run_dir


def _learning_context(
    project: Path, envelope: Mapping[str, object], platform: str
) -> LearningContext:
    active_capability = None
    selected_providers: tuple[str, ...] = ()
    run_dir = _active_run_dir(project)
    if run_dir is not None:
        state = reconcile_run(run_dir)
        active_capability = state.active_capability
        if state.active_provider:
            selected_providers = (state.active_provider,)
    return LearningContext(
        current_request=prompt_from_envelope(envelope),
        project_root=str(project),
        repo_name=project.name,
        platform=platform,
        active_capability=active_capability,
        selected_providers=selected_providers,
    )


def recall_context(
    envelope: Mapping[str, object],
    platform: str,
    *,
    backend: object | None = None,
) -> str:
    """Return bounded advisory recall, failing open on every integration error."""
    try:
        project = project_from_envelope(envelope)
        context = _learning_context(project, envelope, platform)
        config = resolve_learning_config(project)
        if config.recall_owner not in SAGE_RECALL_OWNERS:
            return ""
        selected = backend
        if selected is None:
            selected = create_learning_backend(config.backend, config=config)
        return render_recall_context(recall_before_work(selected, context))  # type: ignore[arg-type]
    except Exception:
        return ""


def _extra(envelope: Mapping[str, object]) -> Mapping[str, object]:
    value = envelope.get("extra")
    return value if isinstance(value, Mapping) else {}


def _structured_event(envelope: Mapping[str, object]) -> Mapping[str, object] | None:
    value = envelope.get("sage_event")
    if isinstance(value, Mapping):
        return value
    value = _extra(envelope).get("sage_event")
    return value if isinstance(value, Mapping) else None


def _first(envelope: Mapping[str, object], *keys: str) -> object | None:
    extra = _extra(envelope)
    for key in keys:
        value = envelope.get(key)
        if value is not None:
            return value
        value = extra.get(key)
        if value is not None:
            return value
    return None


def _event_hash(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:24]


def normalized_observation(
    envelope: Mapping[str, object], *, occurred_at: str | None = None
) -> NormalizedEvent | None:
    structured = _structured_event(envelope)
    timestamp = utc_now(occurred_at)
    if structured is not None and structured.get("type") == "user.correction":
        if structured.get("explicit") is not True:
            return None
        observation = structured.get("observation_id") or _event_hash(structured)
        return NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"user-correction-{_event_hash(observation)}",
                "type": "user.correction",
                "occurred_at": timestamp,
                "payload": {
                    "explicit": True,
                    "observation_id": str(observation),
                    "message": str(structured.get("message", "")),
                },
            }
        )

    if structured is not None and structured.get("type") == "verification.recorded":
        passed = structured.get("passed")
        target = structured.get("verification_id") or structured.get("name")
        if not isinstance(passed, bool) or not isinstance(target, str) or not target.strip():
            return None
        observation = structured.get("observation_id") or _event_hash(structured)
        return NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"verification-{_event_hash(observation)}",
                "type": "verification.recorded",
                "occurred_at": timestamp,
                "payload": {
                    "verification_id": target,
                    "passed": passed,
                    "observation_id": str(observation),
                },
            }
        )

    if structured is not None and structured.get("type") == "behavior.observed":
        contradicted = structured.get("contradicts_event_id")
        if structured.get("verified") is not True or not isinstance(contradicted, str):
            return None
        observation = structured.get("observation_id") or _event_hash(structured)
        return NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"behavior-observed-{_event_hash(observation)}",
                "type": "behavior.observed",
                "occurred_at": timestamp,
                "payload": {
                    "verified": True,
                    "observation_id": str(observation),
                    "contradicts_event_id": contradicted,
                },
            }
        )

    response = _first(envelope, "tool_response", "tool_result", "result")
    tool_name = _first(envelope, "tool_name", "name")
    observation = _first(envelope, "tool_use_id", "tool_call_id", "observation_id")
    if not isinstance(tool_name, str) or response is None:
        return None
    response_map: Mapping[str, object] = response if isinstance(response, Mapping) else {}
    if isinstance(response, str):
        try:
            decoded = json.loads(response)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, Mapping):
            response_map = decoded
    success_value = response_map.get("success")
    if isinstance(success_value, bool):
        success = success_value
    else:
        success = not bool(response_map.get("error") or response_map.get("is_error"))
    error = (
        response_map.get("error_code")
        or response_map.get("error")
        or response_map.get("exit_code")
        or ("tool-error" if not success else "")
    )
    observation_id = str(observation or _event_hash(envelope))
    payload: dict[str, object] = {
        "tool_name": tool_name,
        "success": success,
        "observation_id": observation_id,
    }
    if not success:
        payload["error"] = str(error)
        payload["failure_fingerprint"] = f"{tool_name}:{error}"
    return NormalizedEvent.from_dict(
        {
            "schema": "sage-event/v1",
            "event_id": f"tool-outcome-{_event_hash(observation_id)}",
            "type": "tool.outcome",
            "occurred_at": timestamp,
            "payload": payload,
        }
    )


def _candidate_ids(run_dir: Path) -> set[str]:
    return {
        str(event.payload.get("candidate_id"))
        for event in read_events(run_dir)
        if event.type == "learning.candidate" and event.payload.get("candidate_id")
    }


def _claim_candidate_dispatch(
    run_dir: Path, candidate_id: str, *, occurred_at: str | None = None
) -> bool:
    return append_event(
        run_dir,
        NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"learning-candidate-dispatched-{candidate_id}",
                "type": "learning.candidate.dispatched",
                "occurred_at": utc_now(occurred_at),
                "payload": {
                    "run_id": run_dir.name,
                    "candidate_id": candidate_id,
                },
            }
        ),
    )


def pending_candidate_context(
    envelope: Mapping[str, object], *, occurred_at: str | None = None
) -> str:
    """Claim and render candidates persisted by observer-only platform hooks."""
    try:
        project = project_from_envelope(envelope)
        run_dir = lifecycle_run_dir(project, envelope, create=False)
        if run_dir is None:
            return ""
        rendered: list[str] = []
        for event in read_events(run_dir):
            if event.type != "learning.candidate":
                continue
            candidate_id = event.payload.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                continue
            if _claim_candidate_dispatch(
                run_dir, candidate_id, occurred_at=occurred_at
            ):
                candidate = load_candidate(run_dir, candidate_id)
                rendered.append(render_candidate_context(candidate))
        return "\n\n".join(rendered)
    except Exception:
        return ""


def complete_lifecycle_run(
    project: Path, envelope: Mapping[str, object], *, occurred_at: str | None = None
) -> Path | None:
    run_dir = lifecycle_run_dir(project, envelope, create=False)
    if run_dir is None:
        return None
    state = reconcile_run(run_dir)
    if state.status == "active":
        append_event(
            run_dir,
            NormalizedEvent.from_dict(
                {
                    "schema": "sage-event/v1",
                    "event_id": f"run-completed-{state.run_id}",
                    "type": "run.completed",
                    "occurred_at": utc_now(occurred_at),
                    "payload": {"run_id": state.run_id},
                }
            ),
        )
    return run_dir


def observe_context(
    envelope: Mapping[str, object],
    *,
    occurred_at: str | None = None,
    dispatch: bool = False,
) -> str:
    """Persist structured evidence and return only newly detected candidates."""
    try:
        project = project_from_envelope(envelope)
        event_name = str(envelope.get("hook_event_name", "")).casefold()
        if event_name in {
            "on_session_end",
            "on_session_finalize",
            "sessionend",
        }:
            complete_lifecycle_run(project, envelope, occurred_at=occurred_at)
            return ""
        event = normalized_observation(envelope, occurred_at=occurred_at)
        if event is None:
            return ""
        run_dir = lifecycle_run_dir(
            project, envelope, create=True, occurred_at=occurred_at
        )
        assert run_dir is not None
        before = _candidate_ids(run_dir)
        if not append_event(run_dir, event):
            return ""
        result = detect_learning_candidates(run_dir)
        newly_detected = [item for item in result.candidates if item.id not in before]
        if dispatch:
            newly_detected = [
                item
                for item in newly_detected
                if _claim_candidate_dispatch(
                    run_dir, item.id, occurred_at=occurred_at
                )
            ]
        return "\n\n".join(render_candidate_context(item) for item in newly_detected)
    except Exception:
        return ""


def reflection_context(
    envelope: Mapping[str, object],
    *,
    source: str,
    occurred_at: str | None = None,
) -> str:
    """Complete the lifecycle run and request one evidence-based reflection."""
    try:
        project = project_from_envelope(envelope)
        run_dir = complete_lifecycle_run(project, envelope, occurred_at=occurred_at)
        if run_dir is None:
            return ""
        request = request_reflection(
            run_dir,
            mode="evidence",
            source=source,
            occurred_at=occurred_at,
        )
        if request.requested:
            for candidate_id in request.candidate_ids:
                _claim_candidate_dispatch(
                    run_dir, candidate_id, occurred_at=occurred_at
                )
        return render_reflection_context(request)
    except Exception:
        return ""
