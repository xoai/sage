---
name: quality-locked
description: >
  When --quality-locked is active, loop review/revise at each Quality
  Gate until findings reach a clean bar (no Critical, no Major, only
  cosmetic Minor) or the iteration cap (10) is reached. Uses a
  deterministic Python checker for classification and decision logic;
  agent runs the actual review and revision steps.
version: "2.0.0"
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

   python -m core.quality_locked check \
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

1. **Python primary:** `python -m core.quality_locked check ...`
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

## Quality Criteria

- Checker is deterministic (same input → same output, verified by tests)
- Both review formats produce identical unified counts
- Stuck detection requires findings >0 (three clean reviews aren't "stuck")
- Cap-reached prompt offers actionable choices
- Manifest history is complete and machine-readable
- Fallback announcement is mandatory when degrading to prose
