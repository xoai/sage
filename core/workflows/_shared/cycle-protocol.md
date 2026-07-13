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

## Phase announcements

Announce each phase transition before doing its work, with the cycle id (the
`.sage/work/` directory name), e.g. `Sage: Entering DELIVER phase [cycle-id] —
<what this phase does>`. Each workflow lists its own phase set.

## Session-break contract

At any `[N]` / context-budget break, write the manifest (phase, status,
gate_state, context summary, handoff guidance) BEFORE ending — the manifest is
the bridge between sessions.
