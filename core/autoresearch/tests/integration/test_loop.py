"""Integration test: run autoresearch loop against the fixture project."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from core.autoresearch.brief import parse_brief
from core.autoresearch.loop import run_baseline
from core.autoresearch.results import read_iterations
from core.autoresearch.types import Status
from core.autoresearch import git

FIXTURE_DIR = Path(__file__).parent.parent / "fixture"


@pytest.fixture
def fixture_repo(tmp_path):
    """Create a git repo from the fixture with a known initial state."""
    proj = tmp_path / "project"
    proj.mkdir()

    # Copy fixture files
    shutil.copytree(FIXTURE_DIR / "src", proj / "src")
    shutil.copy(FIXTURE_DIR / "verify.sh", proj / "verify.sh")
    os.chmod(proj / "verify.sh", 0o755)

    # Init git repo
    subprocess.run(["git", "init"], cwd=proj, capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=proj, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=proj, capture_output=True, check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    return proj


def test_baseline_produces_metric(fixture_repo, tmp_path):
    """Baseline run should parse the METRIC line from verify.sh."""
    brief = parse_brief(FIXTURE_DIR / "brief.md")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    git.create_branch(brief.branch_name, fixture_repo)
    baseline = run_baseline(brief, work_dir, fixture_repo)

    assert baseline is not None
    assert baseline.status == Status.BASELINE
    assert "size_bytes" in baseline.metrics
    assert baseline.metrics["size_bytes"] > 0


def test_jsonl_written_after_baseline(fixture_repo, tmp_path):
    """JSONL file should exist with one entry after baseline."""
    brief = parse_brief(FIXTURE_DIR / "brief.md")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    git.create_branch(brief.branch_name, fixture_repo)
    run_baseline(brief, work_dir, fixture_repo)

    iterations = read_iterations(work_dir / "autoresearch.jsonl")
    assert len(iterations) == 1
    assert iterations[0].iteration == 0
    assert iterations[0].status == Status.BASELINE


def test_tsv_written_after_baseline(fixture_repo, tmp_path):
    """TSV file should exist and contain header + baseline row."""
    brief = parse_brief(FIXTURE_DIR / "brief.md")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    git.create_branch(brief.branch_name, fixture_repo)
    run_baseline(brief, work_dir, fixture_repo)

    tsv = (work_dir / "results.tsv").read_text()
    assert "size_bytes" in tsv
    assert "baseline" in tsv


def test_dirty_tree_refused(fixture_repo, tmp_path):
    """Session should refuse to start on a dirty working tree."""
    brief = parse_brief(FIXTURE_DIR / "brief.md")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    # Make tree dirty
    (fixture_repo / "dirty.txt").write_text("uncommitted")

    from core.autoresearch.loop import run_session
    # Should return without crashing (prints error, returns)
    run_session(brief, work_dir, fixture_repo)

    # No JSONL should be created
    assert not (work_dir / "autoresearch.jsonl").exists()
