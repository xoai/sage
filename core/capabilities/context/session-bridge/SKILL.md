---
name: session-bridge
description: >
  Preserves and restores context across agent sessions using plan file
  checkboxes as source of truth. Use when starting a new session, resuming
  previous work, ending a session, or when the user says "continue from last
  time", "what was I doing", or "save progress".
version: "2.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: haiku
activation: auto
tags: [context, persistence, session, continuity]
inputs: [codebase]
outputs: [session-state]
-->

# Session Bridge

Maintain continuity across sessions using the plan file as the source of truth.

**Core Principle:** State persistence is a side effect of doing the work, not a
separate action that can be forgotten. Checking a task's checkbox in the plan
file IS saving progress. If the session dies unexpectedly, the plan file on
disk shows exactly where things stand.

## State Architecture

Two levels of state, each with a different purpose:

### Ground Truth: The Plan File

`.sage/work/<feature>/plan.md` contains:
- Task checkboxes: `[x]` = done, `[ ]` = not done, `🔄` = in progress, `🚫` = blocked
- Gate results in the Gate Log table
- Completion markers with commit hashes

**This is always accurate** because it's updated by the `implement` skill as a
natural part of completing each task. No separate "save" action needed.

### Quick Pointer: progress.md

`.sage/progress.md` contains:
- Current mode (fix/build/architect)
- Active feature name
- Path to the active plan file
- Last known phase
- Brief notes

**This may be stale** if the session ended abruptly. That's OK — the plan file
is the real state. progress.md just helps the next session find it quickly.

## Loading (Start of Session)

When resuming work, follow this priority order:

### Step 1: Read progress.md for orientation

```
Mode: build
Feature: 003-jwt-auth
Plan: .sage/work/003-jwt-auth/plan.md
Phase: implementation
```

This tells you WHERE to look, not what the status is.

### Step 1.5: Read journal for project context

If `.sage/journal.md` exists, read the "Current Artifacts" section (top of
file). This tells you what artifacts exist and their status (active, reference,
archived). If you need to understand WHY the project is in its current state,
read the last 2-3 change log entries — they capture recent decisions and
direction changes.

### Step 2: Read the plan file for ground truth

Open the plan file. Count checkboxes:
- How many `[x]` tasks? (completed)
- Any `🔄 IN PROGRESS` tasks? (interrupted mid-task)
- Any `🚫 BLOCKED` tasks? (needs human input)
- How many `[ ]` tasks remain?
- Check the Gate Log for any failed gates that need re-running

### Step 3: Verify against the codebase

If a task is marked `[x]` in the plan but the code doesn't exist (maybe the
commit was lost), trust the codebase over the plan. Mark the task back to `[ ]`.

If a task is NOT checked but the code exists (maybe the plan update was lost),
trust the codebase. Check the box and add the commit hash.

### Step 4: Report to human

```
Resuming feature 003-jwt-auth.
Progress: 4 of 7 tasks complete.
Task 5 was in progress when the last session ended.
Next: Complete task 5 (add token refresh endpoint), then tasks 6-7.
```

## Saving (Between Tasks)

The `implement` skill updates the plan file after each task. Session-bridge
adds a lightweight progress.md update:

### After each task completion:

Update progress.md (brief — just the pointer):
```markdown
# Progress

Mode: build
Feature: 003-jwt-auth
Plan: .sage/work/003-jwt-auth/plan.md
Phase: implementation
Last completed: Task 4 — JWT validation middleware
Next: Task 5 — Token refresh endpoint
Updated: 2025-03-13T14:22:00Z
```

### After significant decisions:

Append to `.sage/journal.md` change log:
```markdown
### 2025-03-13 — Token storage decision
**Key:** Chose httpOnly cookies over localStorage for JWT storage.
  XSS protection outweighs CSRF handling cost.
**Changed:** spec.md updated with cookie-based auth approach.
**Next:** Continue implementation with cookie approach.
```

Update the journal's "Current Artifacts" section if any artifact's status
changed (e.g., a new decision record was produced, a reasoning document was updated).

### After discovering conventions:

Append to `.sage/conventions.md`:
```markdown
### Error handling
Project uses a centralized error handler in src/middleware/error-handler.ts.
All route handlers throw typed errors; the middleware formats the response.
```

## Saving (End of Session)

If the session is ending gracefully (human says "stop", "done for now", etc.):

1. Update the plan file with current task status (if mid-task, mark `🔄 IN PROGRESS`)
2. Update progress.md with the pointer
3. Report: "Progress saved. [N] of [M] tasks complete. Next session: [what to do]."

**If the session ends abruptly** (no graceful shutdown): the plan file already
has the correct state from the last completed task. The in-progress task won't
be checked off, which is correct — it needs to be resumed or restarted.

## FIX Mode State

FIX mode typically doesn't have a plan file. For FIX mode:
- Save the bug description, hypothesis, and fix status in progress.md
- After the fix is committed, update progress.md to "complete"
- State is simpler because fixes are small and usually complete in one session

## Recovery: Stale or Missing State

**progress.md is missing:** Scan `.sage/work/` for plan files with
unchecked tasks. The most recently modified one is likely the active feature.

**progress.md points to a completed plan:** All tasks checked. Report
"Previous feature [name] is complete. Ready for a new task."

**Plan file has `🔄 IN PROGRESS` on a task:** The previous session was
interrupted mid-task. Check if the code was committed. If yes, complete the
task. If no, resume from the beginning of that task.

**Plan file and codebase disagree:** Always trust the codebase (git log, file
existence) over the plan file. The codebase is the ultimate source of truth.
Update the plan file to match reality.

## Rules

- The plan file is the ground truth. progress.md is a pointer.
- Update the plan file AS PART OF completing each task (implement skill handles this).
- Update progress.md as a quick pointer between tasks and at session end.
- Keep progress.md under 20 lines. It's a pointer, not a journal.
- Append to decisions.md and conventions.md — never overwrite.
- If state is ambiguous, verify against the codebase (git log, file system).

## Failure Modes

- **progress.md missing:** Scan `.sage/work/` for plan files with unchecked
  tasks. The most recently modified one is likely active. Report what you find.
- **progress.md points to nonexistent plan:** The feature directory may have been
  deleted or renamed. List available features and ask the human which to resume.
- **Plan file and codebase disagree:** Trust the codebase. Update the plan to match.
  If a checked task's code is gone, uncheck it. If unchecked task's code exists, check it.
- **Session interrupted mid-task (🔄 marker):** Check if the code was committed.
  If committed, complete the task (check box, add hash). If not, restart the task.
- **Multiple features have unchecked tasks:** Ask the human which to resume.
  Don't guess — the wrong choice wastes a session.
