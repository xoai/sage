# Opencode Platform Notes

## Files Sage Writes

| File | Purpose |
|------|---------|
| `AGENTS.md` (project root) | System context — same content as Codex; shared if both installed. |
| `.opencode/commands/*.md` | One markdown command per Sage workflow with YAML frontmatter. |
| `.opencode/agents/sage-reviewer.md` | Markdown sub-agent for spec/plan/ADR/QA reviews. READ-ONLY. |
| `.opencode/agents/sage-classifier.md` | Markdown sub-agent for navigator routing. |

## Command File Format

Per Opencode docs, command files use YAML frontmatter:

```markdown
---
description: Brief shown in TUI
---
[command body / prompt template]
```

Sage's generator writes:
- `description:` from the workflow's `produces:` field
- Workflow body (preamble + steps + `$ARGUMENTS` placeholder)

## Sub-Agent File Format

```markdown
---
description: ...
mode: subagent
permission:
  edit: deny
---
[system prompt]
```

Permissions differ by job (since 1.3.13): `sage-reviewer` carries
`edit: deny` only — code review needs bash for `git diff`/`grep`, so bash
stays available and the prose pins it to inspection, matching claude-code
reviewer parity. `sage-classifier` keeps both `edit: deny` and
`bash: deny` (classification needs no tools). Independent reviews are
dispatched AS `sage-reviewer` (the binding note in AGENTS.md and the
review-bearing commands) because on opencode the agent carries the model
binding — `general` would run on the primary model. Caveat: with multiple
AGENTS.md-writing platforms installed, the last generator wins the file;
list `opencode` after `codex` in `platforms:` (the default order) or the
note survives only in `.opencode/commands/`, which is the stronger
carrier anyway.

## Sub-Agent Invocation

Opencode invokes sub-agents with `@agent-name`. Sage workflows reference
them as `@sage-reviewer` when running reviews.

## Multi-Platform Behavior

If both Codex and Opencode are selected for a project, the second
generator overwrites AGENTS.md with its own terminology swaps. Both
platforms read the same file; the content is functionally equivalent
but the terminology differs slightly (Codex generator says "AGENTS.md
(this file)", Opencode generator says "`.opencode/commands/[workflow].md`").

To avoid this churn, install platforms in a deterministic order — the
last one wins. Or accept that AGENTS.md is "good enough" for both,
since the routing/process content is identical.

## Sub-Agent Capability

Opencode supports sub-agents natively. Sage's auto-review, auto-qa,
and quality-locked features work with full independent context on
Opencode. No fallback needed.

## What's NOT Supported in v1

- Custom skill loaders in `.opencode/skills/` (TBD — sage skills are
  referenced by path from the workflow body)
- Plugin distribution

(The hook system was ported 2026-07-17 as the enforcement adapter —
`.opencode/plugin/sage.js` — and extended 2026-08-04 with the scope judge's
journal/trigger/delivery wire; see STATUS.md and platform.yaml.)

## Detection Heuristic

`sage init` and `sage update` detect Opencode via `.opencode/` directory.
If AGENTS.md exists but no `.opencode/`, Sage assumes Codex (and asks
once if ambiguous).
