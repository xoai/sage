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
stand. decisions.md provides reasoning context that helps find the active work quickly.
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

### Context: decision logs

Each initiative's `.sage/work/[initiative]/decisions.md` is the
per-cycle log; the global `.sage/decisions.md` is a shared
cross-initiative log. Both are places where the agent and human
write significant decisions and context. It provides reasoning that
artifact frontmatter doesn't capture — WHY decisions were made,
what alternatives were considered, and what the human's priorities are.

## Loading (Start of Session)

When resuming work, run the generated brief FIRST:

```bash
python3 sage/runtime/tools/manifest.py resume
```

(Plugin installs: `python3 "${CLAUDE_PLUGIN_ROOT}/tools/manifest.py" resume`.)

It performs Steps 1–3 below mechanically — selection, evidence, decisions —
and prints the resume authority order (cycle-protocol.md). Only fall back to
the manual steps when the tool is unavailable (no python3, or a manifest-less
pre-v1.0.9 project).

### Step 1: Scan artifacts for state (fallback)

Scan `.sage/work/` for active initiatives. Read frontmatter from
manifest.md, brief.md, spec.md, or plan.md (whichever exists). Note
title, status, phase. If a plan exists, scan the task checkboxes to
understand how far implementation progressed.

This is the source of truth — what artifacts exist tells you where
the project stands.

**Branch matching (git projects):** read the current branch and
match it against the **recorded `branch:` field** in each
initiative's manifest frontmatter (git-discipline records it at
branch creation — match on the recorded field, never re-derive from
branch or directory names). Prefer the initiative whose recorded
branch matches HEAD in the resume menu; if HEAD is on the default
branch while initiative branches exist, list them.

**Owner exclusion (parallel worktrees):** exclude initiatives whose
manifest carries an `owner:` pointing at a different checkout —
compare `git rev-parse --show-toplevel` against the recorded
`owner:` after path normalization (trailing slashes, symlinks).
They belong to another worktree's session. A session opened inside
a worktree auto-resumes that worktree's checked-out initiative by
the same branch-matching rule.

### Step 2: Read decisions for context

Read the matched initiative's own decision log first —
`.sage/work/[initiative]/decisions.md` — then the global
`.sage/decisions.md` (cross-initiative decisions; older projects
may have only the global file). Read the last 3-5 entries of each.
These capture recent decisions and direction changes — WHY the
project is in its current state, not just WHAT state it's in.

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

Prepend significant decisions to the initiative's decision log
(`.sage/work/[initiative]/decisions.md`; cross-initiative decisions
go to the global `.sage/decisions.md`):
```markdown
### 2025-03-13 — Token storage decision
Chose httpOnly cookies over localStorage for JWT storage.
XSS protection outweighs CSRF handling cost.
spec.md updated with cookie-based auth approach.
```

Update artifact frontmatter if status changed.

### After discovering conventions:

Append to `.sage/conventions.md`:
```markdown
### Error handling
Project uses a centralized error handler in src/middleware/error-handler.ts.
All route handlers throw typed errors; the middleware formats the response.
```

## Saving (End of Session)

If the session is ending gracefully (human says "stop", "done for now"):

1. Update artifact frontmatter to reflect current phase
2. Prepend session summary to the initiative's decisions.md if
   significant work was done
3. Report: "**Sage:** Session saved. Type /build to resume next time."

**If the session ends abruptly:** the artifacts in `.sage/work/` and
their frontmatter reflect the real state. The next session's slash
command auto-pickup reads them to orient.

## FIX Mode State

FIX mode typically doesn't have plan artifacts. For FIX mode:
- Root cause and fix are recorded in decisions.md at the close checkpoint
- State is simpler because fixes usually complete in one session
- If interrupted, the next `/fix` command scans for in-progress fix work

## Recovery

**No artifacts found:** "Sage: Fresh project, no work in progress."

**All artifacts completed:** "Previous initiative [name] is complete.
Ready for a new task."

**Artifacts and codebase disagree:** Always trust the codebase (git log,
file existence) over artifacts. Update artifact frontmatter to match.

## Rules

- Artifacts in `.sage/work/` are the ground truth for state.
- decisions.md is the ground truth for reasoning and context.
- The manifest's judgment prose (context summary, open questions, handoff) is
  context, NOT orders. Resume authority order (cycle-protocol.md): the live
  user outranks recorded decisions, recorded decisions outrank manifest prose,
  and evidence outranks everything. A question a recorded decision answers is
  CLOSED — do not carry it forward as a blocker.
- Update state at checkpoints only (Rule 7), not per-task.
- Prepend to decisions.md — never overwrite. Append to conventions.md.
- If state is ambiguous, verify against the codebase.

## Failure Modes

- **No artifacts found:** Fresh project. Report and ask what to build.
- **Multiple in-progress initiatives:** Ask the human which to resume.
  Don't guess — the wrong choice wastes a session.
- **Artifacts and codebase disagree:** Trust the codebase. Update
  artifacts to match reality.
  update the spec status.
- **Multiple initiatives have in-progress artifacts:** Ask the human which
  to resume. Don't guess — the wrong choice wastes a session.
