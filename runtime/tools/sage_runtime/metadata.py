"""Bounded safe parsing for nested ``sage-metadata`` comment blocks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from .composition_contracts import CompositionError


_MARKER = re.compile(r"<!--[ \t]*sage-metadata\b")
_BLOCK = re.compile(
    r"<!--[ \t]*sage-metadata[ \t]*\r?\n(?P<body>.*?)-->",
    re.DOTALL,
)


def extract_sage_metadata(path: Path, max_bytes: int = 262144) -> dict[str, Any]:
    """Return one nested metadata mapping without executing YAML constructors."""

    source = Path(path)
    if max_bytes <= 0:
        raise CompositionError("max_bytes must be positive")
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise CompositionError(f"cannot read composition metadata: {source}: {exc}") from exc
    if len(raw) > max_bytes:
        raise CompositionError(
            f"composition metadata source exceeds {max_bytes} byte limit: {source}"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CompositionError(f"composition metadata is not UTF-8: {source}") from exc

    markers = list(_MARKER.finditer(text))
    if not markers:
        return {}
    if len(markers) > 1:
        raise CompositionError(f"multiple sage-metadata blocks are not allowed: {source}")
    match = _BLOCK.search(text)
    if match is None:
        line = text.count("\n", 0, markers[0].start()) + 1
        raise CompositionError(f"unterminated sage-metadata block: {source}:{line}")

    body_start_line = text.count("\n", 0, match.start("body")) + 1
    try:
        loaded = yaml.safe_load(match.group("body")) or {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = body_start_line + (mark.line if mark is not None else 0)
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        raise CompositionError(f"malformed or unsafe YAML at {source}:{line}: {problem}") from exc
    if not isinstance(loaded, Mapping):
        raise CompositionError(
            f"sage-metadata root must be a mapping: {source}:{body_start_line}"
        )
    return dict(loaded)
