"""Shared domain types. Every feature module builds on what lives here."""


class User:
    """A minimal user record."""

    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name
