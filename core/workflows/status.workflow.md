---
name: status
version: "1.0.0"
mode: status
produces: ["Project state summary"]
checkpoints: 0
scope: "Instant"
user-role: "Read and decide next step"
---

# Status Workflow

Show current Sage project state.

## Process

Read and display:

1. `.sage/progress.md` — current mode, active feature, phase, next step
2. `.sage/work/` — read frontmatter from artifact files for status,
   phase, and task progress (tasks-done/tasks-total)
3. `.sage/docs/` — list project-level artifacts

Present concisely:

```
Sage: Project status

  Project: [name]
  Status: [mode] — [feature] — [phase]
  Next: [what progress.md says is next]

  Initiatives:
    20260315-homepage-redesign/  build workflow  spec ✓  plan 5/8 tasks
    20260310-jtbd-analysis/      completed

  Docs: jtbd-momo-qlct.md, decision-auth-provider.md

  [C] Continue current work  |  Or tell me what you'd like to do
```

## Rules

- Report what actually exists, not what should exist.
- If `.sage/progress.md` is missing, say so — don't fabricate state.
