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
descriptive slug. Write `brief.md` following the planner charter —
which begins with a sage-memory recall (planner "Step 0"): when memory
is available the planner recalls this project's prior decisions and
gotchas, cites them in the brief/spec, and writes a compact
`memory-context.md` to the work dir for the downstream roles.

**Branch setup (git projects).** Create the initiative branch per
`sage/core/capabilities/execution/git-discipline/SKILL.md`: propose
`feat/<slug>` (feature work) or `fix/<slug>` (defect work) from the
task description, let the user confirm or rename, create from the
default branch. (This confirm may be bundled with Phase 2's
task-class menu if the user hasn't confirmed earlier — but the
branch must exist before any implementation commits.) The implementer's clean-tree
precondition is then evaluated *on the initiative branch*. Not a git
repository → skip silently.

**Parallel-session note (`isolation: worktree`).** If `isolation:` in
`.sage/config.yaml` is `worktree` and this session is in the main
checkout (not a linked worktree), apply the **worktree bounce** from
git-discipline — offer `sage worktree <slug>` as a guided menu before
branching in place. With `isolation: branch` (default), branch in
place as above.

**Create `manifest.md`** in the work dir (build-x cycles previously
had none): frontmatter carries `title`, `status: in-progress`,
`phase`, `branch:` (the recorded actual branch name —
git-discipline's resume matching reads this field, never derives
from names), and `owner:`/`status:` when the worktree machinery
sets them. This makes build-x initiatives visible to the manifest
scan that `/continue` and session-bridge use.

Update `.sage/progress.md` so `/continue` can pick this up later —
**upsert one entry per active initiative** keyed by slug (slug,
phase, branch, updated); never overwrite the whole file with a
single pointer, so a parallel build-x session does not clobber
another's entry.

## Phase 2 — Spec

Before drafting `spec.md`, classify the **task shape** and reuse Sage
workflows where they fit (see `.sage/prompts/planner.md` for full
guidance). The classification is one of four named words; **propose
the class to the user and confirm before writing**, exactly mirroring
the stakes-tier propose-confirm flow below:

- `architecture-shaped` — new module, cross-cutting refactor,
  storage change, integration → run `/architect` first; spec.md
  then cites the ADRs it produces.
- `knowledge-gap` — unfamiliar domain or research needed → run
  `/research`; spec.md cites findings from `.sage/docs/`.
- `ux-shaped` — user-facing flow, new screen, accessibility → run
  `/design`.
- `mechanical` — config tweak, rename sweep, single-pattern
  refactor → skip the above; draft spec.md directly.

**Anti-downgrade.** When the task description is ambiguous between
two classes, propose the more expensive (more rigorous) one —
`architecture-shaped` beats `knowledge-gap` beats `ux-shaped` beats
`mechanical`. The same discipline `core/workflows/build.workflow.md`
applies to scope assessment ("When in doubt, classify as Standard,
not Lightweight"). After the user confirms, write the chosen word
(no spaces, no quotes) to `.sage/work/<slug>/task-class`:

```
echo architecture-shaped > .sage/work/<slug>/task-class
```

`run-role.sh` reads that file and, for any role whose
`agents.toml` declares `[roles.<role>.tiers.<task-class>]`,
substitutes the override model for that role's default. A missing
file or a class with no override = the role's default model wins.
The resolution is logged at the head of each dispatch's `.log`
file so a reviewer can verify which model ran.

**Classify the stakes** — this sets review rigor, and is separate from
the task-shape classification above:

- **`prototype`** — demo, throwaway, or exploratory work. Spec-review
  cap: **2 iterations**. Plan review (Phase 5) and code review
  (Phase 7) may be skipped, but only with explicit user sign-off.
- **`production`** — work that will be merged and depended on.
  Spec-review cap: **3 iterations**. Every review gate runs.

Propose a tier from the task; let the user override. The tier is the
**single source of the spec-review cap** — Phase 3 refers to it and
never restates a number. Record it in `.sage/progress.md`, and write
the tier word (`prototype` or `production`) to
`.sage/work/<slug>/stakes` — `run-role.sh` reads that file to scale
each reviewer's depth (a missing file defaults to `production`).

Then write `spec.md` following the planner charter. Stop and ask the
user to confirm before continuing:

`[A] Approve · [R] Revise · [X] Cancel`

## Phase 3 — External spec review (severity-gated loop)

Run `/review-spec <slug>`. After **every** review iteration, invoke
the stop-rule script and dispatch on its `action` value:

```
! .sage/scripts/review-stop.sh <slug> spec
```

The script is **canonical** for the loop's verdict — it reads the
timestamped review files under `.sage/work/<slug>/reviews/`, counts
severities, and applies the seven rules below. The planner does
**not** re-derive counts; use the script's `blocker`/`major`/`minor`
values verbatim in the initiative's decision log
(`.sage/work/<slug>/decisions.md`). In case of disagreement
between this prose and the script, the script wins (it is the
determinism this command exists to introduce); flag the doc as the
defect.

The seven rules the script implements:

1. **Proceed (severity-gated exit) → `PROCEED`.** If the latest
   review has **0 BLOCKER and 0 MAJOR** and its verdict is
   `APPROVE`, `REVISE`, or `FIX_BEFORE_MERGE` (the consistent
   no-finding cases), exit the loop and continue to Phase 4 —
   regardless of how many MINOR findings remain. Append open MINORs
   to `.sage/work/<slug>/decisions.md` as deferred items. Never re-run the loop
   on a MINOR-only review.
2. **`REJECT` / `REWORK` → `REJECT`.** A `REJECT` or `REWORK`
   verdict always escalates to the user, regardless of finding
   counts.
3. **Inconsistent review → `INCONSISTENT`.** If the review file
   fails `validate-review.sh`, or its verdict contradicts its counts
   (`APPROVE` / `FIX_BEFORE_MERGE` with any BLOCKER/MAJOR;
   `REJECT` / `REWORK` with none), stop and handle per
   "Reviewer-failure fallback" below.
4. **Cap → `CAP`.** If the iteration count reaches the spec-review
   cap set by the stakes tier (Phase 2 — `prototype`=2,
   `production`=3) while any BLOCKER or MAJOR remains, stop and
   surface the trajectory to the user with `AskUserQuestion`.
5. **One grant, one round.** If the user authorises "one more round",
   that is exactly one iteration; the script re-evaluates on the
   next dispatch. The cap re-arms every round.
6. **Stall → `STALL`.** Once at least three reviews exist, if
   `BLOCKER + MAJOR` fails to strictly decrease across two consecutive
   iterations, or the BLOCKER count rises, stop and escalate. A
   single flat round is normal; the script only fires `STALL` after
   the third iteration.
7. **The loop-ending edit is itself unreviewed.** Any edit to
   `spec.md` made after the review that triggered the exit (including
   patches applied because the user said "stop and just fix") is an
   unreviewed delta — log it verbatim to `.sage/work/<slug>/decisions.md` and name
   it in the degraded-run summary. Preferred: run one more review pass
   on the final state instead.

**Script exit codes** (the planner consumes both the exit code and
the JSON `action`):
- `0` — clean parse; dispatch on the JSON `action` value
  (`PROCEED` | `REVISE` | `CAP` | `STALL` | `REJECT`).
- `2` — `action: MISSING`. Either no review file exists for this
  phase yet, or the file is half-written (no terminal verdict line)
  per spec §F1. Treat as "re-dispatch the reviewer"; not a
  reviewer-failure fallback.
- `9` — `action: INCONSISTENT`. A review file is complete (verdict
  line present) but malformed (fails validate-review.sh rules 2–4)
  or contradicts its own counts. Fall through to Reviewer-failure
  fallback at "Reviewer-failure fallback" below.

If the script returns `REVISE` — a BLOCKER or MAJOR remains and the
cap is not yet reached — patch `spec.md` per the findings and re-run
`/review-spec`.

Log each iteration to `.sage/work/<slug>/decisions.md`, using the script's
counts verbatim:
```
## <ISO timestamp> · spec review iteration N
- Verdict: <script-returned action> (<reviewer verdict word>)
- Counts: BLOCKER=<n> MAJOR=<n> MINOR=<n>
- BLOCKERs addressed: <list>
- Intentional non-changes: <list with reasoning>
```

## Phase 4 — Plan

Write `plan.md` per the planner charter. Each step cites the spec section
it satisfies.

## Phase 5 — Plan review (loop, max 2 iterations)

Run `/review-plan <slug>`. After each iteration, invoke the same
canonical stop-rule script as Phase 3:

```
! .sage/scripts/review-stop.sh <slug> plan
```

Dispatch on the script's `action`; the same seven rules apply, with
the cap pinned to **2 iterations** for plan review (regardless of
the stakes tier — plan-review issues are tighter in scope than
spec-review). The script reads the cap from the stakes file via the
same allowlist; if your project needs the plan cap independent of
spec cap, the script's `cap` field is the source of truth — read it
from the JSON. The common plan-review findings are SCOPE_DRIFT and
PLAN_ADHERENCE issues.

**Review-integrity precondition.** Act on a plan review only if the
dispatcher produced a fresh, schema-valid review for this iteration —
which `review-stop.sh` checks via its exit-9 path. A review that is
missing (exit 2) or malformed (exit 9) is **not** acted on; handle
per "Reviewer-failure fallback" below. Never reuse a prior iteration's
review.

A user directive to skip review applies only to the gate the user
**named**. Never silently extend it — if the instruction does not
explicitly cover plan review, name this gate and confirm before skipping
it. A skipped gate is recorded in the degraded-run summary (before
Phase 8).

**Refresh memory-context after the plan-review APPROVE/REVISE exit.**
By the time plan review exits, the plan has introduced domain words
the brief did not name — and the implementer's `## Project memory`
block (injected from `memory-context.md`) is still keyed on the brief.
If sage-memory is available, follow the planner charter's "Step 0.5 —
Refresh after plan" subsection: run the recall again against the
plan's headers + Goal lines, merge into `memory-context.md` per the
H2 rule. If sage-memory is unavailable, or the plan-keyed query
returns zero results, leave the file unchanged (the brief-keyed
snapshot survives). No-op if `memory-context.md` was never written
in the first place — invariant I1.

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

Run `/review-code <slug>`. After each iteration, invoke the canonical
stop-rule script:

```
! .sage/scripts/review-stop.sh <slug> code
```

Dispatch on the script's `action`. Same seven rules as Phases 3 / 5;
the cap pins to **2 iterations** for code review by default (a third
iteration would have re-implemented twice on the same code-review
file, which is usually a re-scope signal). The script reads code-
review files matching `reviews/diff-code_reviewer-*.md`.

**Review-integrity precondition.** Act on the code review only if
the dispatcher produced a fresh, schema-valid review — which
`review-stop.sh` checks via its exit-2 (no file / mid-write) and
exit-9 (malformed) paths. A missing or malformed review is **not**
acted on; handle per "Reviewer-failure fallback" below. Never reuse
a prior review.

On a valid review (action ∈ `PROCEED` | `REVISE` | `CAP` | `STALL` |
`REJECT`), act on the verdict. On `MISSING` (exit 2), re-dispatch
the reviewer; on `INCONSISTENT` (exit 9), handle per
"Reviewer-failure fallback" below. Phase 7 presents the **single** interactive
decision menu — `/review-code` itself only reports a recommendation,
it does not prompt:

- **APPROVE** → proceed to Phase 8.
- **FIX_BEFORE_MERGE** → present the user `[F]` / `[K]` / `[D]`:
    - `[F]` Fix trivial things yourself (only trivial corrections).
    - `[K]` Route the findings to the implementer. `<code-review-file>`
      below is the review-file path `/review-code` reported for this
      iteration. Probe the implementer kind —
      `! .sage/scripts/run-role.sh probe-kind implementer` — then:
      **`cli`** → delegate to the `kimi-implementer` sub-agent to run
      `.sage/scripts/run-role.sh implementer fix <slug> <code-review-file>`
      (the `fix` dispatch carries the review file to the implementer);
      **`host`** → tell the host implementer, in-session, "you are in
      implementer fix mode (`.sage/prompts/implementer.md`); the
      code-review file is <code-review-file>" and have it fix per that
      charter. After the fix pass, re-run `/review-code <slug>` — the
      loop continues.
    - `[D]` Show the full review and decide.
- **REWORK** → return to Phase 4 (plan), possibly Phase 2 (spec).

Do not auto-merge. Even APPROVE just means "no blocking findings" — the
user decides whether to commit.

**Commit-then-merge gate (git-discipline).** When the loop exits on
**PROCEED** — any 0-BLOCKER/0-MAJOR verdict, not only the literal
`APPROVE` word — the implementation is still an *uncommitted diff*
on the initiative branch (the implementer charter forbids
committing). The sequence is:

1. Offer a **user-gated commit** onto the initiative branch (the
   user decides whether to commit, as above).
2. Only once `git status --porcelain` is empty AND
   `git rev-list <default>..<branch>` is non-empty, offer
   `[M] Merge to <default>` per
   `sage/core/capabilities/execution/git-discipline/SKILL.md` —
   suite gated on its own exit code (or the cycle's smoke procedure
   on a no-harness project), diff-stat shown, `--no-ff`, conflicts
   handed to the user. Skipping step 1 is structurally impossible —
   the preconditions fail on an uncommitted tree.
3. After the commit (and after `[M]`, if taken), **update the
   initiative manifest** — `status:` and phase — so a finished
   build-x cycle does not sit `in-progress` in `/continue`'s scan
   forever.

The ordering is safe for the `[K]` fix loop: fix mode requires the
diff uncommitted, and `[K]` fires only on FIX_BEFORE_MERGE *with
findings* — before any PROCEED exit. Not a git repository or the
user declined branching → the commit offer stands alone, no [M].

A user directive to skip code review counts only if the user named
*this* gate. A directive about an earlier phase (e.g. "skip the spec
review") does not authorise skipping code review — name it and confirm
first. A skipped gate is recorded in the degraded-run summary below.

## Reviewer-failure fallback

A reviewer dispatch can fail outright — `run-role.sh` exits non-zero
(exit 9 = it produced no usable / schema-valid review), or the
`codex-reviewer` sub-agent reports a dispatch failure. When that
happens in any review phase (3, 5, or 7):

1. Surface the failure to the user, with the agent-log path from
   `run-role.sh`'s stderr.
2. You **may** fall back to reviewing **in-session** — the host
   following the relevant `.sage/prompts/<role>.md` charter — but this
   is a **degraded run**: record it in `.sage/work/<slug>/decisions.md` and name
   it in the degraded-run summary. Name the degradation precisely:
   - A **code-review** fallback (Phase 7): the host runs the
     `code_reviewer` charter against `git diff` — it loses the
     cross-model second opinion but is still a review by an agent that
     did not write the diff.
   - A **spec/plan-review** fallback (Phase 3 / 5): the host *is* the
     planner that wrote the artifact, so an in-session fallback is
     **self-review by the author model** — the weakest possible
     review. Prefer to stop and let the user choose; if you do
     self-review, the `decisions.md` entry must say "self-review by
     the author — no independent review occurred".
3. Never reuse a prior iteration's review file as a substitute for a
   failed dispatch.

## Before reflecting — degraded-run summary

If any review gate was skipped (external spec review, plan review, or
code review), or the implementer ran as a host agent with no independent
reviewer, emit an explicit summary before Phase 8:

- which gates were disabled, and the user directive that skipped them;
- which artifacts — the final `spec.md`, `plan.md`, the code — therefore
  received **no independent review**.

Show it to the user and get an explicit acknowledgement, then append it
to `.sage/work/<slug>/decisions.md` so `/reflect` and future cycles see the run was
degraded.

## Phase 8 — Reflect

Run Sage's built-in `/reflect`. It reads the initiative's decision log
(`.sage/work/<slug>/decisions.md`, falling back to the global
`.sage/decisions.md`), the
review files, and `implementer-notes.md` to extract WHEN/CHECK/BECAUSE
learnings for the next cycle.

Then, **after `/reflect` returns**, if sage-memory is available
(attempt a `sage_memory_*` tool; skip on absence or error), store the
cycle's durable **decisions** with `sage_memory_store` — project
scope, tagged `build-x-decision` plus a domain tag. Source them from
the planner's per-iteration entries in `.sage/work/<slug>/decisions.md` — the
architectural choices made in `spec.md`, the stakes tier and why, any
contested-and-resolved invariant — **not** `/reflect`'s prepended
reflection summary, which is already captured under `self-learning`.
Store the *why*, not what is re-readable from `spec.md`. This is what
the next cycle's planner Step 0 recalls.

## Throughout

- Update `.sage/progress.md` after each phase transition — always
  as a per-slug upsert (one entry per active initiative), never a
  whole-file overwrite.
- All reviewer outputs are timestamped under
  `.sage/work/<slug>/reviews/`; never overwrite, always append a new
  timestamped file.
- If any phase produces output the user should see at length, point them
  to the file on disk rather than dumping into the main context.
