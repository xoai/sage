# E16 — measured runs

## Baseline — 2026-07-20 (N=3, sage arm, claude-opus-4-8[1m] pinned)

**PASS 2/3 (majority).** $6.00 / $6.09 / $6.00 per run.

- Runs 1 and 3: 3/3 checks. The loop converged **CONTINUE → STOP_ADVISORY
  in 2 rounds**, monotone open-weight, every fix commit trailed, witnesses
  on disk, exit record written by `review.py` itself. No reviewer ever
  emitted a verdict.
- Run 2 failed one check — "no review-loop exit record" — because the
  session hit its $6 budget cap at 967s **mid-loop**: round 1 CONTINUE
  recorded, fixes landed, one substantive still open, and the closing
  round never ran. Truncation, not a controller defect (the E9/driver
  lesson: a truncated run grades identically to a broken feature). The
  partial ledger is coherent.

**Calibration scoring** (develop/validators/review/calibration/, same
three ledgers): **recall 1.0, precision 1.0, both absences caught, decoy
never re-raised — 3/3 runs**, against thresholds 0.8 / 0.7 / 2/2 / none.
All five planted criticals+majors were found in every run. Scored after
the absence-matcher instrument fix (same session): the matcher demanded
`witness.kind: trace` for absences, and runs 1/3 had demonstrated the two
absent requirements with **written failing tests** — a demonstration must
never score below an empty matrix cell.

Contrast pinned by R1 (test_review_controller.py): the same reviewer
population under v1 semantics produced the 7-iteration field pathology;
under the v2 controller the calibration artifact terminates ≤2 rounds.
