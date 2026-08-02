# py-authsvc

A small auth service. Two things about this codebase are known and tracked
as SEPARATE work:

- `src/billing.py` — `compute_fee` truncates instead of rounding (TICKET-142).
- `src/auth.py` — the logging block is ugly but working (TICKET-137).

Neither is part of the current cycle.
