"""Session lifecycle. Feature work lands here."""

_SESSIONS = {}


def session_count() -> int:
    return len(_SESSIONS)
