# Last re-measured — v1.3.5 (2026-07-15)

**sage arm · N=3 · deterministic graders · result: 3/3, no regression.**

Re-run to satisfy the eval change contract after the v1.3.5 resume close-out cost
levers touched the surfaces this scenario covers (quality-gates / build-loop / tdd
/ gate scripts). The always-on lever defaults — `gate_review: combined`,
`batch_bookkeeping`, and the `--quiet` gate scripts — do not change what this
scenario measures on the first-session path. The resume-specific behavior (the
close-out consolidation, batched bookkeeping, and inherited-red carve-out) is
proven separately by `L1-resume-fidelity` (also 3/3).

Raw results regenerate on demand under `develop/evals/results/` (gitignored);
this note is the committed record that the re-measurement happened.

## Re-measured again — round-2 levers (2026-07-15)

**sage arm · N=3 · result: 3/3, unchanged.** The round-2 levers (`resume_memory`,
`resume_test_cadence`) are resume-close-out only, so first-session behaviour here is
unaffected — confirmed 3/3, 0 truncated, 0 errored, opus-4-8[1m]. The resume path
itself is proven by `L1-resume-fidelity` (also 3/3).

## Re-measured again — mechanical bookkeeping (2026-07-15)

**sage arm · N=3 · result: 3/3, unchanged.** The one-command close-out
(`manifest.py close-out`) also applies at a first-session build's completion
checkpoint, so this scenario was re-run rather than paper-touched: 3/3, 0
truncated, 0 errored, opus-4-8[1m]. The resume path is proven separately by
`L1-resume-fidelity` (3/3, $7.50/run avg).
