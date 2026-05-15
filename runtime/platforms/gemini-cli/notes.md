# Gemini CLI Platform Notes

## Files Sage Writes

| File | Purpose |
|------|---------|
| `GEMINI.md` (project root) | Project context — shared with Antigravity if both installed. |
| `.gemini/commands/*.toml` | One TOML file per Sage workflow. Filename = command name. |
| `.gemini/commands/sage/*.toml` | When `command_prefix: true`, commands are grouped under `sage/` subdirectory, producing `/sage:build`, `/sage:fix`, etc. |

## TOML Command Format

Per Gemini CLI docs:

```toml
description = "One-line help text shown in /help menu"
prompt = """
Multi-line prompt template.
User input is injected via {{args}}.
"""
```

Sage's generator writes one TOML per workflow. The prompt contains:
1. The workflow preamble (compliance rules)
2. The workflow body (steps)
3. Trailing `{{args}}` placeholder

## Argument Handling

Gemini CLI replaces `{{args}}` with the user's input when the command
runs. If a user types `/build --quality-locked ship dark mode`, Gemini
substitutes `--quality-locked ship dark mode` for `{{args}}` in the
prompt template. Sage's flag parser then extracts the flags from that.

## Namespaced Commands

Per Gemini CLI docs, subdirectory paths produce namespaced command
names — `.gemini/commands/sage/build.toml` → `/sage:build`.

Sage uses this when `command_prefix: true` is set in `.sage/config.yaml`:
- Without prefix: `.gemini/commands/build.toml` → `/build`
- With prefix: `.gemini/commands/sage/build.toml` → `/sage:build`

## GEMINI.md Sharing with Antigravity

Both Antigravity and Gemini CLI read `GEMINI.md` from the project
root. If both platforms are installed, the second generator overwrites
the first. The content is functionally equivalent (same routing,
process, rules) — terminology may differ slightly.

## Sub-Agent Support

Gemini CLI's docs reference a subagent concept (`/docs/core/subagents/`)
but the file format and invocation details weren't documented at the
time of generator authoring. **v1 ships without native subagent
definitions** for Gemini CLI:

- `auto-review`, `auto-qa`, and `quality-locked` checkpoints still
  surface to the user
- The review runs in the main agent's context (no independent window)
- A session notice announces the degradation:
  ```
  Sage: Sub-agent reviews require an independent context window.
  Running in single-pass mode for this session — quality is reduced.
  ```

When Gemini CLI's subagent format is documented, v2 will add a
`.gemini/agents/` (or equivalent) generator step.

## What's NOT Supported in v1

- Native sub-agent definitions (single-pass fallback used instead)
- Hook system port (Gemini supports hooks; v2)
- MCP server integration via Sage's generator (users configure
  independently via `~/.gemini/settings.json`)

## Detection Heuristic

`sage init` detects Gemini CLI via the `.gemini/` directory. If only
`GEMINI.md` exists without either `.gemini/` or `.agent/`, Sage assumes
Antigravity (the longer-standing case). When `.gemini/` exists, Gemini
CLI is selected automatically.
