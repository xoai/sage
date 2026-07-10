from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

from sage_runtime.backends.base import LearningBackend
from sage_runtime.learning_contracts import (
    LearningCandidate,
    LearningContext,
    LearningContractError,
    RecallRecord,
    RecallResult,
    stable_dedupe_key,
)


def _record(**overrides: object) -> RecallRecord:
    values: dict[str, object] = {
        "id": "lrn-pnpm",
        "title": "Use the repository package manager",
        "prevention": "Check packageManager before installing dependencies.",
        "rationale": "The repository declares pnpm.",
        "score": 0.92,
        "tags": ("self-learning", "correction"),
        "status": "active",
        "scope": "project",
        "project": "sage",
        "platforms": ("hermes",),
        "capabilities": ("change.implement",),
        "providers": ("external:brainstorm",),
        "paths": ("runtime/platforms/hermes",),
    }
    values.update(overrides)
    return RecallRecord(**values)  # type: ignore[arg-type]


def test_learning_context_is_immutable_and_preserves_selector_order() -> None:
    context = LearningContext(
        current_request="Fix package installation",
        project_root="/work/sage",
        repo_name="sage",
        platform="hermes",
        active_capability="change.implement",
        selected_providers=("sage:build", "external:brainstorm"),
        touched_subsystem="runtime/platforms/hermes",
        touched_paths=("runtime/a.py", "runtime/b.py"),
    )

    assert context.selected_providers == ("sage:build", "external:brainstorm")
    assert context.touched_paths == ("runtime/a.py", "runtime/b.py")
    with pytest.raises(AttributeError):
        context.repo_name = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_request", "x" * 4097),
        ("repo_name", "😀" * 129),
        ("platform", ""),
        ("selected_providers", ("provider",) * 33),
        ("touched_paths", ("path",) * 65),
    ],
)
def test_learning_context_enforces_utf8_byte_and_count_limits(
    field: str, value: object
) -> None:
    kwargs: dict[str, object] = {
        "current_request": "Fix package installation",
        "project_root": "/work/sage",
        "repo_name": "sage",
        "platform": "hermes",
    }
    kwargs[field] = value

    with pytest.raises(LearningContractError, match=field):
        LearningContext(**kwargs)  # type: ignore[arg-type]


def test_active_recall_record_round_trips_selectors_and_correction_link() -> None:
    record = _record(corrects="lrn-npm")
    payload = record.to_dict()

    assert payload["id"] == "lrn-pnpm"
    assert payload["status"] == "active"
    assert payload["corrects"] == "lrn-npm"
    assert payload["dedupe_key"] == record.dedupe_key
    assert payload["paths"] == ["runtime/platforms/hermes"]
    assert RecallRecord.from_dict(payload) == record


def test_record_dedupe_key_is_stable_across_ids_and_whitespace() -> None:
    first = _record(id="backend-a")
    second = _record(
        id="backend-b",
        prevention="  Check packageManager before installing dependencies.  ",
        rationale="The repository   declares pnpm.",
    )

    assert first.dedupe_key == second.dedupe_key
    assert first.dedupe_key == stable_dedupe_key(
        "check packagemanager before installing dependencies.",
        "the repository declares pnpm.",
    )


@pytest.mark.parametrize("status", ["active", "superseded", "invalidated"])
def test_record_statuses_are_explicit(status: str) -> None:
    superseded_by = "lrn-new" if status == "superseded" else None
    record = _record(status=status, superseded_by=superseded_by)
    assert record.status == status


def test_superseded_record_requires_forward_link() -> None:
    with pytest.raises(LearningContractError, match="superseded_by"):
        _record(status="superseded")


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "active", "superseded_by": "lrn-new"},
        {"corrects": "lrn-pnpm"},
        {"superseded_by": "lrn-pnpm", "status": "superseded"},
        {"status": "unknown"},
        {"id": "bad id"},
        {"scope": "team"},
    ],
)
def test_record_rejects_invalid_status_ids_and_correction_links(
    overrides: dict[str, object]
) -> None:
    with pytest.raises(LearningContractError):
        _record(**overrides)


def test_record_fields_are_byte_bounded() -> None:
    with pytest.raises(LearningContractError, match="prevention"):
        _record(prevention="😀" * 513)
    with pytest.raises(LearningContractError, match="rationale"):
        _record(rationale="x" * 1025)


@pytest.mark.parametrize(
    "trigger",
    [
        "user-correction",
        "repeated-failure",
        "fail-to-pass",
        "behavior-contradiction",
        "better-method",
    ],
)
def test_candidate_trigger_vocabulary_is_exact(trigger: str) -> None:
    candidate = LearningCandidate.create(
        trigger=trigger,
        evidence_refs=("event-2", "event-1"),
    )
    assert candidate.trigger == trigger
    assert candidate.id.startswith("candidate-")
    assert len(candidate.dedupe_key) == 64


def test_candidate_key_is_stable_for_reordered_evidence() -> None:
    first = LearningCandidate.create(
        trigger="repeated-failure", evidence_refs=("event-b", "event-a")
    )
    second = LearningCandidate.create(
        trigger="repeated-failure", evidence_refs=("event-a", "event-b")
    )

    assert first.dedupe_key == second.dedupe_key
    assert first.id == second.id
    assert first.evidence_refs == ("event-b", "event-a")


@pytest.mark.parametrize(
    ("trigger", "evidence_refs"),
    [
        ("guess", ("event-1",)),
        ("user-correction", ()),
        ("user-correction", ("event-1", "event-1")),
        ("user-correction", ("bad ref",)),
    ],
)
def test_candidate_rejects_unknown_triggers_and_bad_evidence(
    trigger: str, evidence_refs: tuple[str, ...]
) -> None:
    with pytest.raises(LearningContractError):
        LearningCandidate.create(trigger=trigger, evidence_refs=evidence_refs)


def test_recall_result_has_stable_schema_and_bounded_diagnostics() -> None:
    result = RecallResult(
        query="package manager",
        records=(_record(),),
        backend="sage-memory",
        diagnostics=("index warming",),
    )

    assert result.to_dict()["schema"] == "learning-recall/v1"
    assert result.to_dict()["records"][0]["id"] == "lrn-pnpm"
    with pytest.raises(LearningContractError, match="diagnostic"):
        RecallResult(query="q", diagnostics=("😀" * 129,))


def test_recall_result_rejects_more_than_ten_records() -> None:
    with pytest.raises(LearningContractError, match="records"):
        RecallResult(
            query="package manager",
            records=tuple(_record(id=f"lrn-{index}") for index in range(11)),
        )


def test_backend_protocol_exposes_search_and_skill_storage_operations() -> None:
    class FakeBackend:
        def search_learnings(self, query, context, limit=5):
            return RecallResult(query=query, backend="fake")

        def store_learning(self, record):
            return record

        def update_learning(self, record_id, record):
            return record

        def invalidate_learning(self, record_id, correction_id):
            return True

        def link_learning(self, source_id, target_id, relation):
            return True

        def list_learnings(self, filters=None):
            return ()

    backend: LearningBackend = FakeBackend()
    assert isinstance(backend, LearningBackend)
    assert backend.list_learnings({"status": "active"}) == ()
