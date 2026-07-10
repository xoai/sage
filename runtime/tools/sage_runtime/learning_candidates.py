"""Detect learning candidates from structured, persisted run evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import NormalizedEvent
from .learning_contracts import (
    LearningCandidate,
    LearningContractError,
    stable_dedupe_key,
)
from .state import append_event, read_events


DEFAULT_CONTEXT_BYTES = 2048


@dataclass(frozen=True)
class CandidateDetectionResult:
    candidates: tuple[LearningCandidate, ...]
    appended: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "appended": self.appended,
        }


def _payload(event: NormalizedEvent) -> dict[str, Any]:
    return event.to_dict()["payload"]


def _candidate_from_payload(payload: Mapping[str, object]) -> LearningCandidate:
    evidence = payload.get("evidence_refs")
    if not isinstance(evidence, list):
        raise LearningContractError("candidate evidence_refs must be a list")
    candidate_id = payload.get("candidate_id")
    trigger = payload.get("trigger")
    dedupe_key = payload.get("dedupe_key")
    return LearningCandidate(
        id=candidate_id,  # type: ignore[arg-type]
        trigger=trigger,  # type: ignore[arg-type]
        evidence_refs=tuple(evidence),  # type: ignore[arg-type]
        dedupe_key=dedupe_key,  # type: ignore[arg-type]
    )


def _normalized_failure_key(payload: Mapping[str, Any]) -> str | None:
    supplied = payload.get("failure_fingerprint")
    if isinstance(supplied, str) and supplied.strip():
        return stable_dedupe_key(supplied)
    tool_name = payload.get("tool_name")
    error = payload.get("error_code") or payload.get("error")
    if isinstance(tool_name, str) and tool_name.strip() and isinstance(error, str) and error.strip():
        return stable_dedupe_key(tool_name, error)
    return None


def _discover(events: tuple[NormalizedEvent, ...]) -> list[tuple[int, LearningCandidate]]:
    evidence_ids = {event.event_id for event in events if event.type != "learning.candidate"}
    discovered: list[tuple[int, LearningCandidate]] = []
    failures: dict[str, list[tuple[int, NormalizedEvent]]] = {}
    failed_verifications: dict[str, tuple[int, NormalizedEvent]] = {}
    recovered_targets: set[str] = set()
    seen_observations: set[str] = set()

    for index, event in enumerate(events):
        if event.type == "learning.candidate":
            continue
        payload = _payload(event)

        if event.type == "user.correction" and payload.get("explicit") is True:
            discovered.append(
                (
                    index,
                    LearningCandidate.create(
                        trigger="user-correction",
                        evidence_refs=(event.event_id,),
                    ),
                )
            )

        if event.type in {"tool.outcome", "behavior.observed"}:
            observation_raw = payload.get("observation_id")
            observation_id = (
                observation_raw.strip()
                if isinstance(observation_raw, str) and observation_raw.strip()
                else event.event_id
            )
            if observation_id in seen_observations:
                continue
            seen_observations.add(observation_id)

            if event.type == "tool.outcome" and payload.get("success") is False:
                failure_key = _normalized_failure_key(payload)
                if failure_key is not None:
                    group = failures.setdefault(failure_key, [])
                    group.append((index, event))
                    if len(group) == 2:
                        discovered.append(
                            (
                                index,
                                LearningCandidate.create(
                                    trigger="repeated-failure",
                                    evidence_refs=(
                                        group[0][1].event_id,
                                        group[1][1].event_id,
                                    ),
                                ),
                            )
                        )

            contradicted = payload.get("contradicts_event_id")
            if (
                payload.get("verified") is True
                and isinstance(contradicted, str)
                and contradicted in evidence_ids
                and contradicted != event.event_id
            ):
                discovered.append(
                    (
                        index,
                        LearningCandidate.create(
                            trigger="behavior-contradiction",
                            evidence_refs=(contradicted, event.event_id),
                        ),
                    )
                )

        if event.type == "verification.recorded":
            target = payload.get("verification_id") or payload.get("name")
            if not isinstance(target, str) or not target.strip():
                continue
            normalized_target = " ".join(target.split()).casefold()
            if payload.get("passed") is False and normalized_target not in failed_verifications:
                failed_verifications[normalized_target] = (index, event)
            elif (
                payload.get("passed") is True
                and normalized_target in failed_verifications
                and normalized_target not in recovered_targets
            ):
                failure = failed_verifications[normalized_target][1]
                discovered.append(
                    (
                        index,
                        LearningCandidate.create(
                            trigger="fail-to-pass",
                            evidence_refs=(failure.event_id, event.event_id),
                        ),
                    )
                )
                recovered_targets.add(normalized_target)

    # Distinct detectors may converge on the same logical candidate. Preserve
    # first evidence order and emit only one stable key.
    unique: dict[str, tuple[int, LearningCandidate]] = {}
    for index, candidate in discovered:
        unique.setdefault(candidate.dedupe_key, (index, candidate))
    return sorted(unique.values(), key=lambda item: item[0])


def detect_learning_candidates(run_dir: Path) -> CandidateDetectionResult:
    """Append candidate events for evidence patterns not already persisted."""
    directory = Path(run_dir)
    events = read_events(directory)
    existing: dict[str, LearningCandidate] = {}
    for event in events:
        if event.type != "learning.candidate":
            continue
        candidate = _candidate_from_payload(_payload(event))
        existing[candidate.dedupe_key] = candidate

    appended = 0
    discovered = _discover(events)
    for _, candidate in discovered:
        if candidate.dedupe_key in existing:
            continue
        evidence_by_id = {event.event_id: event for event in events}
        occurred_at = evidence_by_id[candidate.evidence_refs[-1]].occurred_at
        event = NormalizedEvent.from_dict(
            {
                "schema": "sage-event/v1",
                "event_id": f"learning-candidate-{candidate.id}",
                "type": "learning.candidate",
                "occurred_at": occurred_at,
                "payload": {
                    "run_id": directory.name,
                    "candidate_id": candidate.id,
                    "trigger": candidate.trigger,
                    "evidence_refs": list(candidate.evidence_refs),
                    "dedupe_key": candidate.dedupe_key,
                },
            }
        )
        if append_event(directory, event):
            appended += 1
        existing[candidate.dedupe_key] = candidate

    ordered = tuple(candidate for _, candidate in discovered)
    if not ordered and existing:
        ordered = tuple(existing.values())
    return CandidateDetectionResult(candidates=ordered, appended=appended)


def load_candidate(run_dir: Path, candidate_id: str) -> LearningCandidate:
    for event in read_events(Path(run_dir)):
        if event.type != "learning.candidate":
            continue
        candidate = _candidate_from_payload(_payload(event))
        if candidate.id == candidate_id:
            return candidate
    raise LearningContractError(f"learning candidate not found: {candidate_id}")


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    suffix = "\n[candidate context truncated]\n"
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) >= max_bytes:
        return suffix_bytes[:max_bytes].decode("utf-8", errors="ignore")
    prefix = encoded[: max_bytes - len(suffix_bytes)].decode(
        "utf-8", errors="ignore"
    ).rstrip()
    return prefix + suffix


def render_candidate_context(
    candidate: LearningCandidate, max_bytes: int = DEFAULT_CONTEXT_BYTES
) -> str:
    """Request the canonical skill method without authoring a learning."""
    rendered = (
        "Activate the installed canonical `sage-self-learning` skill for this "
        "evidence-backed candidate.\n"
        f"Candidate ID: {candidate.id}\n"
        f"Trigger type: {candidate.trigger}\n"
        f"Evidence event IDs: {', '.join(candidate.evidence_refs)}\n\n"
        "Inspect the referenced evidence, then follow the skill's complete method: "
        "classify the learning; author What happened, Why wrong, What's correct, "
        "and the Prevention rule; search before store; enrich or update an "
        "equivalent record; invalidate and link a correction when an old rule is "
        "wrong; and link the result to relevant tasks, modules, technologies, or "
        "code memories. The hook detected evidence only and has not supplied a "
        "prewritten learning.\n"
    )
    return _truncate_utf8(rendered, max(1, int(max_bytes)))
