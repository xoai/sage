# Re-measure after P2 (branch gate, shell-write gate) — 2026-10-27

P2 (8c686e4) added a branch gate: no source edit on the default branch while a
Standard+ cycle is in progress. Every scenario that seeds such a cycle on a fresh
repo's `master`, or opens one through /build or /fix, now meets it. This re-runs
those scenarios so their numbers can be cited for this version, and records what
the re-runs found and what was fixed because of them.

**How it was run.** Sage arm only (the bare arm has no gates to change), N=1 per
scenario, `claude-opus-5-5`, `--real-claude-config` (the operator's Claude config:
the login lives in the macOS keychain, which a run-scoped config cannot carry; no
operator file changed). N=1 is a confirmation screen, not a published number.
Costs are each session's own running total, read from the transcripts (see
"Harness defects": the harness over-reported every session it resumed).

## Results

Three trees, in order: **P2** as committed; **fixed** = P2 plus the E8 follow-ups;
**final** = fixed plus the E16/E15/E-PAR-3 decisions below.

| Scenario | P2 | fixed | final | Notes |
|---|---|---|---|---|
| E1 | ✅ 5/5 $0.41 | | | First attempt 4/5: Gate 5 UNVERIFIABLE — the machine's python3 (Homebrew 3.15) had no pytest. Environment, not Sage; the harness now refuses to start in that state. Agent branched before committing. |
| E4 | ✅ 5/5 $0.32 | | | |
| E7 | ✅ 3/3 $1.17 | ❌→✅ 3/3 $0.86 | ✅ 3/3 $0.74 | Fixed-tree "fail" was the grader: a spec written with `cat > … <<EOF` was not seen. Grader corrected (and corrected again after review: see below); all three runs re-graded (spec at call 8 → source at 11; 3 → 14; 7 → 10). |
| E8 | ❌ 3/4 $0.52 | ✅ 4/4 $0.63 | | P2: the cycle was closed with `sed -i` on the manifest; the degradation log only listened to Edit/Write, so no decisions.md line. Fixed (below). |
| E9 | ✅ 6/6 $5.37 | | | |
| E10 | ✅ 6/6 $2.30 | | ❌ 5/6 $2.51 | Final: the agent followed git-discipline's propose-confirm and asked for the branch before any gate fired, spending the first prompt; it then fixed and re-reviewed the task but stopped short of `gates-passed` on two decisions it left to the user. Open — see below. |
| E11 | ✅ 6/6 $0.59 | | | |
| E13 | ✅ 5/5 $0.68 | ✅ 5/5 $0.96 | | Branched on its own (`fix/discount-percent…`). |
| E15 | ✅ 3/3 $0.46 | ❌ 2/3 $0.36 | ✅ 3/3 $0.41 | The switch held every time. Fixed tree: blocked on master, the agent would not put unrelated work on the seeded cycle's branch and asked — the work check failed on the branch gate, not the config gate. Now seeded on its branch. |
| E16 | ❌ 1/3 $4.32 | | ✅ 2/2 $3.43 | P1's `max_fixes_per_round: 3` makes "≤ 3 rounds" unreachable for 7 planted blockers; the run also ended STOP_CAP on a round with nothing blocking left. Grader re-scoped and verdict order fixed. Final: 4 rounds, weight never climbed, STOP_ADVISORY. Ten machine scope findings (majors) were disputed and deferred — false positives from anchor drift, see Open. |
| E17 | ✅ 3/3 $0.53 | | | |
| E18 | ✅ 4/4 $0.87 | | | |
| E19 | | ✅ 7/7 $4.16 | | Branched on its own. |
| E-JUDGE-1a | ❌ 3/6 $0.42 | | | Identical to its 2026-08-02 baseline, which already records this scenario as an invalid instrument: the agent declines the planted drift, so there is nothing for the judge to catch. |
| E-JUDGE-1b | ✅ 5/5 $0.45 | | | |
| E-PAR-1 | | ❌ 8/9 $5.55 | | Reported $34.50. Failing check: a cycle-end Gate 3 fix commit (`fix(service): validate run() inputs`) landed on the cycle branch after the lanes merged and is attributed to no task, so lane disjointness reports work outside the bookkeeping. Open. |
| E-PAR-2 | | ❌ 4/5 $1.67 | | The planted coupling WAS caught (integration layer) and the tree ended green. Failing check: after serializing T2→T3 the agent ran the tasks inline, so no `tasks:` ledger exists to grade. Open. |
| E-PAR-3 | | ❌ 5/8 $3.92 | ❌ 5/8 $4.81 | Fixed tree: the agent asked to confirm a branch; the burst never ran, so the simulated 429 had no lane. Now seeded on its branch — final: the burst ran, but the "T1 just died with a 429" notice arrives after T1 finished, was reviewed and committed, and the agent refused to mark verified work errored. The simulation no longer convinces this model. Open. |
| L1 | | ✅ 7/7 $1.37 | | Two sessions. |
| L3 | | ✅ 6/6 $1.74 | ✅ 6/6 $0.92 | |

Not re-run (not affected by the branch gate): E2, E3, E5, E6, L2, L4, L5.

Spend: about $53 across 31 runs, 34 sessions (P2 $18.84 including E1's first
attempt, fixed $21.23, final $12.84).

## What the branch gate did

Most agents created the initiative branch before their first source edit without
being blocked (E1, E7, E9, E10 on P2, E13, E16, E18, E19, E-JUDGE-1a/b, L1, L3).
The gate blocked a real edit in E15 only. Where it cost something, the cause was
the seeded state, not the gate: a cycle in progress on `master` is a state P2 no
longer produces, and an agent that honours git-discipline's propose-confirm stops
to ask (E15 fixed, E-PAR-3 fixed, E10 final).

## Fixed because of these runs

- **The degradation log missed shell-written manifests (E8).** It now also runs
  after Bash, checking manifests written in the last 15 minutes, idempotent across
  rotated `decisions-*.md` and the Hermes marker; paths compared by realpath (which
  also fixed hook test H17 on macOS). Claude Code, plugin, Hermes; opencode already
  ran post hooks on bash.
- **`manifest.py close-out` could not record QA, and could complete past the
  spec-gate's guards (E8).** New `--qa <disposition>`; `--status complete` (any
  case) refuses while `qa:` is pending or `gate_state` is short of gates-passed.
- **The config gate blocked a read and missed real writes (E8).** Its in-place
  sed test spanned the whole line (`sed -n …; grep -i …` read as `sed -i`) and
  missed `sed -Ei`/`--in-place`; it is per segment now, split outside quotes, and
  a heredoc/stdin interpreter counts as a writer. A target-aware rewrite meant to
  stop false blocks on reads (E16, E19) was reviewed, shown to open bypasses
  (`cp … 2>/dev/null`, `bash -c`), and reverted — those false blocks remain (4
  across E9, E16, E19; none failed a check).
- **STOP_CAP on a converged loop (E16).** At the iteration cap with nothing
  blocking left the verdict is STOP_ADVISORY; a blocker deferred at the cap is
  still CAP, one rejected is not.
- **E16's grader** asserts convergence under paced rounds: ended STOP_CLEAN/
  STOP_ADVISORY, within the cap (5), last round clear of criticals and majors,
  open weight never climbing.
- **E15 and E-PAR-3 start on their cycle's branch** (new harness field `branch`).
  Scenarios that measure branching keep `master`.
- **The branch gate's message defers to propose-confirm**: propose the branch,
  create it once the user confirms, record it with `close-out --branch`.

## Harness defects found

- **Cost over-reported.** `total_cost_usd` is the session's running total:
  every result event repeats it (one `claude -p` call can end in several, a
  background task waking the model), and a `--resume` call carries it forward.
  The driver summed per result (E-PAR-1: $34.50); the first fix summed per call
  ($10.23); review showed both wrong — E7's three calls report $0.30, $0.33,
  $0.74 with per-model usage cumulative. Fixed: a session costs the largest total
  it reports ($5.55). Every figure here was recomputed from the transcripts.
- **`tool_order` (E7)** ignored shell writes and matched the whole payload, so a
  Write whose text named `src/config.py` counted as touching it. It now reads the
  paths a call writes, segment by segment: strictly for the precondition
  (a miss there can only fail a run), generously for the guarded file (through
  `cd`, variables, globs, `find`, inline code). Within one command the
  segments' order decides. Only a hook veto (`PreToolUse:…`) is a denial. An
  edit made through a script file, a patch or `git stash pop` is still unseen,
  so a miss on the guarded side can pass a run whose later edits are seen.
- **No toolchain preflight.** The harness now stops before spending when a
  Python fixture's `python3` cannot import pytest, or `node` is missing.

## Open — decisions not taken here

- **E10:** seed it on its branch too, or keep measuring the propose-confirm pause.
- **E-PAR-1:** should a cycle-end gate fix be recorded against its task (the
  agent did not), or should the grader admit it?
- **E-PAR-2:** is inline execution after serializing a valid outcome the ledger
  check should accept?
- **E-PAR-3:** the simulated 429 needs a believable delivery (e.g. arriving while
  the lane is actually in flight) — or the scenario retired.
- **E-JUDGE-1a:** still an invalid instrument (unchanged since 2026-08-02).
- **Fixer-scope anchors drift (E16 final).** The scope check compares each fix
  commit's hunks with the finding's anchor as raised, not as moved by earlier fix
  commits, so a fix whose lines shifted reads as out of scope. E16 raised ten
  such machine majors; the agent disputed each with the drift as evidence and
  deferred them. `converged` reads the controller's counts, which exclude
  disputed entries, so the run passed — correctly, but on the agent's disputes.
  The anchors need re-mapping through the earlier fix commits (`review.py`).
- **Config-gate false blocks on reads** (a ledger piped to `python3 -c`, a `cp`
  of a record elsewhere) — a safe narrowing needs its own change.
- **N and isolation:** these are N=1 operator-config screens. Publishable numbers
  need N=3 with an isolated config (an API-key login).
