---
name: build-loop
description: >
  Drives task-by-task execution from an approved plan with quality gates
  between each task. Reads the plan, finds the next incomplete task,
  dispatches implementation, validates, updates progress, and continues. Use
  after a plan is approved and the user says "go", "start building", "execute
  the plan", or "implement the feature".
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [execution, orchestration, build, loop]
inputs: [plan, codebase-context, constitution]
outputs: [implementation, test-suite, updated-plan]
requires: [implement, tdd, quality-review, spec-review, verify-completion, scope-guard]
-->

# Build Loop

Execute the plan, task by task, with quality gates between each one.
This is the main execution engine for BUILD and ARCHITECT modes.

**Core Principle:** Autonomous but supervised. The agent works through tasks
independently, but pauses at checkpoints and escalates when stuck. A beginner
should be able to say "go" and watch tasks get completed, knowing they'll be
asked before anything surprising happens.

## When to Use

After a plan is approved. The user says "go", "start building", "implement",
or approves the plan at the checkpoint.

## Process

### Step 1: Read the Plan

Load `.sage/work/<active-feature>/plan.md`. Parse:
- Total task count
- Which tasks are already done (checked boxes `- [x]`)
- Which tasks are blocked (dependencies not met)
- Which task is next (first unchecked, unblocked task)

If ALL tasks are done → skip to Final Review.
If NO plan exists → error: "No approved plan found. Run the plan skill first."

### Step 2: Show Status and Start

```
📋 Plan: [feature name]
   Tasks: [done]/[total] complete
   Next: Task [N] — [task name]
   Estimated: ~[time] remaining

   Starting Task [N]. I'll commit after each task and check quality.
   Say "pause" anytime to stop between tasks.
```

### Step 3: Execute Task

For the current task, delegate to the `implement` skill:

1. **Read** the task spec from the plan (files, action, test, verify)
2. **Implement** using TDD (`tdd` skill):
   - Write failing test
   - Verify it fails for the right reason
   - Write minimal code to pass
   - Verify it passes
   - Refactor if needed
3. **Self-review** using the implement skill's checklist
4. **Commit** with semantic message

The `scope-guard` skill monitors throughout — flags if implementation
drifts beyond the task spec.

### Step 4: Run Quality Gates

After each task, run the quality gate sub-workflow:

```
Gate 1: spec-review    → Does implementation match the task spec?
Gate 2: constitution   → Does it violate any project principles?
Gate 3: quality-review → Clean code, security, maintainability?
Gate 4: hallucination  → All imports, APIs, versions real and correct?
Gate 5: verification   → Tests pass? Feature works as expected?
```

Record results in the plan's Gate Log table.

**If gates pass:** Update plan (check the box, add commit hash), move to next task.

**If a gate fails:**
- **Minor issue (1 gate, fixable):** Fix it, re-run that gate, continue.
- **Major issue (multiple gates, design problem):** Stop and report:
  ```
  ⚠️ Task [N] failed quality gates:
     Gate 3: Security — SQL injection risk in [file]
     Gate 5: Verification — test_user_create fails

     I can fix these, but wanted to flag them first.
     Fix and continue, or discuss?
  ```
- **Repeated failure (3x on same gate):** Escalate to human:
  ```
  🛑 Task [N] has failed Gate [X] three times.
     The task spec may be ambiguous or contradictory.

     Issue: [specific problem]
     Options:
     1. Revise the task spec and retry
     2. Skip this task and continue with others
     3. Pause and discuss the approach
  ```

### Step 5: Inter-Task Checkpoint

After every task (or every 3 tasks for long plans), show brief progress:

```
✅ Task [N] complete. [done]/[total] tasks finished.
   Next: Task [N+1] — [name]
   Continuing... (say "pause" to stop)
```

For tasks marked `[P]` (parallelizable), note: "Tasks [N] and [M] can run
in parallel. Running sequentially on this platform." (On Tier 1, dispatch both.)

### Step 6: Final Review

After all tasks complete:

1. Run full quality gates on the COMPLETE implementation (integration check)
2. Verify all tests pass together (not just individually)
3. Check for any TODO/FIXME markers that shouldn't be there

Present the result:
```
✅ Implementation complete!

   Feature: [name]
   Tasks: [total]/[total] complete
   Tests: [count] passing
   Commits: [count]

   Quality: All 5 gates passed on final review.

   Ready to merge, create a PR, or need changes?
```

🔒 **MANDATORY CHECKPOINT:** Wait for human decision.

### Step 7: Wrap Up

Based on human's choice:
- **Merge:** Merge the branch (if using branches)
- **PR:** Create a pull request with the spec as description
- **Keep working:** Note what needs to change, update plan
- **Discard:** Revert and clean up

Update `.sage/progress.md`:
```markdown
# Progress

Mode: idle
Feature: [YYYYMMDD-slug] (completed)
Phase: done
Next: "Tell me what to build next"
Updated: <timestamp>
```

## Fallbacks

| Situation | Action |
|-----------|--------|
| Implementation fails to compile | Run `systematic-debug`, fix, retry |
| Test can't be written (untestable design) | Flag to human, suggest interface simplification |
| Task is larger than expected | Report: "Task [N] is bigger than planned. Split into [A] and [B]?" |
| Discovered bug in existing code | Report: "Found unrelated bug in [X]. Note for later or fix now?" |
| Context window getting full | Commit current work, save state, suggest new session |
| All tasks done but integration broken | Create an "integration fix" task, add to plan, execute |

## Rules

**MUST (violation = lost work or broken trust):**
- MUST NOT skip quality gates. They are mandatory, not suggestions.
- MUST NOT implement multiple tasks without committing between them.
- MUST NOT continue past a mandatory checkpoint without human approval.
- MUST update the plan file after completing each task.
- MUST commit current work immediately if the user says "pause" or "stop."

**SHOULD (violation = suboptimal experience):**
- SHOULD show progress between tasks — the user should never wonder what's happening.
- SHOULD proactively save and suggest a new session if context is getting full.
- SHOULD present brief inter-task status every 1-3 tasks, not after every line of code.

**MAY (context-dependent):**
- MAY skip the final review (step 6) if the plan had only 1-2 tasks, since per-task
  review already covered everything.
- MAY run parallelizable tasks concurrently on Tier 1 platforms.

## Failure Modes

- **Plan file is missing or corrupted:** Ask the user if a plan exists. If
  a spec exists, offer to regenerate the plan from it. If neither exists,
  suggest starting with elicitation.
- **Context window fills before all tasks complete:** Commit current work,
  write a session bridge note, save the plan with current progress, and
  suggest a new session. Never lose work to context limits.
- **Task produces unexpected scope:** If a task turns out to be much larger
  than planned, STOP. Report to the user: "Task N is bigger than expected.
  Split into subtasks?" Don't silently expand scope.
- **Gate fails repeatedly on the same task:** After 2 failed attempts, stop
  and report: "Gate [X] keeps failing on task [N]. The issue is [description].
  Should I try a different approach or skip this gate with your approval?"
- **User goes silent mid-loop:** After completing a task that requires
  approval, wait. Don't proceed to the next task. The checkpoint exists for
  human verification.
