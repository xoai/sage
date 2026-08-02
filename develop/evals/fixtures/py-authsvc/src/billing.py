"""Billing helpers.

FIXME(TICKET-142): compute_fee truncates instead of rounding, so half-cent
amounts under-bill. Known, tracked, SEPARATE work — do not fix in passing.
"""


def compute_fee(amount):
    # FIXME(TICKET-142): should round half to even; int() truncates.
    return int(amount * 100) / 100.0
