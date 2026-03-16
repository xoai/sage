# Why State Lives in the Plan File

## The Problem

AI agent sessions end without warning. The terminal closes, the context window fills,
the connection drops. Any state that depends on a "save before exit" action gets lost.

Every framework we studied had this problem:
- Superpowers works around it by committing code to branches (the branch IS the state)
- BMAD uses structured YAML files updated as part of the workflow
- Spec-Kit uses checkbox files where checking a box IS completing the work

## The Insight

The frameworks that handle this well make **state persistence a side effect of doing
the work**, not a separate action.

Spec-Kit's approach is the cleanest: tasks.md has checkboxes. When the agent completes
a task, it checks the box. If the session dies, the file on disk shows which boxes are
checked. No "save" action needed.

## Our Design

Sage v2.0 follows this pattern:

### Ground Truth: The Plan File

`.sage/work/<feature>/plan.md` contains checkbox tasks:

```markdown
- [x] **Task 1:** Create user model ✅ DONE (commit: abc1234)
- [x] **Task 2:** Add validation ✅ DONE (commit: def5678)
- [ ] **Task 3:** 🔄 IN PROGRESS — Build auth middleware
- [ ] **Task 4:** Add token refresh
```

The `implement` skill checks the box as the final step of completing each task.
This is part of the natural workflow, not a separate save action.

### Quick Pointer: progress.md

`.sage/progress.md` is a lightweight pointer:

```markdown
Mode: build
Feature: 003-jwt-auth
Plan: .sage/work/003-jwt-auth/plan.md
Phase: implementation
Next: Task 3 — Build auth middleware
```

This may be stale if the session died abruptly. That's OK — the plan file is the
real state.

### Recovery Priority

When resuming, the agent follows this priority:

1. **Plan file checkboxes** — absolute truth for which tasks are done
2. **Codebase state** (git log, file existence) — resolves plan/code disagreements
3. **progress.md** — orientation only (which feature, which plan file)

If progress.md says "Task 5 in progress" but the plan file shows Tasks 1-3 checked
and Task 4 unchecked, the plan file wins. progress.md was stale.

If the plan file shows Task 3 checked but the code doesn't exist (commit was lost),
the codebase wins. Uncheck Task 3.

## What We Don't Do

We don't build scripts for:
- **Codebase scanning** — the agent does this better than regex
- **Import verification** — the agent understands code context
- **Automated analysis** — all four frameworks leave analysis to the agent

We learned from BMAD, Superpowers, and Spec-Kit that scripts should handle
only what agents CANNOT do (session bootstrapping, git operations, file scaffolding)
or SHOULDN'T do (deterministic structural operations). All analysis and judgment
stays with the agent.
