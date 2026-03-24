---
name: spec-compliance
description: Verifies implementation matches task specification — nothing missing, nothing extra.
version: "1.0.0"
order: 1
cost-tier: sonnet
required-context: [task-spec, implementation]
category: compliance
---

# Gate 1: Spec Compliance

Does the code do what was requested? Only what was requested?

## Deterministic Check Script

**Run the spec compliance script for file existence verification:**

```bash
bash .sage/gates/scripts/sage-spec-check.sh .sage/work/YYYYMMDD-slug/plan.md TASK_NUMBER
```

This script automatically: extracts the task spec from the plan, verifies
all listed files exist, checks test files exist for each source file, and
reports completion status. Exit code 0 = all deliverables present.

The script handles WHAT exists. The manual checks below handle WHETHER
the code is correct — semantic verification that requires reading the code.

## Check Criteria

For each requirement in the task specification:
- [ ] The requirement IS implemented (verify in actual code, not from reports)
- [ ] The implementation is CORRECT (logic matches intent, not just structure)
- [ ] A test EXISTS that verifies this requirement
- [ ] The test was written BEFORE the implementation (TDD compliance)

For each piece of code in the implementation:
- [ ] There IS a corresponding requirement for this code
- [ ] Or it IS necessary infrastructure (imports, types, config, error handling mandated by constitution)
- [ ] It is NOT unrequested functionality, optimization, or "nice to have"

## Adversarial Guidance

Assume the implementer:
- Described what they intended, not what they built
- Missed requirements they considered "obvious"
- Added features they thought would be "helpful"
- Wrote tests that pass but don't verify actual behavior

Read the CODE. Not the commit message. Not the self-review. The code.

## Blocked Rationalizations

- "The implementation covers the intent, even if not every detail" —
  intent is not spec compliance. Check every requirement literally.
- "This extra code is just good practice, not scope creep" — if it's
  not in the spec, it's extra. Remove it or get the spec amended.
- "The test verifies the feature works" — tests can pass while missing
  requirements. Check each spec requirement against code, not tests.
- "I read through the code, it matches" — reading is not checking.
  Use the checklist. Tick each box against actual code lines.

## Failure Response

**Missing requirement:** FAIL. Implementer adds the missing functionality + test. Re-run this gate.
**Extra functionality:** FAIL. Implementer removes unrequested code. Re-run this gate.
**Missing test:** FAIL. Implementer adds the test following TDD (observe failure first). Re-run.
**Ambiguous spec:** FAIL with `escalate-to-human`. Present the ambiguity, don't interpret it.
