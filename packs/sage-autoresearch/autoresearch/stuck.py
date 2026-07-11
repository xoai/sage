"""Stuck detection and recovery context for autoresearch."""

from __future__ import annotations

from .types import Iteration, Status


def detect_stuck(iterations: list[Iteration], n: int = 5) -> bool:
    """Return True if the last N iterations are all discard or crash."""
    if len(iterations) < n:
        return False
    tail = iterations[-n:]
    return all(it.status in (Status.DISCARD, Status.CRASH) for it in tail)


def build_recovery_context(iterations: list[Iteration]) -> str:
    """Build a structured recovery context for the agent's IDEATE phase.

    Analyzes the full iteration history to identify:
    - Clusters of similar failed ideas
    - Near-misses (small regressions that almost improved)
    - Directions that haven't been tried
    """
    if not iterations:
        return "No history to analyze."

    lines = ["## Stuck Recovery Analysis\n"]

    # Categorize all iterations
    keeps = [it for it in iterations if it.status == Status.KEEP]
    discards = [it for it in iterations if it.status == Status.DISCARD]
    crashes = [it for it in iterations if it.status == Status.CRASH]

    lines.append(f"**History:** {len(iterations)} iterations — "
                 f"{len(keeps)} kept, {len(discards)} discarded, {len(crashes)} crashed\n")

    # What worked
    if keeps:
        lines.append("**What worked (KEEP):**")
        for it in keeps:
            metric_str = ", ".join(f"{k}={v}" for k, v in it.metrics.items())
            lines.append(f"  - #{it.iteration}: {it.description} → {metric_str}")
        lines.append("")

    # What didn't work
    if discards:
        lines.append("**What didn't work (DISCARD):**")
        for it in discards[-10:]:
            metric_str = ", ".join(f"{k}={v}" for k, v in it.metrics.items())
            lines.append(f"  - #{it.iteration}: {it.description} → {metric_str}")
        if len(discards) > 10:
            lines.append(f"  ... and {len(discards) - 10} more")
        lines.append("")

    # What crashed
    if crashes:
        lines.append("**What crashed:**")
        for it in crashes[-5:]:
            lines.append(f"  - #{it.iteration}: {it.description} — {it.notes}")
        lines.append("")

    # Near-misses (discards that were close to the best)
    if keeps and discards:
        best_metrics = {}
        for it in keeps:
            for k, v in it.metrics.items():
                if k not in best_metrics:
                    best_metrics[k] = v

        near_misses = []
        for it in discards:
            for k, v in it.metrics.items():
                if k in best_metrics:
                    gap = abs(v - best_metrics[k])
                    threshold = abs(best_metrics[k]) * 0.05
                    if gap <= max(threshold, 1.0):
                        near_misses.append(it)
                        break

        if near_misses:
            lines.append("**Near-misses (within 5% of best):**")
            for it in near_misses[-5:]:
                metric_str = ", ".join(f"{k}={v}" for k, v in it.metrics.items())
                lines.append(f"  - #{it.iteration}: {it.description} → {metric_str}")
            lines.append("  Consider combining these approaches.\n")

    lines.append("**Recovery playbook:**")
    lines.append("1. Re-read ALL in-scope files (don't rely on context)")
    lines.append("2. Try combining the two best near-misses")
    lines.append("3. Try the OPPOSITE of the recent direction")
    lines.append("4. Try a radical structural change")

    return "\n".join(lines)
