# Platforms

Sage is platform-agnostic at its core. Platform adapters translate Sage's
capabilities into the format each IDE/agent platform expects.

## Supported Platforms

| Platform | Tier | Status | How Sage Integrates |
|----------|:----:|--------|---------------------|
| [Claude Code](claude-code/) | 1 | **Stable** | `CLAUDE.md` + skills in `.claude/` |
| [Antigravity](antigravity/) | 1 | **New** | `GEMINI.md` + `.agent/rules/` + `.agent/skills/` + `.agent/workflows/` |
| [Generic](generic/) | 2 | **Stable** | Markdown-based instructions for any agent |

## Platform Architecture

```
Sage Core (platform-agnostic)
├── capabilities/      # Process engine
├── skills/            # Knowledge + methodology
├── constitution/      # Project principles
└── workflows/         # FIX / BUILD / ARCHITECT

        ↓ Platform Adapter ↓

Claude Code                     Antigravity
├── CLAUDE.md                   ├── GEMINI.md
└── (skills inline or .sage/)  ├── .agent/rules/
                                ├── .agent/skills/
                                └── .agent/workflows/
```

Both platforms share the same `.sage/` project state directory.

## Mapping

| Sage Concept | Claude Code | Antigravity |
|--------------|------------|-------------|
| Constitution (always-on) | Inline in CLAUDE.md | `.agent/rules/*.md` |
| Skills (on-demand) | Inline or `.sage/skills/` | `.agent/skills/` with SKILL.md |
| Mode workflows | User says "fix/build/architect" | `/fix`, `/build`, `/architect` commands |
| Project state | `.sage/` | `.sage/` (shared) |
