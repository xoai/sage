"""Tests for METRIC line parser."""

import pytest
from core.autoresearch.harness import parse


def test_single_metric():
    assert parse("METRIC bundle_kb=205.7") == {"bundle_kb": 205.7}


def test_multiple_metrics():
    stdout = "METRIC size=100\nsome output\nMETRIC time=3.14\n"
    assert parse(stdout) == {"size": 100.0, "time": 3.14}


def test_duplicate_name_last_wins():
    stdout = "METRIC x=1\nMETRIC x=2\nMETRIC x=3\n"
    assert parse(stdout) == {"x": 3.0}


def test_scientific_notation():
    assert parse("METRIC val=1.5e2") == {"val": 150.0}


def test_negative_number():
    assert parse("METRIC delta=-3.5") == {"delta": -3.5}


def test_integer():
    assert parse("METRIC count=42") == {"count": 42.0}


def test_nan_rejected():
    assert parse("METRIC x=nan") == {}


def test_inf_rejected():
    assert parse("METRIC x=inf") == {}
    assert parse("METRIC x=-inf") == {}


def test_no_metric_lines():
    assert parse("just some output\nno metrics here\n") == {}


def test_empty_string():
    assert parse("") == {}


def test_malformed_value():
    assert parse("METRIC x=not_a_number") == {}


def test_metric_mixed_with_output():
    stdout = """Building project...
[webpack] compiled in 2.3s
METRIC bundle_kb=205.7
Done.
"""
    assert parse(stdout) == {"bundle_kb": 205.7}


def test_metric_with_spaces_in_value():
    assert parse("METRIC x= 42.0 ") == {"x": 42.0}
