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

## Step 1: Scan for Active Cycles

Scan `.sage/work/*/manifest.md` for cycles where
`status: in-progress` or `status: paused`.

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

On [C]: Load manifest context. Route to the workflow's Auto-Pickup
with manifest as primary context source. The resuming agent follows
the handoff guidance and does NOT re-ask questions already resolved.

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

1. Read the selected manifest.md
2. Read the relevant artifacts (spec, plan, brief)
3. Read decisions.md entries for this cycle
4. Resume at the phase indicated by the manifest

The resuming agent behaves as if it has the context described
in the manifest's context summary. It follows the handoff
guidance. It does NOT re-ask questions the previous agent
already resolved — those decisions are in the manifest and
decisions.md.

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

- /continue reads the manifest as PRIMARY context source
- Do NOT ignore the manifest and re-scan artifacts from scratch
- The manifest's phase routing and context summary take precedence
- Agent MAY additionally read artifacts for detail
- If manifest doesn't exist but artifacts do, route to the
  workflow's Auto-Pickup which will use file-scan fallback
