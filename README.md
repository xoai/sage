# Sage

**An intelligent skills framework for AI agents.**

Think clearly. Work thoroughly. Deliver excellence.

Sage equips AI agents with skills that truly understand what's needed,
choose the right approach, and produce outstanding results — from user
research to UX design to shipping code to crafting strategy and beyond.
Any domain. Any task that demands excellence. Sage grows as far as your
ambition takes it.

- **Understands before building** — the navigator detects missing research, specs, or plans before you waste time building the wrong thing
- **Focuses the agent, not floods it** — three-layer context loading keeps the AI sharp instead of drowning in instructions
- **Catches drift automatically** — quality gates verify work at every stage transition without slowing you down
- **Grows sharper as you work** — three layers of persistent intelligence learn your codebase, avoid past mistakes, and track relationships automatically
- **36 built-in skills + 2,100+ community skills** — install what you need, contribute what you build

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
| `sage new <n>` | Create a new project with Sage |
| `sage init` | Add Sage to the current directory |
| `sage update` | Regenerate platform files after changes |
| `sage upgrade` | Update Sage to the latest version |
| `sage learn [path]` | Learn a codebase or module |
| `sage find <query>` | Search community skill catalog |
| `sage add <registry> <skill>` | Install a community skill |
| `sage remove <skill>` | Remove a skill from project |
| `sage skills` | List installed skills |

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

### The Navigator — Intelligence That Prevents Waste

Most AI agent frameworks go straight from request to code. Sage's
navigator thinks first.

Every request maps to an intent spectrum — UNDERSTAND → ENVISION →
DELIVER. When multiple intents are present ("redesign this page"),
the navigator starts from the left: understand the problem before
designing the solution, design the solution before building it. This
prevents the most expensive mistake in product work: building the
wrong thing.

The navigator also detects gaps. Building without research? It tells
you what 15 minutes of discovery would prevent — then lets you decide.
This is gap detection, not gatekeeping. The navigator suggests the best
route. You decide where to go.

### The Context Loader — Focus, Not Overload

The context window is the scarcest resource in AI agent work. Most
frameworks dump everything into it — all rules, all skills, all
instructions — and the agent loses focus in the noise.

Sage uses a three-layer loading strategy. The process constitution is
always-on (~200 words) — just enough to ground every interaction. The
navigator and skills load on-demand when the current task needs them.
Reference material is never pre-loaded — it's read only when actively
used. What you DON'T load matters as much as what you do.

This isn't just efficient — it changes how the agent thinks. A focused
agent with the right 500 tokens of context outperforms a distracted
agent with 50,000 tokens of everything.

### Quality Gates — Reliability Without Friction

AI agents silently drift from the plan. They skip steps, hallucinate
requirements, and produce output that looks right but isn't. Most
frameworks have no answer for this.

Sage runs quality gates at every stage transition. Deterministic checks:
does the implementation match the spec? Are tests passing? Were
checkpoints honored? Gates catch drift early — before it compounds into
wasted work. They run automatically. The user doesn't manage them, just
benefits from the safety net.

The principle: quality should be verified, not hoped for. And
verification should be invisible until it catches something.

### Three Layers of Persistent Intelligence

AI agents forget everything between sessions. Every time you open
your editor, your agent starts from scratch — re-reading files,
re-discovering patterns, re-learning your codebase's quirks.

Sage solves this with three complementary skills on a single
lightweight backend ([sage-memory](https://github.com/xoai/sage-memory)
— local SQLite, 91% recall, sub-3ms search):

- **Memory** — prose knowledge. Architecture decisions, conventions,
  domain insights, research findings. The agent remembers what it
  learned about your codebase.
- **Self-learning** — mistakes and prevention rules. When the agent
  gets corrected or discovers a gotcha, it stores a forward-looking
  rule so the same mistake never happens twice.
- **Ontology** — structured relationships. Typed entities (tasks,
  people, projects) and relations (blocks, depends on, assigned to)
  form a knowledge graph the agent can query and traverse.

Each works standalone. Together they compound: the agent understands
your codebase (memory), avoids past mistakes (self-learning), and
tracks structured relationships between things (ontology). The more
you use Sage, the sharper it gets — not because you configured
anything, but because the skills capture knowledge automatically
as you work.

## How Sage Works

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

### Session Continuity

Close your IDE, come back tomorrow, type `/sage` — Sage picks up exactly
where you left off. Every decision, artifact, and progress update persists
in `.sage/`. With sage-memory configured, the agent also retains what it
learned about your codebase, architecture decisions, and conventions
across sessions.

## Skills

### Philosophy

Skills are Sage's knowledge architecture — a principled way to put LLMs
in the best position to do excellent work.

Every skill uses **progressive disclosure**: a short description triggers
activation, SKILL.md provides the full process, and reference files offer
depth when needed. This mirrors how experts work — you don't recite the
entire textbook before solving a problem. You know what you know, and you
reach for references when the situation demands it.

Skills are designed to **maximize LLM capabilities**. Clear structure
(frontmatter, process steps, quality criteria) gives the agent
unambiguous guidance. Domain vocabulary in the right places improves
reasoning. Reference material separated from instructions keeps the
agent focused on the task, not on parsing a wall of text.

### Relationships

Skills relate to each other in three ways:

- **Complement** (default) — cover different concerns for the same area.
  `react` and `react-testing` work side by side without conflict.
- **Extend** — add stricter or modified patterns on top of a base skill.
  A community `react-strict` extends `react` with tighter rules.
- **Replace** — a complete alternative. Deactivates the other skill.

The default is peaceful coexistence. The ecosystem grows without
conflicts — adding a community skill doesn't break what's already
working.

### Built-in Bundles

- **[product-management](skills/product-management/)** — JTBD → opportunity map → user interview → brief
- **[ux-design](skills/ux-design/)** — audit → evaluate → brief → specify → writing
- **[skill-builder](skills/skill-builder/)** — tools for building new Sage skills
- **[memory](skills/memory/)** — persistent knowledge across sessions via sage-memory

### Ecosystem

2,100+ community skills from 68 registries, installable with one command:

```bash
sage find vue                    # search the catalog
sage add antfu/skills vue        # install
```

Contributing is deliberately simple. Drop a folder with a `SKILL.md`
into `sage/skills/` and it works. Add Sage frontmatter (type, tags,
relationships) for smarter integration. The bar is low by design — the
framework makes simple skills useful and rewards deeper investment.

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
