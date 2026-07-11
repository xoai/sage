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
  bash: deny
---
[system prompt]
```

Sage's sub-agents use `permission.edit: deny` and `permission.bash: deny`
to enforce the READ-ONLY constraint for review sub-agents.

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
- Hook system port

## Detection Heuristic

`sage init` and `sage update` detect Opencode via `.opencode/` directory.
If AGENTS.md exists but no `.opencode/`, Sage assumes Codex (and asks
once if ambiguous).
