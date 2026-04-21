"""Memory integration for autoresearch — cross-session learning.

This module generates the structured data for sage-memory. The actual
MCP calls are made by the agent (not the runtime), since the runtime
is pure Python with no MCP access. The module provides:

- session_end_summary(): generates the structured summary for the agent to store
- format_priors(): formats retrieved memory priors for IDEATE context
"""

from __future__ import annotations

from .types import BriefConfig, Iteration, Status


def session_end_summary(
    brief: BriefConfig,
    iterations: list[Iteration],
) -> dict:
    """Generate a structured summary for sage-memory storage at session end.

    The agent should store this via sage_memory_store with tags
    ["autoresearch", metric_name, ...domain_tags].
    """
    winning = []
    losing = []
    best_value = None

    for it in iterations:
        if it.status == Status.KEEP:
            winning.append(it.description)
            val = it.metrics.get(brief.metric.name)
            if val is not None:
                if best_value is None:
                    best_value = val
                elif brief.metric.direction.value == "lower" and val < best_value:
                    best_value = val
                elif brief.metric.direction.value == "higher" and val > best_value:
                    best_value = val
        elif it.status == Status.DISCARD:
            losing.append(it.description)

    baseline_val = None
    for it in iterations:
        if it.status == Status.BASELINE:
            baseline_val = it.metrics.get(brief.metric.name)
            break

    return {
        "metric": brief.metric.name,
        "direction": brief.metric.direction.value,
        "baseline": baseline_val,
        "best_achieved": best_value,
        "iterations": len(iterations),
        "kept": len(winning),
        "winning_patterns": winning[:10],
        "losing_patterns": losing[:10],
    }


def format_summary_for_storage(summary: dict, brief: BriefConfig) -> dict:
    """Format the summary as sage_memory_store parameters.

    Returns a dict with title, content, tags, scope — ready for the
    agent to pass to sage_memory_store.
    """
    improvement = ""
    if summary["baseline"] is not None and summary["best_achieved"] is not None:
        delta = summary["best_achieved"] - summary["baseline"]
        improvement = f" ({delta:+.1f} from baseline)"

    title = (
        f"Autoresearch: {brief.goal} — "
        f"{summary['metric']}={summary['best_achieved']}{improvement}"
    )

    lines = [
        f"Goal: {brief.goal}",
        f"Metric: {summary['metric']} ({summary['direction']})",
        f"Baseline: {summary['baseline']}",
        f"Best achieved: {summary['best_achieved']}",
        f"Iterations: {summary['iterations']} ({summary['kept']} kept)",
        "",
        "Winning patterns:",
    ]
    for p in summary["winning_patterns"]:
        lines.append(f"  - {p}")

    lines.append("")
    lines.append("Losing patterns:")
    for p in summary["losing_patterns"]:
        lines.append(f"  - {p}")

    return {
        "title": title,
        "content": "\n".join(lines),
        "tags": ["autoresearch", summary["metric"], "self-learning"],
        "scope": "project",
    }


def format_priors(priors: list[dict]) -> str:
    """Format memory priors for injection into IDEATE context.

    Takes a list of memory search results (dicts with title/content)
    and returns a formatted string for the agent to use.
    """
    if not priors:
        return ""

    lines = ["## Previous autoresearch sessions on this repo\n"]
    for i, prior in enumerate(priors, 1):
        lines.append(f"### Session {i}: {prior.get('title', 'untitled')}")
        content = prior.get("content", "")
        lines.append(content[:500])
        lines.append("")

    lines.append(
        "Use winning patterns as starting points. "
        "Avoid losing patterns unless your approach is fundamentally different."
    )
    return "\n".join(lines)
