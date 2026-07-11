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
```

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
