---
name: fix
version: "1.0.0"
mode: fix
---

# Fix Workflow

Quick debug and patch.

## Step 1: Understand the Problem

Ask for or identify: what's broken, when it started, error messages,
steps to reproduce. If the user already provided details, confirm
your understanding before proceeding.

```
Here's what I understand:
- [Problem summary]
- [Expected vs actual behavior]

[C] Correct — start debugging  |  Or clarify what I got wrong
```

## Step 2: Locate

Read the relevant code. Identify the root cause — not just the symptom.
If multiple potential causes exist:

```
I found two possible causes:

1) [Cause A] — in [file:line] — [why this might be it]
2) [Cause B] — in [file:line] — [why this might be it]

Which should I investigate first?
```

## Step 3: Fix

Write a failing test that reproduces the bug. Fix the code. Verify the
test passes. Run the full test suite to check for regressions.

## Step 4: Verify and Close

```
Fix applied:
- Root cause: [what was wrong]
- Change: [what was changed, in which files]
- Tests: [passing/failing]

[A] Approve — commit and close
[R] Revise — something's not right
```

Update `.sage/progress.md`. Done.

## Rules

- Test first: write a failing test before writing the fix.
- Minimal change: fix the bug, don't refactor the neighborhood.
- If the fix reveals a larger issue, note it and offer to create
  a separate task — don't scope-creep a fix into a feature.
