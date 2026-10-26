# Sage on Claude Code

Setup guide for using Sage with Claude Code.

## Quick Setup

```bash
sage init
# Select Claude Code when prompted (or auto-detected)
```

Or run the Claude Code generator directly:

```bash
bash sage/runtime/platforms/claude-code/setup/generate-claude-code.sh .
```

## What Gets Generated

```
your-project/
├── CLAUDE.md                    # Always-on project instructions
├── .claude/
│   └── commands/                # Slash commands
│       ├── sage.md              # /sage — intelligent entry point
│       ├── build.md             # /build — feature development
│       ├── fix.md               # /fix — debug and patch
│       ├── architect.md         # /architect — system design
│       └── status.md            # /status — project state
├── .sage/                       # Project state (platform-agnostic)
│   ├── decisions.md          # Shared decision log
│   ├── docs/
│   └── work/
└── sage/                        # Framework source
```

## How It Works

### CLAUDE.md = Process Constitution + Navigator

CLAUDE.md is always-on — Claude Code reads it at the start of every
session. It contains:

- The five non-negotiable process rules (state first, skills before
  assumptions, use Sage's planning, checkpoints are sacred, save state)
- Instructions to activate the sage-navigator for substantial tasks
- The build loop with checkpoint markers
- Available commands reference
- Interaction patterns (numbered options, `[A]/[R]`, `[C]`)

### Commands = Slash Shortcuts

Type `/` in Claude Code to see available commands:

| Command | What Happens |
|---------|-------------|
| `/sage` | **Start here.** Navigator reads state, assesses intent, guides process |
| `/build` | Feature development with scope assessment and checkpoints |
| `/fix` | Debug → test → fix → verify |
| `/architect` | Deep elicitation → architecture → milestone plan |
| `/status` | Show current project state |

Commands are markdown files in `.claude/commands/`. They provide the
prompt context for each workflow.

### Skills = On-Demand Knowledge

Sage skills live in `sage/skills/`. When the navigator or a
command references a skill, the agent reads its SKILL.md and follows
the methodology. Skills aren't auto-loaded — they're read on demand
when referenced. This keeps context clean.

### Project State

All Sage state lives in `.sage/` — platform-agnostic:

- `.sage/decisions.md` — shared decision log (agent + human)
- `.sage/docs/` — analyses, voice & tone guides, decision records
- `.sage/work/` — specs, plans, briefs per initiative

## Switching Between Platforms

Sage supports both Claude Code and Antigravity from the same project:

```bash
sage init
# Choose "Both" when prompted
```

This creates CLAUDE.md + `.claude/` (for Claude Code) and GEMINI.md +
`.agent/` (for Antigravity) side by side. The `.sage/` state is shared.

## Updating

```bash
sage update
```

Regenerates CLAUDE.md and `.claude/commands/` without touching `.sage/`.

### Your own files are kept

- **CLAUDE.md** — Sage's instructions live in one block between
  `<!-- BEGIN SAGE … -->` and `<!-- END SAGE -->`; `sage update` rewrites only
  that block. Anything outside it is yours and is kept — a CLAUDE.md you had
  before `sage init` stays line for line, with the block added at the end. A
  CLAUDE.md written by an older Sage (no markers) is backed up once to
  `.sage/backups/` when it moves into the block. If the markers get damaged,
  the file is left alone and the update says how to fix it. A symlinked
  CLAUDE.md stays a symlink.
- **`.claude/settings.local.json`** and **`.claude/settings.json`** — merged,
  never replaced: Sage adds or refreshes its own hook entries and leaves your
  permissions and other settings alone. A file that is not valid JSON is left
  untouched (the update reports it).
- **`.claude/skills/`** — one loader per Sage skill. Skills written for another
  platform (the Hermes port) are not deployed here, and no skill is named
  `sage`, so `/sage` always reaches the command. Your own skills in this folder
  are never touched.
