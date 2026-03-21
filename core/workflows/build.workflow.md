---
name: build
version: "1.0.0"
mode: build
produces: ["Brief (medium+ tasks)", "Spec", "Plan with task checkboxes"]
checkpoints: 3
scope: "Single session for medium tasks, multi-session for large"
user-role: "Review and approve at each gate"
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

Present your assessment:

```
Sage recommends the **build** workflow for this [size] task:

[1] [Recommended path]
[2] [Lighter alternative]
[3] Something else — describe your preference
```

## Step 3: Brief (medium/large tasks)

If no brief exists and the task warrants one, define: what to build,
why, acceptance scenarios, and constraints.

Save to `.sage/work/YYYYMMDD-slug/brief.md` with frontmatter:

```yaml
---
title: "Brief description of the initiative"
status: in-progress
phase: brief
priority: high  # high | medium | low
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

🔒 **CHECKPOINT:**
```
Sage: Brief saved to .sage/work/YYYYMMDD-slug/brief.md

[A] Approve — continue to spec
[R] Revise — tell me what to change
```

On approval: update brief frontmatter to `status: completed`.
Run Post-Flight (update journal, store findings).

## Step 4: Spec

Define: components, data model, APIs, key decisions, edge cases.
Resolve open questions from the brief.

Save to `.sage/work/YYYYMMDD-slug/spec.md` with frontmatter:

```yaml
---
title: "Spec for [initiative]"
status: in-progress
phase: spec
priority: high
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

🔒 **CHECKPOINT:**
```
Sage: Spec saved to .sage/work/YYYYMMDD-slug/spec.md

[A] Approve — continue to plan
[R] Revise — tell me what to change
```

On approval: update spec frontmatter to `status: completed`.
Run Post-Flight (update journal, store findings).

## Step 5: Plan

Break into small tasks (2-5 min each). Each task: what to do, done
criteria, files involved. Checkboxes for tracking.

Save to `.sage/work/YYYYMMDD-slug/plan.md` with frontmatter:

```yaml
---
title: "Plan for [initiative]"
status: in-progress
phase: plan
priority: high
created: YYYY-MM-DD
updated: YYYY-MM-DD
tasks-total: 0   # count of checkboxes
tasks-done: 0    # count of checked boxes
---
```

🔒 **CHECKPOINT:**
```
Sage: Plan saved to .sage/work/YYYYMMDD-slug/plan.md

[A] Approve — start building
[R] Revise — tell me what to change
```

On approval: run Post-Flight (update journal, store findings).

## Step 6: Implement

Per task: test first → code → refactor → run suite → commit.

**After completing each task:**
1. Check the box in plan.md (`- [ ]` → `- [x]`)
2. Update `tasks-done` and `updated` in plan.md frontmatter
3. Run Post-Flight if the task produced significant findings

If relevant Sage skills exist, read and follow them.

## Step 7: Review and Close

Run full test suite. Review against spec. Check for missed edge cases.

🔒 **CHECKPOINT:**
```
Sage: Build complete. [summary of what was built]

[A] Approve — merge/ship
[R] Revise — here's what needs fixing
[N] Next — what should we work on next?
```

**On approval — final state management:**
1. Update plan.md frontmatter: `status: completed`
2. Update `.sage/progress.md` with completion
3. Update `.sage/journal.md` with final status for all artifacts
4. Store key findings in memory (architecture, conventions, insights)
5. Recommend what's next

## Quality Criteria

**Communication style:** Engineering precision. Emphasize trade-offs,
edge cases, and implementation specifics. Reference file paths, function
names, and test results concretely.

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
