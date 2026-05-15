"""Deterministic flag parser for workflow $ARGUMENTS.

Recognized flags (boolean, no value):
- --quality-locked
- --autonomous

Parsing rules:
1. Flags must appear at the start of the input, before any goal text.
2. Flag order doesn't matter.
3. Unknown flags (starting with --) produce an error.
4. Goal is everything after the flags, trimmed.
5. No values — flags are bare switches.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

SUPPORTED_FLAGS = ("--quality-locked", "--autonomous")


@dataclass
class ParseResult:
    quality_locked: bool
    autonomous: bool
    goal: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse(arguments: str) -> ParseResult:
    """Parse $ARGUMENTS into flag state and goal.

    Examples:
        parse("ship dark mode")
            → ParseResult(False, False, "ship dark mode", None)

        parse("--quality-locked ship dark mode")
            → ParseResult(True, False, "ship dark mode", None)

        parse("--autonomous --quality-locked ship dark mode")
            → ParseResult(True, True, "ship dark mode", None)

        parse("--foo bar")
            → ParseResult(False, False, "", "Unknown flag '--foo'. ...")
    """
    if arguments is None:
        return ParseResult(False, False, "", None)

    remaining = arguments.strip()
    quality_locked = False
    autonomous = False

    while remaining.startswith("--"):
        # Split off the first whitespace-separated token
        parts = remaining.split(None, 1)
        token = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        if token == "--quality-locked":
            quality_locked = True
        elif token == "--autonomous":
            autonomous = True
        else:
            supported = ", ".join(SUPPORTED_FLAGS)
            return ParseResult(
                False, False, "",
                f"Unknown flag '{token}'. Supported flags: {supported}.",
            )

        remaining = rest.lstrip()

    return ParseResult(quality_locked, autonomous, remaining, None)
