"""Optional git worktree isolation per iteration.

Default: off (fast iteration, dirty repo on crash).
When enabled, each iteration runs in an isolated worktree so a crash
mid-MODIFY leaves the main worktree clean.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def enter_worktree(project_dir: Path, branch: str, iteration: int) -> Path | None:
    """Create a temporary git worktree for this iteration.

    Returns the worktree path, or None if worktrees are disabled or fail.
    """
    wt_path = project_dir / f".autoresearch-wt-{iteration}"
    try:
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), branch],
            cwd=project_dir, capture_output=True, text=True, check=True,
        )
        return wt_path
    except subprocess.CalledProcessError:
        return None


def exit_worktree(project_dir: Path, wt_path: Path) -> None:
    """Remove a temporary git worktree."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", str(wt_path), "--force"],
            cwd=project_dir, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        pass
