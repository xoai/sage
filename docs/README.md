# Sage Documentation

## Philosophy

Design decisions and rationale behind Sage's architecture.

| Document | What It Covers |
|----------|---------------|
| [design-philosophy.md](philosophy/design-philosophy.md) | Core principles: why Sage exists, how it differs from other frameworks, the advisory board model |
| [project-state-convention.md](philosophy/project-state-convention.md) | How generated files are organized in `.sage/` — naming conventions, folder structure, cross-cutting vs initiative-specific |
| [skill-philosophy.md](philosophy/skill-philosophy.md) | Why everything installable is a "skill," progressive enhancement, and compatibility with community skills |
| [why-state-lives-in-plan.md](philosophy/why-state-lives-in-plan.md) | Why plan.md checkboxes are the progress tracker, not a separate state file |

## Ecosystem

How Sage skills work as an ecosystem.

| Document | What It Covers |
|----------|---------------|
| [skill-manifest-format.md](ecosystem/skill-manifest-format.md) | Complete reference for SKILL.md frontmatter — all fields, defaults, examples |
| [skill-relationships.md](ecosystem/skill-relationships.md) | How skills relate: extends, complements, replaces. Default: peaceful coexistence |

## Key Design Choices

Decisions made during Sage's development, documented here for transparency.

### Naming: `docs/` and `work/` (not `reasoning/` and `features/`)

We chose the most universally understood terms. A new team member doing
`ls .sage/` should immediately understand the structure without reading
documentation. "docs" contains documents. "work" contains work items.
Every alternative we considered (`reasoning`, `features`, `specs`, `initiatives`)
either required explanation or was too narrow for the range of content.

Advisory board input: Torvalds ("name things by what they contain"), Ritchie
("short, lowercase, obvious"), Evans ("use the words people naturally say"),
DHH ("one-word names that a child could understand").

### Naming: `brief.md`, `spec.md`, `plan.md`

The three core files per initiative use words people already use in conversation:
"I wrote the brief," "check the spec," "look at the plan." We avoided jargon
like PRD (not everyone knows this abbreviation) and ADR (requires a glossary).

### Naming: `YYYYMMDD-slug` for work folders

Date prefixes provide chronological sort order without arbitrary numbering.
They support the real-world pattern of revisiting initiatives: `20260315-baseline`
and `20260901-baseline-v2` are clearly related but distinct. The date tells you
WHEN the work started; the slug tells you WHAT it is.

### Naming: Skill prefixes in `docs/`

Files in `docs/` use the producing skill's name as a prefix: `jtbd-product-analysis.md`,
`ux-writing-voice-and-tone.md`, `decision-auth-provider.md`. This provides natural
grouping when sorted alphabetically — all JTBD analyses cluster together, all
decisions cluster together — without requiring subfolders.

### Naming: "Decision" not "ADR"

Architecture Decision Records (ADRs) are a well-established engineering practice.
But "ADR" is jargon that requires a glossary entry. "Decision" is what everyone
calls it: "What was the decision on auth?" The file format (context → options →
choice → consequences) is identical to a traditional ADR. Only the label changed.

### Structure: Feature-specific research in `work/*/research/`

When a JTBD analysis or usability test is done specifically for one initiative,
it travels with that initiative in a `research/` subfolder. When the same kind
of analysis applies to the whole product, it goes in `docs/`. This follows
Spec-Kit's principle (one folder = one initiative = complete context) while
keeping project-level knowledge accessible at the top.

### Structure: Everything installable is a "skill"

The AI ecosystem uses "skill" as the standard term for installable agent
capabilities. Sage aligns with this convention. Internal process steps are
"capabilities" (the engine). User-installable knowledge, methodology, and
bundles are "skills." See [skill-philosophy.md](philosophy/skill-philosophy.md).

### Structure: Progressive enhancement for skill manifests

All SKILL.md frontmatter fields are optional. A community Claude Code skill
with zero Sage metadata works at Layer 0. Each field you add makes integration
smarter but nothing is required. This maximizes ecosystem compatibility.

### Platform: `.sage/` is platform-agnostic

Project state lives in `.sage/` regardless of whether the user runs Claude Code
or Antigravity. Platform-specific files (`CLAUDE.md`, `.agent/`) are generated
by platform adapters from the same Sage content. Users can switch platforms
mid-project without losing state.

### Orchestration: Two Layers (Constitution + Navigator)

Sage's orchestration uses two components with different characteristics:

**Process Constitution** (always-on, thin, ~200 words). Five rules deployed as
an always-on rule on every platform. Ensures the agent always reads project state,
uses Sage skills instead of ad-hoc approaches, and uses Sage's planning instead
of the platform's default. The constitution doesn't contain workflow logic — it
just prevents Sage from being bypassed.

**Sage Navigator** (on-demand, intelligent, ~400 lines). The judgment layer.
Activates on any substantial user request. Reads project state, detects intent
on the UNDERSTAND → ENVISION → DELIVER spectrum, assesses scope, detects
missing artifacts, and recommends the path that produces the best outcome.
Proactively suggests gap-filling (missing research, briefs, specs) while
respecting the user's right to decline.

The constitution runs at session start; the navigator runs at end of each
workflow step to recommend the next action. Together they ensure Sage is
always present (constitution) and always intelligent (navigator).

### Orchestration: "Navigator" not "Master" or "Orchestrator"

The name reflects Sage's relationship with the user. A navigator reads the
terrain, suggests the best route, warns about hazards — but the user decides
where to go. Sage advises. The user decides. No one is master than any other.

### Orchestration: Proactive gap detection

Most frameworks only do what you ask. Sage also recommends what you haven't
asked for but would improve the outcome. Calibrated to scope: small tasks get
no suggestions, medium tasks get one recommendation, large tasks get a full
discovery → design → delivery path. The user always has the right to decline.
Sage always has the obligation to suggest what's right.

### Platform: Workflows as primary interface on Antigravity

Antigravity's skill auto-activation is unreliable (confirmed by community reports
and our own testing, March 2026). Sage adapts: on Antigravity, `/sage` and
`/build` workflows are the primary interface. They contain the navigator's
intelligence (gap detection, scope assessment, checkpoints) directly inside
the workflow where Antigravity reliably executes it. Auto-activation of skills
via descriptions is kept as a best-effort bonus that improves as the platform
evolves. On Claude Code, the navigator works as designed via the hooks system.

This is not a compromise — it's platform-adaptive design. The same intelligence,
delivered through the mechanism each platform handles most reliably.

### Installation: One Script, Three Commands

The `sage` CLI is installed globally via `curl | bash`. It provides four
directory (the most common action, zero friction). `new <name>` creates a
new project. `update` regenerates platform files after upgrading Sage.

Every competitor uses package managers (npm, pip). Sage distributes as a zip
for maximum portability (no npm, no Python, works offline). The tradeoff is
that users must copy `sage/` into their project. The CLI handles this
automatically for `new` projects and clearly communicates the step for
existing projects.

### Context Loading: Three-Layer Strategy

The context window is the most precious resource in AI agent work. Most
frameworks dump everything upfront — full constitutions, skill libraries,
reference material — hoping the agent sorts it out. This wastes tokens
and overwhelms the agent.

Sage uses a deliberate three-layer strategy:

- **Layer 1: Always-on** (~200 words). Process constitution, commands table,
  interaction patterns. Small enough to never hurt, critical enough to never
  skip. Every platform inlines this.
- **Layer 2: On-demand.** Navigator, skills, workflow details, reference
  material. Referenced by path, read when the current task needs them.
  The agent reads what it needs, when it needs it.
- **Layer 3: Strategy.** The decision framework itself — when to inline,
  when to reference, token budgets, priority ordering. This lives in
  `core/capabilities/context/context-loader/` and guides all generators.

The principle: **load the minimum context needed for the current action.**
Platform generators follow this strategy when producing CLAUDE.md, GEMINI.md,
and commands. It's a deliberate architecture decision, not an accident.

### Core as Single Source of Truth

Core defines the process. Generators adapt it for each platform.

Workflows, constitution, and capabilities live in `core/` as platform-agnostic
source files. Platform generators read from core, substitute platform-specific
paths, and produce the output each platform expects. This means:

- Improving a workflow means editing ONE file in `core/workflows/`
- Adding a platform means writing ONE generator in `runtime/platforms/`
- Core never references `.agent/`, `.claude/`, GEMINI.md, or any platform

### Session Continuity via State Bridge

All Sage state persists in `.sage/` — platform-agnostic, model-agnostic,
session-agnostic. The session-bridge capability ensures the agent can
resume exactly where it left off. Progress is the project's memory,
not the agent's. Close your IDE, switch models, come back in a week —
`.sage/progress.md` tells the agent what happened and what's next.

### Proportional Process via Scope Guard

Not all tasks need full rigor. The scope-guard principle calibrates
process to task size: a CSS fix gets fixed directly, a full redesign
gets the complete research → design → build pipeline. The navigator
reads signals (task complexity, greenfield vs existing code, user
urgency language) and recommends proportionally. When the user says
"just do it," Sage accepts gracefully.

### Quality Gates: Verify Without Blocking

Quality gates run automatically at stage transitions — brief → spec,
spec → plan, plan → implementation. They're deterministic checks:
does the output match what was approved? Are tests passing? Were
checkpoints honored? Gates catch drift early without becoming
bottlenecks. The user doesn't manage them; they benefit from the
safety net.
