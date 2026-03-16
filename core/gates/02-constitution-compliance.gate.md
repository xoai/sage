---
name: constitution-compliance
description: Verifies implementation respects all project and organizational governance principles.
version: "1.0.0"
order: 2
cost-tier: sonnet
required-context: [constitution, implementation]
category: compliance
---

# Gate 2: Constitution Compliance

Does the code respect every active principle in the merged constitution?

## Check Criteria

For each principle in the effective constitution (org + project + feature):
- [ ] The implementation does NOT violate this principle
- [ ] If the principle mandates a pattern (e.g., "all APIs require auth"),
      the pattern IS present in the implementation
- [ ] If a waiver exists for this principle in this scope, the waiver is
      documented with reason, approver, and expiration

## Adversarial Guidance

Agents are prone to "creative interpretation" of constitution principles.
If a principle says "no third-party dependencies without license check," the
agent might rationalize that a "well-known" library doesn't need checking.
It does. The constitution is literal.

Check for:
- Principles technically followed but violated in spirit
- Mandated patterns that are present but implemented incorrectly
- Implicit assumptions that contradict constitution constraints

## Failure Response

**Principle violated:** FAIL. Implementer changes code to comply. Re-run.
**Mandated pattern missing:** FAIL. Implementer adds the pattern. Re-run.
**Legitimate conflict between task and constitution:** FAIL with `escalate-to-human`.
The human decides: waiver (documented) or change approach.
