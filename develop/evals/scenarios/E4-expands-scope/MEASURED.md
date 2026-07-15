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
