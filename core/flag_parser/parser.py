"""Deterministic flag parser for workflow $ARGUMENTS.

Recognized flags (boolean, no value):
- --strict               enable runtime invariant enforcement for this run
- --quality-locked       turn quality-locked mode on
- --no-quality-locked    turn quality-locked mode off (overrides config default)
- --autonomous           turn autonomous mode on
- --no-autonomous        turn autonomous mode off (overrides config default)

Parsing rules:
1. Flags must appear at the start of the input, before any goal text.
2. Flag order doesn't matter.
3. Unknown flags (starting with --) produce an error.
4. Goal is everything after the flags, trimmed.
5. No values — flags are bare switches.
6. Defaults (from .sage/config.yaml) apply only when no flag for that
   mode is passed. Any flag (positive or --no-) always wins over config.
7. Passing both --quality-locked and --no-quality-locked (same for
   autonomous) is a user error.

Precedence (highest to lowest):
1. --no-X flag      → off, source="flag"
2. --X flag         → on, source="flag"
3. config default   → on if config has X: true, source="config"
4. nothing          → off, source=None
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

POSITIVE_FLAGS = {"--strict", "--quality-locked", "--autonomous"}
NEGATIVE_FLAGS = {"--no-quality-locked", "--no-autonomous"}
FLAG_TO_KEY = {
    "--strict": "strict",
    "--quality-locked": "quality_locked",
    "--no-quality-locked": "quality_locked",
    "--autonomous": "autonomous",
    "--no-autonomous": "autonomous",
}
ALL_FLAGS = POSITIVE_FLAGS | NEGATIVE_FLAGS
SUPPORTED_FOR_ERROR = sorted(ALL_FLAGS)


@dataclass
class ParseResult:
    strict: bool
    quality_locked: bool
    autonomous: bool
    goal: str
    error: Optional[str] = None
    # Source of each value: "flag" (any flag form), "config", or None
    # (when the value is the implicit default-off).
    strict_source: Optional[str] = None
    quality_locked_source: Optional[str] = None
    autonomous_source: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse(arguments: str, defaults: Optional[dict] = None) -> ParseResult:
    """Parse $ARGUMENTS into flag state and goal.

    Args:
        arguments: The $ARGUMENTS string from the slash command.
        defaults: Optional dict of {"quality_locked": bool, "autonomous": bool}
            from .sage/config.yaml. Only `True` values become defaults;
            False/missing means no default.

    Returns:
        ParseResult with resolved values, goal, error (or None), and
        source for each value.
    """
    if arguments is None:
        arguments = ""
    defaults = defaults or {}

    # Track each key's state as we parse: "positive", "negative", or None
    flag_state: dict[str, Optional[str]] = {
        "strict": None,
        "quality_locked": None,
        "autonomous": None,
    }

    remaining = arguments.strip()

    while remaining.startswith("--"):
        parts = remaining.split(None, 1)
        token = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        if token not in ALL_FLAGS:
            supported = ", ".join(SUPPORTED_FOR_ERROR)
            return ParseResult(
                False, False, False, "",
                f"Unknown flag '{token}'. Supported flags: {supported}.",
            )

        key = FLAG_TO_KEY[token]
        new_state = "positive" if token in POSITIVE_FLAGS else "negative"

        if flag_state[key] is not None and flag_state[key] != new_state:
            # Conflict: --X and --no-X both passed for the same key
            return ParseResult(
                False, False, False, "",
                f"Conflicting flags for {key}: both --{key.replace('_', '-')} "
                f"and --no-{key.replace('_', '-')} passed.",
            )
        flag_state[key] = new_state
        remaining = rest.lstrip()

    # Resolve each key by precedence
    def resolve(key: str) -> tuple[bool, Optional[str]]:
        state = flag_state[key]
        if state == "positive":
            return True, "flag"
        if state == "negative":
            return False, "flag"
        # No flag passed — consult config defaults
        if key != "strict" and defaults.get(key) is True:
            return True, "config"
        return False, None

    strict_value, strict_source = resolve("strict")
    ql_value, ql_source = resolve("quality_locked")
    auto_value, auto_source = resolve("autonomous")

    return ParseResult(
        strict=strict_value,
        quality_locked=ql_value,
        autonomous=auto_value,
        goal=remaining,
        error=None,
        strict_source=strict_source,
        quality_locked_source=ql_source,
        autonomous_source=auto_source,
    )
