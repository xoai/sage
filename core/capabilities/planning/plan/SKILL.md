---
name: plan
description: >
  Creates implementation plans from specifications by breaking work into small
  tasks (2-5 min each) with exact file paths, tests, and dependency ordering.
  Use after a spec is approved and before implementation begins, or when the
  user says "create a plan", "break this down", "how should we build this", or
  "task breakdown".
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [planning, decomposition, tasks, implementation]
inputs: [spec, codebase-context, constitution]
outputs: [plan, tasks]
requires: []
-->

# Plan

Turn a specification into an actionable implementation plan. This is where
technology decisions are made and work is broken into tasks small enough
for a single focused implementation session.

**Core Principle:** A plan should be clear enough for an enthusiastic junior
engineer with no project context, poor taste, no judgment, and an aversion to
testing to follow — and still produce correct, well-tested code. If the plan
is ambiguous, the implementation will be wrong.

## When to Use

After a spec is approved, before implementation begins.

## Process

### Step 1: Constitution Compliance Check

Before planning anything, verify the spec against the constitution:
- Do any requirements conflict with project principles?
- Are there constitution-mandated patterns (auth, logging, error handling) that
  apply to this feature?
- Are there constitution-mandated constraints (approved databases, forbidden
  dependencies) that constrain technology choices?

Document any constitution requirements that apply. These are non-negotiable
constraints on the plan.

### Step 2: Technology Decisions (ARCHITECT mode only)

For BUILD mode, the tech stack already exists — use what's there.
For ARCHITECT mode, make and document technology decisions:

- What technologies fit the requirements AND the constitution constraints?
- For each significant decision, create a decision record (Architectural Decision Record):
  - Context: Why this decision matters
  - Options considered (minimum 2)
  - Decision: Which option and WHY
  - Consequences: What this means for implementation

### Step 3: Task Decomposition

Read the spec's **Deliverable** field to determine task style.

#### PRD-Informed Planning

If the spec was produced from a PRD (the spec will reference the PRD and
include a component map and milestone structure):

1. **Read the milestone structure.** The spec maps PRD requirements marked
   "Delivers value independently: Yes" to milestone boundaries. Group
   tasks into these milestones:

   ```markdown
   ## Milestone 1: [What's demoable after this group]
   Delivers: R1, FR1, FR2 (foundational — internal, verifiable)

   [ ] Task 1: ...
   [ ] Task 2: ...

   🔒 CHECKPOINT: [What to verify. Can this be shipped independently?]

   ## Milestone 2: [What's demoable]
   Delivers: R3, R5 (first user-visible value)

   [ ] Task 3: ...
   [ ] Task 4: ...

   🔒 CHECKPOINT: [What to verify. Ship decision point.]
   ```

2. **Use the lean task template.** Each task carries three fields beyond
   the title — enough context to execute independently without duplicating
   content from the spec:

   ```markdown
   [ ] Task N: [Title]
       Read first: [specific spec sections, PRD scenarios, pack files]
       Done: [1-2 line acceptance criteria — what "finished" looks like]
       Scope: [what this task does NOT touch — prevents scope creep]
   ```

   "Read first" is a pointer, not a copy. The agent loads the referenced
   files at execution time. "Done" is derived from the PRD's acceptance
   scenarios — each scenario maps to at least one task's done criteria.
   "Scope" prevents the agent from expanding work beyond the task boundary.

3. **Enforce no forward dependencies.** Every task must be completable
   based only on previous tasks. A task must never require a future task
   to function. If task ordering creates a forward dependency, restructure.

4. **Size tasks for a single AI session.** Each task should be completable
   within one context window. If a task requires reading 15 files and
   modifying 8 components, it's too large — split it. This is guidance,
   not a hard rule (some tasks are legitimately complex).

5. **Map PRD acceptance scenarios to tasks.** Each Given/When/Then scenario
   from the PRD should be covered by at least one task's "Done" criteria
   or by an explicit integration test task. The final task in the plan
   should verify all PRD scenarios pass as automated tests.

If the spec was NOT produced from a PRD (standard elicitation path), use
the existing task templates below.

#### Standard Task Templates

Break the work into tasks. Each task must be:

- **Small:** 2-5 minutes of focused work. If a task description is longer than
  a short paragraph, it's too big — split it.
- **Complete:** Contains everything needed to execute: what to produce, where
  to put it, what the result should look like.
- **Verifiable:** Includes how to verify the task is done correctly.
- **Ordered:** Tasks are sequenced to respect dependencies. No forward
  dependencies — each task depends only on previous tasks.

#### For code deliverables (or code tasks in mixed):

```
### Task N: [descriptive name]

**Read first:** [pack pattern files relevant to this task — check .sage/skills/]
**Files:** [exact file paths to create or modify]
**Action:** [what to do — be specific enough that there's no ambiguity]
**Test:** [what test to write, what it should verify]
**Verify:** [command to run to confirm task is complete]
**Depends on:** [task numbers that must complete first, or "none"]
```

The **Read first** field tells the agent which pack detail files to read before
starting the task. This ensures framework-specific guidance is loaded fresh at
the moment of decision — not stale from earlier in the conversation. If the
project uses inline mode (all pack content in CLAUDE.md), this field can say
"(pack content already loaded)" instead of listing files.

#### For document deliverables (or document tasks in mixed):

```
### Task N: [descriptive name] [DOC]

**Read first:** [playbook reference files relevant to this section]
**Output:** [file path for the document, e.g. .sage/work/NNN/competitive-analysis.md]
**Action:** [what to write — be specific about scope, structure, expected sections]
**Criteria:** [checklist of what "done" looks like for this section]
**Depends on:** [task numbers that must complete first, or "none"]
```

Document tasks use **[DOC]** marker. They have **Criteria** instead of **Test**
(a checklist reviewed against the spec's acceptance criteria, not a test command).
They have **Output** instead of **Files** (a single document path, not source code
files). Gates 04-06 (hallucination, verification, visual) skip for [DOC] tasks.
Gates 01-02 (spec compliance, constitution) always run.

#### For mixed deliverables:

The plan contains both code and document tasks. Each task is marked with its type.
Code tasks use the code template. Document tasks use the document template with
[DOC] marker. Gates apply per-task based on the marker.

### Step 4: Identify Parallelism

Mark tasks that can run simultaneously (no dependency between them) with `[P]`.
This enables parallel subagent execution on Tier 1 platforms.

```
Task 3 [P]: Create user model       (depends on: Task 1)
Task 4 [P]: Create auth middleware   (depends on: Task 1)
Task 5:     Integrate auth with user (depends on: Task 3, Task 4)
```

### Step 5: Output Plan

Save to `.sage/work/<YYYYMMDD>-<slug>/plan.md` using the plan template.
The plan uses **checkbox format** for built-in progress tracking:

```markdown
# Implementation Plan: [feature name]

**Spec:** .sage/work/YYYYMMDD-slug/spec.md
**PRD:** .sage/work/YYYYMMDD-slug/brief.md (if applicable)
**Mode:** build
**Status:** not-started
**Started:**
**Last updated:**

## Constitution Constraints
[principles that apply, mandated patterns]

## Technology Decisions
[decision records for ARCHITECT mode, or "Using existing stack" for BUILD mode]

## Milestone 1: [What's demoable — e.g., "Baseline computation (internal)"]

Delivers: [which PRD requirements, e.g., R1, FR1, FR2]

- [ ] **Task 1:** [name]
  - **Read first:** [spec sections, PRD scenarios, pack files]
  - **Done:** [1-2 line criteria]
  - **Scope:** [what this does NOT touch]

- [ ] **Task 2:** [name]
  - **Read first:** [files to load]
  - **Done:** [criteria]
  - **Scope:** [boundaries]

🔒 CHECKPOINT: [What to verify. Ship decision if applicable.]

## Milestone 2: [What's demoable — e.g., "Baseline in QLCT view (user value)"]

Delivers: [PRD requirements]

- [ ] **Task 3:** [name]
  - **Read first:** [files]
  - **Done:** [criteria]
  - **Scope:** [boundaries]

🔒 CHECKPOINT: [What to verify. Ship/demo decision.]

## Final: Integration verification

- [ ] **Task N:** End-to-end integration test
  - **Read first:** brief.md all acceptance scenarios
  - **Done:** All [count] PRD acceptance scenarios pass as automated tests
  - **Scope:** Tests only. No new code.

## Gate Log

| Task | Gate 1 | Gate 2 | Gate 3 | Gate 4 | Gate 5 |
|------|:---:|:---:|:---:|:---:|:---:|
| Task 1 | | | | | |
| Task 2 | | | | | |
```

For plans without a PRD source (standard elicitation), milestones are
optional — use a flat task list if the feature is small enough.

**The checkboxes ARE the progress tracker.** When `implement` completes a task,
it checks the box (`- [x]`) and adds the commit hash. If the session dies, the
plan file shows exactly which tasks are done. No separate save action needed.

Also update `.sage/progress.md` with the pointer to this plan:
```markdown
# Progress

Mode: [build/architect]
Feature: [YYYYMMDD-slug]
Plan: .sage/work/YYYYMMDD-slug/plan.md
Phase: planning
Next: Human approval of plan, then implementation
Updated: [timestamp]
```

Show the plan to the human. Wait for approval before implementation begins.

## Rules

**MUST (violation = broken plan or wasted work):**
- MUST NOT make tasks larger than 5 minutes of work. If in doubt, split.
- MUST NOT create forward dependencies — every task depends only on previous
  tasks. If task 5 requires task 7, restructure the plan.
- MUST NOT leave file paths vague. "Update the auth code" is bad. "Modify
  `src/middleware/auth.ts`, add `validateExpiry()` function" is good.
- MUST NOT skip the verification step in tasks. Every task must be verifiable.
- MUST order tests before implementation (TDD compliance).
- MUST check the constitution before making technology decisions.
- MUST get human approval on the plan before starting implementation.
- MUST map every PRD acceptance scenario to at least one task's done criteria
  (when a PRD exists). If a scenario isn't covered, the plan is incomplete.

**SHOULD (violation = suboptimal but workable):**
- SHOULD keep BUILD mode plans to 3-10 tasks. If you have 30 tasks,
  you're either in the wrong mode or the feature needs to be split.
- SHOULD group tasks into milestones when a PRD with "Shippable Alone?"
  flags exists. Milestones end at requirements that deliver user value
  independently.
- SHOULD size tasks for what an AI agent can accomplish in a single session.
  If a task requires loading more context than fits in one context window,
  split it.
- SHOULD mark parallelizable tasks with `[P]` for potential concurrent execution.
- SHOULD include estimated time per task so the human can gauge total effort.

**MAY (context-dependent):**
- MAY skip technology decisions in BUILD mode (use existing stack).
- MAY combine very small related tasks if splitting would add overhead.
- MAY use a flat task list (no milestones) for small features with 3-5 tasks.

## Failure Modes

- **Too many tasks:** Feature is too large for BUILD mode. Suggest splitting
  into multiple features, or switching to ARCHITECT mode.
- **Circular dependencies:** Redesign the task order. Extract shared infrastructure
  as an earlier task.
- **Forward dependency detected:** Task N requires task N+M to function. This
  means the task ordering is wrong. Move the depended-upon work earlier, or
  restructure to eliminate the dependency.
- **Can't determine task order:** The requirements are underspecified. Go back
  to the spec and clarify.
- **Tech stack conflict with constitution:** Flag it. The human decides whether
  to request a waiver or change the approach.
- **PRD scenarios not fully covered:** If any PRD acceptance scenario doesn't
  map to at least one task's done criteria, the plan has gaps. Add tasks or
  expand existing task criteria to cover the missing scenario.
- **Task too large for one AI session:** The task requires reading too many
  files or modifying too many components. Split into smaller tasks that each
  fit within a single context window.
