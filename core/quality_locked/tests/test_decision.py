"""Tests for the quality-locked decision logic."""

from core.quality_locked.classifier import Counts
from core.quality_locked.decision import (
    Action,
    decide,
    is_clean,
    is_stuck,
)


def _h(*pairs):
    """Build a history list. Each pair is (critical, major)."""
    return [
        {"counts": {"critical": c, "major": m, "substantive": 0, "cosmetic": 0}}
        for c, m in pairs
    ]


def test_clean_bar_zero_findings():
    assert is_clean(Counts(0, 0, 0, 0)) is True
    assert is_clean(Counts(0, 0, 0, 5)) is True  # cosmetic allowed


def test_clean_bar_with_findings():
    assert is_clean(Counts(1, 0, 0, 0)) is False
    assert is_clean(Counts(0, 1, 0, 0)) is False
    assert is_clean(Counts(0, 0, 1, 0)) is False  # substantive blocks clean


def test_pass_action_when_clean():
    d = decide(Counts(0, 0, 0, 2), iteration=3, history=[])
    assert d.action == Action.PASS
    assert d.is_clean is True
    assert d.cap_reached is False


def test_revise_action_with_findings():
    d = decide(Counts(2, 1, 0, 0), iteration=1, history=[])
    assert d.action == Action.REVISE
    assert d.is_clean is False
    assert d.cap_reached is False
    assert d.stuck is False


def test_cap_reached_action():
    d = decide(Counts(1, 0, 0, 0), iteration=10, history=[])
    assert d.action == Action.CAP_REACHED
    assert d.cap_reached is True


def test_cap_takes_priority_over_clean():
    """Clean wins even at the cap — if it's clean, we PASS."""
    d = decide(Counts(0, 0, 0, 0), iteration=10, history=[])
    assert d.action == Action.PASS


def test_escalate_when_stuck():
    history = _h((2, 1), (2, 1), (2, 1))
    d = decide(Counts(2, 1, 0, 0), iteration=4, history=history)
    assert d.action == Action.ESCALATE
    assert d.stuck is True


def test_not_stuck_when_findings_decrease():
    history = _h((5, 2), (3, 1), (2, 1))
    d = decide(Counts(1, 0, 0, 0), iteration=4, history=history)
    assert d.action == Action.REVISE
    assert d.stuck is False


def test_not_stuck_when_findings_increase():
    history = _h((1, 0), (2, 1), (3, 2))
    assert is_stuck(history) is False  # different counts each time


def test_not_stuck_with_fewer_than_3_iterations():
    assert is_stuck(_h((2, 1), (2, 1))) is False
    assert is_stuck(_h((2, 1))) is False


def test_not_stuck_when_all_zero_counts():
    """Three iterations with zero findings each isn't 'stuck' — it's clean."""
    history = _h((0, 0), (0, 0), (0, 0))
    assert is_stuck(history) is False


def test_pass_priority_over_cap_and_stuck():
    history = _h((1, 0), (1, 0), (1, 0))
    d = decide(Counts(0, 0, 0, 0), iteration=10, history=history)
    assert d.action == Action.PASS


def test_decision_to_dict():
    d = decide(Counts(1, 0, 0, 0), iteration=2, history=[])
    out = d.to_dict()
    assert out["action"] == "REVISE"
    assert out["counts"] == {"critical": 1, "major": 0, "substantive": 0, "cosmetic": 0}
    assert out["is_clean"] is False
    assert out["cap_reached"] is False
    assert out["stuck"] is False


def test_substantive_minor_blocks_clean():
    """A substantive minor finding alone keeps the loop going."""
    d = decide(Counts(0, 0, 1, 0), iteration=1, history=[])
    assert d.action == Action.REVISE
    assert d.is_clean is False


def test_cosmetic_minor_alone_passes():
    """Cosmetic minors don't block clean bar."""
    d = decide(Counts(0, 0, 0, 5), iteration=1, history=[])
    assert d.action == Action.PASS
