---
name: fix
version: "1.1.0"
mode: fix
produces: ["Root cause diagnosis with evidence", "Reproducing test", "Minimal patch"]
checkpoints: 2
scope: "Single session"
user-role: "Confirm root cause, approve fix"
---

# Fix Workflow

Diagnose, then fix. Never the reverse.

## Step 1: Understand the Problem

Ask for or identify: what's broken, when it started, error messages,
steps to reproduce. If the user already provided details, confirm
your understanding before proceeding.

Sage: Here's what I understand:
- [Problem summary]
- [Expected vs actual behavior]

[C] Correct — start debugging  |  Or clarify what I got wrong

## Step 2: Investigate Root Cause

**NO FIXES BEFORE THIS STEP COMPLETES.** Read the relevant code.
Trace the error. Gather evidence. The goal is UNDERSTANDING, not
a fix.

Produce a root cause statement with evidence:

Sage: Root cause identified.

  Cause: [what's actually wrong — the source, not the symptom]
  Evidence: [what you observed that confirms this]
  Chain: [how the root cause leads to the visible symptom]
  Confidence: [high / medium / low]

If multiple potential causes exist:

Sage: I found two possible causes:

[1] [Cause A] — in [file:line] — [evidence for this]
[2] [Cause B] — in [file:line] — [evidence for this]

Which should I investigate first?

**Red flags — STOP and return to investigation if you catch
yourself thinking:**
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "Should work now" (without evidence)

**If stuck after 3+ attempts:** Activate the `problem-solving` skill.
Start with the Minimal Reproduction technique — strip the problem to
the smallest case that still exhibits the issue.

🔒 **ROOT CAUSE GATE:**
Sage: Root cause analysis complete.

  Cause: [root cause statement]
  Evidence: [what confirms it]
  Confidence: [high/medium/low]

[A] Approve diagnosis — proceed to fix
[R] Revise — investigate further
[S] Stuck — try a different approach (activates problem-solving)

Do not proceed to Step 3 until the user confirms the root cause.

## Step 3: Fix

Write a failing test that reproduces the bug. Confirm the test fails
for the right reason (the root cause, not a setup issue). Fix the
code. Verify the test passes.

## Step 4: Verify

**Run the verification command. Read the output. THEN report.**

1. Run the project's test suite (full or relevant subset)
2. Read the actual output — don't summarize from memory
3. Confirm: zero failures, zero errors
4. If any test fails, diagnose and fix before proceeding —
   do NOT present the checkpoint with failing tests

Sage: Verification results:

  Test suite: [command that was run]
  Result: [X passed, 0 failed] ← paste actual output
  Regression check: [any related tests that also pass]

**If tests fail after the fix:** Return to Step 2. The root cause
analysis was incomplete — either the diagnosis was wrong, or the
fix introduced a new issue.

## Step 5: Close

Sage: Fix verified.
- Root cause: [what was wrong]
- Change: [what was changed, in which files]
- Tests: [X passed, 0 failed — from actual output]

[A] Approve — commit and close
[R] Revise — something's not right

**On approval — Post-Flight:**
1. Update `.sage/progress.md`
2. Update `.sage/journal.md` if relevant
3. Store root cause and fix in memory (tagged `learning`) — this
   prevents the same bug from being re-investigated in future sessions

## Quality Criteria

**Communication style:** Diagnostic precision. State root cause clearly,
explain the chain of causation, and describe the fix in terms of what
changed and why. Be specific about test coverage.

Good fix output:
- Root cause identified with evidence, not just symptoms addressed
- The cause→symptom chain is explained (how the root cause leads
  to the visible problem)
- A reproducing test exists before the fix is applied
- The fix doesn't introduce new issues — verification output is pasted
- If the bug has related patterns elsewhere, those are flagged
- The fix is minimal — no unrelated refactoring mixed in

## Self-Review

Before presenting the close checkpoint, verify:
- Is this the ROOT cause, or the first thing that stopped the error?
- Did I paste actual test output, or just claim tests pass?
- Would this fix prevent the bug from recurring, or just mask it?
- Did I check for related patterns elsewhere in the codebase?

## Rules

- Diagnose first: no fixes before root cause is confirmed.
- Test first: write a failing test before writing the fix.
- Verify with evidence: paste test output, don't summarize.
- Minimal change: fix the bug, don't refactor the neighborhood.
- If stuck, use problem-solving: don't keep trying the same approach.
- If the fix reveals a larger issue, note it and offer to create
  a separate task — don't scope-creep a fix into a feature.
