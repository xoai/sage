---
name: continue
description: >-
  Session resumption with context
disable-model-invocation: true
---

- Announce: "Sage → continue." before starting work

# Continue Workflow

Resume any active cycle with full context. The user doesn't need
to remember which workflow or initiative was in progress.

## Step 1: Find the Cycle — run the tool, don't scan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/manifest.py" resume
```

One command. It applies the selection rules (active status including
`blocked`, owner exclusion, branch preference) and prints the resume
brief: machine fields, plan tasks, git evidence, decisions in force,
the previous session's judgment, and the authority order. Same files,
same brief.

**Manual fallback** (no python3 only): scan `.sage/work/*/manifest.md`
for cycles where `status: in-progress`, `paused`, or `blocked`.

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
primary context source. The resuming agent does NOT re-ask questions
already resolved — and does not inherit a dead session's hesitation.
The authority order (printed with the brief): the live user's
instruction outranks recorded decisions; recorded decisions outrank
the manifest's judgment prose; evidence outranks everything. A
question a recorded decision answers is CLOSED — choosing among
options a decision already sanctions is execution, not a new
approval: pick, record the choice, proceed.

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

### No cycles found (Zone 4: Open)

```
Sage: No active cycles found.

Describe what you want to work on, or type / to see commands.
```

## Step 2: Load Context and Resume

The brief already contains the state, the evidence, the decisions in
force, and the manifest body. Do NOT re-derive them by hand. Then:

1. Read spec.md and plan.md for the *detail* of the remaining work
2. Resume at the phase the brief indicates

The resuming agent does NOT re-ask questions the previous agent
already resolved — those decisions are in decisions.md. It also does
not treat the previous session's judgment as orders: an "open
question" or "blocked" claim that a recorded decision answers is
CLOSED, and the live user's instruction to continue IS the approval a
pending checkpoint was waiting for.

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
  prose (context summary, open questions, handoff) is context, NOT orders
- Agent MAY additionally read artifacts for detail
- If manifest doesn't exist but artifacts do, route to the
  workflow's Auto-Pickup which will use file-scan fallback
