# E19 — measured runs

## Run 1 — 2026-10-26 (N=1, sage arm, claude-opus-5-5, operator config)

**Terminated: yes. Graded 6/7 as written; 7/7 under the corrected check.**
$6.48, 419 s, 61 tool calls, 3 review sub-agents, one session, no truncation.

Run with `--real-claude-config`: the operator's Claude CLI login lives in the
macOS keychain, which a run-scoped config dir cannot carry. The operator's
settings, permissions, hooks, plugins and user CLAUDE.md therefore applied to
the session — not comparable to an isolated run without that caveat. None of
the operator's `~/.claude` files changed during the run (the harness checks).

What the cycle did, from its ledger and transcript:

- **Baseline** recorded at cycle start (`verify-baseline.json`, v3): exactly
  the fixture's pre-existing red test, `test/report.test.mjs:6:1 usage report
  uses the v2 column format`; 2 tests ran.
- **Review rounds: 4** — spec 1 (STOP_ADVISORY; 2 substantive deferred),
  plan 2 (CONTINUE on one major, F-003, fixed; then STOP_CLEAN), code 1
  (STOP_ADVISORY; one cosmetic finding rejected — the NaN-clock shape the
  review report cited as "deferred to cleanup.md" before P1, now dispositioned
  in the loop).
- **Gate attempts: 6, failures 0** — every gate passed first time. Gate 5
  passed as "no new test failures; 1 pre-existing (baseline)": the exact red
  suite that made the pre-P1 loop unable to close.
- **Budget:** 4 of 10 spent (gate passes do not spend).
- **Outcome:** limiter built with 9 new passing tests, committed on
  `feat/add-rate-limiter`, the pre-existing red test left untouched, and the
  session ended on its own at /build's Step 8 checkpoint ("Sage: Build
  complete." — [A] approve / [M] merge), manifest `gate_state: gates-passed`.

For scale, the review that motivated P1 measured the same task before it:
Opus $3.93 / 65 calls, stopped after task 1 of 3 because Gate 5 could never
pass, and could not commit. Run 1 cost more and finished; the two are not a
like-for-like cost comparison.

### The check corrected after this run

As first written, the termination check accepted only `status: complete` or a
logged `STOP_BUDGET`/`ESCALATE`. That was wrong about the workflow: /build's
Step 8 ends at a user checkpoint, and `complete` is written only after the
user's [A]. A successful autonomous cycle therefore ends at `gate_state:
gates-passed` with the session over — where run 1 ended, failing that check
alone. The check now also accepts `gates-passed`; that the session ended by
itself is still asserted separately (`session_ended_itself`). Corrected after
seeing the run, and recorded here because it was.

Re-graded against the corrected scenario (same workspace and transcript): 7/7.
The `review_loop` grader's detail line reads "7 round(s)": it counts the three
checkpoint markers in `history[]`; the review rounds were 4.

Not yet measured: N>1, an isolated (non-operator-config) run, and a run where
the budget — not a clean finish — is what ends the cycle.
