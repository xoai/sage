"""Parse METRIC lines from verify command stdout."""

from __future__ import annotations

import math
import re

_METRIC_RE = re.compile(r"^METRIC\s+(\w+)=(.+)$", re.MULTILINE)


def parse(stdout: str) -> dict[str, float]:
    """Extract metric name-value pairs from stdout.

    Format: METRIC <name>=<number>
    If a name appears multiple times, the last value wins.
    nan/inf are rejected (returned dict won't contain them).
    """
    metrics: dict[str, float] = {}
    for match in _METRIC_RE.finditer(stdout):
        name = match.group(1)
        raw = match.group(2).strip()
        try:
            value = float(raw)
        except ValueError:
            continue
        if math.isnan(value) or math.isinf(value):
            continue
        metrics[name] = value
    return metrics
