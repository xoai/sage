"""Billing. Feature work lands here."""

CENTS_PER_CREDIT = 25


def credits_to_cents(credits: int) -> int:
    return credits * CENTS_PER_CREDIT
