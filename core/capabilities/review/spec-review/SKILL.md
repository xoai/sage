---
name: spec-review
description: >
  Adversarial review verifying implementation matches its specification —
  checks completeness (nothing missing) and precision (nothing extra).
  Distrusts the implementer's self-report. Use after implementation,
  or when the user says "check against spec", "does this match requirements",
  or "verify the implementation".
version: "1.1.0"
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

## Review Loop v2 (ledger mode)

Active by DEFAULT (an absent `review_loop:` block means `mode: v2`)
(loop: orchestration/quality-locked; ledger: `sage/runtime/tools/
review.py`). When active, the Step 4 RESULT block above is replaced by
the contract below. With `mode: v1` this section is inert.

### Output contract (v2 — no verdict)

Include verbatim in the reviewer's instructions:

> You do not decide the loop; you report findings. The decision is
> computed from them.
>
> A critical or major must come with a witness: a failing test you
> wrote and ran, a concrete repro (input → observed → expected), or an
> execution trace. If you cannot demonstrate it, report it — it will be
> recorded as substantive. This is not a penalty; it is the definition
> of the severities.
>
> An empty finding list is a valid, creditable outcome; you are scored
> on precision, not volume. Every critical/major must cite the spec
> clause, constitution rule, or requirement it violates — a finding
> that cites nothing is capped at substantive automatically, so spend
> your effort on citations and witnesses, not on quantity.

Findings are ONE fenced ```json block — an array of objects (prose
outside it is not parsed):

```json
[{
  "pass": "spec-conformance",
  "severity": "critical | major | substantive | cosmetic",
  "cited_rule": "spec §4.2 | null",
  "anchor": {"file": "src/auth.ts", "region": [118, 141]},
  "claim": "one falsifiable sentence",
  "witness": {"kind": "test | repro | trace | none",
              "ref": "path or matrix cell, else null",
              "status": "red | green | n/a"},
  "exit_criteria": "what specifically would make this finding pass"
}]
```

### The trace matrix (this gate's pass: spec-conformance)

Emit a requirement → implementation-anchor → test-anchor table, one row
per spec requirement and acceptance criterion. **Every empty cell is a
finding** with `witness.kind: trace` and the cell as `ref` — the empty
cell is the demonstration, absence made observable. Enumerate coverage;
do not react to presence. Unrequested code (the scope check above) is a
finding anchored at the extra code, `cited_rule` naming the boundary it
violates.

### Two-phase (rounds >1)

Phase A: verify each open/not-fixed ledger entry (`FIXED | NOT-FIXED |
DISPUTED-STANDS`, evidence required; a test witness is run at current
HEAD — green is FIXED, mechanically). Phase B: new findings from the
revision delta plus Phase-A anchors only; the full matrix was built at
round 1 and only changed rows are re-derived.

### Input packet (v2)

Assembled by the dispatching workflow, in order: (1) the diff/changed
files (delta since last reviewed fingerprint on rounds >1); (2)
deterministic gate outputs verbatim; (3) test output + per-file coverage
for touched files; (4) sage-ontology blast radius for changed symbols —
when absent, the packet says so (loud degradation); (5) the spec
excerpts the diff claims to implement; (6) the ledger (open + settled);
(7) mutation-survivor report if present.

## Failure Modes

- **Ambiguous specification:** Don't guess. Report the ambiguity and escalate.
- **Implementation is better than spec:** Still fails. The spec is the contract.
  If the improvement is worth keeping, update the spec first, then re-review.
- **Trivial missing item:** Still fails. Partial compliance is non-compliance.
  The implementer fixes it, then you re-review.
