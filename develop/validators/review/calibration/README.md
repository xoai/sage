# Review-loop calibration (RR-27)

The fixture is `develop/evals/fixtures/py-calibration/` — a wallet spec,
an implementation with PLANTED defects, and a green happy-path suite.
Planted: 2 critical (spec-violating, each witnessable), 3 major,
3 substantive, 2 ABSENT requirements (spec clauses with no
implementation — the trace matrix's job), and 1 settled decoy (a
pre-rejected ledger entry whose region has not changed; re-raising it
is the amnesia failure).

- `answers.json` — the key: every plant with anchor + match keywords,
  thresholds, and one exemplar finding per plant (the perfect review).
- `score_calibration.py` — deterministic scorer. `--self-test` scores
  the exemplars against the key and must be perfect (wired into
  fastcheck, so key and scorer cannot drift apart silently).

Run per release, model-in-loop (budget-gated):

1. Drive a v2 review round over the fixture (E16 does review→fix→review
   end-to-end; a single review dispatch also works for prompt tuning).
2. Score the round-1 findings:
   `python3 score_calibration.py --findings <review-ledger.json>`
3. Thresholds (RR-27): recall ≥ 0.8 on planted criticals+majors,
   precision ≥ 0.7, both absences caught by matrix rows, decoy NOT
   re-raised, loop convergence ≤ 3 rounds with monotone open-weight.
   Drift in these numbers is a reviewer-prompt regression.

The decoy's seeded ledger entry lives in the E17 scenario setup
(`develop/evals/scenarios/E17-review-ledger-amnesia/`), not in the
fixture — `sage init` creates `.sage/` after the fixture is copied.
