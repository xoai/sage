---
name: review
description: >
  Independent artifact review via sub-agent delegation. Evaluates
  completeness, consistency, and quality with severity classification.
disable-model-invocation: true
---

RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/reviewer.persona.md for your mindset.
- Announce: "Sage → review workflow." before starting work
- Present artifact list with [1] [2] [3] bracket notation
- Present findings with [A] Accept / [R] Revise / [D] Discuss
- Load producing skill's quality criteria — mandatory, not optional
- DELEGATION: If Task tool is available, you MUST use it for review.
  Self-review is NOT independent review. Do NOT review your own work
  and present it as an independent evaluation.
- Never use code blocks for interaction output

Review an artifact with independent evaluation via sub-agent delegation.

## Step 1: Identify What to Review

If not specified, scan `.sage/work/` and `.sage/docs/` for recent
artifacts. Present them:

**Sage:** Available for review:

[1] .sage/work/20260316-checkout/brief.md (updated today)
[2] .sage/work/20260316-checkout/spec.md (updated today)
[3] .sage/docs/ux-audit-homepage.md (updated yesterday)

Which artifact should I review?

If the user specifies an artifact, proceed directly.

## Step 2: Prepare Review Context

Before delegating, gather three pieces of information:

1. **Artifact path** — the file to review
2. **Producing skill path** — find which skill or workflow created it.
   Check filename prefix, content references, or `.sage/decisions.md`.
   The quality criteria are in that skill's `## Quality Criteria` section
   (look in `sage/skills/[skill]/SKILL.md` or `sage/core/workflows/[workflow].workflow.md`)
3. **Memory query** — 3-5 keywords describing the artifact's domain
   (e.g., "billing checkout payment saga")

## Step 3: Delegate to Review Sub-Agent

**Delegation is MANDATORY when Task tool is available.**
Do NOT skip delegation because:
- "I can review this myself" → self-review is not independent review
- "The artifact is simple" → simple artifacts still benefit from fresh eyes
- "It will be faster" → speed is not the goal, independence is

If Task tool is NOT available (e.g., Antigravity platform), proceed with
self-review but announce it: "Sage: Task tool not available. Performing
self-review — note this is not independent evaluation. Consider a
fresh-session /review for critical artifacts."

Tell the user: "Sage: Delegating to a review sub-agent for independent
evaluation. The reviewer gets a fresh context window without my
reasoning from this session."

Use the Task tool to spawn a sub-agent with this prompt:

```
You are independently reviewing a Sage project artifact. You were
NOT involved in producing this work — evaluate it with fresh eyes.

CONTEXT PACKAGE:
1. PERSONA: Read sage/core/agents/reviewer.persona.md for mindset.
2. ARTIFACT: Read the artifact at: [ARTIFACT PATH]
3. CRITERIA: Read quality criteria from: [SKILL/WORKFLOW PATH],
   section titled "## Quality Criteria"
4. DECISIONS: Read .sage/decisions.md for last 5 entries.
5. LEARNINGS: Call sage_memory_search(query: "[MEMORY QUERY]", limit: 5)
   If this tool is not available, check .sage-memory/ folder.

EVALUATE the artifact against EACH quality criterion specifically.

CLASSIFY each finding by severity:
- CRITICAL: Blocks proceeding. Must fix before next step.
- MAJOR: Significant gap. Should fix before next step.
- MINOR: Improvement opportunity. Can fix later.

PRESENT YOUR REVIEW AS:

## Review: [artifact name]

### Critical Issues
[If none, say "None found." Do not omit this section.]

### Major Issues
[If none, say "None found." Do not omit this section.]

### Minor Issues / Improvements
[Specific observations with suggested actions]

### Strengths
[Specific observations — not generic praise]

### Verdict
PASS — ready to proceed [minor notes if any]
NEEDS REVISION — [specific items to address, with severity]
FAIL — [significant gaps, recommend returning to earlier step]
```

## Step 4: Present Findings

Share the sub-agent's review with the user.

**Critical findings block approval.** If the review contains CRITICAL
issues, do NOT present [A] Accept as the first option:

Sage: Review found critical issues that must be addressed:
[critical findings summary]

[R] Address critical issues first
[D] Discuss — let's talk about specific findings
[A] Accept anyway — I understand the risks

If no critical issues:

Sage: Review complete. [verdict summary]

[A] Accept findings — proceed with suggested next step
[R] Revise — I'll address the issues found
[D] Discuss — let's talk about specific findings

Append review findings to `.sage/decisions.md`.

$ARGUMENTS
