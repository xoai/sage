# Codex (OpenAI) Platform Notes

## Files Sage Writes

| File | Purpose |
|------|---------|
| `AGENTS.md` (project root) | Sage's process constitution, routing table, workflow gates. Codex reads this as its system prompt. |
| `.codex/agents/sage-reviewer.toml` | TOML sub-agent definition for spec/plan/ADR/QA reviews. READ-ONLY. |
| `.codex/agents/sage-classifier.toml` | TOML sub-agent for navigator routing classification. |

## Platform-Specific Behavior

### Your own AGENTS.md

Sage's text lives between `<!-- BEGIN SAGE … -->` and `<!-- END SAGE -->`
markers, and `sage init` / `sage update` only ever rewrite that block. A
project's own `AGENTS.md` is kept line for line with the block appended; one
Sage wrote whole before the markers existed is backed up once to
`.sage/backups/` and then replaced by the block; malformed markers leave
the file untouched with a warning (`_shared/managed-md.sh`). Opencode writes
the same file: there is one block, and the last generator to run fills it.

### 32 KiB AGENTS.md cap

Codex reads at most 32 KiB of AGENTS.md (`project_doc_max_bytes`) and drops
the rest without a word. Inlined like on the other community platforms, the
seven system skills made a fresh AGENTS.md ~33.5 KB — and they come last, so a
default install lost the tail of Sage's instructions.

So Codex's AGENTS.md **lists** the system skills instead of inlining them: each
skill's own description (the trigger text native discovery matches on) and the
path of its `SKILL.md` under `sage/core/system-skills/`, which `sage init`
copies into the project. The agent reads the file when a description matches —
discovery done by hand (`emit_system_skills_index` in `_shared/system-skills.sh`).
A fresh AGENTS.md is about 11.5 KB (13 KB with Opencode's note), leaving ~20 KB
for a project's own text. When Opencode shares the file it lists them too, or
it would put the oversized block back.

`generation-smoke.sh` holds a fresh AGENTS.md (codex, and codex + opencode) to
24 KiB — 8 KiB of the cap kept for the project — and checks that every listed
path exists. The generator still measures the whole file, the project's own
text included, and warns when it is over; users can raise the cap via
`project_doc_max_bytes` in `~/.codex/config.toml`.

Not used, because nobody has checked it: recent Codex releases are reported
to discover `SKILL.md` skills themselves. If that is attested, the skills can
be emitted for discovery and `native-skill-discovery` set accordingly.

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
