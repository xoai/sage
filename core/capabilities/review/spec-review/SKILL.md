---
name: spec-review
description: >
  Adversarial review verifying implementation matches its specification —
  checks completeness (nothing missing) and precision (nothing extra).
  Distrusts the implementer's self-report. Use after implementation,
  or when the user says "check against spec", "does this match requirements",
  or "verify the implementation".
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: mandatory
tags: [review, compliance, quality, verification]
inputs: [task-spec, implementation]
outputs: [review-result]
-->

# Spec Review

Verify that the implementation matches its specification — nothing more, nothing less.

**Core Principle:** Do NOT trust the implementer's report. The implementer may have
finished too quickly, missed requirements, added unrequested features, or described
what they intended rather than what they built. Verify EVERYTHING independently.

## When to Use

After every task implementation, as part of the quality gate sequence.
This is Gate 1 of 5 — it runs first because all other gates are meaningless
if the code doesn't even match what was requested.

## Process

### Step 1: Read the Specification

Read the COMPLETE task specification. Understand:
- What was requested (functional requirements)
- What was explicitly excluded (boundaries)
- What the acceptance criteria are (verification)

### Step 2: Read the Implementation

Read the ACTUAL code that was written. Not the implementer's summary. Not
the commit message. The code itself.

### Step 3: Checklist Comparison

For each requirement in the specification:
- [ ] Is it implemented? (Check the code, not the report)
- [ ] Is it implemented CORRECTLY? (Does the logic match the intent?)
- [ ] Is it tested? (Does a test exist that verifies this requirement?)

For each piece of code in the implementation:
- [ ] Was it requested? (Is there a corresponding requirement?)
- [ ] If not requested, is it necessary infrastructure? (Imports, types, config)
- [ ] Or is it scope creep? (Features, optimizations, "nice to haves" not in spec)

### Step 4: Produce Result

```
GATE: spec-compliance
RESULT: PASS | FAIL

REQUIREMENTS CHECK:
  ✓ [requirement 1] — Implemented and tested
  ✓ [requirement 2] — Implemented and tested
  ✗ [requirement 3] — MISSING: not implemented
  ✗ [requirement 4] — PARTIAL: implemented but not tested

SCOPE CHECK:
  ✓ No unrequested features added
  — OR —
  ✗ EXTRA: [description of unrequested code]

ACTION: none | fix-and-retry | escalate-to-human
```

## Rules

- NEVER trust the implementer's self-report. Read the code yourself.
- NEVER approve an implementation that is missing a requirement, even if
  the implementer says "I'll add it later."
- NEVER approve an implementation that adds unrequested features. Extra
  code is extra bugs. The implementer must remove it.
- ALWAYS check that tests exist for each requirement. Untested requirements
  are unverified requirements.
- If the spec is ambiguous, note the ambiguity and ask the human — don't
  interpret it yourself.

## Adversarial Mindset

Assume the implementer:
- Finished suspiciously quickly
- Described what they INTENDED, not what they BUILT
- Missed edge cases they didn't think about
- Added "helpful" features that weren't requested
- Wrote tests that pass but don't actually verify the requirement

Your job is to be the skeptic. If you can't find evidence that a requirement
is implemented and tested, it isn't — regardless of what anyone claims.

## Failure Modes

- **Ambiguous specification:** Don't guess. Report the ambiguity and escalate.
- **Implementation is better than spec:** Still fails. The spec is the contract.
  If the improvement is worth keeping, update the spec first, then re-review.
- **Trivial missing item:** Still fails. Partial compliance is non-compliance.
  The implementer fixes it, then you re-review.
