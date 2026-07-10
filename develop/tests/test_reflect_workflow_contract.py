from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REFLECT = ROOT / "core" / "workflows" / "reflect.workflow.md"
LEARN = ROOT / "core" / "workflows" / "learn.workflow.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_reflect_gathers_observed_run_evidence_before_asking_user() -> None:
    text = _text(REFLECT).casefold()
    for evidence in (
        "transcript",
        "event log",
        "tool outcomes",
        "corrections",
        "artifacts",
        "verification",
        "prior learnings",
    ):
        assert evidence in text


def test_reflect_supports_evidence_and_interactive_modes() -> None:
    text = _text(REFLECT)
    assert "evidence mode" in text.casefold()
    assert "interactive mode" in text.casefold()
    assert "--interactive" in text
    assert "--evidence" in text


def test_user_feedback_is_conditional_on_unobserved_external_signal() -> None:
    text = _text(REFLECT).casefold()
    assert "unobserved external outcome" in text
    assert "personal preference" in text
    assert "stakeholder signal" in text
    assert "do not ask the user to restate" in text


def test_reflect_categories_and_candidate_format_remain_explicit() -> None:
    text = _text(REFLECT)
    for category in ("Reinforce", "Prevent", "Improve"):
        assert category in text
    for field in ("WHEN:", "CHECK:", "BECAUSE:"):
        assert field in text


def test_every_reflect_candidate_delegates_to_canonical_self_learning() -> None:
    text = _text(REFLECT).casefold()
    assert "canonical `sage-self-learning` skill" in text
    assert "one invocation per candidate" in text
    assert "classify" in text
    assert "four-part" in text
    assert "search-before-store" in text
    assert "enrich" in text
    assert "invalidate" in text
    assert "link" in text
    assert "sage_memory_store" not in text


def test_learn_workflow_delegates_corrections_instead_of_storing_ad_hoc() -> None:
    text = _text(LEARN).casefold()
    assert "canonical `sage-self-learning` skill" in text
    assert "correction" in text
    assert "search-before-store" in text
    assert "do not store correction prose directly" in text
