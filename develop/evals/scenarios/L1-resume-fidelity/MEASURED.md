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

## Re-measured again — round-2 levers (2026-07-15)

**sage arm · N=3 · result: 3/3, no resume fidelity lost.** The two round-2 levers —
`resume_memory: skip` and `resume_test_cadence: lean` — engaged without breaking the
resume: session 2 recovers and finishes correctly in all three runs, 0 truncated, 0
errored, on opus-4-8[1m]. Cost dropped further ($11.29 → **$8.13/run**), so unlike
`batch_bookkeeping`, these prose levers appear to hold — but that cost delta is
noisy (N=3, cross-batch) and no tightened ratio is published from it. Pass-rate
parity is the merge gate; the cost reduction is a signal, not a claim.

## Re-measured again — mechanical bookkeeping (2026-07-15)

**sage arm · N=3 · result: 3/3, no resume fidelity lost.** `manifest.py close-out`
(the one-command bookkeeping write) + machine-owned `updated:` engaged without
breaking the resume: 0 truncated, 0 errored, opus-4-8[1m]. Cost: $8.13 → **$7.50/run
avg** (runs $8.77/$8.66/$5.09 — high variance; the $5.09 run shows the floor). Fresh
ratio ~2.5× vs bare — trend down, **below-2× not yet demonstrated on this N=3**.
Workspaces were not kept, so command-adoption wasn't verified per-transcript; the
next kept profile run should confirm the bookkeeping share actually collapsed.
