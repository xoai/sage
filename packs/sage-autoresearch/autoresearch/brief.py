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


def _extract_value(line: str) -> str:
    """Extract value after FIRST colon, stripping surrounding quotes/whitespace."""
    _, _, val = line.partition(":")
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    return val


def _parse_list_items(lines: list[str], start: int) -> tuple[list[str], int]:
    """Parse YAML list items (lines starting with '- ') from start index."""
    items = []
    i = start
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if (item.startswith('"') and item.endswith('"')) or \
               (item.startswith("'") and item.endswith("'")):
                item = item[1:-1]
            items.append(item)
            i += 1
        else:
            break
    return items, i


def _parse_inline_list(val: str) -> list[str]:
    """Parse an inline YAML list like ["a", "b", "c"]."""
    val = val.strip()
    if not val.startswith("[") or not val.endswith("]"):
        return [val] if val else []
    inner = val[1:-1]
    items = []
    for item in inner.split(","):
        item = item.strip().strip('"').strip("'")
        if item:
            items.append(item)
    return items


def parse_brief(path: Path) -> BriefConfig:
    """Parse brief.md frontmatter into a BriefConfig.

    Note on verify commands: the parser takes everything after the first
    colon and strips surrounding quotes. Verify commands containing inner
    escaped quotes (\\") are not supported — use single quotes in the
    command or move complex commands to a .sh file.
    """
    text = path.read_text()

    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"No YAML frontmatter found in {path}")

    lines = fm_match.group(1).split("\n")

    # First pass: extract top-level and nested keys
    data: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Skip stray list items at top level
        if stripped.startswith("- "):
            i += 1
            continue

        if ":" not in stripped:
            i += 1
            continue

        key = stripped.split(":")[0].strip()
        val = _extract_value(stripped)

        # Nested block (metric, scope, budget) — value is empty, children indented
        if key in ("metric", "scope", "budget") and not val:
            sub: dict = {}
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                subline = lines[i].strip()
                if not subline:
                    i += 1
                    continue
                if subline.startswith("- "):
                    # Orphan list item in a block — skip
                    i += 1
                    continue
                if ":" in subline:
                    subkey = subline.split(":")[0].strip()
                    subval = _extract_value(subline)
                    # Check if next lines are list items
                    if not subval and i + 1 < len(lines) and lines[i + 1].strip().startswith("- "):
                        items, i = _parse_list_items(lines, i + 1)
                        sub[subkey] = items
                    elif subval.startswith("["):
                        sub[subkey] = _parse_inline_list(subval)
                        i += 1
                    else:
                        sub[subkey] = subval
                        i += 1
                else:
                    i += 1
            data[key] = sub
        elif val.startswith("["):
            data[key] = _parse_inline_list(val)
            i += 1
        else:
            data[key] = val
            i += 1

    # Build config from parsed data
    metric_data = data.get("metric", {})
    if isinstance(metric_data, str):
        metric_data = {}
    scope_data = data.get("scope", {})
    if isinstance(scope_data, str):
        scope_data = {}
    budget_data = data.get("budget", {})
    if isinstance(budget_data, str):
        budget_data = {}

    writable = scope_data.get("writable", [])
    if isinstance(writable, str):
        writable = _parse_inline_list(writable)
    frozen = scope_data.get("frozen", [])
    if isinstance(frozen, str):
        frozen = _parse_inline_list(frozen)

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
