<h1 align="center">Sage</h1>
<p align="center">
  <img src="sage-logo-eagle.svg" alt="Sage - An intelligent skills framework for AI agents." width="150" />
</p>
<p align="center"><strong>An intelligent skills framework for AI agents.</strong></p>

<p align="center">Think clearly. Work thoroughly. Deliver excellence.</p>

Sage is a skills framework that makes AI agents think before they act,
stay focused under complexity, and deliver outcomes you can trust.
Built for product and engineering teams, open to any domain.

- **Think first, build second** — prevents the most expensive mistake: solving the wrong problem
- **Focus over noise** — loads only what the task needs, producing sharper reasoning
- **Reliable by design** — quality gates catch drift at every stage, automatically
- **Gets smarter over time** — persistent memory turns every session into accumulated wisdom
- **Grows with its ecosystem** — built-in skills for product, design, and engineering, extensible with a growing community catalog, easy to contribute

## Why Sage

### The Navigator

Most AI frameworks skip from request to implementation. Sage's navigator
thinks first — mapping every request to an intent spectrum (UNDERSTAND →
ENVISION → DELIVER) and detecting what's missing before work begins.
Building without research? It tells you what 15 minutes of discovery
would prevent, then lets you decide. Gap detection, not gatekeeping.
The belief: an AI agent's job isn't to execute fast — it's to arrive at
the right outcome.

### Hybrid Loading

Most frameworks dump all instructions into the context window and hope
for the best. Sage loads in two layers: the **eager layer** (process
rules, workflow gates, engineering principles — ~200 lines, always in
context) enforces what must never be skipped. The **lazy layer**
(capabilities like TDD discipline, systematic debugging, build-loop
orchestration — loaded when the workflow step needs them) adds depth
without bloating context. A focused agent with the right 500 tokens
outperforms a distracted agent with 50,000 tokens of everything.

### The Quality Gates

AI agents drift silently — skipping steps, hallucinating imports,
claiming "tests pass" without running them. Sage runs **deterministic
verification scripts** that don't rely on the agent's self-assessment:
`sage-verify.sh` runs your test suite, `sage-hallucination-check.sh`
verifies imports exist, `sage-spec-check.sh` confirms deliverables
match the plan. Scripts run first; agent review runs second. The script
says tests fail → gate fails, regardless of what the agent thinks.
Five gates sequence after every implementation: spec compliance,
constitution compliance, code quality, hallucination check, verification.

<p align="center">
  <img src="sage_routing.svg" alt="Sage Enforcement Model." width="600" />
</p>

## Get Started

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash
```

Works on macOS and Linux. On Windows, use
[Git Bash](https://git-scm.com/downloads/win) or WSL:

```bash
# Windows — open Git Bash, then:
curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash
```

All `sage` commands run in bash. On Windows, use Git Bash or WSL
for both installation and daily use.

### Create a Project

```bash
sage new my-app
```

### Or Add to an Existing Project

```bash
cd your-project
sage init                        # interactive — asks for platform and preset
sage init --preset startup       # non-interactive with preset
sage init --preset enterprise    # auth, audit trails, postmortems
```

Available presets: `base` (default), `startup`, `enterprise`, `opensource`.
Presets add engineering principles on top of the universal base (TDD, no
secrets, explicit deps). Choose during init or configure later in
`.sage/constitution.md`.

### Upgrade an Existing Project

```bash
sage update    # regenerates platform files, preserves .sage/ state
sage upgrade   # pulls latest Sage framework from GitHub
```

`sage update` regenerates CLAUDE.md, commands, workflows, and gate
scripts while preserving your project state (progress, journal, work
artifacts). It also migrates stale patterns from previous versions.

That's it. Open your project in your IDE, type `/sage`, and describe
what you want to build. Sage reads your project, assesses the task,
and guides you through the right process.

### CLI Commands

Run in your terminal:

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

Sage: Fresh project, no work in progress.

This looks like a comprehensive task — redesign involves understanding
what's not working before designing what's next.

[1] Start with UX audit of current homepage, then redesign
[2] Skip research, go straight to redesign
[3] Something else — describe what you have in mind

> 1

Sage → build workflow. Starting with UX audit. Reading ux-audit skill...

[Sage runs the audit, saves findings to .sage/docs/ux-audit-homepage.md]

Sage: UX audit complete. Key findings:
- Navigation is clear but CTA is buried below the fold
- Mobile load time is 4.2s (target: <2s)
- No social proof visible in first viewport

[C] Continue with brief  |  Or tell me what you'd like to do
```

Every step: structured options with `[1] [2] [3]`, saved artifacts,
recommended next step. You stay in control — Sage stays intelligent.

## How Sage Works

### Slash Commands

Use inside your IDE (Claude Code, Antigravity):

| Command | What It Does |
|---------|-------------|
| `/sage` | **Start here.** Routes via keywords → classify → confirm |
| `/build` | Feature: spec → plan → build-loop → quality gates |
| `/fix` | Diagnose → scope → fix → verify (escalates large fixes) |
| `/architect` | Elicit → design → milestone plan → phased build |
| `/research` | Interview → JTBD → opportunity map |
| `/design` | Brief → spec → copy (reads research context) |
| `/analyze` | UX audit → evaluation → findings |
| `/status` | Compute project state from artifacts |
| `/review` | Independent evaluation via sub-agent |
| `/learn` | Codebase scan → memory storage |
| `/reflect` | Review cycle → extract learnings → seed next cycle |

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

### Enforcement Model

<p align="center">
  <img src="sage_enforcement.svg" alt="Sage Enforcement Model." width="600" />
</p>

Sage uses triple reinforcement to ensure agents follow the process:

**1. Eager layer (CLAUDE.md / GEMINI.md)** — always in context. Contains
the 7 process rules, workflow gates ("DO NOT implement before spec
approved"), engineering principles, and a self-check loop. This is the
safety net — even if the agent loads nothing else, the gates prevent
the worst violations.

**2. Command preambles** — at the top of every slash command file. Each
workflow gets specific enforcement rules that the agent reads first.

**3. Capabilities** — loaded at the right workflow step. `build-loop`
orchestrates task-by-task execution with quality gates. `tdd` enforces
test-first discipline. `systematic-debug` structures root cause
investigation. These add depth when loaded; the eager layer provides
enforcement even when they're not.

This matters because agents skip instructions. A single layer of
enforcement fails when the agent is eager to help. Three independent
layers mean the agent has to bypass all three to skip the spec.

### Constitution Stack

Sage uses a three-tier constitution model:

**Base** (5 principles, all projects) — TDD, no silent failures, no
secrets in code, explicit dependencies, reversible changes.

**Preset** (chosen during init) — startup (ship small, monolith first),
enterprise (auth everywhere, audit trails, postmortems), or opensource
(docs mirror code, semver contract).

**Project additions** — your own principles in `.sage/constitution.md`.

The generator merges all three tiers into the always-on instructions.
Lower tiers add constraints but cannot remove inherited ones.

### The Pipeline: UNDERSTAND → ENVISION → DELIVER → REFLECT

<p align="center">
  <img src="sage_workflows_v108.svg" alt="Sage Workflows." width="600" />
</p>

Sage organizes work into four phases. Each phase has dedicated
workflows that chain skills automatically:

```
UNDERSTAND              ENVISION               DELIVER              REFLECT
/research  /analyze     /design  /architect    /build  /fix         /reflect
/learn                                         /review
```

`/research` chains user-interview → JTBD → opportunity-map.
`/design` chains ux-brief → ux-specify → ux-writing and reads
research findings automatically. `/build` chains spec → plan →
build-loop → quality-gates and reads design specs. `/reflect`
reviews the full cycle, extracts WHEN/CHECK/BECAUSE learnings,
and seeds the next cycle with concrete recommendations.

You can enter at any phase. But the further right you start, the
more you're building on assumptions. The addition of Reflect as
a distinct phase is what separates teams that improve from teams
that just ship.

Routing is deterministic: keywords match to workflows before any
LLM judgment. When keywords don't match, a focused sub-agent
classifier picks the right phase. Every routing decision is
confirmed with the user before proceeding.

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
- **[memory](skills/memory/)** — persistent knowledge, typed ontology, and self-learning from mistakes
- **[skill-builder](skills/skill-builder/)** — tools for building new Sage skills

### Ecosystem

Community skills from dozens of registries, installable with one command:

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
├── constitution.md          # Preset selection + project principles
├── docs/                    # Project knowledge (analyses, decisions, guides)
├── work/                    # Per-initiative deliverables
│   └── YYYYMMDD-slug/       # brief.md, spec.md, plan.md
└── gates/
    ├── gate-modes.yaml      # Which gates run per workflow mode
    └── scripts/             # Deterministic verification scripts
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
