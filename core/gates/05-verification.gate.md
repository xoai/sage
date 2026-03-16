---
name: verification
description: Executes tests and features to verify they actually work. Requires evidence, not claims.
version: "1.0.0"
order: 5
cost-tier: sonnet
required-context: [implementation, test-suite]
category: verification
---

# Gate 5: Verification

Run it. Show the output. Prove it works.

An implementation is not done when someone says "done." It's done when
evidence proves it works. Evidence means command output, test results,
and observable behavior.

## Deterministic Verification Script

**ALWAYS run the verification script first.** Language-based checking is
supplementary — the script provides deterministic evidence.

```bash
bash .sage/gates/scripts/sage-verify.sh .
```

This script automatically: detects the test runner (vitest, jest, pytest,
flutter test, go test), runs all tests, checks the build compiles, scans
for TODO/FIXME markers, and returns exit code 0 on pass / 1 on fail.

If the script passes, proceed to the manual checks below only for
acceptance criteria that can't be automated.

## Check Criteria

### Test Execution
- [ ] All tests were actually executed (show the command and output)
- [ ] All tests PASS (zero failures, zero errors)
- [ ] No tests were skipped without documented reason
- [ ] Test count is reasonable for the scope of changes

### Feature Verification
- [ ] Each acceptance criterion was checked against actual behavior
- [ ] For FIX mode: the original bug no longer reproduces
- [ ] For BUILD mode: the feature works end-to-end, not just in unit tests
- [ ] At least one error/edge path was exercised (not just happy path)

### Regression Check
- [ ] Tests that existed BEFORE this change still pass
- [ ] No new warnings introduced
- [ ] Build still succeeds cleanly

## Adversarial Guidance

Agents love to say "all tests pass" without running them. They infer from
reading the code that tests "should" pass. That's not verification.

Requirements:
- Show the EXACT command that was executed
- Show the ACTUAL output (or relevant excerpt)
- If tests can't be run (missing environment, tool, etc.), report BLOCKED
  — do NOT report PASS

## Failure Response

**Test failure:** FAIL. Investigate with `systematic-debug`. Fix through TDD. Re-run all gates from Gate 1 (the fix might have changed things).
**Can't run tests:** BLOCKED. Resolve the environment issue first. Do NOT skip.
**Flaky test:** FAIL. Flaky tests are bugs. Investigate, don't re-run and hope.
**Feature doesn't work despite passing tests:** FAIL. Tests are insufficient. Write better tests, then fix.
