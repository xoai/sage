"""Scope enforcement — check changed files against writable/frozen globs."""

from __future__ import annotations

from fnmatch import fnmatch


def _matches(filepath: str, pattern: str) -> bool:
    """Check if a filepath matches a glob pattern, supporting ** recursion.

    ** matches zero or more directory segments.
    src/**/*.ts matches src/a.ts, src/x/a.ts, src/x/y/a.ts.
    src/** matches anything under src/.
    """
    if "**" not in pattern:
        return fnmatch(filepath, pattern)

    # Split on ** and match each segment
    parts = pattern.split("**")
    if len(parts) != 2:
        return fnmatch(filepath, pattern)

    prefix, suffix = parts
    # Remove trailing/leading slashes from the split
    prefix = prefix.rstrip("/")
    suffix = suffix.lstrip("/")

    # filepath must start with prefix
    if prefix and not filepath.startswith(prefix + "/") and filepath != prefix:
        return False

    # Get the part after prefix
    if prefix:
        remainder = filepath[len(prefix):].lstrip("/")
    else:
        remainder = filepath

    # If no suffix, ** matches everything under prefix
    if not suffix:
        return True

    # The suffix must match the filename or tail portion
    # Try matching against every possible tail of the remainder
    segments = remainder.split("/")
    for i in range(len(segments)):
        candidate = "/".join(segments[i:])
        if fnmatch(candidate, suffix):
            return True

    return False


def check_scope(
    changed_files: list[str],
    writable: list[str],
    frozen: list[str],
) -> tuple[bool, list[str]]:
    """Check if changed files are within allowed scope.

    Returns (ok, violations) where violations lists files that either
    match a frozen glob or don't match any writable glob.
    Supports ** for recursive directory matching.
    """
    violations = []
    for f in changed_files:
        if any(_matches(f, pat) for pat in frozen):
            violations.append(f"frozen: {f}")
            continue
        if writable and not any(_matches(f, pat) for pat in writable):
            violations.append(f"outside writable scope: {f}")

    return len(violations) == 0, violations
