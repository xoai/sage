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

## Step 2: Assess Scope

Classify by structural complexity — not time, not gut feeling.

**Lightweight:** One component, no design decisions, no behavior changes
visible to other team members. The change is obvious from the request.
→ Skip to Step 6, implement directly.

**Standard:** Multiple components, OR any design decision, OR
coordination between modules. DO NOT skip the spec.
→ MUST write spec (Step 4) → plan (Step 5) → implement (Step 6).
→ If the task also needs scope definition, write brief first (Step 3).

**Comprehensive:** New subsystem, cross-cutting changes, or multiple
stakeholder impact.
→ MUST write brief (Step 3) → spec (Step 4) → plan (Step 5) → implement.

**Complexity signals** (any ONE makes it Standard or above):
- Touches more than 3 files
- Involves a new API endpoint or data model change
- Requires coordination between multiple modules or services
- Has user-facing behavior changes (new UI, changed flow)
- Involves a decision a team member would need to know about
- Multiple layers affected (database + backend + frontend)

Present your assessment:

**Sage → build workflow.** [Scope] — [what makes it this scope].
Starting with [first required step].

If the user wants to skip a required step, note the risk and proceed —
but record the skip and rationale in progress.md.

## Step 3: Brief (Standard with unclear scope, or Comprehensive)

If scope is unclear or the task is Comprehensive, elicit requirements
before defining the brief.

For structured elicitation process, read
`sage/core/capabilities/elicitation/quick-elicit/SKILL.md`.
It provides 3 focused rounds (~2 minutes):
1. Intent — what should this do when working perfectly?
2. Boundaries — what should this NOT do?
3. Verification — how will we know it works?

If quick-elicit cannot be loaded, ask these three questions directly
and draft a brief from the answers.

Define: what to build, why, acceptance scenarios, and constraints.

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

Sage: Brief saved to .sage/work/YYYYMMDD-slug/brief.md

[A] Approve — continue to spec
[R] Revise — tell me what to change

On approval: update brief frontmatter to `status: completed`.
Run Post-Flight (update journal, store findings).

## Step 4: Spec

Define: components, data model, APIs, key decisions, edge cases.
Resolve open questions from the brief.

For detailed spec writing process, read
`sage/core/capabilities/planning/specify/SKILL.md`.

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

Break into small, independently testable tasks. Each task: what to do,
done criteria, files involved. Use checkboxes as a guide.

For detailed planning process, read
`sage/core/capabilities/planning/plan/SKILL.md`.

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

Sage: Plan saved to .sage/work/YYYYMMDD-slug/plan.md

[A] Approve — start building
[R] Revise — tell me what to change

On approval: run Post-Flight (update journal, store findings).

## Step 6: Implement

Execute the plan task by task using the build loop.

Read and follow `sage/core/capabilities/orchestration/build-loop/SKILL.md`.
It provides:
- Task-by-task execution with status reporting
- TDD discipline for each task (loads `sage/core/capabilities/execution/tdd/SKILL.md`)
- Scope guard to prevent drift (loads `sage/core/capabilities/context/scope-guard/SKILL.md`)
- Quality gates between tasks (loads `sage/core/workflows/sub-workflows/quality-gates.workflow.md`)
- Inter-task checkpoints every 1-3 tasks
- Escalation on repeated failure (3x → ask human)
- Context budget awareness (suggest new session if full)

For implementation discipline, the developer persona at
`sage/core/agents/developer.persona.md` applies.

If the build-loop cannot be loaded, follow these minimum rules:
implement one task at a time, write tests before code, run full
suite after each task, stay in scope, commit after each task.

If relevant Sage skills exist in `sage/skills/`, read and follow them.

**If stuck during implementation:** Activate the `problem-solving` skill.
Match the stuck pattern to a technique — complexity spiral → Simplification,
forced solution → Inversion, works-locally-but-fails → Scale Testing,
can't isolate → Minimal Reproduction.

## Step 7: Quality Gates

Run quality gates on the completed implementation.

Read and follow `sage/core/workflows/sub-workflows/quality-gates.workflow.md`.
It sequences 5 verification stages:
1. Spec compliance — does implementation match the plan? (adversarial)
2. Constitution compliance — does it respect project principles?
3. Code quality — clean, secure, maintainable?
4. Hallucination check — are all imports, APIs, versions real?
5. Verification — tests pass with pasted evidence?

Each gate that fails triggers fix-and-retry (max 3 attempts) or
escalation to the user.

If quality-gates cannot be loaded, follow these minimum rules:
run full test suite, paste output, verify implementation matches spec,
check for hallucinated imports or APIs.

## Step 8: Review and Close

Review against spec. Check for missed edge cases.

🔒 **CHECKPOINT:**

Sage: Build complete. [summary of what was built]

[A] Approve — merge/ship
[R] Revise — here's what needs fixing
[N] Next — what should we work on next?

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

- Spec before implementing (Rule 0 gate). DO NOT implement without
  an approved spec in .sage/work/.
- Tests before code (Base Principle 1). Write failing test first.
- Checkpoints mandatory (Rule 4). Present [A]/[R] and wait.
- Verify with evidence (Rule 5). Paste actual test output.
- Capture corrections (Rule 6). Store as self-learning.
- State at checkpoints (Rule 7). Update progress.md.
- Stay in scope — note improvements, don't add them.
- If stuck, use problem-solving skill. Don't retry the same approach.
