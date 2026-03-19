---
name: build
version: "1.0.0"
mode: build
---

# Build Workflow

Feature development guided by Sage.

## Step 1: Orient

Read `.sage/progress.md`. If work is in progress for this feature,
resume from where you left off — do NOT re-elicit or re-plan.

Scan `.sage/docs/` and `.sage/work/` for relevant artifacts (briefs,
specs, plans, research).

## Step 2: Assess Scope and Gaps

Follow the sage-navigator's intelligence layer to assess
scope and detect gaps:

- **Small** (< 30 min): Skip to Step 5, implement directly.
- **Medium** (hours): Recommend a spec first (Step 4).
- **Large** (days): Recommend brief → spec → plan (Steps 3-5).

Present your assessment using numbered options:

```
This looks like a [size] task. I recommend:

1) [Recommended path with time estimates]
2) [Lighter alternative]
3) Something else — describe your preference
```

## Step 3: Brief (medium/large tasks)

If no brief exists and the task warrants one, define: what to build,
why, acceptance scenarios, and constraints.

Save to `.sage/work/YYYYMMDD-slug/brief.md`.

🔒 **CHECKPOINT:**
```
[A] Approve — continue to spec
[R] Revise — tell me what to change
```

## Step 4: Spec

Define: components, data model, APIs, key decisions, edge cases.
Resolve open questions from the brief.

Save to `.sage/work/YYYYMMDD-slug/spec.md`.

🔒 **CHECKPOINT:**
```
[A] Approve — continue to plan
[R] Revise — tell me what to change
```

## Step 5: Plan

Break into small tasks (2-5 min each). Each task: what to do, done
criteria, files involved. Checkboxes for tracking.

Save to `.sage/work/YYYYMMDD-slug/plan.md`.

🔒 **CHECKPOINT:**
```
[A] Approve — start building
[R] Revise — tell me what to change
```

## Step 6: Implement

Per task: test first → code → refactor → run suite → commit →
check the box in plan.md.

If relevant Sage skills exist, read and follow them.

## Step 7: Review and Close

Run full test suite. Review against spec. Check for missed edge cases.

🔒 **CHECKPOINT:**
```
[A] Approve — merge/ship
[R] Revise — here's what needs fixing
[N] Next — what should we work on next?
```

Update `.sage/progress.md`. Recommend what's next.

## Quality Criteria

Good build output:
- Implementation matches the spec — no undocumented deviations
- Tests exist for new functionality and pass
- Edge cases from the spec are handled, not just happy paths
- Code follows project conventions (naming, structure, patterns)
- No unrelated changes mixed in — scope discipline maintained
- Plan checkboxes reflect actual completion status

## Self-Review

Before presenting completed work, check each criterion above. Note
what's covered and what gaps exist. Present your self-assessment
alongside the implementation summary.

## Rules

- Test first, always.
- Checkpoints are mandatory — never skip human approval.
- Stay in scope — note improvements, don't add them.
- Save state after every significant step.
