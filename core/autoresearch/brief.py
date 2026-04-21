"""Parse brief.md frontmatter into BriefConfig."""

from __future__ import annotations

import re
from pathlib import Path

from .types import (
    BriefConfig,
    BudgetConfig,
    Direction,
    MetricConfig,
    ScopeConfig,
    Termination,
)


def _parse_yaml_value(line: str) -> str:
    """Extract value after colon, stripping quotes."""
    _, _, val = line.partition(":")
    val = val.strip().strip('"').strip("'")
    return val


def _parse_list(lines: list[str], start: int) -> tuple[list[str], int]:
    """Parse a YAML list starting at the given index."""
    items = []
    i = start
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip().strip('"').strip("'"))
            i += 1
        else:
            break
    return items, i


def parse_brief(path: Path) -> BriefConfig:
    """Parse brief.md frontmatter into a BriefConfig."""
    text = path.read_text()

    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"No YAML frontmatter found in {path}")

    lines = fm_match.group(1).split("\n")
    data: dict = {}
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if stripped.startswith("- "):
            i += 1
            continue

        if ":" in stripped:
            key = stripped.split(":")[0].strip()
            val = _parse_yaml_value(stripped)

            if key in ("metric", "scope", "budget") and not val:
                sub: dict = {}
                i += 1
                while i < len(lines) and lines[i].startswith("  "):
                    subline = lines[i].strip()
                    if subline.startswith("- "):
                        break
                    if ":" in subline:
                        subkey = subline.split(":")[0].strip()
                        subval = _parse_yaml_value(subline)
                        if not subval and i + 1 < len(lines) and lines[i + 1].strip().startswith("- "):
                            items, i = _parse_list(lines, i + 1)
                            sub[subkey] = items
                        else:
                            sub[subkey] = subval
                    i += 1
                data[key] = sub
            else:
                data[key] = val
                i += 1
        else:
            i += 1

    metric_data = data.get("metric", {})
    scope_data = data.get("scope", {})
    budget_data = data.get("budget", {})

    writable = scope_data.get("writable", [])
    if isinstance(writable, str):
        writable = [w.strip().strip('"').strip("'") for w in writable.strip("[]").split(",")]
    frozen = scope_data.get("frozen", [])
    if isinstance(frozen, str):
        frozen = [f.strip().strip('"').strip("'") for f in frozen.strip("[]").split(",")]

    target = metric_data.get("target")
    target_val = float(target) if target else None

    per_run = int(budget_data.get("per_run_seconds", 120))
    max_iter_raw = budget_data.get("max_iterations")
    max_iter = int(max_iter_raw) if max_iter_raw else None

    term_raw = budget_data.get("termination", "interrupt")
    if target_val is not None and term_raw == "interrupt":
        term_raw = "target"

    slug_match = re.search(r"/(\d{8}-[\w-]+)/?", str(path))
    slug = slug_match.group(1) if slug_match else "session"

    return BriefConfig(
        goal=data.get("goal", ""),
        metric=MetricConfig(
            name=metric_data.get("name", "metric"),
            direction=Direction(metric_data.get("direction", "lower")),
            target=target_val,
        ),
        verify=data.get("verify", ""),
        scope=ScopeConfig(writable=writable, frozen=frozen),
        budget=BudgetConfig(
            per_run_seconds=per_run,
            max_iterations=max_iter,
            termination=Termination(term_raw),
        ),
        slug=slug,
    )
