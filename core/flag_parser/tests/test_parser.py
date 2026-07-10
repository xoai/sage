"""Tests for the flag parser."""

from core.flag_parser.parser import parse


# ── Existing tests (kept; updated for source fields) ──────────────────

def test_empty_input():
    r = parse("")
    assert r.quality_locked is False
    assert r.autonomous is False
    assert r.goal == ""
    assert r.error is None
    assert r.quality_locked_source is None
    assert r.autonomous_source is None


def test_goal_only():
    r = parse("ship dark mode")
    assert r.quality_locked is False
    assert r.autonomous is False
    assert r.goal == "ship dark mode"
    assert r.error is None
    assert r.quality_locked_source is None


def test_quality_locked_only():
    r = parse("--quality-locked ship dark mode")
    assert r.quality_locked is True
    assert r.autonomous is False
    assert r.goal == "ship dark mode"
    assert r.quality_locked_source == "flag"


def test_autonomous_only():
    r = parse("--autonomous design billing v2")
    assert r.quality_locked is False
    assert r.autonomous is True
    assert r.goal == "design billing v2"
    assert r.autonomous_source == "flag"


def test_both_flags_order_one():
    r = parse("--quality-locked --autonomous ship feature")
    assert r.quality_locked is True
    assert r.autonomous is True
    assert r.goal == "ship feature"
    assert r.quality_locked_source == "flag"
    assert r.autonomous_source == "flag"


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


def test_to_dict_includes_source_fields():
    r = parse("--autonomous ship it")
    d = r.to_dict()
    assert d == {
        "strict": False,
        "quality_locked": False,
        "autonomous": True,
        "goal": "ship it",
        "error": None,
        "strict_source": None,
        "quality_locked_source": None,
        "autonomous_source": "flag",
    }


def test_strict_is_a_supported_explicit_mode():
    r = parse("--strict --quality-locked ship it")
    assert r.strict is True
    assert r.strict_source == "flag"
    assert r.quality_locked is True
    assert r.goal == "ship it"


def test_strict_cannot_be_enabled_by_config_default():
    r = parse("ship it", defaults={"strict": True})
    assert r.strict is False
    assert r.strict_source is None


def test_unknown_flag_after_valid_flag():
    """Unknown flag after a valid flag is still rejected."""
    r = parse("--quality-locked --unknown stuff")
    assert r.error is not None
    assert "--unknown" in r.error


def test_typo_in_flag():
    r = parse("--quality-lock ship")  # typo: missing 'ed'
    assert r.error is not None
    assert "--quality-lock" in r.error


# ── New tests for config defaults + --no-* flags ──────────────────────

def test_default_quality_locked_on():
    """Defaults={quality_locked: True}, no flags → on, source 'config'."""
    r = parse("ship it", defaults={"quality_locked": True})
    assert r.quality_locked is True
    assert r.quality_locked_source == "config"
    assert r.autonomous is False
    assert r.autonomous_source is None


def test_default_autonomous_on():
    r = parse("ship it", defaults={"autonomous": True})
    assert r.autonomous is True
    assert r.autonomous_source == "config"


def test_default_overridden_by_flag():
    """Defaults on, --quality-locked passed → source is 'flag' (explicit wins)."""
    r = parse("--quality-locked ship", defaults={"quality_locked": True})
    assert r.quality_locked is True
    assert r.quality_locked_source == "flag"


def test_default_overridden_by_no_flag():
    """Defaults on, --no-quality-locked → off, source 'flag' (override recorded)."""
    r = parse("--no-quality-locked ship", defaults={"quality_locked": True})
    assert r.quality_locked is False
    assert r.quality_locked_source == "flag"


def test_no_flag_without_default():
    """--no-quality-locked alone → off, source 'flag'."""
    r = parse("--no-quality-locked ship")
    assert r.quality_locked is False
    assert r.quality_locked_source == "flag"


def test_no_autonomous_alone():
    r = parse("--no-autonomous ship")
    assert r.autonomous is False
    assert r.autonomous_source == "flag"


def test_conflict_quality_locked():
    r = parse("--quality-locked --no-quality-locked ship")
    assert r.error is not None
    assert "quality_locked" in r.error.lower() or "quality-locked" in r.error.lower()


def test_conflict_autonomous():
    r = parse("--autonomous --no-autonomous ship")
    assert r.error is not None
    assert "autonomous" in r.error.lower()


def test_conflict_does_not_affect_other_flag():
    """A conflict on one flag still reports cleanly (errors short-circuit)."""
    r = parse("--autonomous --quality-locked --no-quality-locked ship")
    assert r.error is not None


def test_flag_and_default_agree():
    """Flag wins for source label even when value matches config."""
    r = parse("--quality-locked", defaults={"quality_locked": True})
    assert r.quality_locked is True
    assert r.quality_locked_source == "flag"


def test_source_is_null_when_off_by_default():
    r = parse("ship something")
    assert r.quality_locked is False
    assert r.autonomous is False
    assert r.quality_locked_source is None
    assert r.autonomous_source is None


def test_mixed_sources():
    """One from config, one from flag."""
    r = parse("--autonomous ship", defaults={"quality_locked": True})
    assert r.quality_locked is True
    assert r.quality_locked_source == "config"
    assert r.autonomous is True
    assert r.autonomous_source == "flag"


def test_defaults_with_false_value_treated_as_no_default():
    """Config explicitly false is same as missing — no default."""
    r = parse("ship it", defaults={"quality_locked": False})
    assert r.quality_locked is False
    assert r.quality_locked_source is None


def test_defaults_empty_dict():
    r = parse("ship it", defaults={})
    assert r.quality_locked is False
    assert r.quality_locked_source is None


def test_no_flag_overrides_config_default():
    """The override scenario from the spec — defaults on, user explicitly off."""
    r = parse("--no-quality-locked fix a typo", defaults={"quality_locked": True})
    assert r.quality_locked is False
    assert r.quality_locked_source == "flag"
    assert r.goal == "fix a typo"
