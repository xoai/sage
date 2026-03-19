---
name: architect
version: "1.0.0"
mode: architect
---

# Architect Workflow

System design for new projects or major redesigns.

## Step 1: Orient

Read `.sage/progress.md` and scan `.sage/docs/` for existing research,
briefs, or decisions. Understanding what exists prevents redundant work.

## Step 2: Deep Elicitation

This is the most important step. Understand the full picture before
designing anything. Explore in focused rounds:

**Round 1 — Vision:** What are you building and why? Who is it for?
What does success look like?

**Round 2 — Constraints:** Technical constraints, timeline, team size,
existing systems to integrate with, non-negotiables.

**Round 3 — Gaps:** What's still unclear? What assumptions are we making?

If Sage has relevant UNDERSTAND skills (research, analysis), recommend
them here:

```
Before designing the architecture, I recommend:

1) Start with research — understand user needs first (~15 min)
2) Skip research — go straight to architecture design
3) Something else
```

## Step 3: Architecture Design

Define: system components, data model, API boundaries, technology choices,
deployment architecture, security model. Document key trade-offs and
the reasoning behind each decision.

Save architecture decisions to `.sage/docs/decision-*.md`.
Save the full design to `.sage/work/YYYYMMDD-slug/spec.md`.

🔒 **CHECKPOINT:**
```
[A] Approve — continue to planning
[R] Revise — here's what needs changing
[Q] Question — I want to understand [specific decision] better
```

## Step 4: Milestone Plan

Break the build into milestones (not tasks — milestones). Each milestone
should be deployable and testable independently. Within each milestone,
create a task plan.

Save to `.sage/work/YYYYMMDD-slug/plan.md`.

🔒 **CHECKPOINT:**
```
[A] Approve — start building milestone 1
[R] Revise — adjust the breakdown
```

## Step 5: Phased Build

Execute milestone by milestone. Each milestone follows the build workflow:
implement → test → review → checkpoint before moving to the next.

After each milestone:
```
Milestone [N] complete: [summary]

[C] Continue to milestone [N+1]
[R] Revise — adjust before continuing
[P] Pause — save state for next session
```

## Quality Criteria

Good architecture output:
- Trade-offs are named explicitly — if there are no trade-offs, the thinking isn't deep enough
- Failure modes are addressed for every integration point
- The design handles the next 3x scale, not just today's requirements
- System boundaries are clear — what's in scope, what's external
- Each milestone is independently deployable and valuable
- The architecture can be explained in one paragraph to a non-technical stakeholder

## Self-Review

Before presenting architecture decisions, check each criterion above.
Challenge your own assumptions — what would a skeptical senior engineer
question? Present your self-assessment alongside the design.

## Rules

- Architecture decisions must be documented with rationale, not just chosen.
- Each milestone must be independently testable.
- Re-validate architecture assumptions after each milestone —
  real implementation reveals things design missed.
- Save state frequently. Architect-scale work spans sessions.
