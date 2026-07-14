---
name: continue
version: "1.0.0"
mode: continue
produces: ["Session resumption with context"]
checkpoints: 0
scope: "Instant — routes to another workflow"
user-role: "Confirm which cycle to resume"
---

# Continue Workflow

Resume any active cycle with full context. The user doesn't need
to remember which workflow or initiative was in progress.

## Step 1: Find the Cycle — run the tool, don't scan

```bash
python3 sage/runtime/tools/manifest.py resume
```

(Plugin installs: `python3 "${CLAUDE_PLUGIN_ROOT}/tools/manifest.py" resume`.)

One command. It applies the selection rules (active status including `blocked`,
owner exclusion, branch preference) and prints the resume brief: machine fields,
plan tasks, git evidence, decisions in force, the previous session's judgment,
and the authority order. Same files, same brief.

**Manual fallback** (no python3 only): scan `.sage/work/*/manifest.md` for
cycles where `status:` is `in-progress`, `paused`, or `blocked` (never
`abandoned`). Skip cycles whose `owner:` field does not match this session's
`git rev-parse --show-toplevel` after path normalization — they belong to
another worktree (see git-discipline). Prefer the cycle whose recorded
`branch:` field matches the current branch.

### One cycle found (Zone 2: Approval)

```
Sage: Resuming [{title}] — {workflow}, phase: {phase}.
{context summary, verbatim from manifest}
Next step: {next step from manifest}

[C] Continue — pick up where we left off
[S] Status — show me full cycle state before continuing
[X] Different — I want to work on something else

Pick C/S/X, or tell me what you need.
```

On [C]: Route to the workflow's Auto-Pickup with the resume brief as
primary context source. Do NOT re-ask resolved questions or inherit a
dead session's hesitation — apply the authority order the brief prints
(live user > recorded decisions > manifest prose; evidence beats all).

On [S]: Show full manifest contents (State, Context summary,
Decisions, Open questions, Handoff guidance). Then offer [C]/[X].

On [X]: "Describe what you want to work on, or type / to see commands."

### Multiple cycles found (Zone 1: Choice)

```
Sage: Found {N} active cycles:

[1] {title A} — {workflow}, phase: {phase} (updated: {date})
[2] {title B} — {workflow}, phase: {phase} (updated: {date})
[3] Start something new

Pick 1-{N+1}, type / for commands, or describe what you need.
```

On selection: load that cycle's manifest, route to its workflow.

### No cycles found (Zone 4: Open) — this is also `/status`

With no active cycle, `/continue` prints the **project status** (folding in the
former `/status` workflow): compute state from artifacts — never from a
progress file — and report only what exists.

Scan and display:
1. `.sage/work/` — read each artifact's frontmatter for status and phase
2. `.sage/docs/` — count project-level artifacts
3. `.sage/decisions.md` — the last 2–3 entries for recent context
4. `.sage/gates/gate-modes.yaml` — current gate activation config

```
Sage: Project status for [name]

Active:   [initiative] [status, phase] — brief ✓ spec ✓ plan (in-progress)
Completed:[initiative] [completed]
Docs:     [N] files in .sage/docs/
Recent:   [last 2–3 decision titles]
Gates:    [mode config summary]

No active cycle to resume. Describe what you want to work on, or type / for
commands.
```

If `.sage/work/` is empty, say so — do not fabricate state. Always suggest the
next slash command.

## Step 2: Load Context and Resume

The brief already contains the state, evidence, decisions in force, and the
manifest body — do NOT re-derive them by hand. Read spec.md and plan.md for
the *detail* of the remaining work, and resume at the phase the brief indicates.

Do NOT re-ask questions already resolved in decisions.md, and do not
treat the previous session's judgment as orders: an "open question" or
"blocked" claim a recorded decision answers is CLOSED (choose among the
sanctioned options, record the choice, proceed), and the live user's
instruction to continue IS the approval a pending checkpoint was
waiting for (cycle-protocol.md § Resume authority order).

## Routing

/continue reads the `workflow` field in the manifest and activates
the corresponding workflow's Auto-Pickup:

| workflow field | Routes to |
|---------------|-----------|
| build | /build Auto-Pickup |
| architect | /architect Auto-Pickup |
| fix | /fix Auto-Pickup |
| research | /research Auto-Pickup |
| design | /design Auto-Pickup |
| analyze | /analyze Auto-Pickup |
| reflect | /reflect Auto-Pickup |

## What /continue Does NOT Do

- Does not manage parallel execution
- Does not replace decisions.md (manifest decisions are a subset)
- Does not replace handoff fields in artifact frontmatter
- Does not auto-save on crash (manifest may be stale if session
  died unexpectedly — fallback to artifact-scanning still works)

## Rules

- /continue reads the generated resume brief as PRIMARY context source
- Do NOT ignore the brief and re-scan artifacts from scratch
- Phase routing comes from the manifest's machine fields; its judgment
  prose (context summary, open questions, handoff) is context, NOT
  orders — see cycle-protocol.md § Resume authority order
- Agent MAY additionally read artifacts for detail
- If manifest doesn't exist but artifacts do, route to the
  workflow's Auto-Pickup which will use file-scan fallback
