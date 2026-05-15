"""Tests for the flag parser."""

from core.flag_parser.parser import parse


def test_empty_input():
    r = parse("")
    assert r.quality_locked is False
    assert r.autonomous is False
    assert r.goal == ""
    assert r.error is None


def test_goal_only():
    r = parse("ship dark mode")
    assert r.quality_locked is False
    assert r.autonomous is False
    assert r.goal == "ship dark mode"
    assert r.error is None


def test_quality_locked_only():
    r = parse("--quality-locked ship dark mode")
    assert r.quality_locked is True
    assert r.autonomous is False
    assert r.goal == "ship dark mode"


def test_autonomous_only():
    r = parse("--autonomous design billing v2")
    assert r.quality_locked is False
    assert r.autonomous is True
    assert r.goal == "design billing v2"


def test_both_flags_order_one():
    r = parse("--quality-locked --autonomous ship feature")
    assert r.quality_locked is True
    assert r.autonomous is True
    assert r.goal == "ship feature"


def test_both_flags_order_two():
    r = parse("--autonomous --quality-locked ship feature")
    assert r.quality_locked is True
    assert r.autonomous is True
    assert r.goal == "ship feature"


def test_unknown_flag():
    r = parse("--foo bar")
    assert r.quality_locked is False
    assert r.autonomous is False
    assert r.goal == ""
    assert r.error is not None
    assert "--foo" in r.error


def test_flag_in_middle_not_parsed():
    """Flags only parsed if at the start."""
    r = parse("ship --quality-locked feature")
    assert r.quality_locked is False
    assert r.goal == "ship --quality-locked feature"


def test_flag_only_no_goal():
    r = parse("--quality-locked")
    assert r.quality_locked is True
    assert r.goal == ""
    assert r.error is None


def test_extra_whitespace():
    r = parse("   --quality-locked    ship    feature   ")
    assert r.quality_locked is True
    assert r.goal == "ship    feature"


def test_none_input():
    r = parse(None)
    assert r.quality_locked is False
    assert r.autonomous is False
    assert r.goal == ""


def test_to_dict():
    r = parse("--autonomous ship it")
    d = r.to_dict()
    assert d == {
        "quality_locked": False,
        "autonomous": True,
        "goal": "ship it",
        "error": None,
    }


def test_unknown_flag_after_valid_flag():
    """Unknown flag after a valid flag is still rejected."""
    r = parse("--quality-locked --unknown stuff")
    assert r.error is not None
    assert "--unknown" in r.error


def test_typo_in_flag():
    r = parse("--quality-lock ship")  # typo: missing 'ed'
    assert r.error is not None
    assert "--quality-lock" in r.error
