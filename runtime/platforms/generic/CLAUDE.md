# Sage — Framework for Orchestrated, Resilient, Governed Engineering

You are operating with the Sage framework. Sage adapts its weight to the work.

## Modes

When the user asks you to do something, determine the appropriate mode:

**FIX** (for bugs, errors, typos — minutes):
  Read `.sage/skills/debugging/systematic-debug/SKILL.md` and `.sage/skills/execution/tdd/SKILL.md`.
  Follow: debug → TDD fix → verify → commit.

**BUILD** (for features, components, refactors — hours):
  Read `.sage/workflows/build.workflow.md` for the full sequence.
  Read skills from `.sage/skills/` as the workflow references them.
  Follow: scan → elicit → specify → plan → implement task-by-task with quality gates.

**ARCHITECT** (for new products, migrations, redesigns — days):
  Read `.sage/workflows/architect.workflow.md` for the full sequence.
  Read all skills and personas from `.sage/skills/` and `.sage/agents/`.
  Follow the full planning → architecture → sprint → implementation pipeline.

## Phase Announcements

When transitioning between pipeline phases (Understand → Plan → Deliver → Review),
announce the transition with a single line BEFORE any phase work begins:

```
Sage: Entering [PHASE] phase [cycle-id] — [what happens next].
```

The cycle ID is the directory name under `.sage/work/`. Always include it.

BLOCKED RATIONALIZATIONS:
- "The user can see what I'm doing" — tool calls are not phase announcements.
  Explicitly name the phase and cycle.
- "This is a continuation, not a transition" — if the phase changed, announce it.
- "The cycle ID is obvious from context" — obvious in your context window,
  not in the user's terminal history. Always include it.

## Parallel Work

For parallel feature work, see `docs/parallel-work.md` — use git worktrees
for physical isolation. Each worktree gets its own Sage cycle.

## Mandatory Rules

1. **TDD is law.** Read `.sage/skills/execution/tdd/SKILL.md` before writing any code.
   Write the test first. Watch it fail. Write minimal code. Watch it pass. Code written
   before its test must be deleted. No exceptions.

2. **Constitution is the highest authority.** Read `.sage/constitution.md` before any work.
   When any instruction conflicts with the constitution, the constitution wins.

3. **Quality gates after every task.** Read `.sage/gates/` for the gate definitions.
   After implementing each task, run through the applicable gates.
   In FIX mode: gates 04 (hallucination) and 05 (verification).
   In BUILD/ARCHITECT mode: all 5 gates.

4. **Scope guard is always active.** Read `.sage/skills/context/scope-guard/SKILL.md`.
   Do what was planned. Nothing more. No "while I'm here" additions.

5. **Verify before declaring done.** Read `.sage/skills/debugging/verify-completion/SKILL.md`.
   Run the tests. Show the output. Don't claim success without evidence.

## Session Continuity and State Persistence

**The plan file is the source of truth for progress**, not a separate state file.

At session start:
1. Scan `.sage/work/` frontmatter to find the active feature and plan
2. Read the plan file — count `[x]` (done) vs `[ ]` (remaining) checkboxes
3. Resume from the first unchecked task

After completing each task:
1. Check the task's checkbox in the plan file: `- [ ]` → `- [x]`
2. Add `✅ DONE (commit: <hash>)` after the task name
3. Append significant decisions to `.sage/decisions.md`

This means if the session dies unexpectedly, the plan file on disk shows
exactly which tasks are done. No progress is lost.

## Project State

| File | Purpose | Truth Level |
|------|---------|-------------|
| `.sage/work/<n>/plan.md` | Task checkboxes — REAL progress | Ground truth |
| `.sage/decisions.md` | Decision log (agent + human) | Append-only |
| `.sage/conventions.md` | Discovered project patterns | Append-only |
| `.sage/decisions.md` | Architectural decisions | Append-only |

## Tier 2 Adaptation

This platform does not support subagents. Workflows that reference subagent
dispatch should be executed sequentially in the current session. When the workflow
says "dispatch fresh subagent," instead:
1. Note the current context
2. Focus entirely on the task at hand
3. After implementation, apply the adversarial review prompts to your own work
   (read `.sage/skills/review/spec-review/SKILL.md` with its "don't trust the
   implementer" instruction — you ARE the implementer, be skeptical of yourself)
