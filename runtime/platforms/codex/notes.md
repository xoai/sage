# Codex (OpenAI) Platform Notes

## Files Sage Writes

| File | Purpose |
|------|---------|
| `AGENTS.md` (project root) | Sage's process constitution, routing table, workflow gates. Codex reads this as its system prompt. |
| `.codex/agents/sage-reviewer.toml` | TOML sub-agent definition for spec/plan/ADR/QA reviews. READ-ONLY. |
| `.codex/agents/sage-classifier.toml` | TOML sub-agent for navigator routing classification. |

## Platform-Specific Behavior

### 32 KiB AGENTS.md cap

Codex caps the combined instructions file at 32 KiB by default. The
Sage-generated AGENTS.md is currently ~15 KB, well under the limit.
If a project's preset + project additions grow the file, the
generator will warn. Users can raise the cap via
`project_doc_max_bytes` in `~/.codex/config.toml`.

### Sub-agent invocation

Codex's documented invocation pattern is to ask the agent by name:
"Spawn the `sage-reviewer` agent with this prompt..." rather than
calling a Task tool API. Sage workflows reference sub-agents by name
in their preambles.

### Terminology swaps applied to AGENTS.md

The shared instructions-body emits CLAUDE.md content. The Codex
generator post-processes:

- "Task tool" → "sub-agent invocation"
- "the Task tool" → "the sub-agent system"
- ".claude/commands/[workflow].md" → "AGENTS.md (this file)"

### Multi-file AGENTS.md concatenation

Codex concatenates all `AGENTS.md` files from the git root down to
CWD. Sage writes one at the project root. User-level instructions in
`~/.codex/AGENTS.md` are not managed by Sage — users may add their
own preferences there safely; Codex layers them with Sage's content.

## What's NOT Supported

- **Custom slash commands** — Codex docs do not document a custom
  command directory format. Workflows are surfaced through AGENTS.md
  routing instructions rather than registered as `/build` commands.
  Users invoke workflows by name in conversation.
- **Hooks** — Codex supports hooks but Sage's `sage-verify.sh` Claude
  Code hook is not yet ported. v2.
- **Plugins** — Codex plugin distribution not available in v1.

## Sub-Agent Capability

Codex DOES support sub-agents via `.codex/agents/*.toml`. Sage's
auto-review, auto-qa, and quality-locked features work with full
independent context windows on Codex. No fallback needed.
