"""Tests for the config loader's strict-match contract (spec §5.4)."""

from pathlib import Path

import pytest

from core.flag_parser.config_loader import load_defaults


def write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ── No-defaults cases (fail-soft) ────────────────────────────────────

def test_none_path():
    assert load_defaults(None) == {}


def test_missing_file(tmp_path):
    assert load_defaults(tmp_path / "does-not-exist.yaml") == {}


def test_empty_file(tmp_path):
    p = write(tmp_path, "")
    assert load_defaults(p) == {}


def test_no_relevant_keys(tmp_path):
    p = write(tmp_path, "sage-version: \"1.0.0\"\nproject-name: foo\n")
    assert load_defaults(p) == {}


def test_directory_not_file(tmp_path):
    # Path points to a directory, not a file
    assert load_defaults(tmp_path) == {}


def test_explicit_false_is_no_default(tmp_path):
    p = write(tmp_path, "quality_locked: false\nautonomous: false\n")
    assert load_defaults(p) == {}


# ── Canonical matches ────────────────────────────────────────────────

def test_quality_locked_true(tmp_path):
    p = write(tmp_path, "quality_locked: true\n")
    assert load_defaults(p) == {"quality_locked": True}


def test_autonomous_true(tmp_path):
    p = write(tmp_path, "autonomous: true\n")
    assert load_defaults(p) == {"autonomous": True}


def test_both_keys_true(tmp_path):
    p = write(tmp_path, "quality_locked: true\nautonomous: true\n")
    assert load_defaults(p) == {"quality_locked": True, "autonomous": True}


def test_realistic_config_with_other_keys(tmp_path):
    p = write(tmp_path, """sage-version: "1.0.0"
project-name: "my-app"
auto_review: true
auto_qa: true
quality_locked: true
autonomous: false
command_prefix: false
""")
    assert load_defaults(p) == {"quality_locked": True}


# ── Strict-match rejections ──────────────────────────────────────────

def test_uppercase_True_rejected(tmp_path):
    p = write(tmp_path, "quality_locked: True\n")
    assert load_defaults(p) == {}


def test_uppercase_TRUE_rejected(tmp_path):
    p = write(tmp_path, "quality_locked: TRUE\n")
    assert load_defaults(p) == {}


def test_quoted_string_rejected(tmp_path):
    p = write(tmp_path, 'quality_locked: "true"\n')
    assert load_defaults(p) == {}


def test_yes_alias_rejected(tmp_path):
    p = write(tmp_path, "quality_locked: yes\n")
    assert load_defaults(p) == {}


def test_extra_whitespace_after_colon_rejected(tmp_path):
    # Two spaces between colon and value
    p = write(tmp_path, "quality_locked:  true\n")
    assert load_defaults(p) == {}


def test_no_space_after_colon_rejected(tmp_path):
    p = write(tmp_path, "quality_locked:true\n")
    assert load_defaults(p) == {}


def test_trailing_comment_rejected(tmp_path):
    p = write(tmp_path, "quality_locked: true  # comment\n")
    assert load_defaults(p) == {}


def test_indented_key_rejected(tmp_path):
    """Nested keys (not at top level) shouldn't be picked up."""
    p = write(tmp_path, "defaults:\n  quality_locked: true\n")
    assert load_defaults(p) == {}


def test_partial_match_rejected(tmp_path):
    """Key must be exactly quality_locked or autonomous."""
    p = write(tmp_path, "quality_locked_default: true\n")
    assert load_defaults(p) == {}


# ── Robustness ───────────────────────────────────────────────────────

def test_mixed_canonical_and_rejected(tmp_path):
    """Canonical match wins even when other variants present."""
    p = write(tmp_path, """quality_locked: True
quality_locked: true
autonomous: "true"
""")
    assert load_defaults(p) == {"quality_locked": True}


def test_unicode_file(tmp_path):
    """UTF-8 content with non-ASCII chars elsewhere shouldn't break parsing."""
    p = write(tmp_path, "project-name: 日本語\nquality_locked: true\n")
    assert load_defaults(p) == {"quality_locked": True}
