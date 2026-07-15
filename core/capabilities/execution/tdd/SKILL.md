---
name: tdd
description: >
  Enforces test-driven development: write failing test, write minimal code to
  pass, refactor. Mandatory for all implementation work. Use when writing any
  production code, implementing features, fixing bugs, refactoring, or when
  the user says "write code", "implement", "fix this", or "add a feature".
  Code written before its test is deleted.
version: "1.1.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: mandatory
tags: [testing, quality, discipline, implementation]
inputs: [task-spec]
outputs: [implementation, test-suite]
-->

# Test-Driven Development

Write the test first. Watch it fail. Write minimal code to pass. Refactor. Commit.

**The Iron Law:** If *nobody* watched the test fail, you don't know if it tests
the right thing. The failure must have been observed, with evidence. Almost
always that observer is you, this session — see "Inherited red" for the single
narrow case where a prior session already banked the observation. Violating the
letter of these rules IS violating the spirit.

## When to Use

ALWAYS. Every time you write production code. Every feature. Every bug fix. Every
refactor that changes behavior. The urge to skip "just this once" is a rationalization
signal, not a legitimate exception.

## The Cycle

```
RED → VERIFY FAIL → GREEN → VERIFY PASS → REFACTOR → VERIFY STILL PASS → COMMIT → NEXT
```

### Phase 1: RED — Write One Failing Test

Write one minimal test that describes the expected behavior.

Rules:
- Test name describes BEHAVIOR, not mechanism: `rejects expired tokens` not `test auth`
- Test demonstrates the desired API as if writing a usage example
- One assertion per test. If name contains "and" → split it
- Write the assertion FIRST, then work backward to setup

Run the test. It MUST fail. If it passes on first run, the test is suspect —
it's either testing something that already works (useless) or testing the wrong
thing (dangerous). Investigate before proceeding.

The failure must be the RIGHT failure — the test should fail because the feature
doesn't exist yet, not because of a syntax error or wrong import.

### Phase 2: GREEN — Write Minimal Code

Write the SIMPLEST code that makes the test pass. Nothing more.

Rules:
- Do NOT add optional parameters not required by the test
- Do NOT handle edge cases not covered by a test
- Do NOT add "future-proofing" or "nice to have" code
- Do NOT refactor during GREEN — that's the next phase
- The implementation exists ONLY to pass the current test

Run ALL tests. The new test must pass. All existing tests must still pass.
If any test fails, fix it before proceeding. Never leave tests red.

### Phase 3: REFACTOR — Clean Up

Now — and ONLY now — you may improve the code. Remove duplication, extract
helpers, rename for clarity, simplify logic.

Rules:
- Do NOT add behavior. Refactoring changes structure, not behavior.
- After EVERY change, re-run ALL tests. They must stay green.
- If a test breaks during refactor, undo and try a smaller refactor.
- Keep tests green. Always.

### Phase 4: COMMIT — Lock It In

Commit with a semantic message referencing what behavior was added.
Then start the next RED cycle for the next behavior.

## Rules — Non-Negotiable

### The Deletion Rule

If production code was written before its corresponding test existed and was
observed failing: **DELETE THE CODE.** Implement fresh from tests only.

Delete means delete. Not "comment out." Not "keep as reference." Delete.
Then write the test. Watch it fail. Then rewrite the code.

This is not punitive. Code written without tests cannot be trusted. The cost
of rewriting with TDD is lower than the cost of debugging code you can't verify.

### The Sunk Cost Trap

"But I already wrote 200 lines!" — Sunk cost fallacy. The time is gone.
Your choice now:
- Delete and rewrite with TDD → takes more time, high confidence
- Keep and add tests after → fast but low confidence, likely bugs

The "waste" is keeping code you can't trust.

### Why Not Tests-After?

Tests written after code answer: "What does this code do?"
Tests written before code answer: "What should this code do?"

Tests-after pass immediately. Passing immediately proves nothing — you never
see them fail, so you don't know if they test the right thing. Tests-after
also test implementation details instead of behavior, making them brittle.

### The Completion Checklist

Before declaring implementation complete, verify ALL of these:

- [ ] Every piece of production code has a test that was written FIRST
- [ ] Every test was observed FAILING before the code was written — by this
      session, or (resume only) banked by the prior session per "Inherited red"
- [ ] Every test was observed PASSING after the code was written
- [ ] All tests pass right now (run them, don't assume)
- [ ] No production code exists without a corresponding test

Can't check all boxes? You skipped TDD. Start over from the first unchecked item.

## Common Rationalizations (All Invalid)

| Rationalization | Why It's Wrong | What to Do |
|----------------|---------------|------------|
| "This is too simple to test" | Simple bugs cause outages. Tests are fast for simple code. | Write the test. It'll take 30 seconds. |
| "I'll write tests after" | Tests-after test implementation, not behavior. They prove nothing. | Delete code. Write test first. |
| "Just this once" | That's what everyone says every time. It's never just once. | Follow the process. It's faster than debugging. |
| "I'm just refactoring" | If behavior changes, you need a test. If it doesn't, existing tests suffice. | Run existing tests. If they break, you're changing behavior — write a test. |
| "Manual testing is fine" | You think you tested everything. You didn't. You can't remember what you tested tomorrow. | Automated tests are repeatable. Manual tests are guesses. |
| "The deadline is tight" | TDD is faster than debugging untested code under deadline pressure. | Skipping TDD makes deadlines worse, not better. |
| "It's just a config change" | Config bugs are the hardest to debug and the easiest to test. | Write a test that verifies the config does what you expect. |

## Failure Modes

- **Test passes on first run:** Suspicious. Investigate whether it actually tests new behavior. It might be testing something that already exists (useless test).
- **Can't figure out how to test it:** The code is too coupled. This is a design signal. Simplify the interface. Use dependency injection. Make it testable.
- **Bug found:** Write a failing test that reproduces the bug. Then fix it through the TDD cycle. The test proves the fix and prevents regression. NEVER fix bugs without a test.
- **Hard to test in current framework:** Extract the logic into a testable unit. If the framework makes testing impossible, discuss with your human partner.

## Inherited red — the one place VERIFY-FAIL is already banked

This is NOT a way to skip the red-confirm. It is the recognition that on a
resumed cycle, the red-confirm may have *already happened*, in the session that
wrote the test — and re-watching it adds no information, only a full-suite run
that the 2026-07-15 resume profile counted as 2.5× the test runs of a bare agent.

The carve-out applies **only** when ALL of these hold (`trust_inherited_red`,
default `true`; set `false` to always re-confirm):

1. **This session resumed the cycle** (`manifest.py resume` produced the brief).
   A first-session build is never inherited red — you write the test, you watch
   it fail, always.
2. **The prior session's evidence records the test as written-and-observed-failing** —
   the plan/manifest names it, and the test file exists in the tree. Its red was
   observed and banked by the session that wrote it; that is the observer the
   Iron Law requires.
3. **The test is for the SAME behavior you are now implementing** — not a new
   assertion you are adding this session.

When all three hold: you may go straight to GREEN — write the minimal code, then
**VERIFY PASS** (run the test, watch it pass). You still confirm green; you skip
only the re-run whose sole purpose was to re-witness a failure already witnessed.

**Fall back to the full RED → VERIFY-FAIL cycle the moment any condition breaks:**
the named test is absent from the tree, or it is unexpectedly *green* before you
write code (a green inherited test is exactly the "testing something that already
works / testing the wrong thing" trap — investigate it, do not trust it), or you
find yourself adding a new assertion (that is a new RED, and it is yours to
watch). A test THIS session authors always goes through the full cycle. When in
doubt, re-confirm — the re-run is cheap insurance against building on a test that
never actually failed.

## Waiver Process

The ONLY way to skip TDD is an explicit human override:

```
Human: "skip-tdd for this change"
```

The waiver is logged in `.sage/decisions.md` with reason and scope.
The resulting code is flagged as untested technical debt for follow-up.
The agent MUST NOT suggest or encourage waivers.

## Examples

### Good: Bug Fix with TDD

```
RED:   test('login rejects expired JWT tokens', () => { ... })
       → Run → FAILS (expected: 401, got: 200) ✓ Correct failure
GREEN: Add expiry check to auth middleware
       → Run → PASSES ✓
       → All other tests → PASS ✓
REFACTOR: Extract token validation to shared utility
       → Run → All PASS ✓
COMMIT: "fix: reject expired JWT tokens"
```

### Bad: Implementation Without TDD

```
Agent writes auth middleware with expiry check → 200 lines
Agent writes tests after → All pass immediately
PROBLEM: Tests pass because they test what the code does, not what it should do.
         Edge cases missed. Expiry check has off-by-one error. Nobody will find
         it until production.
CORRECT ACTION: Delete the code. Start with the test.
```
