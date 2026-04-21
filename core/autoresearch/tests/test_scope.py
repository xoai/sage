"""Tests for scope enforcement."""

from core.autoresearch.scope import check_scope


def test_all_writable():
    ok, v = check_scope(["src/a.ts", "src/b.ts"], ["src/**"], [])
    assert ok is True
    assert v == []


def test_frozen_violation():
    ok, v = check_scope(["package.json"], ["src/**"], ["package.json"])
    assert ok is False
    assert any("frozen" in x for x in v)


def test_outside_writable():
    ok, v = check_scope(["docs/readme.md"], ["src/**"], [])
    assert ok is False
    assert any("outside" in x for x in v)


def test_no_writable_constraint():
    ok, v = check_scope(["anything.txt"], [], [])
    assert ok is True


def test_frozen_takes_priority():
    ok, v = check_scope(["src/config/db.ts"], ["src/**"], ["src/config/**"])
    assert ok is False
    assert any("frozen" in x for x in v)
