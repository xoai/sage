---
name: implement
description: >
  Implements a single task from the plan using TDD discipline. Reads the task
  spec, writes tests first, writes minimal passing code, refactors, and
  commits. Use when executing a planned task, writing code for a feature, or
  when the user says "implement this", "write the code", "build this task", or
  "execute the plan".
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [implementation, coding, development]
inputs: [task-spec, plan, codebase-context, constitution]
outputs: [implementation, test-suite]
requires: [tdd, scope-guard]
-->

# Implement

Write code for one task. Follow TDD. Stay in scope. Commit.

**Core Principle:** Implementation is the mechanical part. The thinking was done
in the spec and plan. Your job now is to faithfully translate the plan into working,
tested code — not to redesign, optimize, or "improve" beyond what was specified.

## When to Use

During the execution phase of any workflow, when a task from the plan is ready
for implementation.

## Process

### Step 1: Read the Task Completely

Read the full task specification from the plan. Understand:
- What files to create or modify
- What the code should do
- What test to write
- How to verify completion
- What this task depends on (verify dependencies are complete)

If anything is unclear, ASK before proceeding. Guessing at requirements
causes rework. It is always faster to ask one question than to rewrite
200 lines of code.

### Step 2: Check Conventions

Reference the codebase-scan output and `.sage/conventions.md`:
- What patterns are used for similar code in this project?
- What naming conventions apply?
- What test patterns are established?
- What import style is used?

Your implementation MUST follow existing conventions unless the task
explicitly requires deviating from them.

### Step 3: Implement Using TDD

Follow the `tdd` skill strictly:

1. **Write the test first.** The test describes the behavior from the task spec.
   Watch it fail. Verify it fails for the right reason.
2. **Write minimal code to pass.** Only enough to make the test green.
   Don't add error handling, edge cases, or optimizations not required by the task.
3. **Refactor if needed.** Clean up duplication. Improve names. Keep tests green.
4. **Repeat** for each behavior in the task.

### Step 4: Self-Review Before Committing

Before declaring the task complete, check:

- [ ] Every piece of the task spec is implemented
- [ ] Every behavior has a test that was written FIRST
- [ ] All tests pass (run them, don't assume)
- [ ] No code outside the task scope was changed (scope-guard)
- [ ] Code follows project conventions (from codebase-scan)
- [ ] No TODO/FIXME/HACK comments added (fix it now or don't do it)

### Step 5: Update Plan Progress

**This is the critical persistence step.** After committing, update the plan file
to record completion. This is NOT optional — it IS the state persistence mechanism.

In the plan file (`.sage/work/<feature>/plan.md`):
1. Check the task's checkbox: `- [ ]` → `- [x]`
2. Add the completion marker after the task name: `✅ DONE (commit: <hash>)`
3. Fill in the gate results in the Gate Log table (after gates run)
4. Update the plan's `**Last updated:**` timestamp
5. If this was the last task, update `**Status:**` to `complete`

**Why this matters:** If the session ends unexpectedly — terminal closed, context
window full, connection dropped — the plan file on disk shows exactly which tasks
are done. The next session reads the plan file, sees the checkboxes, and resumes
from the right place. This works even if progress.md is stale.

### Step 6: Commit

Write a semantic commit message:
```
<type>(<scope>): <short description>

<what was done and why, referencing the task>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

## Rules

**MUST (violation = broken code or lost work):**
- MUST NOT implement multiple tasks without committing between them.
  Each task = one commit (or a small sequence of commits).
- MUST NOT skip TDD. The `tdd` skill is mandatory and has no exceptions.
- MUST NOT expand scope. The `scope-guard` skill is active. Do what the task says.
- MUST NOT guess at unclear requirements. Ask the human.
- MUST update the plan file checkbox after completing each task.

**SHOULD (violation = suboptimal but working):**
- SHOULD follow existing project conventions over personal preference.
- SHOULD report if a task is harder than expected. Don't silently
  spend 30 minutes on a "5-minute task" without communicating.
- SHOULD use semantic commit messages following the type(scope): description format.

**MAY (context-dependent):**
- MAY split a commit into multiple smaller commits if the task has natural breakpoints.
- MAY ask the human to clarify conventions when existing code is inconsistent.

## Subagent Mode

On Tier 1 platforms (Claude Code, Codex), each task implementation MAY be
dispatched to a fresh subagent with clean context. The subagent receives:

- The task specification (full text)
- Relevant codebase context (from codebase-scan)
- The constitution (always loaded)
- The developer persona (behavioral overlay)

The subagent implements, tests, self-reviews, and commits. Then the spec-review
and quality-review run as separate subagents (adversarial review).

On Tier 2 platforms, the same process runs sequentially in one session.

## Failure Modes

- **Task is too large:** Report it. "This task is larger than estimated. I recommend
  splitting it into [A] and [B]. Approve?"
- **Can't write a test for the behavior:** The code is too coupled. Simplify the
  interface. Use dependency injection. If the framework makes testing impossible,
  flag it and discuss.
- **Discovered a bug in existing code:** Don't fix it silently. Report it.
  "Found a bug in [X]: [description]. Should I fix it now (adds scope) or note
  it for later?" If approved, create a separate task and commit.
- **Blocked by missing dependency:** Report BLOCKED status. Don't work around
  missing dependencies with hacks.
