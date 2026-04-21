"""Tests for memory integration."""

from core.autoresearch.memory import (
    format_priors,
    format_summary_for_storage,
    session_end_summary,
)
from core.autoresearch.types import (
    BriefConfig,
    BudgetConfig,
    Direction,
    Iteration,
    MetricConfig,
    ScopeConfig,
    Status,
)


def _brief():
    return BriefConfig(
        goal="Reduce bundle size",
        metric=MetricConfig(name="bundle_kb", direction=Direction.LOWER, target=200),
        verify="bash verify.sh",
        scope=ScopeConfig(writable=["src/**"], frozen=[]),
        budget=BudgetConfig(),
        slug="test",
    )


def _iterations():
    return [
        Iteration(0, "t", "abc", "abc", "initial", {"bundle_kb": 300}, 1.0, status=Status.BASELINE),
        Iteration(1, "t", "def", "abc", "tree-shake lodash", {"bundle_kb": 280}, 1.0, status=Status.KEEP),
        Iteration(2, "t", "", "def", "switch bundler", {"bundle_kb": 310}, 1.0, status=Status.DISCARD),
        Iteration(3, "t", "ghi", "def", "lazy-load admin", {"bundle_kb": 250}, 1.0, status=Status.KEEP),
        Iteration(4, "t", "", "ghi", "remove polyfills", {}, 1.0, status=Status.CRASH),
    ]


def test_session_end_summary():
    summary = session_end_summary(_brief(), _iterations())
    assert summary["metric"] == "bundle_kb"
    assert summary["baseline"] == 300
    assert summary["best_achieved"] == 250
    assert summary["iterations"] == 5
    assert summary["kept"] == 2
    assert "tree-shake lodash" in summary["winning_patterns"]
    assert "lazy-load admin" in summary["winning_patterns"]
    assert "switch bundler" in summary["losing_patterns"]


def test_format_for_storage():
    summary = session_end_summary(_brief(), _iterations())
    params = format_summary_for_storage(summary, _brief())
    assert "title" in params
    assert "content" in params
    assert "autoresearch" in params["tags"]
    assert "bundle_kb" in params["tags"]
    assert params["scope"] == "project"
    assert "Winning patterns" in params["content"]


def test_format_priors_empty():
    assert format_priors([]) == ""


def test_format_priors_with_data():
    priors = [
        {"title": "Previous session", "content": "Winning: lazy-load\nLosing: esbuild"},
    ]
    result = format_priors(priors)
    assert "Previous autoresearch sessions" in result
    assert "Previous session" in result
    assert "winning patterns" in result.lower()
