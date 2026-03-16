---
name: status
version: "1.0.0"
mode: status
---

# Status Workflow

Show current Sage project state.

## Process

Read and display:

1. `.sage/progress.md` — current mode, active feature, phase, next step
2. `.sage/work/` — list initiatives with their status (has brief? spec? plan?)
3. `.sage/docs/` — list project-level artifacts

Present concisely:

```
Project: [name]
Status: [mode] — [feature] — [phase]
Next: [what progress.md says is next]

Initiatives:
  20260315-homepage-redesign/  brief ✓  spec ✓  plan ✓  (building)
  20260310-jtbd-analysis/      complete

Docs: jtbd-momo-qlct.md, decision-auth-provider.md

[C] Continue current work  |  Or tell me what you'd like to do
```

## Rules

- Report what actually exists, not what should exist.
- If `.sage/progress.md` is missing, say so — don't fabricate state.
