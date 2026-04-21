"""Git operations for autoresearch — branch, commit, reset."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=True
    )


def create_branch(name: str, cwd: Path) -> None:
    """Create and checkout a new branch. If it exists, just checkout."""
    try:
        _run(["git", "checkout", "-b", name], cwd)
    except subprocess.CalledProcessError:
        _run(["git", "checkout", name], cwd)


def current_branch(cwd: Path) -> str:
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return result.stdout.strip()


def short_sha(cwd: Path) -> str:
    result = _run(["git", "rev-parse", "--short", "HEAD"], cwd)
    return result.stdout.strip()


def is_clean(cwd: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True
    )
    return result.stdout.strip() == ""


def commit(message: str, cwd: Path) -> str:
    """Stage all changes and commit. Returns the short SHA."""
    _run(["git", "add", "-A"], cwd)
    if is_clean(cwd):
        return short_sha(cwd)
    _run(["git", "commit", "-m", message], cwd)
    return short_sha(cwd)


def reset_hard(cwd: Path, undo_commit: bool = False) -> None:
    """Reset working tree, discarding changes.

    If undo_commit=True, also undo the last commit (reset to HEAD~1).
    Used after DECIDE when discarding or crashing — the commit from
    Phase 4 needs to be removed from the branch.
    """
    target = "HEAD~1" if undo_commit else "HEAD"
    _run(["git", "reset", "--hard", target], cwd)
    _run(["git", "clean", "-fd"], cwd)


def changed_files(cwd: Path) -> list[str]:
    """List files changed in working tree (staged + unstaged)."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"], cwd=cwd, capture_output=True, text=True
    )
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"], cwd=cwd, capture_output=True, text=True
    )
    files = set(result.stdout.strip().split("\n") + staged.stdout.strip().split("\n"))
    return [f for f in files if f]
