# Platforms

Sage is platform-agnostic at its core. Platform adapters translate Sage's
capabilities into the format each IDE/agent platform expects.

## Supported Platforms

| Platform | Tier | Status | How Sage Integrates |
|----------|:----:|--------|---------------------|
| [Claude Code](claude-code/) | 1 | **Stable** | `CLAUDE.md` + skills in `.claude/` |
| [Antigravity](antigravity/) | 1 | **New** | `GEMINI.md` + `.agent/rules/` + `.agent/skills/` + `.agent/workflows/` |
| [Hermes Agent](hermes/) | 1 | **New** | `AGENTS.md` + Hermes plugin, skills, hooks, and toolset config |
| [Generic](generic/) | 2 | **Stable** | Markdown-based instructions for any agent |

## Platform Architecture

```
Sage Core (platform-agnostic)
├── capabilities/      # Process engine
├── skills/            # Knowledge + methodology
├── constitution/      # Project principles
└── workflows/         # FIX / BUILD / ARCHITECT

        ↓ Platform Adapter ↓

Claude Code                     Antigravity                     Hermes
├── CLAUDE.md                   ├── GEMINI.md
└── (skills inline or .sage/)  ├── .agent/rules/                ├── AGENTS.md
                                ├── .agent/skills/
                                └── .agent/workflows/           └── $HERMES_HOME/plugins/sage/
```

All platform adapters share the same `.sage/` project state directory.

## Mapping

| Sage Concept | Claude Code | Antigravity | Hermes |
|--------------|------------|-------------|--------|
| Constitution (always-on) | Inline in CLAUDE.md | `.agent/rules/*.md` | AGENTS.md + profile SOUL.md |
| Skills (on-demand) | Inline or `.sage/skills/` | `.agent/skills/` with SKILL.md | `$HERMES_HOME/plugins/sage/skills` + `$HERMES_HOME/skills` |
| Mode workflows | User says "fix/build/architect" | `/fix`, `/build`, `/architect` commands | Plugin slash commands |
| Project state | `.sage/` | `.sage/` (shared) | `.sage/` (shared) |
