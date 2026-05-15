---
name: quality-locked
description: >
  When --quality-locked is active, loop review/revise at each Quality
  Gate until findings reach a clean bar (no Critical, no Major, only
  cosmetic Minor) or the iteration cap (10) is reached.
version: "1.0.0"
type: process
---

# Quality-Locked Loop

When the workflow has `quality_locked_mode: true` (set by `--quality-locked`
flag, see flag-parser/SKILL.md), every review checkpoint behaves as a
loop instead of a single review-then-user-decides pass.

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

## Clean Bar Definition

A review is "clean" when:
- **CRITICAL** = 0
- **MAJOR** = 0
- **MINOR-substantive** = 0
- (MINOR-cosmetic is allowed — won't trigger another iteration)

If the review prompt uses different severity terms (Gate 3 uses
WARNING/SUGGESTION), the substantive/cosmetic distinction still
applies to the lowest severity:
- Gate 3: CRITICAL=0, WARNING=0, SUGGESTION-substantive=0

## Loop Algorithm

```
iteration = 0
WHILE iteration < 10:
  result = run_review_sub_agent()
  critical = count(result.findings, severity=CRITICAL)
  major = count(result.findings, severity=MAJOR)
  substantive_minor = count(result.findings, severity=MINOR-substantive)

  IF critical == 0 AND major == 0 AND substantive_minor == 0:
    PASS — exit loop, continue workflow

  IF iteration == 9:
    BREAK — present cap-reached prompt (below)

  announce: "Auto-revising (iteration {iteration+1}/10, --quality-locked active)..."
  apply_fixes(result.findings, only=[CRITICAL, MAJOR, MINOR-substantive])
  log_iteration_to_manifest(result, iteration)
  iteration += 1
```

## Per-Iteration Logging

After each iteration, append to manifest.md under
`quality_locked_history`:

```yaml
quality_locked_history:
  - checkpoint: spec
    iteration: 1
    findings: { critical: 2, major: 1, minor_substantive: 0, minor_cosmetic: 1 }
    actions: ["added auth failure handling", "added empty list edge case"]
  - checkpoint: spec
    iteration: 2
    findings: { critical: 0, major: 0, minor_substantive: 0, minor_cosmetic: 1 }
    actions: []
    result: PASS
```

## Cap-Reached Behavior

When iteration reaches 10 without converging:

```
Sage: --quality-locked cap reached (10 iterations).
  Remaining at checkpoint {checkpoint_name}:
  - Critical: {n}
  - Major: {n}
  - Minor (substantive): {n}

The same findings keep returning. This suggests:
- The spec/plan/code has a structural issue that revision can't fix
- Consider escalating to /architect for a design rethink
- Or accept the findings and proceed manually

[F] Force-proceed — accept the remaining findings, continue the workflow
[R] Revise manually — drop --quality-locked, let me edit
[E] Escalate — type /architect to rethink the design
[A] Abort — cancel this workflow

Pick F/R/E/A, or describe what to do.
```

Always log the cap-hit state to manifest with `result: CAP_REACHED`
and the user's choice.

## Architecture Escalation Heuristic

If 3 consecutive iterations show no decrease in CRITICAL+MAJOR counts
(findings keep returning), suggest escalation BEFORE hitting the cap:

```
Sage: 3 iterations with no improvement in findings count.
  Iteration 1: 2 critical, 1 major
  Iteration 2: 2 critical, 1 major
  Iteration 3: 2 critical, 1 major

This suggests architectural-level issues that spec revision can't fix.

[E] Escalate to /architect (recommended)
[C] Continue iterating (up to 10)
[R] Revise manually — drop --quality-locked

Pick E/C/R, or describe what to do.
```

## Fallback: Sub-Agent Unavailable

If the Task tool is not available, `--quality-locked` cannot run its
review-revise loop (it depends on independent sub-agents). In that case:

```
Sage: --quality-locked requires the Task tool for independent reviews.
Task tool not available — falling back to single self-review pass.
Findings will be presented as usual; the loop is skipped.
```

Continue the workflow with a normal review checkpoint.

## Scope Preservation

The auto-revise step MUST stay within scope:
- /build: writable areas declared in the brief/spec
- /fix: the files identified in the fix plan
- /architect: ADR files only (not implementation code)

A scope violation during auto-revise is itself a CRITICAL finding and
must surface to the user immediately, breaking the loop.

## Rules

- Iteration cap is non-negotiable at 10. No `--max-iter` flag in v1.
- MINOR-cosmetic findings NEVER trigger another iteration.
- Every iteration logs to manifest before incrementing.
- User can interrupt at any iteration; the loop respects KeyboardInterrupt.
- The clean bar is binary: either all three counts are zero, or loop continues.

## Quality Criteria

- Findings are classified accurately (substantive vs cosmetic distinction
  is principled, not arbitrary)
- Auto-revise targets exactly the findings — no scope creep
- Manifest history is complete and inspectable
- Cap-reached prompt offers clear next steps
- Architecture escalation triggers when appropriate (3 unchanging iterations)
