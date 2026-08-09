"""Authentication. Feature work lands here."""

KNOWN_USERS = {"u1": "alice", "u2": "bob"}


def user_exists(user_id: str) -> bool:
    return user_id in KNOWN_USERS
