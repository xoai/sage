# Changelog

All notable changes to Sage will be documented in this file.

## [1.0.2] — Memory & Persistent Knowledge

### Memory Skill (new built-in skill)
- **Three-layer memory architecture** — Layer 1: automatic recall
  (search memory at session start), Layer 2: automatic remember
  (store findings during any workflow), Layer 3: deliberate learning
  (user-triggered codebase scan via `sage learn`).
- **Quality-first design** — skill teaches the agent WHEN and WHY to
  use memory, not just how. Principles: specific titles with domain
  vocabulary, one insight per memory, store rationale not just facts,
  search before store to avoid duplicates.
- **Knowledge reports** — `sage learn` produces two outputs: focused
  memory entries (agent-searchable, persistent) and a human-readable
  knowledge report saved to `.sage/docs/memory-{name}.md` with insights,
  diagrams, and recommendations.
- **Reference docs** — good vs bad memory examples with explanations
  (`memory-patterns.md`), knowledge report guide with complete examples
  for code modules and UX systems (`knowledge-report.md`).

### `sage learn` Command
- **`sage learn`** — broad scan of whole project. Agent reads structure,
  config, architecture, identifies patterns and conventions, stores
  10-20 focused memories, generates knowledge report.
- **`sage learn <path>`** — deep dive into a specific module, service,
  or feature. Traces dependencies, analyzes data flow, assesses quality,
  stores 5-10 memories with diagrams.

### Navigator Integration
- **Memory in Read the Room** — navigator searches memory for relevant
  context before assessing the user's request. Reports what it found
  and how it informs the approach.
- **Memory during execution** — navigator stores key findings after
  completing significant work. Architecture decisions, conventions,
  debugging insights persist across sessions.
- **Graceful degradation** — if sage-memory MCP server is not configured,
  Sage works normally without cross-session persistence.

### Ontology Skill (new built-in skill)
- **Typed knowledge graph** on sage-memory. Entities (Task, Person,
  Project, Event, Document) and relations (blocks, assigned_to,
  depends_on) stored as independent memory entries — searchable by
  BM25, zero file I/O, zero consistency risk.
- **One write per relation** — no bidirectional updates, no half-links.
  Creating a relation = 1 MCP call. Deleting = 1 MCP call.
- **Planning as graph transformation** — model plans as validated
  sequences of entity/relation operations before committing.
- **Extendable types** — store schema extensions in memory for
  project-specific entity types.
- **Structural validator** — `graph_check.py` (284 lines, zero deps)
  checks cycles, cardinality, dangling references.

### Self-Learning Skill (new built-in skill)
- **Learn from mistakes** — captures agent errors, user corrections,
  and non-obvious behavior so they're not repeated. Five learning types:
  gotcha, correction, convention, api-drift, error-fix.
- **Prevention rules** — every learning includes a forward-looking
  instruction that changes future behavior, not just a record of what
  happened. Prevention rules surface during recall, not incident history.
- **Automatic recall** — searches past learnings before starting tasks
  to avoid known pitfalls. Reports prevention rules, not incident logs.
- **Review workflow** — `sage review` curates the learning database:
  inventory, cluster, stale check, consolidate, promote.
- **Promotion ladder** — learnings escalate from project → global →
  team files as they prove broadly applicable.
- **Ontology integration** — optional cross-referencing with ontology
  entities via edge tags for targeted recall.

### Stats
- 36 built-in skills (33 original + memory + ontology + self-learning)
- Three complementary sage-memory skills: prose knowledge (memory),
  structured relationships (ontology), behavioral improvement
  (self-learning)

## [1.0.1] — Skill Management Improvements

### Improved Search Experience
- **Beautiful display** — skill name left-aligned and bold, registry
  right-aligned with dot leaders, description below in dim. Clean
  vertical rhythm for quick scanning.
- **Interactive install from search** — after `sage find`, type a
  number to install directly. Multi-select loop for installing several
  skills in one session. Press Enter to finish.
- **No auto-refresh** — search uses local index instantly. Bundled seed
  catalog (2,100+ skills) ships with framework for offline use. Explicit
  `--refresh` flag when user wants fresh data from upstream.

### Git-Free Skill Downloads
- **GitHub API download** — `sage add` downloads only the skill folder
  via GitHub API. No git clone of entire repositories. Works on any
  machine with Python 3.8+ and internet.
- **Git as optional fallback** — if API download fails and git is
  available, falls back to cloning. Git is no longer a hard dependency
  for skill management.

### Instant Platform Deployment
- **`sage add` deploys immediately** — skills deploy to `.agent/skills/`
  (Antigravity) right after download. No separate `sage update` needed.
- **`sage remove` undeploys immediately** — removes from both
  `sage/skills/` and `.agent/skills/` in one command.

### Smart Update with Preview
- **`sage skills update`** — shows preview of repositories, skill counts,
  and asks for confirmation before downloading.
- **Selective update** — target by registry (`sage skills update antfu/skills`)
  or individual skill (`sage skills update vue`).
- **Built-in protection** — built-in skills excluded from update (update
  those with `sage upgrade`). `sage remove` warns before removing built-in
  skills.

## [1.0.0] — Initial Release

### Core
- **Sage Navigator** — intelligent process orchestration across the
  UNDERSTAND → ENVISION → DELIVER spectrum. Proactive gap detection,
  scope-adaptive process, workflow chaining.
- **Process Constitution** — five non-negotiable rules (State First,
  Skills Before Assumptions, Never Plan Alone, Checkpoints Are Sacred,
  Save State). Platform-adaptive enforcement.
- **18 core capabilities** — elicitation, planning, execution, review,
  debugging, orchestration, and context management.
- **Quality gates** — deterministic verification at each stage.

### Skills
- **33 official skills:**
  - Knowledge: react, nextjs, web, api, mobile, baas, flutter, react-native
  - Composite: stack-nextjs-supabase, stack-nextjs-fullstack, and more
  - PM Process: jtbd, opportunity-map, user-interview, prd
  - UX Process: ux-audit, ux-research, ux-evaluate, ux-brief, ux-discovery,
    ux-specify, ux-plan-tasks, ux-heuristic-review, ux-writing
  - Builder: pack-discover, pack-draft, pack-observe, pack-source-process,
    pack-validate
  - Bundles: product-management, ux-design, skill-builder
- **Progressive enhancement** — community skills work at Layer 0 with
  zero Sage metadata. Add frontmatter for smarter integration.

### Platforms
- **Claude Code** — CLAUDE.md + `.claude/commands/` with slash commands
  generated from core workflows.
- **Antigravity** — GEMINI.md + `.agent/rules/` + `.agent/skills/` +
  `.agent/workflows/` with `/sage`, `/build`, `/fix`, `/architect`, `/status`.
- **Platform-agnostic state** — `.sage/` shared across platforms.

### Installation
- **`sage` CLI** — global install via `curl | bash`. Commands:
  `sage new`, `sage init`, `sage update`, `sage upgrade`. Auto-detects
  platform and stack.

### Project State Convention
- `docs/` — project-level knowledge (flat, skill-prefixed)
- `work/` — per-initiative (`YYYYMMDD-slug/` folders)
- Core files: `brief.md` (WHAT), `spec.md` (HOW), `plan.md` (ORDER)
- Decision records: `decision-*.md` prefix
