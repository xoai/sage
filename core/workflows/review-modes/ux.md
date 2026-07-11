---
name: analyze
version: "1.0.0"
mode: analyze
produces: ["Audit findings", "Evaluation report", "Severity scores"]
checkpoints: 2
scope: "Single session"
user-role: "Define scope, approve findings"
---

# Analyze Workflow

Evaluate what exists. Audit, measure, score, find gaps.

## Auto-Pickup

Scan `.sage/docs/` for existing evaluation artifacts (ux-audit-*,
ux-evaluate-*, analysis-*). If prior analysis exists, build on it.

Read `.sage/decisions.md` for context.

## Step 1: Scope the Analysis (Zone 1)

Sage → analyze workflow. What are you evaluating?

[1] UX quality — UX audit → usability evaluation (2 steps)
[2] User needs — JTBD analysis on existing product (1 step)
[3] Content quality — content evaluation (1 step)
[4] Custom — describe what you want to evaluate

Pick 1-4, type / for commands, or describe what you need.

## Step 2: Execute Skill Chain

Based on scope, load and execute skills in sequence:

| Scope | Skill Chain |
|-------|-------------|
| UX quality | ux-audit → ux-evaluate |
| User needs | jtbd (applied to existing product) |
| Content | ux-writing (evaluation mode) |
| Custom | select best-matching skill from installed skills |

For each skill in the chain:
1. Announce: "Sage: Starting [skill name]."
2. Load `sage/skills/[skill]/SKILL.md` and follow its process
3. Save output to `.sage/docs/[skill-prefix]-[topic].md`
4. Present per-skill findings (Zone 2):

Sage: [Skill] findings for [topic]:
- [Finding with severity]
- [Finding with severity]

[A] Approve — continue to next step  [R] Revise

Pick A/R, or tell me what to change.

5. On approval, proceed to next skill in chain

## Step 3: Synthesize and Score

After all skills complete:
- Aggregate findings by severity (Critical / Major / Minor)
- Identify patterns across findings
- Prioritize: what to fix first based on impact

🔒 **FINDINGS CHECKPOINT (Zone 2):**

Sage: Analysis complete.

Critical: [N findings — brief summary]
Major: [N findings — brief summary]
Minor: [N findings]

Top priority: [most impactful finding with rationale]

Artifacts:
  .sage/docs/[skill-prefix]-[topic].md

Decision: [analysis conclusions]. (prepended to decisions.md)

[A] Approve findings  [R] Revise  [N] New session → /design to continue

Pick A/R/N, or tell me what to change.

**Findings quality check (before presenting):**
- Severity assigned to each finding (Critical/Major/Minor)?
- Evidence cited (not just opinions)?
- Actionable recommendations included?

## Step 4: Next Step (Zone 3)

Next steps:
  /design  — brief → spec → copy (address the issues found)
  /fix     — diagnose → scope → fix → verify (fix specific issues)
  /reflect — review evaluation quality, extract patterns
  /research — deeper understanding of why issues exist

Type a command, or describe what you want to do next.

## Quality Criteria

Good analysis output:
- Every finding has severity classification
- Evidence supports each finding (not just "this seems wrong")
- Findings are specific (names screens, components, flows)
- Recommendations are actionable (not "improve the UX")
- Priorities are justified by impact, not listing order

## Rules

- Severity classification is mandatory for all findings
- Save all findings to .sage/docs/ with skill-prefix naming
- Present findings BEFORE storing in memory
- Critical findings should surface first in the synthesis
- If the analysis reveals systemic issues, suggest /architect
