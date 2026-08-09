---
name: subagent-execution
description: >
  Replaces the inline build loop when subagent execution is active. A fresh
  implementer subagent per plan task, a fresh reviewer per task, a whole-branch
  reviewer at the end — wired into the manifest ledger, the gates, and the hooks.
  Opt-in (--subagents); loud where the platform cannot dispatch.
version: "1.0.0"
requires: [flag-parser, quality-locked, spec-review, quality-review, tdd]
---

# Subagent Execution Sub-Workflow

Engaged at build-loop entry (build Step 6, fix's implementation step) when
`resolve_execution_mode()` returns `subagent`. Otherwise the inline build loop
runs and nothing here applies.

## What this actually buys, and what it costs

**The mechanism is context isolation, and it is structural.** The inline build
loop accumulates: by task 6, the agent implementing it is carrying five previous
tasks' reasoning, three abandoned approaches, and its own conviction that the
design is right — because it made the design. A fresh implementer carries none of
that. It has no sunk cost in any approach, which makes it the best-placed context
in the cycle to notice that a task, as written, does not make sense.

That is enforcement by construction rather than by persuasion — the category
Sage's own eval says works, and the category prose keeps failing to be.

**The cost is real and is not yet measured.** Total tokens go UP: each subagent
re-reads context the orchestrator already had. What goes DOWN is orchestrator
context, which stays flat across a plan of any length. Whether that trade is
worth it is an empirical question, and it is Phase 5's (E-mode comparison), not a
question this document gets to answer by asserting. Until then, the mode is
**off by default** (C13).

## The orchestrator writes no implementation code

This is the rule the whole design rests on, and it is observable rather than
aspirational: **every implementation commit must be attributable to an implementer
dispatch**, and the ledger records the mapping.

The orchestrator's job is exactly six things:

1. Ledger upkeep
2. Context-packet construction
3. Dispatch
4. Verdict processing
5. Gate runs
6. Checkpoint handling

An orchestrator that "just fixes this one small thing itself" has silently
reverted to the inline loop while still paying for the subagents — and it now has
an opinion about the code its reviewers are judging.

## Step 0 — scaffold the ledger. This is not optional and it is not prose.

**Before the first dispatch:**

```bash
python3 sage/runtime/tools/ledger.py init \
  .sage/work/<initiative>/manifest.md \
  .sage/work/<initiative>/plan.md
```

This generates one ledger entry per plan task — the template's
`- [ ] **Task N:**` bullets or `## Task N` headings — and sets
`execution_mode: subagent`, which arms the completion guard.

**Why a script and not an instruction to you.** E9 measured this. Given a ledger,
the mode is flawless (E10: 3/3 — the reviewer catches a planted spec violation,
the fix lands, the approval is recorded). Asked to *create* the ledger from this
document, the orchestrator simply did not, in two runs out of three — and those
runs looked, from the outside, exactly like a cycle that had done its work.

The ledger is the entire evidence base for this mode's claim that every task was
independently reviewed. It was being produced by goodwill. Now it is produced by
a script, and `ledger.py check` fails a subagent cycle that lacks one.

That is this project's own rule, applied to its own newest feature: *if a rule
matters, make it code.*

## Per-task loop

For each task in the approved plan, in order (respecting `[P]` parallelism where
the platform allows it):

### 1. Build the context packet

Per `core/templates/subagents/context-packet.md` (R99). Assembled from:

- the plan task **verbatim**, plus its `Output:` deliverables
- the spec excerpts **this task cites** — not the whole spec
- the constitution slice relevant to this task
- `sage-memory` results for the task's keywords
- the files-touched-so-far list, **from the ledger**
- global constraints from the plan header

**If sage-memory is unavailable, the packet says so in the section where the
results would have been.** Never drop the section. A missing section reads as
"there is nothing to know", which is a much more confident claim than "we could
not check".

### 2. Mark the ledger, then dispatch

Set the task `status: in-progress`, increment `attempts`. Dispatch a fresh
implementer subagent with `implementer-prompt.md` + the packet.

Record the **serving model** in the entry's `model:` field at dispatch time —
the bound agent's model where the platform binds roles (opencode agent
designation, resolved by `agent_binding.py`, never assumed), else `inherit`.
Sessions record their actual model; this applies that rule per-dispatch. A
re-dispatch overwrites the field: it answers "what served the attempt that
produced these commits", and `attempts` already counts the retries.

The ledger moves BEFORE the dispatch. If the session dies mid-task, a ledger that
was going to be updated afterwards records nothing, and `/continue` restarts a
task that may already be half-done.

### 3. Process the report

The implementer returns `STATUS: DONE | BLOCKED` plus an evidence block.

**BLOCKED** → record `status: blocked` and the reason. If the orchestrator can
resolve it (a missing decision, an ambiguity in the task), resolve it and
re-dispatch. If it cannot, this is one of the two things that may interrupt
continuous execution: surface it to the user.

**DONE without a complete evidence block** → this is *not* accepted at face value
and *not* silently re-run. It goes to review flagged (R106). "Done" with pasted
test output and "done" without it are indistinguishable to a machine, and the
ledger cannot tell them apart either.

### 4. Review the task

Dispatch a fresh task-reviewer with `task-reviewer-prompt.md`, the **same packet**
the implementer got, the implementer's report, and the diff for its commit range.

The reviewer runs three mechanical containment checks before any judgment:

- **Evidence** — is pasted test output present? Absent → Critical.
- **Containment (R106)** — do the commits touch files outside the packet's list,
  beyond tolerance? Unexplained → Important or worse.
- **Test order** — did the test land before or with the implementation?

Then two independent verdicts: spec compliance, and code quality.

### 5. Process the verdict

| Verdict | Ledger | Next |
|---|---|---|
| APPROVED | `review: approved` | Gates (step 6) |
| Findings — Minor only | `review: approved`, findings recorded | Gates. Minors roll into the branch review. |
| Findings — Critical/Important | `review: findings` | Fix loop |

**The fix loop** dispatches a fix subagent with the packet + the findings, then
**re-reviews**. It is governed by the existing quality-locked decision function in
`sage_flags.py` — the same cap, the same semantics. Do not reimplement it here;
a second copy of a cap is a second cap, and they will disagree.

When the cap is hit, the task is escalated to the user, not quietly approved.

### 6. Gates, per task

After a task is approved, run **Gate 4** (hallucination) and **Gate 5** (verify),
scoped to the task's commits, via the existing standalone invocation.

Hooks already fired inside the subagent — that was verified, not assumed
(P3-T1: `sage-tdd-gate` blocked an implementer's untested source edit, the
implementer wrote the test, and its retry was allowed). So these runs are
**belt-and-braces**: they exist to catch an implementer that *lied* — reported
DONE having done something else — not one that was unpoliced.

- exit 0 → task `status: done`. Next task.
- exit 1 → back to the fix loop.
- exit 2 (unverifiable) → the recorded waiver prompt. Exit 2 is never a pass.

The full gate sequence still runs once at cycle end. Per-task gates do not replace
it; they stop a broken task from being built on by the next five.

## Parallel lanes (`--parallel[=N]`, opt-in — A7)

Engaged only when `resolve_parallel()` grants it: parallel exists INSIDE
subagent execution (`--subagents --parallel`), and a refused request is the
same loud-degradation contract as subagents themselves. Default cap 2 lanes,
hard cap 4. Never default-on.

**The scheduler is code, and the graph is its only input.** Every dispatch
decision comes from:

```bash
python3 sage/runtime/tools/lanes.py schedule .sage/work/<cycle>/manifest.md --cap <N> \
    --couplings .sage/work/<cycle>/couplings.json
```

which reads the derived `task_graph:` (A8 — if the plan was underivable,
parallel mode never opened), the ledger, and the `lanes:` block. It prints
what dispatches NOW and why everything else waits: overlap serializes (a
declared overlap is a serialization signal, never a worktree signal), a
non-`[P]` task runs alone, a parked/errored lane freezes its dependents
while siblings continue. Do not re-derive any of this from plan prose.

**The ontology consult (A9), before each burst.** Disjoint files do not
mean independent modules. Query sage-memory's code graph for dependency
between the candidate lanes' file sets (`sage_memory_code_path` /
`sage_memory_code_affected` over each pair's modules) and write the result
to `couplings.json`: `{"pairs": [{"a": 2, "b": 3, "via": "models.Token"}]}`.
The scheduler warn-and-serializes coupled pairs. When sage-memory is
unavailable, write NO file — the scheduler then prints its standing
degradation line ("coupling UNCHECKED") every burst; never fake an empty
consult, an unchecked coupling must not read as checked-and-clean.

**Each lane is a worktree + branch**, created with the existing machinery —
`sage worktree <slug> --from <burst-base sha>` (worktree_copy seeding,
collision guard, harvest on remove). The `--from` is not optional garnish:
bare `sage worktree` bases on the DEFAULT branch, and mid-cycle the
integration checkout is on the feature branch — a lane forked from `main`
is a lane forked from the wrong world. Then, per lane, this sub-workflow's
own per-task loop runs unchanged: context packet, implementer dispatch with
the A6 role bindings, task-reviewer dispatch, verdicts. Hooks fire inside
lane subagents exactly as they do inline (attested, P3-T1).

**Bookkeeping stays single-writer.** Lanes REPORT (`STATUS: DONE | BLOCKED`
+ evidence); only the orchestrator RECORDS, and only through the tool:

```bash
python3 sage/runtime/tools/lanes.py open  <manifest> --task N --branch B --worktree DIR \
    [--model M] --base <merged-HEAD sha> --repo-root . --cap <N> \
    --couplings .sage/work/<cycle>/couplings.json
    # refuses what schedule would not dispatch; --repo-root arms the
    # burst-base assertion (base must BE the integration HEAD) — omit it
    # and the pin is recorded but unproven
python3 sage/runtime/tools/lanes.py mark  <manifest> --task N --state parked|errored|failed|budget-stopped --note "..."
python3 sage/runtime/tools/lanes.py merge <manifest> --task N   # dependency order enforced
```

`open` marks the ledger (status, attempts, `model:`, `lane_branch:`) in the
same pass. A lane subagent that tries to write the manifest itself is
redirected by the bookkeeping-gate — the invariant is enforced, not asked
for. `merged` can only be written by an actual `merge`; a depends edge is
never satisfied by prose.

**Merge policy.** Merge lanes in dependency order (`merge` refuses anything
else). A conflict means declared-disjoint was violated: the tool aborts the
merge, notes the conflicted files on the lane record, and the conflict is
filed as a scope finding via check-diff — serialize or re-plan. Never
resolve a lane conflict by model judgment.

**Integration proof.** After each burst merges, run the FULL suite and the
gate sequence once on merged HEAD. This is never trimmed: lane-level green
is lane evidence only — nothing lane-local ever looked at the composition.
Dependent tasks' context packets are built AFTER this, from merged HEAD.

**Resume.** Open lanes live in the manifest's `lanes:` block; `manifest.py
resume` lists them with the harvest path (`sage worktree remove`, never the
bare git command). A burst interrupted is a burst reconstructible.

**Failure taxonomy (A9) — three states that must never blur:**

- `failed` — a GRADED outcome (review cap, broken work). Fix loop or
  escalation; consumes quality-locked attempts.
- `errored` — an infra death: rate limit, provider outage, detected per
  the 1.3.3 evidence rules (token counts, not "it stopped talking").
  `lanes.py retry --task N` grants exactly ONE re-dispatch — never
  graded, attempts untouched — staggered by `parallel_stagger_seconds`
  (also the gap between normal dispatches; burst-y opens are how rate
  limits happen). A second infra death parks the lane and surfaces.
- `budget-stopped` — the burst's `parallel_budget` (tokens or currency,
  orchestrator-tracked) ran out. In-flight lanes COMPLETE; no new starts
  (`lanes.py schedule --budget-exhausted` reports held tasks); at burst
  end mark held tasks `budget-stopped` — works for never-dispatched
  tasks too, so the stop is an explicit record, never a silent
  truncation graded as failure.

**Questions batch to burst end.** A BLOCKED lane parks (dependents
freeze, siblings continue) and its question joins the burst-end batch —
interrupt the user mid-burst only when ALL remaining work depends on the
answer. Print every lane transition as it happens (open/parked/errored/
merged — the lanes.py commands already emit the lines; surface them).

**Close-out, per lane.** The accounting footer's parallel form adds one
line per lane: task, model, tokens (from the platform's usage surface,
or "unmetered"), attempts, retries, final verdict. Counts, not a
verdict — the cost story is E-PAR's to measure, not this footer's to
claim.

## Between tasks: continuous execution

**No user prompts between tasks.** Not "are you happy with task 3", not "shall I
continue". The `[A]/[R]/[C]` checkpoints stay exactly where they were — at plan
approval and at completion.

Progress is visible in the **ledger**, not in chat. A user who wants to watch can
read it; a user who does not should not have to click through fourteen
confirmations to get a feature built.

Exactly two things may interrupt: a **BLOCKED** task the orchestrator cannot
resolve, and a **gate exit 2** waiver decision. Both are decisions only a human
can make. Nothing else is.

## At the end: the branch review

When every ledger task is `done` + `approved`, dispatch the **branch reviewer**
(`branch-reviewer-prompt.md`) over the whole diff, with the spec, the plan, and
the ledger.

**This is not optional and it is not a formality.** Per-task review is
*definitionally* incapable of seeing across tasks: every task can satisfy its own
bullet while the assembled result misses the point of the spec. If the branch
review is skipped, then nothing in the entire cycle has ever looked at the change
as a whole — which is the only way anyone will ever experience it. Everybody
approved their piece; the shape of the thing was nobody's job.

Its findings loop like any other. Only then does the cycle proceed to
`gate_state: gates-passed` — and the spec-gate hook will refuse that transition
while any ledger task is not done+approved (R101), so this is enforced, not
merely expected.

## The accounting footer

At completion, the manifest carries:

```
## Execution accounting

Mode: subagent
Tasks: 5
Implementer dispatches: 7      (2 tasks needed a second attempt)
Reviewer dispatches: 6         (1 task needed a re-review)
Branch reviews: 1
Gate runs: 10                  (Gate 4 + Gate 5 per approved task)
Models: implementer=deepseek/deepseek-v4-flash ×7 · task-reviewer=deepseek/deepseek-v4-flash ×6 · branch=inherit
```

The `Models:` line aggregates the ledger's per-entry `model:` fields plus the
reviewer/branch dispatches — it is what you compare against an inline run
before deciding mixed-tier dispatch is worth it (the cost story is
deliberately unmeasured; see "Planner/implementer model split" in
docs/configuration.md).

**These are counts, not a verdict.** The mode's cost story is measured in Phase 5,
not asserted here. What the footer is for is the *next* cycle's planner: a task
that took three implementer attempts is usually not a task that was hard — it is a
task whose plan was wrong, and that is worth knowing before writing the next plan.

## Unavailability is loud

Where the platform contract lacks `subagent-dispatch`, this sub-workflow does not
run. `resolve_execution_mode()` returns the degraded result, and the workflow:

- **announces it** — "per-task review will NOT be independent"
- writes **one line** to `decisions.md` via the existing degradation machinery
- records `execution_mode: inline (subagents-unavailable)` in the manifest
- falls back to the inline build loop

It does not quietly do the inline thing while the user believes they asked for
per-task independent review. That failure mode — a degraded run indistinguishable
from a clean one — is the one v1.2.x was spent eliminating, and re-introducing it
here would be an unusually stupid way to lose the argument.
