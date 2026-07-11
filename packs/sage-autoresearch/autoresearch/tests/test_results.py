"""Tests for JSONL, TSV, and stuck detection."""

import json
import tempfile
from pathlib import Path

import pytest
from core.autoresearch.results import (
    append_iteration,
    current_best,
    read_iterations,
    render_tsv,
)
from core.autoresearch.stuck import detect_stuck
from core.autoresearch.types import Iteration, Status


def _make_iter(n: int, status: Status = Status.KEEP, value: float = 100.0) -> Iteration:
    return Iteration(
        iteration=n,
        timestamp="2026-01-01T00:00:00Z",
        commit=f"abc{n:04d}" if status in (Status.KEEP, Status.BASELINE) else "",
        parent="parent",
        description=f"change {n}",
        metrics={"size": value},
        duration_s=1.0,
        status=status,
    )


def test_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "test.jsonl"
    it = _make_iter(1)
    append_iteration(path, it)
    result = read_iterations(path)
    assert len(result) == 1
    assert result[0].iteration == 1
    assert result[0].metrics == {"size": 100.0}


def test_multiple_appends(tmp_path):
    path = tmp_path / "test.jsonl"
    for i in range(5):
        append_iteration(path, _make_iter(i))
    result = read_iterations(path)
    assert len(result) == 5


def test_detect_stuck_true():
    iters = [_make_iter(i, Status.DISCARD) for i in range(5)]
    assert detect_stuck(iters, n=5) is True


def test_detect_stuck_false_not_enough():
    iters = [_make_iter(i, Status.DISCARD) for i in range(3)]
    assert detect_stuck(iters, n=5) is False


def test_detect_stuck_mixed():
    iters = [
        _make_iter(1, Status.DISCARD),
        _make_iter(2, Status.KEEP),
        _make_iter(3, Status.DISCARD),
        _make_iter(4, Status.DISCARD),
        _make_iter(5, Status.DISCARD),
    ]
    assert detect_stuck(iters, n=5) is False


def test_detect_stuck_crash_counts():
    iters = [_make_iter(i, Status.CRASH) for i in range(5)]
    assert detect_stuck(iters, n=5) is True


def test_current_best_lower():
    iters = [
        _make_iter(0, Status.BASELINE, 200),
        _make_iter(1, Status.KEEP, 180),
        _make_iter(2, Status.DISCARD, 190),
        _make_iter(3, Status.KEEP, 170),
    ]
    assert current_best(iters, "size", "lower") == 170.0


def test_current_best_higher():
    iters = [
        _make_iter(0, Status.BASELINE, 50),
        _make_iter(1, Status.KEEP, 60),
        _make_iter(2, Status.KEEP, 55),
    ]
    assert current_best(iters, "size", "higher") == 60.0


def test_render_tsv():
    iters = [
        _make_iter(0, Status.BASELINE, 200),
        _make_iter(1, Status.KEEP, 180),
    ]
    tsv = render_tsv(iters, "size")
    assert "iter\tcommit\tsize\tdelta\tstatus\tdescription" in tsv
    assert "baseline" in tsv
    assert "keep" in tsv
