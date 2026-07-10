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
│   ├── commands/                # Slash commands
│       ├── sage.md              # /sage — intelligent entry point
│       ├── build.md             # /build — feature development
│       ├── fix.md               # /fix — debug and patch
│       ├── architect.md         # /architect — system design
│       └── status.md            # /status — project state
│   └── hooks/                   # Session, advisory router, strict gate
├── .sage/                       # Project state (platform-agnostic)
│   ├── decisions.md          # Shared decision log
│   ├── docs/
│   ├── runtime/              # Catalog, active pointer, run event/state files
│   └── work/
└── sage/                        # Framework source
```

## How It Works

### CLAUDE.md = Optional Sage Runtime Contract

CLAUDE.md is always-on — Claude Code reads it at the start of every
session. It contains:

- Explicit-command, advisory-routing, and active-run authority rules
- Neutral skill composition and scoped strict-mode behavior
- Instructions to activate the navigator only for `/sage`, accepted advice,
  guidance requests, or an active run
- Deterministic recall plus canonical self-learning/reflection handoff
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

### Routing and Strict Mode

Sage routing is advisory by default. A natural-language match such as
"map this repository" may add a short suggestion, but it never starts a run or
arms a mutation gate. Only an installed, catalog-validated command such as
`/map` or `/build` is authoritative. While a run is active, natural-language
inference is suppressed; use another explicit command to switch or `/cancel`
to cancel.

Strict mode is opt-in per run:

```text
/build --strict
```

Even then, read-only inspection remains allowed. The PreToolUse hook may deny
only a requirement declared for the current scope and stage: a missing
artifact, missing approval, failed required verification, or a write outside a
configured lane. It does not guess which skill should have loaded. A lightweight
scope does not inherit artifacts that its policy explicitly skips.

If the runtime, route catalog, state, or policy cannot be loaded, hooks fail
open and emit no routing authority. Local git-first, shell-edit, and lane
policies remain independent settings; installing Sage does not turn them on.

Runtime facts are stored at:

```text
.sage/runtime/route-catalog.json
.sage/runtime/active-run.json
.sage/runtime/runs/<run-id>/events.jsonl
.sage/runtime/runs/<run-id>/state.json
```

`events.jsonl` is the source of truth. Recover a missing or stale projection
with:

```bash
python sage/runtime/tools/sage_runtime_cli.py state reconcile \
  --project . --run-id <run-id>
```

The generator merges SessionStart, UserPromptSubmit, and PreToolUse entries
into `.claude/settings.local.json` without replacing unrelated hooks. Malformed
settings are backed up and rejected before generation changes the project.

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
