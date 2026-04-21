"""Scope enforcement — check changed files against writable/frozen globs."""

from __future__ import annotations

from fnmatch import fnmatch


def check_scope(
    changed_files: list[str],
    writable: list[str],
    frozen: list[str],
) -> tuple[bool, list[str]]:
    """Check if changed files are within allowed scope.

    Returns (ok, violations) where violations lists files that either
    match a frozen glob or don't match any writable glob.
    """
    violations = []
    for f in changed_files:
        if any(fnmatch(f, pat) for pat in frozen):
            violations.append(f"frozen: {f}")
            continue
        if writable and not any(fnmatch(f, pat) for pat in writable):
            violations.append(f"outside writable scope: {f}")

    return len(violations) == 0, violations
