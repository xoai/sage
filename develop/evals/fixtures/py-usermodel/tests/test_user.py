import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.user import User


def test_valid_user():
    assert User("Ada", "Lovelace", "ada@example.com").is_valid()


def test_initials():
    assert User("Ada", "Lovelace", "ada@example.com").initials() == "AL"
