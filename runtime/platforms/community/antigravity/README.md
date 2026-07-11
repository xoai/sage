# Sage on Antigravity

Setup guide for using Sage with Google Antigravity.

## Quick Setup

From your project root (where `sage/` is located):

```bash
sage init
# Select option 2 (Antigravity) or 3 (Both)
```

Or run the Antigravity generator directly:

```bash
sage update
```

## What Gets Generated

```
your-project/
├── GEMINI.md                    # Always-on project rules (like CLAUDE.md)
├── .agent/
│   ├── rules/                   # Passive rules (constitution, conventions)
│   │   ├── sage-core.md        # Core Sage rules (TDD, scope, state)
│   │   └── skill-*-constitution.md  # Skill-specific rules
│   ├── skills/                  # Sage skills (auto-activated by agent)
│   │   ├── react/               # Knowledge skills
│   │   ├── nextjs/
│   │   ├── jtbd/                # Process skills
│   │   ├── prd/
│   │   ├── ux-writing/
│   │   └── ...                  # All 30 non-bundle skills
│   └── workflows/               # User-triggered with /command
│       ├── sage.md              # /sage — intelligent entry point
│       ├── fix.md               # /fix — quick bug fix
│       ├── build.md             # /build — feature development
│       ├── architect.md         # /architect — system design
│       └── status.md            # /status — check project state
├── .sage/                      # Sage project state (platform-agnostic)
│   ├── decisions.md          # Shared decision log
│   ├── docs/
│   └── work/
└── sage/                       # Sage framework source
```

## How It Works

### Rules = Process Constitution

Antigravity rules are always-on instructions. Sage deploys its process
constitution to `.agent/rules/sage-core.md` — five non-negotiable rules
that ensure the agent always reads project state, uses Sage skills, and
follows Sage's planning instead of the platform's default Planning mode.

Additional skill-specific rules deploy as `skill-*-constitution.md` files.

### Sage Navigator = Intelligent Orchestration

The `sage-navigator` skill deploys to `.agent/skills/sage-navigator/`.
It's the intelligent entry point for all substantial work. When the user
asks to build, create, redesign, analyze, or fix anything, the navigator:

1. Reads project state (what exists, what's in progress)
2. Detects intent (understand, envision, or deliver)
3. Assesses scope (lightweight, standard, or comprehensive)
4. Detects gaps (missing research, briefs, specs)
5. Recommends the best path and waits for approval

The navigator replaces the need to memorize workflows — it figures out
what skills to use and in what order based on the user's request.

### Skills = Knowledge + Process

Sage skills deploy to `.agent/skills/`. Antigravity auto-activates them
based on the skill's `description` field. The navigator orchestrates which
skills to use. Users can also trigger skills directly.

Skills include their references, templates, and examples — everything
the agent needs is in the skill folder.

### Workflows = Shortcuts

Type `/` in Antigravity for direct access to common workflows:

| Command | What Happens |
|---------|-------------|
| `/sage` | **Start here.** Reads project state, assesses intent, guides the process |
| `/fix` | Quick debug → test → fix → verify → commit |
| `/build` | Scan → elicit → specify → plan → implement → review |
| `/architect` | Deep elicitation → architecture → milestone plan → phased build |
| `/status` | Show current project state from `.sage/work/` frontmatter |

These are shortcuts. The navigator handles everything else automatically.

### Project State

All Sage state lives in `.sage/` — this is platform-agnostic. Whether you
use Claude Code or Antigravity, the project state is the same:

- `.sage/decisions.md` — shared decision log (agent + human)
- `.sage/docs/` — JTBD analyses, voice & tone guides, decision records
- `.sage/work/` — specs, plans, PRDs per feature

## Multi-Model Usage

Antigravity supports multiple models. Sage works with all of them, but
some considerations:

| Model | Best For |
|-------|---------|
| Gemini 3 Pro | Complex planning, multi-step reasoning, code generation |
| Claude Sonnet 4.6 | Nuanced writing (PRDs, UX copy), careful analysis |
| Claude Opus 4.6 | Architecture decisions, deep reasoning |
| GPT-OSS | General coding tasks |

The Sage workflows and skills are model-agnostic — they provide structured
process regardless of which model executes them.

## Switching Between Platforms

Sage supports both Claude Code and Antigravity from the same project:

```bash
# Generate for both platforms
sage init
# Choose option 3 (Both)
```

This creates CLAUDE.md (for Claude Code) and .agent/ (for Antigravity)
side by side. The `.sage/` project state is shared — you can switch
between platforms mid-project.

## Updating

After modifying Sage skills or configuration:

```bash
sage update
```

This regenerates `.agent/` from the current Sage source without
touching `.sage/` project state.

## Platform Notes

### Skill Auto-Activation

Antigravity's skill auto-activation based on semantic description matching is
a best-effort feature. The platform may not always detect and activate Sage
skills automatically. This is a known Antigravity limitation affecting all
skill-based frameworks (not specific to Sage).

**Recommended approach:** Use `/sage` or `/build` workflows as your primary
entry point. These reliably trigger Sage's process because you invoke them
explicitly.

**Auto-activation works when:** You describe a task that closely matches a
skill's description (e.g., "audit this design" may activate ux-audit). But
it's not guaranteed, especially in Planning or Fast conversation modes.

### Planning Mode

Antigravity's built-in Planning mode may override Sage's planning process.
The GEMINI.md constitution instructs the agent to use Sage's planning instead,
but enforcement depends on the model following instructions reliably.

**Recommended approach:** Use `/build` which includes Sage's full planning
pipeline (brief → spec → plan → implement with checkpoints).

### Model Selection

Sage works with any model Antigravity supports. For best results with
skill-following and instruction adherence, Claude Sonnet 4.6 or Claude Opus
4.6 tend to follow Sage's structured process more reliably than Gemini
models in current testing.
