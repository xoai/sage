from src.auth import login
from src.session import create_session, get_session


def test_login_ok():
    assert login("ada", "pw")["ok"] is True


def test_login_none_user():
    assert login(None, "pw")["ok"] is False


def test_session_roundtrip():
    token = create_session("ada")
    assert get_session(token) == "ada"
