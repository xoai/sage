---
name: research
version: "1.0.0"
mode: research
produces: ["Research findings", "Need analysis", "Opportunity map"]
checkpoints: 2
scope: "Single session for focused, multi-session for comprehensive"
user-role: "Define scope, approve findings before storage"
---

# Research Workflow

Understand before building. Research users, needs, and opportunities.

## Auto-Pickup

Scan `.sage/docs/` for existing research artifacts (jtbd-*, ux-audit-*,
opportunity-*, user-interview-*). Scan `.sage/work/` for in-progress
research initiatives.

If prior research exists: "Sage: Found existing research — [list].
Building on what's already known."

If in-progress initiative: resume from current phase.

Read `.sage/decisions.md` for context.

## Step 1: Scope the Research (Zone 1)

Sage → research workflow. What do you want to understand?

[1] Users — interview → JTBD analysis (2 steps)
[2] Opportunity — JTBD → opportunity map (2 steps)
[3] Experience — UX audit → evaluation (2 steps)
[4] Comprehensive — interview → JTBD → UX audit → opportunity map (4 steps)

Pick 1-4, type / for commands, or describe what you need.

## Step 2: Execute Skill Chain

Based on scope, load and execute skills in sequence:

| Scope | Skill Chain |
|-------|-------------|
| Users | user-interview → jtbd |
| Opportunity | jtbd → opportunity-map |
| Experience | ux-audit → ux-evaluate |
| Comprehensive | user-interview → jtbd → ux-audit → opportunity-map |

For each skill in the chain:
1. Announce: "Sage: Starting [skill name]."
2. Load `sage/skills/[skill]/SKILL.md` and follow its process
3. Save output to `.sage/docs/[skill-prefix]-[topic].md`
4. Present per-skill findings (Zone 2):

Sage: [Skill] findings for [topic]:
- [Key finding 1]
- [Key finding 2]

[A] Approve — continue to next step  [R] Revise

Pick A/R, or tell me what to change.

5. On approval, proceed to next skill in chain

## Step 3: Synthesize

After all skills in the chain complete:
- Cross-reference findings across skills
- Identify the top 3-5 insights with supporting evidence
- Note contradictions or gaps between findings

🔒 **FINDINGS CHECKPOINT (Zone 2):**

Sage: Research complete. Key findings:

1. [Top insight with evidence]
2. [Second insight]
3. [Third insight]

Artifacts:
  .sage/docs/[skill-prefix]-[topic].md (for each skill)

Decision: [research conclusions]. (appended to decisions.md)

[A] Approve findings  [R] Revise  [N] New session → /design to continue

Pick A/R/N, or tell me what to change.

**Findings quality check (before presenting):**
- Specific? Names concrete things, not vague patterns.
- Insight, not inventory? Tells you something beyond file listings.
- Actionable? A designer or builder could use this finding.

## Step 4: Next Step (Zone 3)

Next steps:
  /design — brief → spec → copy (reads your research findings)
  /build  — spec → plan → implement → verify
  /analyze — deeper evaluation of specific areas

Type a command, or describe what you want to do next.

## Quality Criteria

Good research output:
- Findings are specific and evidence-based, not generic
- Each finding includes supporting data or quotes
- Contradictions between sources are noted, not hidden
- The synthesis connects individual findings into a narrative
- Artifacts are saved to .sage/docs/ with clear naming

## Rules

- Search existing knowledge before researching (don't re-learn).
- Save all findings to .sage/docs/ with skill-prefix naming.
- Present findings BEFORE storing in memory (user approves first).
- Use WHEN/CHECK/BECAUSE for any self-learning captures.
- Each skill in the chain gets its own checkpoint.
- The synthesis is more than a summary — it connects findings.
