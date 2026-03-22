---
name: review
version: "1.0.0"
mode: review
produces: ["Review report with strengths, issues, risks, verdict"]
checkpoints: 1
scope: "Single session"
user-role: "Accept findings, revise, or discuss"
---

# Review Workflow

Independent evaluation of Sage artifacts. Designed to work in a fresh
session for maximum objectivity, but also works within an existing session.

## Step 1: Identify What to Review

If not specified, scan `.sage/work/` and `.sage/docs/` for recent
artifacts. Present them:

Sage: Available for review:

[1] .sage/work/20260316-checkout/brief.md (updated today)
[2] .sage/work/20260316-checkout/spec.md (updated today)
[3] .sage/docs/ux-audit-homepage.md (updated yesterday)

Which artifact should I review? Or describe what you'd like evaluated.

If the user specifies an artifact, proceed directly.

## Step 2: Gather Context

Search for prior knowledge by calling the MCP tool:
```
sage_memory_search(query: "<artifact topic and domain>", limit: 5)
```
If the tool is not available, proceed without memory context.

Read the artifact fully.

Identify which skill or workflow produced this artifact — check for
skill prefixes in the filename, references in the content, or metadata.
Load the producing skill's quality criteria — these become the primary
evaluation framework. If the producing skill cannot be identified,
use the three general lenses in Step 3.

If this is a fresh session, note: "Sage: Reviewing with fresh eyes —
I wasn't involved in producing this work."

If this is the same session, note: "Sage: I produced this work, so my
review may have blind spots. For a more independent evaluation,
consider a fresh session or the /review command."

## Step 3: Evaluate

Review the artifact against three lenses:

For detailed code quality review, read
`sage/core/capabilities/review/quality-review/SKILL.md`.

**Completeness** — Does it cover what it should? Are there missing
sections, unaddressed scenarios, or gaps in reasoning? Check against
the producing skill's quality criteria if available.

**Consistency** — Does it align with other project artifacts? Does
the spec match the brief? Does the plan match the spec? Are there
contradictions within the document itself?

**Quality** — Is the thinking sound? Are claims supported by evidence?
Are trade-offs named explicitly? Would a domain expert find this
credible? Is anything vague where it should be specific?

For each finding, note:
- What you observed (specific, with quotes or references)
- Why it matters (impact on downstream work)
- Suggested action (fix, clarify, investigate, or accept as-is)

## Step 4: Present Findings

Structure the review clearly:

```
## Review: [artifact name]

### Strengths
[What's well-done — be specific, not generic praise]

### Issues Found
[Each issue: observation → impact → suggestion]

### Risks
[Things that aren't wrong but could cause problems downstream]

### Verdict

[One of:]
  ✓ Ready to proceed — [minor notes if any]
  ⚠ Needs revision — [specific items to address]
  ✗ Significant gaps — [recommend rework before proceeding]
```

## Step 5: Next Steps

Based on the verdict:

- **Ready:** Recommend the natural next step in the workflow
- **Needs revision:** List specific items to address, offer to help
- **Significant gaps:** Recommend which step to return to and why

[A] Accept findings — proceed with suggested next step
[R] Revise — I'll address the issues found
[D] Discuss — let's talk about specific findings

Update `.sage/progress.md` with review completion.

## Rules

- Be specific. "The spec is good" is not a review. "The spec covers
  the happy path thoroughly but doesn't address what happens when the
  payment gateway times out" is a review.
- Be honest. The purpose of review is to catch problems before they
  become expensive. Diplomatic honesty serves the user better than
  comfortable vagueness.
- Evaluate against criteria, not preferences. Use the producing skill's
  quality criteria when available. When not, use the three lenses above.
- Fresh session review is always recommended for high-stakes artifacts
  (briefs, specs, architecture decisions).
