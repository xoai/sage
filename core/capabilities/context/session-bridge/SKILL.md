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

**Core Principle:** The file system is the source of truth. What artifacts
exist in `.sage/work/` and their frontmatter status tells you where things
stand. progress.md is a pointer that helps find the active work quickly.
State updates happen at checkpoints (Rule 7), not per-task.

## State Architecture

Two levels of state, each with a different purpose:

### Ground Truth: Artifacts in .sage/work/

`.sage/work/<feature>/` contains artifacts with YAML frontmatter:
- `brief.md`, `spec.md`, `plan.md` — each with `status` and `phase`
- Status field: `pending`, `in-progress`, `completed`, `blocked`
- The EXISTENCE of artifacts and their frontmatter status IS the state

**This is always accurate** because artifacts are created and updated
as part of the workflow. No separate "save" action needed.

### Quick Pointer: progress.md

`.sage/progress.md` contains:
- Current mode (fix/build/architect)
- Active feature name
- Path to the active work directory
- Last known phase
- Brief notes

**This may be stale** if the session ended abruptly. That's OK — the
artifacts are the real state. progress.md just helps the next session
find them quickly. If they disagree, trust the artifacts.

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

### Step 2: Read artifacts for ground truth

Scan `.sage/work/` for active initiatives. Read frontmatter from
brief.md, spec.md, or plan.md (whichever exists). Note title, status,
phase. If a plan exists, scan the task checkboxes to understand how
far implementation progressed.

### Step 3: Verify against the codebase

If artifacts and the codebase disagree (e.g., plan says "spec phase"
but implementation files exist), trust the codebase. The file system
is the ultimate source of truth. Update artifacts to match reality.

### Step 4: Report to human

**Sage:** Resuming [feature name]. [Phase] phase.
[Summary of what exists and what's next.]

## Saving (At Checkpoints)

State updates happen ONLY at checkpoints (Rule 7), not per-task:

### At each checkpoint:

Update progress.md (brief — just the pointer):
```markdown
# Progress

Mode: build
Feature: 003-jwt-auth
Work: .sage/work/003-jwt-auth/
Phase: implementation
Next: Continue implementing from plan
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

1. Update progress.md with current phase and next steps
2. Update journal.md if artifacts were created or changed
3. Report: "**Sage:** Progress saved. Next session: [what to do]."

**If the session ends abruptly** (no graceful shutdown): the artifacts
in `.sage/work/` and their frontmatter status reflect the real state.
The next session reads them to orient.

## FIX Mode State

FIX mode typically doesn't have a plan file. For FIX mode:
- Save the bug description, hypothesis, and fix status in progress.md
- After the fix is committed, update progress.md to "complete"
- State is simpler because fixes are small and usually complete in one session

## Recovery: Stale or Missing State

**progress.md is missing:** Scan `.sage/work/` for artifact directories.
Read frontmatter from the most recently modified artifacts. Report what
you find.

**progress.md points to a completed initiative:** All artifact statuses
are `completed`. Report: "Previous initiative [name] is complete. Ready
for a new task."

**Artifacts and codebase disagree:** Always trust the codebase (git log,
file existence) over artifacts. The codebase is the ultimate source of
truth. Update artifact frontmatter to match reality.

## Rules

- Artifacts in `.sage/work/` are the ground truth. progress.md is a pointer.
- Update state at checkpoints only (Rule 7), not per-task.
- Keep progress.md under 20 lines. It's a pointer, not a journal.
- Append to journal.md and conventions.md — never overwrite.
- If state is ambiguous, verify against the codebase (git log, file system).

## Failure Modes

- **progress.md missing:** Scan `.sage/work/` for artifact directories.
  The most recently modified one is likely active. Report what you find.
- **progress.md points to nonexistent work:** The feature directory may have
  been deleted or renamed. List available features and ask the human.
- **Artifacts and codebase disagree:** Trust the codebase. Update artifacts
  to match. If spec says "in-progress" but implementation is complete,
  update the spec status.
- **Multiple initiatives have in-progress artifacts:** Ask the human which
  to resume. Don't guess — the wrong choice wastes a session.
