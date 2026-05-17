---
description: Run the configured spec_reviewer on plan.md for the given slug
argument-hint: [slug]
allowed-tools: Bash(.sage/scripts/run-role.sh:*), Bash(ls -1t .sage/work/*), Read, Glob
---

# /review-plan — adversarial review of plan.md

Active slug: $ARGUMENTS

If no slug was given:

! ls -1t .sage/work/ 2>/dev/null | head -1

Run the reviewer (delegate to `codex-reviewer` sub-agent):

! .sage/scripts/run-role.sh spec_reviewer doc "$ARGUMENTS" plan.md

Read the produced review file. Plan reviews most often surface
**SCOPE_DRIFT** (plan implements things the spec doesn't ask for) and
**CONTRADICTIONS** (plan step contradicts spec requirement). Surface
these inline:

1. Verdict line.
2. SCOPE_DRIFT findings (if any) — these tell you the spec needs
   tightening, the plan needs trimming, or both.
3. CONTRADICTIONS — list them with both sides quoted.
4. All other BLOCKER + MAJOR findings (≤5 bullets).
5. Recommended next step:
   - `APPROVE` → suggest `/implement <slug>`
   - `REVISE` → list which plan steps need rework
   - `REJECT` → likely means the spec needs revision first
