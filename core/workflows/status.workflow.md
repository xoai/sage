---
name: status
version: "1.1.0"
mode: status
produces: ["Project state summary computed from artifacts"]
checkpoints: 0
scope: "Instant"
user-role: "Read and decide next step"
---

# Status Workflow

Show current Sage project state. Computed from artifacts — always current.

## Process

Scan and display:

1. `.sage/work/` — read frontmatter from artifact files for status and phase
2. `.sage/docs/` — list project-level artifacts
3. `.sage/decisions.md` — last 3-5 entries for recent context
4. `.sage/gates/gate-modes.yaml` — current gate activation config

Present concisely:

**Sage:** Project status for [name]

Active:
  [initiative-name] [status, phase]
    brief ✓  spec ✓  plan (in-progress)
    .sage/work/YYYYMMDD-slug/

Completed:
  [initiative-name] [completed]

Docs: [N] files in .sage/docs/
Recent decisions: [last 2-3 decision titles]
Gates: [mode config summary]

[1] Continue [initiative] — type /build
[2] Start something new

## Rules

- Report what actually exists, not what should exist.
- Compute from artifacts — never read progress.md.
- If `.sage/work/` is empty, say so. Don't fabricate state.
- Always suggest the next slash command.
