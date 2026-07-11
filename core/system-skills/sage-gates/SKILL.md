---
name: sage-gates
description: Sage's quality gates and the file checks each workflow must pass. Use when an edit was blocked, when asking why a hook stopped you, when a gate fails or reports UNVERIFIABLE, before claiming work is done, or when you need the spec/plan preconditions for build, fix, or architect.
version: "1.0.0"
type: system
---

# Gates

Two different mechanisms share the word "gate", and confusing them is how
people end up arguing with a hook.

| | Hooks | Gates |
|---|---|---|
| **When** | Before a tool call (PreToolUse) | After work, on demand |
| **What** | Block the edit itself | Score the result |
| **Failure mode** | **Fail open** — a broken hook must not brick the session | **Fail closed** — an unrun gate is not a passed gate |
| **Examples** | `sage-spec-gate.sh`, `sage-tdd-gate.sh` | Gates 1–6 |

Hooks are guards, not gates.

## Why you were blocked

**"Sage spec gate: no spec exists for the active cycle."** A cycle in
`.sage/work/*/manifest.md` has `gate_state: pre-spec`, and you tried to edit a
source file. Write the spec, get `[A]`, and the manifest advances to
`spec-approved`. Then the edit lands.

**"Sage TDD gate: tests before code."** No test has been written for this
change. Write the failing test first. The gate accepts a dirty/untracked test
file or a red commit (tests touched, no source) as evidence.

**Completion blocked.** The manifest cannot reach `complete` while
`gate_state` is anything short of `gates-passed`, and it cannot complete with
an unresolved `qa:` disposition. This is Rule 5 with a script behind it.

Neither hook is arguing with you. Both are stating a precondition you can
satisfy in about a minute.

## The workflow file checks

**Build (Standard+) — BEFORE implementing, verify both files exist on disk:**

- `.sage/work/<initiative>/spec.md` — `status: completed`
- `.sage/work/<initiative>/plan.md` — `status: completed`

If either is missing, create it first. No exceptions.

*Do not rationalize past this:*

| The thought | The reality |
|---|---|
| "The design is clear from earlier discussion" | Not a spec file. |
| "The user described what they want" | Not a spec file. |
| "This is straightforward" | If it is Standard scope, a spec is required. |
| "Just build it" | Write a minimal five-line spec and get `[A]`. |

**Branch gate (Standard+, git projects).** Before implementation commits begin,
HEAD must not be the default branch — unless a branching decline is recorded in
the initiative's decision log. Merging is **always** a user-gated `[M]` action.
No workflow path merges on its own. Full protocol:
`sage/core/capabilities/execution/git-discipline/SKILL.md`.

**Gate sequence (build):**

1. Spec → `.sage/work/` → `[A]`/`[R]` → wait
2. Plan → `.sage/work/` → `[A]`/`[R]` → wait
3. Implement (tests before code, via the build loop)
4. Verify with **pasted** test output → `[A]`/`[R]`

**Fix — scope AFTER root cause:**

1. Investigate the root cause with evidence → `[A]`/`[R]`/`[S]` → wait
2. **Then** scope the fix:
   - Surgical (1–2 files) → proceed
   - Moderate (3–5 files) → write a fix plan first → `[A]`/`[R]`
   - Systemic (5+ files, interface changes) → escalate to `/build` or `/architect`
3. Implement → verify with pasted output → `[A]`/`[R]`

Do not fix before the root cause is confirmed. Do not skip fix scoping — a
"quick fix" that touches eight files is a rebuild wearing a smaller word.

**Architect — brief BEFORE design:**

1. Complete all three elicitation rounds (vision, constraints, gaps). Each
   produces visible output. `brief.md` must exist before design begins. Do not
   compress the rounds. Do not skip them because "I understand the system."
2. Design with ADRs → `.sage/docs/` → spec → `.sage/work/` → `[A]`/`[R]`
3. Milestone plan → `[A]`/`[R]` → phased build; each milestone follows the
   build gates independently.

## Verify before claiming done (Rule 5, in full)

Before presenting any completion checkpoint:

- Tests exist for the new or changed functionality
- Tests **pass** — paste the actual output, do not summarize it
- The implementation matches the spec or plan
- If tests do not exist or do not pass, **the task is not done**

**Spec compliance is adversarial.** Do not trust your own report that the
implementation matches the spec. You wrote it; you are the last one who will
notice what it does not do. Verify independently, or let a fresh reviewer do it.

## The three-state exit contract

Gate scripts exit `0` pass, `1` fail, `2` **unverifiable**.

Exit 2 is the one that matters. It exists because "the suite is green" and
"there is no suite" are different claims that used to share exit 0 — which is
precisely how a gate reports success on code it never looked at.

**Exit 2 is never a pass.** It is also not a failure: it has produced no
evidence either way. On exit 2, present the choice and record it:

```
[P] Proceed unverified — logged as a waiver in .sage/decisions.md
[F] Fix verification setup — install the runner, then re-run
```
