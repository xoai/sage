# Sage

**An intelligent skills framework for AI agents.**

Think clearly. Work thoroughly. Deliver excellence.

Sage equips AI agents with skills that truly understand what's needed,
choose the right approach, and produce outstanding results — from user
research to UX design to shipping code to crafting strategy and beyond.
Any domain. Any task that demands excellence. Sage grows as far as your
ambition takes it.

> **Status: v1.0 Public Preview** — Architecture, skills, and workflows are
> functional. Both Antigravity and Claude Code are fully supported. We're
> releasing to gather feedback from early adopters.

## Get Started

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash
```

Works on macOS, Linux, and Windows (via WSL or Git Bash).

### Create a Project

```bash
sage new my-app
```

### Or Add to an Existing Project

```bash
cd your-project
sage init
```

That's it. Open your project in your IDE, type `/sage`, and describe
what you want to build. Sage reads your project, assesses the task,
and guides you through the right process.

### Commands

| Command | What It Does |
|---------|-------------|
| `sage new <name>` | Create a new project with Sage |
| `sage init` | Add Sage to the current directory |
| `sage update` | Regenerate platform files after changes |
| `sage upgrade` | Update Sage to the latest version |
| `sage help` | Show available commands |

## What It Looks Like

Type `/sage` and describe what you want to do. Sage reads your project,
assesses the task, and guides you:

```
> /sage
> Redesign our homepage for better conversion

Sage navigator: Fresh project, no work in progress.

This looks like a comprehensive task — redesign involves understanding
what's not working before designing what's next.

I recommend starting with research before redesigning — it typically
surfaces requirements not visible from the initial request.

1) Start with UX audit of current homepage (~15 min), then redesign
2) Skip research, go straight to redesign
3) Something else — describe what you have in mind

> 1

Starting UX audit. Reading ux-audit skill...

[Sage runs the audit, saves findings to .sage/docs/ux-audit-homepage.md]

UX audit complete. Key findings:
- Navigation is clear but CTA is buried below the fold
- Mobile load time is 4.2s (target: <2s)
- No social proof visible in first viewport

Recommended next: Create a brief defining redesign goals (~10 min)

[C] Continue with brief  |  Or tell me what you'd like to do
```

Every step: clear options, saved artifacts, recommended next step. You
stay in control — Sage stays intelligent.

## Why Sage

Most AI agent frameworks focus on one thing: writing code faster. Sage
is built on a different belief — that the biggest waste isn't slow coding,
it's building the wrong thing. Here's what that means in practice:

**Works across the full spectrum, not just code.** Sage ships 33 skills
spanning discovery (JTBD analysis, user interviews, opportunity mapping),
design (UX audit, evaluation, voice & tone, heuristic review), and
engineering (specs, plans, implementation, review). Other frameworks
start at "plan the code." Sage starts at "understand the problem."

**Detects what's missing before you start.** The navigator doesn't just
route you to a skill — it checks whether the necessary understanding,
design, and planning have been done. Building without research? Sage
tells you what 15 minutes of discovery would prevent and lets you
decide. This is gap detection, not gatekeeping.

**Understands intent, not just commands.** The UNDERSTAND → ENVISION →
DELIVER spectrum maps every request to where it falls in the thinking
process. When multiple intents are present ("redesign this page"), Sage
starts from understanding and works toward delivery — preventing the
most expensive mistake in product work.

**Clear interactions at every step.** Numbered options at decision
points. `[A] Approve` / `[R] Revise` at checkpoints. `[C] Continue`
at transitions. You always know what to do next. Free-form input
always works too.

**Session continuity that actually works.** `.sage/` persists every
decision, artifact, and progress update. Close your IDE, come back
tomorrow, type `/sage` — Sage picks up exactly where you left off.
No lost context. No re-explaining.

**Domain-agnostic by design.** The navigator's principles work for any
domain — not just software. PM, UX, content strategy, data analysis.
Install the skills you need, and the same intelligent process applies.

## How Sage Works

### The Navigator

Sage's intelligence lives in the **sage-navigator** — a process navigator
that activates on every substantial task. It does three things:

1. **Reads the room.** Checks project state, maps your request to
   an intent (understand → envision → deliver), and assesses scope.

2. **Detects gaps.** Finds what's missing — research, specs, plans —
   and recommends filling them when the value justifies the time.

3. **Guides the process.** Proposes a path with clear options, runs
   the appropriate skills, and bridges each step to the next.

The navigator is not a gatekeeper. It suggests the best route. You
decide where to go.

### The Spectrum

Every request maps to an intent spectrum:

```
UNDERSTAND              ENVISION               DELIVER
(why, who, what)        (how it should work)   (make it real)

Research & Discovery    Design & Definition     Planning & Execution
```

When multiple intents are present, Sage starts from the left and works
rightward. Understanding before envisioning. Envisioning before delivering.
This prevents the most common mistake: building the wrong thing.

### Workflows

Type `/` in your IDE for direct access:

| Command | What It Does |
|---------|-------------|
| `/sage` | **Start here.** Sage reads your project and guides the process |
| `/build` | Feature development: spec → plan → implement |
| `/fix` | Quick debug → test → fix → verify |
| `/architect` | System design: deep elicitation → architecture → phased build |
| `/status` | Check current project state |

### Interaction Patterns

Sage communicates clearly at every step:

**Decision points** — numbered options when you need to choose a direction.
**Checkpoints** — `[A] Approve` / `[R] Revise` shortcuts on deliverables.
**Continuations** — `[C] Continue` with a recommended next step.

Free-form input always works. These patterns guide, they don't constrain.

## Skills

Everything installable is a **skill**. Skills have types:

| Type | What It Does | Examples |
|------|-------------|---------|
| `knowledge` | Technology-specific patterns and judgment | react, nextjs, web |
| `process` | Methodology with steps and references | jtbd, prd, ux-writing |
| `composite` | Composes skills for a full stack | stack-nextjs-supabase |
| `bundle` | Metapackage that installs related skills | product-management, ux-design |

### Official Bundles

- **[@sage/product-management](skills/@sage/product-management/)** — JTBD → opportunity map → user interview → brief
- **[@sage/ux-design](skills/@sage/ux-design/)** — audit → evaluate → brief → specify → writing
- **[@sage/skill-builder](skills/@sage/skill-builder/)** — tools for building new Sage skills

### Compatibility

Any community Claude Code skill works in Sage. Drop a folder with a `SKILL.md`
into `skills/@custom/` and it works. Add Sage frontmatter for smarter integration.

## How Sage Is Built

```
sage/
├── core/                    # The engine (platform-agnostic)
│   ├── capabilities/        #   elicitation, planning, execution,
│   │                        #   review, debugging, orchestration,
│   │                        #   context management
│   ├── workflows/           #   canonical process definitions
│   └── constitution/        #   non-negotiable process rules
├── skills/@sage/            # 33 official skills
├── skills/@community/       # Community skills
├── skills/@custom/          # Your own skills
├── runtime/platforms/       # Antigravity + Claude Code generators
├── develop/                 # For contributors (contracts, validators)
└── docs/                    # Philosophy and design decisions
```

### Design Principles

**Lean context, sharp focus.** The context window is the most precious
resource in AI agent work. Sage uses a three-layer loading strategy:
the process constitution is always-on (~200 words), the navigator and
skills are loaded on-demand when the current task needs them, and skill
reference material is never pre-loaded. This keeps the agent focused
instead of drowning in instructions. Platform generators follow this
strategy — what gets inlined vs referenced is a deliberate decision,
not an accident. See [context-loader](core/capabilities/context/context-loader/)
for the full strategy.

**Session continuity.** Every decision, artifact, and progress update
persists in `.sage/`. The session-bridge capability ensures the agent
can resume exactly where it left off — even after the IDE closes, the
model changes, or days pass between sessions. State is the project's
memory, not the agent's.

**Proportional process.** Sage calibrates rigor to scope. A CSS fix
gets fixed — no brief, no spec, no ceremony. A full product redesign
gets the complete pipeline: research → design → brief → spec → plan →
phased build. The navigator reads signals (task size, greenfield vs
existing code, user urgency) and recommends accordingly. When the user
says "just do it," Sage accepts gracefully and proceeds.

**Quality without friction.** Quality gates verify work at each stage
without becoming bottlenecks. They're deterministic checks (does the
implementation match the spec? are tests passing? were checkpoints
honored?) that catch drift early. Gates run automatically at stage
transitions — the user doesn't manage them, they just benefit from
the safety net.

See [docs/philosophy/](docs/philosophy/) for the full design rationale.

## Project State

When Sage runs in your project, it manages state in `.sage/`:

```
.sage/
├── progress.md              # Session continuity — where you left off
├── journal.md               # Artifact index + change log
├── docs/                    # Project knowledge (analyses, decisions, guides)
└── work/                    # Per-initiative deliverables
    └── YYYYMMDD-slug/       # brief.md, spec.md, plan.md
```

## Platforms

Sage is platform-agnostic. It works wherever AI agents work.

| Platform | How Sage Integrates | Status |
|----------|---------------------|--------|
| [Antigravity](runtime/platforms/antigravity/) | GEMINI.md + `.agent/` with rules, skills, workflows | Full |
| [Claude Code](runtime/platforms/claude-code/) | CLAUDE.md + `.claude/commands/` with slash commands | Full |

Both share the same `.sage/` project state. Switch platforms mid-project.

## Why sage/ Lives in Your Project

Sage copies its framework source into each project. This is intentional:

- **Self-contained.** No external dependencies. Works offline.
- **Version-locked.** Your project uses the exact version you installed.
  No surprise updates. Upgrade when you're ready.
- **Inspectable.** Read any skill, workflow, or capability. No magic.
  If something isn't working, you can see exactly what it's doing.
- **Portable.** Clone the repo and everything is there. No global
  installs, no PATH configuration, no package managers.

## License

MIT
