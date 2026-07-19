---
name: quality-locked
description: >
  When --quality-locked is active, loop review/revise at each Quality
  Gate until findings reach a clean bar (no Critical, no Major, only
  cosmetic Minor) or the iteration cap (10) is reached. Uses a
  deterministic Python checker for classification and decision logic;
  agent runs the actual review and revision steps.
version: "2.1.0"
modes: [build, architect]
type: process
---

# Quality-Locked Loop

When the workflow has `quality_locked_mode: true` (set by `--quality-locked`
flag, see flag-parser/SKILL.md), every review checkpoint runs as a
deterministic loop instead of a single review-then-user-decides pass.

**Decision logic is in code, not prose.** The agent calls a Python
checker that parses review output, applies the clean bar, and returns
the next action. This eliminates "I think this is clean enough"
miscounts and silent iteration drift.

## Activation Points

The loop runs at these checkpoints (the same ones where auto-review
normally fires):

| Workflow | Checkpoint | Review type |
|----------|-----------|-------------|
| /build | After spec [A] | spec review |
| /build | After plan [A] | plan review |
| /build | Gate 3 (during quality gates) | code quality review |
| /build | After gates pass | auto-QA |
| /architect | After design [A] | ADR review |
| /architect | After plan [A] | plan review |
| /fix | After diagnosis [A] | root cause review |
| /fix | After fix plan [A] | fix plan review |

## Per-Iteration Loop (what the agent does)

For each iteration (1..10):

```
1. Run the review sub-agent (Task tool, fresh context).
   Capture the raw text output.

2. Call the quality-locked checker:

   python3 sage/runtime/tools/sage_flags.py check \
     --review-output "<sub-agent output text>" \
     --iteration <current iteration number> \
     --history-json '<JSON array of prior iteration records>'

   Returns JSON with: counts, is_clean, cap_reached, stuck, action,
   iteration_record.

3. Append iteration_record to manifest.md under quality_locked_history
   (the agent writes; the checker provides the structured record).

4. Dispatch on `action`:
   - PASS:         exit loop, continue the workflow
   - REVISE:       apply fixes to the artifact/code, increment, loop
   - CAP_REACHED:  present F/R/E/A prompt to the user
   - ESCALATE:     present escalation prompt (3 iterations no improvement)
```

The agent never decides "is this clean enough" — the checker does.
The agent only runs the sub-agent and applies the revisions.

## Fallback Chain

The check command is the primary path. If Python is unavailable:

1. **Python primary:** `python3 sage/runtime/tools/sage_flags.py check ...`
2. **Prose fallback:** read this SKILL.md's decision rules below and
   reason manually. Announce the fallback to the user so the
   reliability degradation is visible.

(Unlike flag-parser, there is no Bash fallback layer here. The parsing
and state logic are non-trivial enough that a Bash implementation would
be its own reliability risk.)

## JSON Contract

The checker emits this shape:

```json
{
  "counts": {
    "critical": 0,
    "major": 0,
    "substantive": 0,
    "cosmetic": 1
  },
  "is_clean": true,
  "cap_reached": false,
  "stuck": false,
  "action": "PASS",
  "iteration_record": {
    "iteration": 3,
    "counts": { ... },
    "result": "PASS"
  }
}
```

`action` is one of: `PASS`, `REVISE`, `CAP_REACHED`, `ESCALATE`.

## Clean Bar Definition (used by the checker)

A review is "clean" when ALL of:
- `critical == 0`
- `major == 0`
- `substantive == 0`

`cosmetic` count is ignored for the clean bar. Cosmetic findings never
trigger another iteration.

The classifier maps both review formats to this unified schema:
- auto-review/auto-qa: CRITICAL/MAJOR/MINOR-substantive/MINOR-cosmetic
- quality-review: CRITICAL/WARNING/SUGGESTION-substantive/SUGGESTION-cosmetic
- Mapped: WARNING → major, SUGGESTION-substantive → substantive, etc.

## Action Behavior

### PASS
- Exit the loop
- Append the final iteration record to manifest
- Continue the workflow to the next step
- Briefly announce: "Auto-review PASS (n iterations)."

### REVISE
- Announce: "Auto-revising (iteration N/10, --quality-locked active)..."
- Read the findings list from the sub-agent output
- Apply fixes for ALL Critical, Major, and substantive Minor findings
- Stay within scope (writable files only)
- Re-loop with `iteration + 1`

### CAP_REACHED

```
Sage: --quality-locked cap reached (10 iterations).
  Remaining at {checkpoint_name}:
  - Critical: {n}
  - Major: {n}
  - Minor (substantive): {n}

The same findings keep returning. This suggests:
- The artifact has a structural issue that revision can't fix
- Consider escalating to /architect for a design rethink
- Or accept the findings and proceed manually

[F] Force-proceed — accept the remaining findings, continue
[R] Revise manually — drop --quality-locked, let me edit
[E] Escalate — type /architect to rethink the design
[A] Abort — cancel this workflow

Pick F/R/E/A, or describe what to do.
```

### Interaction with --autonomous

When `--autonomous` is also active, the `[A] Review` checkpoint that
triggers this loop is auto-picked by the agent. The cap-reached and
stuck-escalation prompts below still require user input — see
`sage/core/capabilities/orchestration/autonomous/SKILL.md` section
"Auto-Pick at Checkpoints" for the full rules.

### ESCALATE (stuck — 3 iterations with same critical+major count)

```
Sage: 3 iterations with no improvement in findings count.
  Iteration {n-2}: {c} critical, {m} major
  Iteration {n-1}: {c} critical, {m} major
  Iteration {n}:   {c} critical, {m} major

This suggests architectural-level issues that spec revision can't fix.

[E] Escalate to /architect (recommended)
[C] Continue iterating (up to cap of 10)
[R] Revise manually — drop --quality-locked

Pick E/C/R, or describe what to do.
```

Always log the chosen action to manifest with the user's selection.

## Manifest Update Format

After each iteration, agent appends to manifest.md:

```yaml
quality_locked_history:
  - checkpoint: spec
    iteration: 1
    counts: { critical: 2, major: 1, substantive: 0, cosmetic: 1 }
    result: REVISE
  - checkpoint: spec
    iteration: 2
    counts: { critical: 0, major: 0, substantive: 0, cosmetic: 1 }
    result: PASS
```

Pass the existing array (or `[]` for first iteration) as
`--history-json` so the checker can detect "stuck" patterns.

## Failure Modes

| Situation | Behavior |
|---|---|
| Sub-agent times out / Task tool absent | Skip the loop entirely; fall back to single self-review pass. Announce: "Task tool not available — --quality-locked degraded to single-pass review." |
| Python checker unavailable | Use prose-rule fallback. Announce: "Quality-locked checker unavailable — using prose rules." |
| Sub-agent output unparseable | Checker returns zero counts; agent surfaces raw output to user and exits the loop with action=REVISE. The user can decide manually. |
| User Ctrl+C mid-iteration | KeyboardInterrupt exits cleanly; current iteration is already logged. |
| Scope violation during auto-revise | Treat as CRITICAL finding for next iteration. Loop continues. |

## Rules

- Iteration cap is non-negotiable at 10.
- MINOR-cosmetic findings NEVER trigger another iteration.
- Every iteration logs to manifest BEFORE the next sub-agent call.
- Stuck detection requires ≥3 prior iterations and matching counts >0.
- The agent does not interpret findings — the classifier does. The
  agent's job is to RUN the sub-agent and APPLY the fixes.

## Review Loop v2 (ledger mode)

The ledger loop is the DEFAULT: it REPLACES the v1 loop above unless
`.sage/config.yaml` carries `review_loop:` with `mode: v1` (the explicit
pin `sage update` writes into pre-flip projects). Everything else in
this skill (activation points, fallback announcements, autonomous
interaction) still applies on both paths.

What changes and why: the reviewer loses the verdict — findings are
structured evidence, the decision is computed by
`sage/runtime/tools/review.py` + `sage_flags.py` from ledger facts. A
finding that cites nothing and demonstrates nothing is capped at
substantive on intake and never blocks. Findings, once recorded, cannot
be forgotten or silently re-raised.

Per iteration (1..cap, default cap 5 — `review_loop.iteration_cap`):

```
1. Assemble the input packet (template in the review capability's
   "Input packet (v2)" section) and dispatch the review sub-agent.

2. Rounds >1 — Phase A first: for each open/not-fixed ledger entry the
   sub-agent returns FIXED | NOT-FIXED | DISPUTED-STANDS with evidence.
   Record it:
     python3 sage/runtime/tools/review.py verify \
       .sage/work/<slug>/review-ledger.json \
       --iteration N --results-json '<Phase A JSON>'

3. Phase B findings (the JSON array from the sub-agent output's fenced
   block — prose outside it is not parsed) go through intake:
     python3 sage/runtime/tools/review.py intake \
       .sage/work/<slug>/review-ledger.json \
       --iteration N --artifact <spec|plan|code|adr> \
       --findings-file <saved findings JSON>
   intake computes fingerprints, caps severities, dedups, and guards
   re-litigation. Its normalization is not yours to re-litigate.

4. Close the round — the verdict is computed, never reported:
     python3 sage/runtime/tools/review.py close-round \
       .sage/work/<slug>/review-ledger.json --iteration N

5. Dispatch on `action`:
   - CONTINUE:      run the fix round (fixer protocol in the review
                    capability), increment, loop.
   - STOP_CLEAN:    exit loop, continue the workflow.
   - STOP_ADVISORY / STOP_CAP: close-round REFUSES to record until every
                    open entry has a disposition. Present the remaining
                    entries (`review.py report`) with the disposition
                    menu below, record each choice via
                    `review.py disposition`, then close-round again.
   - ESCALATE:      render `review.py report`, present the escalation
                    prompt. The controller does not spend past a stall.
```

Disposition menu (per remaining open entry, RR-7):

```
[F] Fix now — one more fix round for this finding (converts the stop
    back into CONTINUE for it)
[D] Defer — ticketed; requires a ticket/issue ref, witness test stays
    red-marked in the suite
[X] Reject — requires a reason, recorded; re-raising it later needs
    the anchor to have actually changed
```

### Fix round (v2) — witness-first, one finding one commit

On CONTINUE, fix open findings in severity order. Per finding:

1. **Materialize the witness before touching code.** `witness.kind:
   test` — run it, confirm red at HEAD. `repro`/`trace` — write the
   test that encodes it at `tests/review/<F-id>.*`, run it red, then
   `review.py attach-witness <F-id> --ref <path>`. A trace-kind finding
   from an empty matrix cell — the witness IS the missing test: write
   it (red or green as the code warrants; an empty test cell over green
   code is still a fix). If the witness cannot be reproduced at HEAD:
   `review.py verify <ledger> --iteration N --cannot-reproduce <F-id>
   --evidence "<run output>"` — bounced to the controller, never
   silently skipped. (The tdd-gate already blocks a source edit without
   a test in scope; witness-first is that rule's loop-shaped
   application.)
2. **Collateral safety (advisory):** when the packet's blast radius
   shows a neighbor of the fix with no covering test, pin current
   behavior with 1–3 asserts first (`tests/review/<F-id>-sentinel.*`).
   You cannot avoid breaking what nothing observes; sentinels are the
   cheapest observer.
3. **Fix, then commit — ONE commit per finding** (cluster only findings
   sharing an anchor), with trailers:

   ```
   Sage-Fix: F-003
   Sage-Cause: <why the defect existed — one line>
   Sage-Change: <what the fix does — one line>
   Sage-Risk: <what could regress — one line>
   Sage-Collateral: src/session.ts:88-95 (why)   # if any
   Sage-License: spec §4.2                        # if behavior changes
   ```

   Cause/Change/Risk is the three-line fix plan — the
   misunderstood-finding tripwire — recorded where bisect finds it.
   Because commits map 1:1 to findings, a regression later bisects to a
   single Sage-Fix trailer.
4. **Scope check** (controller step, per fix commit):
   `review.py check-diff <ledger> --finding <F-id> --commit <sha>`.
   Out-of-scope hunks exit 1 and land in the ledger as a machine
   finding witnessed by the hunk itself. A modified non-witness test
   without `Sage-License` also exits 1 — correctness is amended through
   the spec with approval, never redefined in the diff; if the spec is
   silent, raise a spec finding and pause the code fix behind its
   disposition. `review_loop.scope_check: false` restores v1.
5. **Per commit:** run the finding's witness + targeted tests for
   touched files. **Per round close:** full suite + deterministic gates
   on the fixed HEAD — the closing proof, never trimmed — and record it:
   `review.py close-round ... --suite-evidence "<summary>"
   --gates-evidence "<exits>"`, so the next Phase A verifies against
   facts already on file.

Witness tests are permanent: they land with the fix, run in the suite
thereafter, and are never deleted on STOP — a deferred finding's
witness stays red-marked (`xfail`/`todo` per runner idiom) as the
ticket's executable form.

The exit record in decisions.md is written by `review.py close-round`
itself — do not write it by hand. If any `review.py` command exits 1,
STOP and surface the error verbatim: the ledger fails closed, and a
broken ledger stops the loop loudly. Do not reconstruct ledger state by
hand or continue the loop around it.

The v1 sections above ("cap of 10", `quality_locked_history` in the
manifest, `sage_flags.py check`) do not apply on the v2 path — history
lives in the ledger's `history[]`, written by close-round.

Model routing (`review_loop.review_model: cheap`, optional): the
checklist perspective passes and Phase A verification MAY run on a
cheap model, reserving the default model for one adjudication pass over
the assembled findings — checklist-shaped work transfers down-model;
open judgment does not. The cost delta is UNCLAIMED until measured:
the knob exists, the number waits.

## Quality Criteria

- Checker is deterministic (same input → same output, verified by tests)
- Both review formats produce identical unified counts
- Stuck detection requires findings >0 (three clean reviews aren't "stuck")
- Cap-reached prompt offers actionable choices
- Manifest history is complete and machine-readable
- Fallback announcement is mandatory when degrading to prose
