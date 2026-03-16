---
name: quality-review
description: >
  Reviews code for quality, security, maintainability, and performance beyond
  spec compliance. Checks clean code practices, error handling, security
  vulnerabilities, and convention adherence. Use after implementation, or when
  the user says "review my code", "quality check", "security review", or "is
  this code good".
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: mandatory
tags: [review, quality, security, performance, maintainability]
inputs: [implementation, codebase-context, constitution]
outputs: [review-result]
-->

# Quality Review

Evaluate code craftsmanship — is it clean, secure, maintainable, and performant?

**Core Principle:** Spec compliance (Gate 1) verifies you built the right thing.
Quality review (Gate 3) verifies you built it well. Both are required.

## When to Use

After spec review passes (Gate 1) and constitution compliance passes (Gate 2),
as Gate 3 in the quality pipeline.

## Process

### Dimension 1: Readability

- Is the code clear to someone unfamiliar with it?
- Are names descriptive and consistent with project conventions?
- Is the logic flow easy to follow? Are complex sections commented?
- Is there unnecessary complexity that could be simplified?

### Dimension 2: Error Handling

- Are errors handled, not swallowed? No empty catch blocks.
- Do error messages help diagnose the problem?
- Are failure paths tested?
- Are external call failures handled (network, database, file system)?

### Dimension 3: Security

- Are inputs validated and sanitized?
- Is authentication/authorization checked where needed?
- Are secrets hardcoded? (Should use environment variables or secret management)
- Is user data logged inappropriately?
- Are SQL queries parameterized? (No string concatenation)
- Are dependencies from trusted sources with known versions?

### Dimension 4: Performance

- Are there obvious N+1 query patterns?
- Are there unnecessary allocations in hot paths?
- Are large datasets loaded into memory when streaming would work?
- Are there missing indexes for frequent queries?
- Only flag OBVIOUS issues — don't micro-optimize speculatively.

### Dimension 5: Conventions

- Does the code follow the patterns established in the codebase? (from codebase-scan)
- Is it consistent with project naming, file structure, and style?
- Does it follow the constitution's mandated patterns?

### Output

```
GATE: code-quality
RESULT: PASS | FAIL

FINDINGS:
  Readability: [PASS | issues found]
  Error Handling: [PASS | issues found]
  Security: [PASS | issues found — security issues are always FAIL]
  Performance: [PASS | issues found]
  Conventions: [PASS | issues found]

SEVERITY:
  Critical: [list — these cause FAIL]
  Warning: [list — these are noted but don't block]
  Suggestion: [list — optional improvements]

ACTION: none | fix-and-retry | escalate-to-human
```

## Rules

- Security issues are ALWAYS critical — they cause FAIL regardless of severity assessment.
- Performance opinions must be evidence-based. "This might be slow" is not a finding.
  "This loads all records into memory for a table that could have millions of rows" is a finding.
- Convention deviations are critical only if they break consistency in a meaningful way.
  A different variable name style is critical. A slightly different comment format is a suggestion.
- Don't nitpick style when the project has no established style guide. Pick battles.
- Do NOT suggest rewrites. Flag specific issues with specific locations.

## Failure Modes

- **Code is correct but ugly:** PASS with suggestions. Correctness > aesthetics.
- **Security vulnerability found:** ALWAYS FAIL. Even for internal tools. Security is not optional.
- **Performance concern is speculative:** Note as suggestion, not finding. Don't block on "might be slow."
