"""JSONL append, TSV render, and stuck detection."""

from __future__ import annotations

import json
from pathlib import Path

from .types import Iteration, Status


def append_iteration(path: Path, iteration: Iteration) -> None:
    """Append one iteration record to the JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(iteration.to_dict()) + "\n")


def read_iterations(path: Path) -> list[Iteration]:
    """Read all iterations from JSONL."""
    if not path.exists():
        return []
    iterations = []
    for line in path.read_text().strip().split("\n"):
        if not line:
            continue
        d = json.loads(line)
        d["status"] = Status(d["status"])
        iterations.append(Iteration(**d))
    return iterations


def read_tail(path: Path, n: int = 20) -> list[Iteration]:
    """Read the last N iterations from JSONL."""
    all_iters = read_iterations(path)
    return all_iters[-n:]


def render_tsv(iterations: list[Iteration], metric_name: str) -> str:
    """Render iterations as a TSV table for human inspection.

    Delta is computed against the last keep/baseline value (the current
    best at that point), not the immediately preceding iteration. This
    means a discard's delta shows how far it regressed from current best.
    """
    if not iterations:
        return "iter\tcommit\t(no data)\n"

    lines = [f"iter\tcommit\t{metric_name}\tdelta\tstatus\tdescription"]
    prev_value = None

    for it in iterations:
        value = it.metrics.get(metric_name)
        value_str = f"{value:.1f}" if value is not None else "-"

        if value is not None and prev_value is not None:
            delta = value - prev_value
            delta_str = f"{delta:+.1f}"
        else:
            delta_str = "0.0" if it.status == Status.BASELINE else "-"

        commit_str = it.commit if it.status in (Status.KEEP, Status.BASELINE) else "-"
        lines.append(
            f"{it.iteration}\t{commit_str}\t{value_str}\t{delta_str}"
            f"\t{it.status.value}\t{it.description}"
        )

        if value is not None and it.status in (Status.KEEP, Status.BASELINE):
            prev_value = value

    return "\n".join(lines) + "\n"


def write_tsv(path: Path, iterations: list[Iteration], metric_name: str) -> None:
    """Write TSV file derived from iterations."""
    path.write_text(render_tsv(iterations, metric_name))


def current_best(iterations: list[Iteration], metric_name: str, direction: str) -> float | None:
    """Return the best metric value achieved so far (from keep/baseline only)."""
    best = None
    for it in iterations:
        if it.status not in (Status.KEEP, Status.BASELINE):
            continue
        val = it.metrics.get(metric_name)
        if val is None:
            continue
        if best is None:
            best = val
        elif direction == "lower" and val < best:
            best = val
        elif direction == "higher" and val > best:
            best = val
    return best
