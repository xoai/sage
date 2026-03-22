---
name: build
version: "1.0.0"
mode: build
produces: ["Brief (medium+ tasks)", "Spec", "Implementation plan"]
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

Sage recommends the **build** workflow for this [size] task:

[1] [Recommended path]
[2] [Lighter alternative]
[3] Something else — describe your preference

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
Sage: Spec saved to .sage/work/YYYYMMDD-slug/spec.md

[A] Approve — continue to plan
[R] Revise — tell me what to change

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

Implement tasks following the plan. Focus on quality — tests for each
change, verify before moving on.

If relevant Sage skills exist, read and follow them.

**If stuck during implementation:** Activate the `problem-solving` skill.
Match the stuck pattern to a technique — complexity spiral → Simplification,
forced solution → Inversion, works-locally-but-fails → Scale Testing,
can't isolate → Minimal Reproduction.

## Step 7: Verify

**Run the verification command. Read the output. THEN report.**

1. Run the project's test suite (full suite, not just new tests)
2. Read the actual output — don't summarize from memory
3. Confirm: zero failures, zero errors
4. If any test fails, fix it before proceeding — do NOT present
   the completion checkpoint with failing tests

```
Sage: Verification results:

  Test suite: [command that was run]
  Result: [X passed, 0 failed] ← paste actual output
```

**If tests fail:** Diagnose and fix. If the failure persists after
2 attempts, activate the `problem-solving` skill.

## Step 8: Review and Close

Review against spec. Check for missed edge cases.

🔒 **CHECKPOINT:**
```
Sage: Build complete. [summary of what was built]

[A] Approve — merge/ship
[R] Revise — here's what needs fixing
[N] Next — what should we work on next?
```

**On approval — checkpoint state update (Rule 7):**
1. Walk through plan.md and check completed tasks in bulk
2. Update plan.md frontmatter: `status: completed`
3. Update `.sage/progress.md` with completion
4. Update `.sage/journal.md` with final status for all artifacts
5. Store key findings in memory (architecture, conventions, insights)
6. Recommend what's next

## Quality Criteria

**Communication style:** Engineering precision. Emphasize trade-offs,
edge cases, and implementation specifics. Reference file paths, function
names, and test results concretely.

Good build output:
- Implementation matches the spec — no undocumented deviations
- Tests exist for new functionality and pass — output pasted as evidence
- Edge cases from the spec are handled, not just happy paths
- Code follows project conventions (naming, structure, patterns)
- No unrelated changes mixed in — scope discipline maintained
- Verification output is from the actual test run, not a summary

## Self-Review

Before presenting completed work, check each criterion above. Also:
- Did I paste actual test output, or just claim tests pass?
- Did I run the FULL suite, or just the new tests?
- Are there spec requirements I didn't implement or test?

## Rules

- Test first, always.
- Verify with evidence: paste test output, don't summarize.
- Checkpoints are mandatory — never skip human approval.
- Stay in scope — note improvements, don't add them.
- If stuck, use problem-solving: don't keep trying the same approach.
- Save state after every significant step.
