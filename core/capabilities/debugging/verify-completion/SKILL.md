---
name: verify-completion
description: >
  Verifies implementations and fixes actually work by executing commands and
  observing real results. Never trusts claims. Use as the final quality check
  after implementation, after a bug fix, or when the user asks "is it done",
  "does it work", "verify this", or "confirm the fix".
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: mandatory
tags: [verification, quality, completion, testing]
inputs: [implementation, test-suite]
outputs: [verification-result]
-->

# Verify Completion

Run the code. Run the tests. Observe the results. Don't trust claims.

**Core Principle:** An implementation is not done when the agent says "done."
It's done when evidence proves it works. Evidence means command output,
test results, and observable behavior — not descriptions of what should happen.

## When to Use

As the final gate (Gate 5) after spec compliance, constitution compliance,
code quality, and hallucination checks have all passed. Also after any bug fix,
before declaring the fix complete.

## Process

### Step 1: Run All Tests

Execute the full test suite. Not "I believe the tests pass" — actually run them.

```
Capture: exact command executed
Capture: complete output including pass/fail counts
Capture: any warnings or skipped tests
```

ALL tests must pass. If any test fails, the verification FAILS — even if the
failing test is unrelated to the current change (you may have introduced a regression).

### Step 2: Run Specific Acceptance Criteria

For each acceptance criterion in the spec:
- Execute the verification command or scenario
- Capture the actual output
- Compare against expected output

If the spec says "API returns 200 with user.id in body," actually call the API
and inspect the response. Don't just read the code and conclude it would work.

### Step 3: Verify Edge Cases

For FIX mode:
- Reproduce the original bug scenario. It must NOT reproduce.
- Verify the fix doesn't break related functionality.

For BUILD mode:
- Test the happy path AND at least one error path.
- Verify the feature works end-to-end, not just in isolation.

### Step 4: Produce Result

```
GATE: verification
RESULT: PASS | FAIL

EVIDENCE:
  Test suite: [X] passed, [Y] failed, [Z] skipped
  Command: [exact command run]
  Output: [relevant output excerpt]

ACCEPTANCE CRITERIA:
  ✓ [criterion 1] — Verified: [evidence]
  ✓ [criterion 2] — Verified: [evidence]
  ✗ [criterion 3] — FAILED: expected [X], got [Y]

ACTION: none | fix-and-retry | escalate-to-human
```

## Rules

- NEVER say "tests should pass" — run them and report what happened.
- NEVER say "I verified it works" without showing the command and output.
- NEVER skip verification because "it's a small change." Small changes cause outages.
- NEVER mark verification PASS if any test fails, even "unrelated" ones.
- If you can't run the verification (missing tool, environment issue), report
  it as BLOCKED, not PASS.

## Failure Modes

- **Tests pass but feature doesn't work:** Tests are incomplete. Write a new
  test that captures the actual failure, then fix.
- **Can't run tests (environment issue):** Report BLOCKED with details. Do NOT
  skip verification. Help resolve the environment issue first.
- **Flaky test fails:** Not acceptable. Flaky tests are bugs. Investigate
  with systematic-debug skill. Don't re-run and hope.
