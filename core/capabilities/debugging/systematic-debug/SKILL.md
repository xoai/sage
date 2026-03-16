---
name: systematic-debug
description: >
  Four-phase debugging framework that finds root causes before attempting
  fixes. Use when investigating errors, debugging failures, fixing bugs,
  analyzing test failures, diagnosing unexpected behavior, examining stack
  traces, or when the user says "it's broken", "this doesn't work", or "why is
  this failing".
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [debugging, diagnostics, quality, root-cause]
inputs: [error-report, codebase]
outputs: [debug-report, fix]
-->

# Systematic Debugging

Find the root cause BEFORE attempting any fix. Random fixes waste hours and
create new bugs. Quick patches mask underlying issues.

**Core Principle:** If you haven't completed Phase 1, you CANNOT propose fixes.
Symptom fixes are failure. You MUST complete each phase before proceeding to the next.

## When to Use

Any time something is broken: test failures, runtime errors, unexpected behavior,
performance degradation, flaky tests, production incidents, "it works on my machine"
issues. Also use when a previous fix didn't hold — that means root cause was wrong.

## Process

### Phase 1: OBSERVE — Understand What's Actually Happening

Before touching anything:

1. **Read the error message.** Completely. Every line. Stack traces contain the answer
   80% of the time. Read from bottom to top.
2. **Reproduce the failure.** If you can't reproduce it, you can't verify your fix.
   Get to a state where the bug happens reliably.
3. **Check recent changes.** What changed since it last worked? `git log`, `git diff`.
   The cause is almost always in recent changes.
4. **Document observed behavior.** Write down:
   - What SHOULD happen (expected)
   - What ACTUALLY happens (observed)
   - The exact error message or output
   - Steps to reproduce

DO NOT skip this phase. DO NOT propose a fix yet. You don't understand the problem yet.

### Phase 2: HYPOTHESIZE — Form Theories About Root Cause

Form 2-3 hypotheses about what could cause the observed behavior.

For each hypothesis:
- What evidence would CONFIRM it?
- What evidence would REFUTE it?
- How can you test it without modifying code?

For multi-component systems, trace data flow across component boundaries:
- Log what data ENTERS each component
- Log what data EXITS each component
- Verify environment/config propagation at each layer
- The point where input looks correct but output doesn't → that's your failing component

### Phase 3: TEST — Verify Hypotheses With Evidence

For each hypothesis, gather evidence. This means adding targeted logging,
running specific commands, or inspecting state — NOT making code changes.

Rules:
- Test ONE hypothesis at a time
- Gather evidence BEFORE concluding
- If evidence contradicts your hypothesis, form a new one — don't force the data to fit
- Don't "try a fix and see if it works" — that's guessing, not debugging

When you find the root cause:
- You can explain WHY the bug occurs, not just WHERE
- You can predict what else might be affected
- You can describe the minimal change that fixes it

### Phase 4: FIX — Apply Targeted Fix With Verification

Now — and ONLY now — you may fix it:

1. Write a failing test that reproduces the bug (TDD skill applies here)
2. Make the MINIMAL change that fixes the root cause
3. Watch the test pass
4. Run ALL tests — no regressions
5. Verify the original reproduction steps no longer trigger the bug

One fix at a time. Don't combine fixes. Don't "also improve" nearby code.

### Phase 4.5: ESCALATE — When Fixes Keep Failing

If 3+ fixes have failed for the same issue:

**STOP.** You're treating symptoms, not the root cause. Return to Phase 1 with
fresh eyes. Question whether the architecture itself is the problem, not just
the code. Discuss with your human partner before attempting more fixes.

This is NOT a failed hypothesis — it may be wrong architecture.

## Rules

- NEVER skip Phase 1. You don't understand the problem yet.
- NEVER propose a fix before completing Phase 2.
- NEVER apply multiple fixes simultaneously.
- NEVER assume "it's probably X" without evidence.
- If you see a fix that "should work" but doesn't, return to Phase 1.
- If the same bug resurfaces, your previous root cause analysis was wrong. Start over.

## Anti-Patterns to Catch

| Anti-Pattern | What to Do Instead |
|-------------|-------------------|
| "Let me just try..." | STOP. What's your hypothesis? What evidence supports it? |
| Changing 5 things at once | Revert. Change ONE thing. Verify. |
| "It works now but I'm not sure why" | DANGER. Find out why or the bug will return. |
| Fixing the test instead of the code | Tests are the specification. If the test is wrong, fix it with evidence. If the code is wrong, fix the code. |
| Adding a workaround | Find the root cause. Workarounds become permanent. |
| "Works on my machine" | The difference between your machine and the failing one IS the bug. |

## Failure Modes

- **Can't reproduce:** Gather more context. Environment differences, timing, data variations. Ask the person who found it for exact steps.
- **Root cause spans multiple systems:** Trace data flow at every boundary. The bug is at the boundary where good data goes in and bad data comes out.
- **Flaky test:** This is NOT random. There's a timing dependency, shared state, or test pollution. Use condition-based waiting instead of sleeps. Bisect test order to find the polluter.
- **Truly no root cause found (rare):** 95% of the time this means incomplete investigation. 5% of the time it's environmental/external. If truly external, document and add defensive validation.

## References

See `references/` for specialized techniques:
- `root-cause-tracing.md` — Backward tracing through call stack to find original trigger
- `defense-in-depth.md` — Adding validation at multiple layers after finding root cause
