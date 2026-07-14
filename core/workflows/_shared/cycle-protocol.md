# Cycle protocol (shared by /build, /fix, /architect)

The delivery workflows share a common cycle discipline. Each workflow's own file
keeps the parts that genuinely differ (its Auto-Pickup routing, its Manifest
Lifecycle gate_state mapping, its Phase Announcement names); this file is the one
place the *shared* rules live.

## Decision-log target (Rule 7)

"decisions.md" in a delivery workflow means the initiative's log at
`.sage/work/[initiative]/decisions.md`. The global `.sage/decisions.md` is only
for cross-initiative decisions. Readers check the initiative log first, then fall
back to the global file.

## Manifest gate_state discipline

`gate_state` is the machine field the spec-gate hook reads, and the field a resumed
session trusts to tell it where the work stopped. The vocabulary is closed:

```
pre-spec → spec-approved → plan-approved → building → gates-passed → complete
```

**You are not asked to advance it to `building` any more.** The
`sage-manifest-sync` PostToolUse hook does that: the moment source is written under
an active `plan-approved` cycle, the manifest records `building`. It fires because
you wrote code, and the firing *is* the evidence.

This used to be your job, and L1 measured what that was worth. Three runs of the
identical cycle, all three completing and committing all three tasks:

| run | `gate_state` recorded | reality |
|---|---|---|
| 1 | `gates-passed` | 3/3 tasks done |
| 2 | **`plan-approved`** | 3/3 tasks done |
| 3 | `complete` | 3/3 tasks done |

Run 2 is why this is a hook. A session resuming from *"plan approved, no tasks
started"* redoes work that is already committed. The bridge between sessions had
drifted from the tree it describes.

**What is still yours, and cannot be automated:** `spec-approved`, `plan-approved`,
`gates-passed`, `complete`. Those are *approval* states. A script that awarded
`gates-passed` because the files looked finished would be forging the signature the
gate exists to collect — so the hook refuses to, by design, and the completion guard
(Rule 5) still blocks a `complete` that outruns `gates-passed`.

Fact is mechanical. Approval is not.

Check a cycle at any time:

```bash
python3 sage/runtime/tools/manifest.py check      # does the manifest match the tree?
python3 sage/runtime/tools/manifest.py sync <manifest.md>   # repair it if not
```

## Resume: the brief is generated

Resuming a cycle starts with ONE command, not a scan:

```bash
python3 sage/runtime/tools/manifest.py resume
```

(Plugin installs: `python3 "${CLAUDE_PLUGIN_ROOT}/tools/manifest.py" resume`.
No python3 → fall back to the manual scan your workflow describes.)

It selects the cycle (active status, owner exclusion, branch preference — the
same rules /continue states, computed), and prints: the machine fields, the plan's
tasks, the git evidence since the cycle began, the decisions in force, and the
previous session's manifest body verbatim. Same files, same brief. Do not
re-derive by hand what the brief already states — read spec/plan/source for
*detail*, not to re-establish state.

## Resume authority order

L1 measured what happens without this, and it is why the brief prints it. One run
in three, session 1 hedged — wrote a speculative "blocked, needs the user's call"
into the manifest — and session 2 inherited the hedge as law: it refused to
implement the remaining task twice, under an explicit user instruction to keep
going, while the recorded decision (D-002) had already sanctioned the exact shape
it refused to pick. The dead session outranked the live user.

The order, highest authority first:

1. **The live user's instruction in THIS session.** An instruction to proceed or
   finish IS the approval a pending checkpoint was waiting for. Do not re-present
   a question to someone who just answered it.
2. **Recorded decisions.** A question a recorded decision answers is CLOSED.
   Choosing among options a decision already sanctions is *execution*, not a new
   approval — pick the option that best fits the approved spec, record the choice
   (Rule 7), and proceed.
3. **The manifest's judgment sections** (context summary, open questions, handoff
   guidance). Context, not orders. They inform the resuming session; they bind it
   only where no recorded decision answers and no live user has spoken.

And evidence outranks all prose: where the manifest and the tree disagree, trust
the tree (`manifest.py sync` repairs the machine field).

**Blocking a cycle is a claim that must name its question.** `status: blocked`
requires `blocked_on:` in the frontmatter — the question, the options, whose call
it is. `manifest.py check` fails a blocked manifest without it: a blocker nobody
can name is not a blocker, it is a hesitation the next session will inherit as
law. And Rule 4 is about *approval* checkpoints — brief, spec, plan, final
deliverable. An implementation choice inside an approved plan, with the option
space already sanctioned by a recorded decision, is not a Rule 4 checkpoint.

## Phase announcements

Announce each phase transition before doing its work, with the cycle id (the
`.sage/work/` directory name), e.g. `Sage: Entering DELIVER phase [cycle-id] —
<what this phase does>`. Each workflow lists its own phase set.

## Session-break contract

At any `[N]` / context-budget break, write the manifest (phase, status,
gate_state, context summary, handoff guidance) BEFORE ending — the manifest is
the bridge between sessions.
