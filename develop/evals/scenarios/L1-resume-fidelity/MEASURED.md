# Last re-measured — v1.3.5 (2026-07-15)

**sage arm · N=3 · deterministic graders · result: 3/3, no resume fidelity lost.**

This is the decisive proof for the v1.3.5 resume close-out cost levers. Session 2
resumes the interrupted cycle correctly in all three runs — precondition met
(session 1 completed Task 1), and session 2 does not restart it — with:
- `gate_review: combined` consolidating the close-out review,
- `batch_bookkeeping` deferring memory/prose to the checkpoint,
- `trust_inherited_red` skipping re-confirmation of a test the prior session
  already recorded as failing.

Runs were clean: 0 truncated, 0 errored; the 3 `interrupted` flags are the
by-design session-1 cutoff. Matches the corrected baseline (3/3). No cheaper cost
ratio is published from this run — pass-rate parity is the claim, not a discount.
