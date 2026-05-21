---
description: Augmented build cycle — planner → spec review → plan → plan review → implementer → code review → reflect. Uses roles configured in .sage/agents.toml.
argument-hint: <task description>
allowed-tools: Read, Write, Edit, Bash, Task, Glob
---

# /build-x — cross-model build cycle

**Task:** $ARGUMENTS

You are the host agent (per `.sage/agents.toml` → `roles.planner`). You
plan and orchestrate. When the `implementer` role is a **CLI agent**, you
do **not** write production code in this command — that role does it in
Phase 6. When the `implementer` role is a **host agent**, there is no
separate CLI to delegate to: Phase 6 has you run the implementation
in-session yourself, following `.sage/prompts/implementer.md`.

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

**Classify the stakes** — this sets review rigor, and is separate from
the task-shape classification above:

- **`prototype`** — demo, throwaway, or exploratory work. Spec-review
  cap: **2 iterations**. Plan review (Phase 5) and code review
  (Phase 7) may be skipped, but only with explicit user sign-off.
- **`production`** — work that will be merged and depended on.
  Spec-review cap: **3 iterations**. Every review gate runs.

Propose a tier from the task; let the user override. The tier is the
**single source of the spec-review cap** — Phase 3 refers to it and
never restates a number. Record it in `.sage/progress.md`.

Then write `spec.md` following the planner charter. Stop and ask the
user to confirm before continuing:

`[A] Approve · [R] Revise · [X] Cancel`

## Phase 3 — External spec review (severity-gated loop)

Run `/review-spec <slug>`, then evaluate the stop rules below after
**every** review iteration. The *iteration count* is the number of
completed `spec_reviewer` review files for this slug's `spec.md` under
`.sage/work/<slug>/reviews/` (equivalently, "spec review iteration N"
entries in `.sage/decisions.md`).

Count findings yourself from the review file: lines matching
`### [BLOCKER]` and `### [MAJOR]` inside its `## Findings` section. A
`## Findings` section with no such headers counts as 0 BLOCKER /
0 MAJOR.

1. **Proceed (severity-gated exit).** If the latest review has
   **0 BLOCKER and 0 MAJOR** and its verdict is `APPROVE` or `REVISE`,
   exit the loop and continue to Phase 4 — regardless of how many
   MINOR findings remain. Append open MINORs to `.sage/decisions.md`
   as deferred items. Never re-run the loop on a MINOR-only review.
2. **`REJECT` → stop.** A `REJECT` verdict always escalates to the
   user, regardless of finding counts.
3. **Distrust an inconsistent review.** If the review file fails
   `.sage/scripts/validate-review.sh`, or its verdict contradicts its
   counts (`APPROVE` with any BLOCKER/MAJOR, or `REJECT` with none),
   none of the other rules apply — stop and surface the inconsistency
   to the user.
4. **Cap → escalate.** If the iteration count reaches the spec-review
   cap set by the stakes tier (Phase 2) while any BLOCKER or MAJOR
   remains, stop and surface the trajectory to the user with
   `AskUserQuestion`.
5. **One grant, one round.** If the user authorises "one more round",
   that is exactly one iteration; re-evaluate these rules after it and
   ask again if still not exited. The cap re-arms every round.
6. **Stall → escalate.** Once at least three reviews exist, if
   `BLOCKER + MAJOR` fails to strictly decrease across two consecutive
   iterations, or the BLOCKER count rises, stop and escalate: the
   trajectory is not converging, and the spec scope or the brief is
   the likely cause. A single flat round is normal.
7. **The loop-ending edit is itself unreviewed.** Any edit to
   `spec.md` made after the review that triggered the exit (including
   patches applied because the user said "stop and just fix") is an
   unreviewed delta — log it verbatim to `.sage/decisions.md` and name
   it in the degraded-run summary. Preferred: run one more review pass
   on the final state instead.

If none of rules 1–7 ends the loop — a BLOCKER or MAJOR remains and the
cap is not yet reached — patch `spec.md` per the findings and re-run
`/review-spec`.

Log each iteration to `.sage/decisions.md`:
```
## <ISO timestamp> · spec review iteration N
- Verdict: <verdict>
- BLOCKERs addressed: <list>
- Intentional non-changes: <list with reasoning>
```

## Phase 4 — Plan

Write `plan.md` per the planner charter. Each step cites the spec section
it satisfies.

## Phase 5 — Plan review (loop, max 2 iterations)

Run `/review-plan <slug>`. Same verdict semantics as Phase 3, but the
common findings here are SCOPE_DRIFT and PLAN_ADHERENCE issues.

A user directive to skip review applies only to the gate the user
**named**. Never silently extend it — if the instruction does not
explicitly cover plan review, name this gate and confirm before skipping
it. A skipped gate is recorded in the degraded-run summary (before
Phase 8).

## Phase 6 — Implementation

First determine how the configured `implementer` role runs:

! .sage/scripts/run-role.sh probe-kind implementer

- **`cli`** → Run `/implement <slug>`. It delegates to the implementer
  sub-agent, which isolates the (large) implementer stdout so your main
  context gets back only a short summary: files touched, tests added,
  spec ambiguities flagged.
- **`host`** → There is no separate CLI to delegate to. Run the
  implementation yourself, in this session, following
  `.sage/prompts/implementer.md` as the charter against the slug's
  `spec.md` and `plan.md`. Do **not** call `/implement` — its
  `allowed-tools` grant no write access; it is for CLI implementers.

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

A user directive to skip code review counts only if the user named
*this* gate. A directive about an earlier phase (e.g. "skip the spec
review") does not authorise skipping code review — name it and confirm
first. A skipped gate is recorded in the degraded-run summary below.

## Before reflecting — degraded-run summary

If any review gate was skipped (external spec review, plan review, or
code review), or the implementer ran as a host agent with no independent
reviewer, emit an explicit summary before Phase 8:

- which gates were disabled, and the user directive that skipped them;
- which artifacts — the final `spec.md`, `plan.md`, the code — therefore
  received **no independent review**.

Show it to the user and get an explicit acknowledgement, then append it
to `.sage/decisions.md` so `/reflect` and future cycles see the run was
degraded.

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
