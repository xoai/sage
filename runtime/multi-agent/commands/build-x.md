---
description: Augmented build cycle — planner → spec review → plan → plan review → implementer → code review → reflect. Uses roles configured in .sage/agents.toml.
argument-hint: <task description>
allowed-tools: Read, Write, Edit, Bash, Task, Glob
---

# /build-x — cross-model build cycle

**Task:** $ARGUMENTS

You are the host agent (per `.sage/agents.toml` → `roles.planner`). You
plan and orchestrate. You do **not** write production code in this
command — the configured `implementer` role does that.

Read `.sage/prompts/planner.md` once at the start of this command and
treat it as your operating charter for the cycle.

## Phase 1 — Establish work directory

Create `.sage/work/$(date +%Y%m%d)-<slug>/` from the task. Pick a short,
descriptive slug. Write `brief.md` following the planner charter.

Update `.sage/progress.md` so `/continue` can pick this up later.

## Phase 2 — Spec

Before drafting `spec.md`, classify the task and reuse Sage workflows
where they fit (see `.sage/prompts/planner.md` for full guidance):

- Architecture-shaped (new module, cross-cutting refactor, storage
  change, integration) → run `/architect` first; spec.md then cites
  the ADRs it produces.
- Knowledge-gap or unfamiliar domain → run `/research`; spec.md cites
  findings from `.sage/docs/`.
- UX-shaped (user-facing flow, new screen, accessibility) → run
  `/design`.
- Mechanical (config tweak, rename sweep) → skip the above; draft
  spec.md directly.

Then write `spec.md` following the planner charter. Stop and ask the
user to confirm before continuing:

`[A] Approve · [R] Revise · [X] Cancel`

## Phase 3 — External spec review (loop, max 3 iterations)

Run `/review-spec <slug>`. Iterate based on verdict:

- **REVISE** → patch `spec.md` per findings, re-run review
- **REJECT** → stop, escalate to user with the reviewer's summary
- **APPROVE** → continue to Phase 4

Log each iteration to `.sage/decisions.md`:
```
## <ISO timestamp> · spec review iteration N
- Verdict: <verdict>
- BLOCKERs addressed: <list>
- Intentional non-changes: <list with reasoning>
```

If iterations exceed 3 without APPROVE, the brief may be unclear —
return to Phase 1.

## Phase 4 — Plan

Write `plan.md` per the planner charter. Each step cites the spec section
it satisfies.

## Phase 5 — Plan review (loop, max 2 iterations)

Run `/review-plan <slug>`. Same verdict semantics as Phase 3, but the
common findings here are SCOPE_DRIFT and PLAN_ADHERENCE issues.

## Phase 6 — Implementation

Run `/implement <slug>`. The implementer sub-agent isolates stdout, so
your main context gets back only a short summary: files touched, tests
added, spec ambiguities flagged.

If the implementer reports unresolved spec ambiguities, treat them as
late-binding findings: patch `spec.md`, re-run `/review-spec`, and
re-implement only the affected steps.

## Phase 7 — Code review (loop)

Run `/review-code <slug>`. Verdicts:

- **APPROVE** → proceed to Phase 8
- **FIX_BEFORE_MERGE** → present findings to the user with options:
    - `[F]` Fix small things yourself (only for trivial corrections)
    - `[K]` Send fix list back to `/implement` with the review file in
            the prompt
    - `[D]` Show the full review and decide
- **REWORK** → return to Phase 4 (plan), possibly Phase 2 (spec)

Do not auto-merge. Even APPROVE just means "no blocking findings" — the
user decides whether to commit.

## Phase 8 — Reflect

Run Sage's built-in `/reflect`. It reads `.sage/decisions.md`, the
review files, and `implementer-notes.md` to extract WHEN/CHECK/BECAUSE
learnings for the next cycle.

## Throughout

- Update `.sage/progress.md` after each phase transition.
- All reviewer outputs are timestamped under
  `.sage/work/<slug>/reviews/`; never overwrite, always append a new
  timestamped file.
- If any phase produces output the user should see at length, point them
  to the file on disk rather than dumping into the main context.
