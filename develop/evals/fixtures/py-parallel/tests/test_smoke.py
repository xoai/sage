"""Baseline smoke: every module imports and answers its trivial question."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src import auth, billing, models, report, session  # noqa: E402


def test_smoke():
    assert models.User("u1", "alice").user_id == "u1"
    assert auth.user_exists("u1")
    assert not auth.user_exists("nobody")
    assert session.session_count() == 0
    assert billing.credits_to_cents(4) == 100
    assert report.report_header("x") == "== x =="
