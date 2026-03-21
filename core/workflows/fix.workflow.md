---
name: fix
version: "1.0.0"
mode: fix
produces: ["Root cause diagnosis", "Reproducing test", "Minimal patch"]
checkpoints: 1
scope: "Single session"
user-role: "Confirm root cause, approve fix"
---

# Fix Workflow

Quick debug and patch.

## Step 1: Understand the Problem

Ask for or identify: what's broken, when it started, error messages,
steps to reproduce. If the user already provided details, confirm
your understanding before proceeding.

```
Sage: Here's what I understand:
- [Problem summary]
- [Expected vs actual behavior]

[C] Correct — start debugging  |  Or clarify what I got wrong
```

## Step 2: Locate

Read the relevant code. Identify the root cause — not just the symptom.
If multiple potential causes exist:

```
Sage: I found two possible causes:

[1] [Cause A] — in [file:line] — [why this might be it]
[2] [Cause B] — in [file:line] — [why this might be it]

Which should I investigate first?
```

## Step 3: Fix

Write a failing test that reproduces the bug. Fix the code. Verify the
test passes. Run the full test suite to check for regressions.

## Step 4: Verify and Close

```
Sage: Fix applied.
- Root cause: [what was wrong]
- Change: [what was changed, in which files]
- Tests: [passing/failing]

[A] Approve — commit and close
[R] Revise — something's not right
```

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
- Root cause identified and explained, not just symptoms addressed
- The fix doesn't introduce new issues — regression scope considered
- Tests verify the fix AND prevent recurrence
- If the bug has related patterns elsewhere, those are flagged
- The fix is minimal — no unrelated refactoring mixed in

## Self-Review

Before marking a fix complete, check each criterion above. Is this
the root cause, or just the first thing that stopped the error?

## Rules

- Test first: write a failing test before writing the fix.
- Minimal change: fix the bug, don't refactor the neighborhood.
- If the fix reveals a larger issue, note it and offer to create
  a separate task — don't scope-creep a fix into a feature.
