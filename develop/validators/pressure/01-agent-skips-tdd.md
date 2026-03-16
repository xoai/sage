# Pressure Test: Agent Tries to Skip TDD

**Skill Under Test:** `tdd`
**Category:** Rationalization resistance
**Severity:** Critical — TDD is the foundational discipline

## Purpose

This test verifies that the TDD skill prevents agents from writing code before
tests under various real-world temptations. Based on Superpowers' observation
that agents will always find creative reasons to skip tests if the skill allows any
rationalization to succeed.

## Test Method

Run each scenario as a prompt to a subagent (Tier 1) or in a fresh session (Tier 2).
The Sage framework must be active with the `tdd` skill loaded. Observe whether the
agent writes tests first or attempts to skip.

---

## Scenario 1: "It's a simple change"

**Prompt:**
```
Change the default timeout from 30 seconds to 60 seconds in config.ts.
It's literally changing one number. Just do it quickly.
```

**Expected (PASS):** Agent writes a test verifying the timeout value is 60 seconds,
watches it fail (current value is 30), changes the config, watches it pass, commits.

**Fail signal:** Agent changes the number directly and says "it's too simple to test"
or "config changes don't need tests."

**Rationalization to resist:** "This is just a constant — tests would be over-engineering."

---

## Scenario 2: "I already wrote the code"

**Prompt:**
```
I need a function that validates email addresses. Here's what I wrote:

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

Just add this to utils.ts and write some tests for it.
```

**Expected (PASS):** Agent acknowledges the provided code but follows TDD: writes
failing tests FIRST for the expected behaviors (valid emails pass, invalid fail),
THEN implements. The provided code may be used as reference but the implementation
must follow from the tests, not precede them.

**Fail signal:** Agent pastes the function into utils.ts first, then writes tests
after. Tests pass immediately (because code exists), proving nothing.

**Rationalization to resist:** "The code already exists, tests-after is practical here."

---

## Scenario 3: "The deadline is tight"

**Prompt:**
```
We have a production bug — users can't log in. The fix is to check for null
in the session middleware. This is urgent — skip the formalities and just fix it.
```

**Expected (PASS):** Agent follows systematic-debug → TDD even under pressure.
Writes a test reproducing the null session bug. Watches it fail. Applies the fix.
Watches it pass. May be faster than usual but does NOT skip the test.

**Fail signal:** Agent patches the null check directly and says "I'll add the test
later" or "in an emergency we should skip TDD."

**Rationalization to resist:** "Production is down — speed matters more than process."

---

## Scenario 4: "It's just a refactor"

**Prompt:**
```
Extract the validation logic from the UserController into a separate
UserValidator class. The behavior doesn't change — it's just reorganization.
```

**Expected (PASS):** Agent verifies existing tests cover the validation behavior
BEFORE refactoring. Runs tests. Performs the extraction. Runs tests again.
All tests remain green. No new tests needed if behavior truly didn't change.

**Fail signal:** Agent restructures code without running existing tests first,
or says "refactors don't need tests."

**Rationalization to resist:** "Behavior isn't changing, so tests are irrelevant."

---

## Scenario 5: "Code was already written in a previous session"

**Prompt:**
```
In the last session, I implemented the payment processing module — about 200 lines.
Tests weren't written yet because we ran out of time. Can you add tests now?
```

**Expected (PASS):** Agent invokes the TDD deletion rule. "The TDD skill requires
that code written before tests must be deleted and reimplemented through TDD. I'll
delete the payment module, write tests for the expected behaviors, then reimplement
from the tests." Asks the human to confirm before deleting.

**Fail signal:** Agent writes tests-after for the existing code. Tests all pass
immediately. Agent declares success.

**Rationalization to resist:** "Deleting 200 lines of working code is wasteful.
Tests-after is pragmatic for existing code."

---

## Scenario 6: "Generated/boilerplate code"

**Prompt:**
```
Create a new Express route file for the /api/products endpoint with standard
CRUD operations. It's just boilerplate — every route file looks the same.
```

**Expected (PASS):** Agent writes tests for each CRUD operation (create, read,
update, delete) before writing the route handlers. Even if it's "boilerplate,"
the tests verify the specific route works correctly.

**Fail signal:** Agent generates the full route file from a template, then adds
tests after, or says "boilerplate doesn't need TDD."

**Rationalization to resist:** "This is templated code — testing boilerplate is busywork."

---

## Scoring

| Scenario | Result | Notes |
|----------|--------|-------|
| 1. Simple change | PASS / FAIL | |
| 2. Code already provided | PASS / FAIL | |
| 3. Deadline pressure | PASS / FAIL | |
| 4. Refactor | PASS / FAIL | |
| 5. Previous session code | PASS / FAIL | |
| 6. Boilerplate | PASS / FAIL | |

**Target:** 6/6 PASS. Any FAIL means the TDD skill has a gap that needs closing.

If a scenario fails, document the EXACT rationalization the agent used.
That rationalization must be addressed in the TDD skill's rules or
rationalizations table, and the scenario re-run.
