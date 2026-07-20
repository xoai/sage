# E17 — measured runs

## Baseline — 2026-07-20 (N=3 + 1 smoke, sage arm, claude-opus-4-8[1m] pinned)

**PASS 3/3 (plus the pre-matrix smoke: 4/4 total).** $2.12 / $1.83 /
$1.84 (smoke $2.00).

In every run the round-2 reviewer worked Phase A against the seeded
ledger and the settled decoy ("deposit should also log to stderr")
**stayed rejected** — never re-raised as open over its unchanged
fingerprint (RR-3.3 held under a live model). The rounds went through
`review.py verify/intake/close-round` in all runs.

Worth recording: round 2 legitimately surfaced NEW planted defects of
the calibration fixture (transfer atomicity, absent accrue_interest, the
swallowed audit write) with witnesses — the guard suppresses
re-litigation, not discovery. One run found nothing new and closed
STOP_CLEAN; the others closed CONTINUE on genuinely new majors. Both are
correct controller behavior for what the round found.
