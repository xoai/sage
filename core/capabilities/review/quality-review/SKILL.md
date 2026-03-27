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

### Sub-Agent Delegation (REQUIRED when Task tool available)

Gate 3 REQUIRES sub-agent delegation when Task tool is available.
Self-review is the fallback when Task tool is NOT available, not
a choice the agent makes.

**Step 1:** Check Task tool availability.

**Step 2 — Task tool available AND `independent_gate3` ≠ false:**

Announce: "⚡ Running code quality review (sub-agent)..."

Spawn a sub-agent with the following prompt:

```
You are a code reviewer. You were NOT involved in writing this code.
Review it for quality, security, and maintainability. Be specific.

INPUTS:
- Changed files: {FILE_LIST}
- Project conventions: {CONVENTIONS_FILE or "none detected"}
- Stack: {DETECTED_STACK or "unknown"}

REVIEW THESE 5 DIMENSIONS:

1. READABILITY: Are names descriptive? Is flow obvious? Are complex
   sections commented with WHY? Is there unnecessary complexity?

2. ERROR HANDLING: Are errors handled, not swallowed? Do error
   messages help diagnose? Are failure paths tested? Are external
   calls protected?

3. SECURITY: Are inputs validated? Is auth checked? Are secrets
   hardcoded? Is user data logged? Are queries parameterized?
   Security issues are ALWAYS critical.

4. PERFORMANCE: Are there N+1 patterns? Unnecessary allocations?
   Large datasets loaded into memory? Only flag OBVIOUS issues —
   no speculative optimization.

5. CONVENTIONS: Does the code match existing project patterns?
   Naming, file structure, style? Is it internally consistent?

CLASSIFY each finding:
- CRITICAL: Security vulnerability or will break in production.
  Must fix. Security issues are ALWAYS critical.
- WARNING: Quality issue. Should fix before shipping.
- SUGGESTION: Optional improvement. Can defer.

FORMAT (strict):
GATE: code-quality
RESULT: PASS | FAIL
CRITICAL: [list with file:line or "None"]
WARNING: [list with file:line or "None"]
SUGGESTION: [list with file:line or "None"]

Be concise. Every finding names a specific file and line.
No generic praise. No vague observations. Just findings.
Security issues found = ALWAYS FAIL.
```

Present the sub-agent's findings as the Gate 3 result. Do NOT
filter, downgrade, or dismiss findings.

**Step 3 — Task tool NOT available OR `independent_gate3` is false:**

Self-review fallback. Announce: "Self-review only — Task tool not
available. For independent review, run /review."

Do NOT self-review when Task tool IS available and config allows
sub-agent. That defeats the purpose of independent review.

Proceed with self-review using the 5 dimensions below.

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
