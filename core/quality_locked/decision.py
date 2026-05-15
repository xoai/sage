"""Decide the next action given current counts, iteration number, and history.

Actions:
- PASS:          Clean bar reached (no Critical/Major/substantive Minor). Exit loop.
- REVISE:        Findings exist, iterate. Agent applies fixes and re-reviews.
- CAP_REACHED:   Hit iteration cap (10). User must choose F/R/E/A.
- ESCALATE:      3 iterations with unchanged Critical+Major counts. Suggest /architect.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .classifier import Counts

ITERATION_CAP = 10
STUCK_THRESHOLD = 3  # consecutive iterations with same critical+major count


class Action(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    CAP_REACHED = "CAP_REACHED"
    ESCALATE = "ESCALATE"


@dataclass
class Decision:
    counts: Counts
    is_clean: bool
    cap_reached: bool
    stuck: bool
    action: Action

    def to_dict(self) -> dict:
        return {
            "counts": self.counts.to_dict(),
            "is_clean": self.is_clean,
            "cap_reached": self.cap_reached,
            "stuck": self.stuck,
            "action": self.action.value,
        }


def is_clean(counts: Counts) -> bool:
    """The clean bar: zero Critical, zero Major, zero substantive Minor.
    Cosmetic Minors are allowed."""
    return counts.critical == 0 and counts.major == 0 and counts.substantive == 0


def is_stuck(history: list[dict]) -> bool:
    """Detect when the last STUCK_THRESHOLD iterations show the same
    critical+major count — suggests structural rather than fixable issues."""
    if len(history) < STUCK_THRESHOLD:
        return False
    tail = history[-STUCK_THRESHOLD:]
    sums = []
    for entry in tail:
        c = entry.get("counts", {})
        sums.append(c.get("critical", 0) + c.get("major", 0))
    # Stuck only if all the same AND there are findings (zero doesn't count)
    return len(set(sums)) == 1 and sums[0] > 0


def decide(counts: Counts, iteration: int, history: list[dict]) -> Decision:
    """Run the decision logic.

    Order matters: PASS > CAP_REACHED > ESCALATE > REVISE.
    """
    clean = is_clean(counts)
    if clean:
        return Decision(counts, True, False, False, Action.PASS)

    cap = iteration >= ITERATION_CAP
    if cap:
        return Decision(counts, False, True, is_stuck(history), Action.CAP_REACHED)

    stuck = is_stuck(history)
    if stuck:
        return Decision(counts, False, False, True, Action.ESCALATE)

    return Decision(counts, False, False, False, Action.REVISE)
