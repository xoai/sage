# Changelog

All notable changes to Sage will be documented in this file.

## [1.0.5] — Intelligent Copilot

### Constitution Rewrite
- **7 rules with compliance checks** — each rule has an observable signal
  that it was followed. Replaces the previous 5 abstract principles.
- **Rule 0: Route Every Request** — scope classification fires FIRST,
  before state reading or skill activation. Tier 1/2/3 routing with
  6 free-input examples showing how to route without asking.
- **Rule 3: Document Decisions** — renamed from "Never Plan Alone."
  Artifacts serve humans AND agents. Even Tier 2 tasks produce a record.
- **Rule 5: Verify Before Claiming Done** — universal pre-completion
  quality gate. Tests must exist, pass, and output must be pasted.
- **Rule 6: Capture Corrections** — automatic self-learning with 6
  trigger types. User corrections are MANDATORY captures.
- **Rule 7: Update State at Checkpoints** — replaces failed per-task
  tracking with checkpoint-only state updates.

### Simplified State Management
- **Removed per-task state tracking** from build and architect workflows.
  Plan.md is a guide, not a tracking database. Checkboxes are checked
  in bulk at completion, not per-task during implementation.
- **Removed `tasks-total` / `tasks-done`** from plan frontmatter
  convention, session hook output, navigator state scanning, and skill
  authoring guide.
- **File system as source of truth** — what artifacts exist and their
  frontmatter status (updated at checkpoints) is the authoritative state.

### Self-Learning Triggers
- **6 trigger types in always-on layer** — correction (mandatory),
  gotcha, convention, api-drift, error-fix. Listed in CLAUDE.md and
  GEMINI.md so they fire automatically, not when the agent decides.
- **Prevention rules required** — every learning must answer "what should
  I check BEFORE this happens again?"

### Document-First Scope Calibration
- **Tightened Lightweight threshold** — now requires "no design decisions
  AND no behavior changes visible to other team members." Any behavior
  change → Tier 2 minimum.
- **New Standard trigger** — "task involves a decision that another team
  member would need to know about."
- **"Documents serve humans too"** principle added to navigator scope
  assessment.

### Sub-Agent Strategy
- **Clear guidance** on when Task delegation adds value (artifact review,
  code review of 5+ file implementations) and when it doesn't (testing,
  state management, small fixes, implementation).
- Advisory — navigator recommends, user decides.

### Routing Strengthened
- **6 free-input routing examples** in CLAUDE.md / GEMINI.md showing
  Tier 1/2/3 classification on natural language requests.
- **Rule 0 position** — routing fires before state reading, before
  skill activation, before any work.

### Enforcement Architecture (hybrid loading)
- **Workflow gates in CLAUDE.md Rule 0** — build (spec→plan→implement),
  fix (root cause→fix→verify), architect (elicit→design→plan) gates
  inline in always-on layer. Enforced for BOTH slash commands and free
  input. "DO NOT implement before spec checkpoint is approved."
- **Self-check loop in Rule 5** — agent verifies against workflow gates
  before presenting any checkpoint. Catches "announced build then
  jumped to code." Includes adversarial spec compliance.
- **Base constitution principles deployed** — 5 engineering principles
  (TDD, no silent failures, no secrets, explicit deps, reversible
  changes) from base.constitution.md now in CLAUDE.md / GEMINI.md.
- **Command preambles** — every generated command file has a RULES
  block at the top with workflow-specific enforcement. Triple
  reinforcement: CLAUDE.md + preamble + workflow steps.
- **Load-command instruction** — Rule 0 tells agent to read the
  command file after routing, with gates as fallback.

### Workflow Compliance Hardening
- **Complexity-based scope** replaces time-based ("< 30 min", "hours",
  "days"). Scope signals: component count, design decisions, team
  visibility. "MUST write spec" replaces "Recommend a spec."
- **All code-fenced checkpoints removed** — interaction renders as
  plain text, not code blocks.
- **Learn workflow** gains a findings review checkpoint (Step 4) before
  storing knowledge in memory.
- **Fix workflow** clarifies vague bug report handling.
- **Navigator** uses mandatory language for Standard scope specs.

### Capability Wiring (13 previously unused capabilities activated)
- **build-loop** → Build Step 6 execution engine. Task-by-task
  implementation with TDD, scope-guard, quality gates between tasks,
  inter-task checkpoints, escalation, context budget awareness.
- **quality-gates** sub-workflow → Build Step 7. Sequences 5 gates:
  spec compliance, constitution, code quality, hallucination check,
  verification. Fix-and-retry with max 3 attempts.
- **quick-elicit** → Build Step 3. Structured 3-round elicitation
  (intent, boundaries, verification) for brief writing.
- **tdd** → Build Step 6 via build-loop. RED→GREEN→REFACTOR with
  deletion rule for code written before tests.
- **scope-guard** → Build Step 6 via build-loop. "Is this in my task?
  Was this in the plan? Did the human ask for this?"
- **systematic-debug** → Fix Step 2. 4-phase debugging framework.
- **verify-completion** → Build/Fix verification via quality-gates.
- **deep-elicit** → Architect Step 2. Comprehensive elicitation.
- **specify** → Build Step 4. PRD-to-spec structured process.
- **quality-review** → Review Step 3 and quality-gates Gate 3.
- **spec-review** → Quality-gates Gate 1. Adversarial verification.
- **Agent personas wired** — reviewer (Task-delegated reviews),
  debugger (fix workflow), analyst (architect elicitation), developer
  (build implementation).
- **Session-bridge concept** — "trust artifacts over progress.md"
  rule added to navigator State section.

### `/sage` Command Rewritten
- Self-contained with structured options using [1] [2] [3] brackets.
- Three conditional templates: work in progress, artifacts exist,
  fresh project. Never asks "What would you like to do?" open-ended.

## [1.0.3] — Quality, Review & Memory Enforcement

### Review Workflow (new)
- **`/review`** — dedicated workflow for evaluating Sage artifacts.
  Works same-session or fresh-session. Evaluates against three lenses:
  completeness, consistency, and quality. Uses the producing skill's
  quality criteria as the evaluation framework.
- **Fresh-session review** — recommended for high-stakes deliverables.
  Combined with sage-memory, provides independent perspective WITH
  project context.

### Quality Criteria & Self-Review
- **Quality criteria in skills** — 6 skills enriched with domain-specific,
  checkable quality standards: jtbd, prd, ux-audit, ux-brief,
  ux-evaluate, ux-specify.
- **Quality criteria in workflows** — 3 workflows enriched: build,
  architect, fix. Each defines what good output looks like.
- **Self-review step** — skills instruct the agent to check its own
  output against quality criteria before presenting it. Transparent
  self-assessment builds user trust.

### Navigator Improvements
- **Transition announcements** — navigator explains what's changing and
  why when switching between skills or phases. Natural language, not
  mechanical labels. Users can redirect because they understand what's
  about to happen.
- **Review judgment** — navigator evaluates when to recommend fresh
  review (high-stakes, long sessions, cross-domain transitions) vs
  self-review (incremental work, short sessions) vs no review (quick
  fixes). Smart recommendations, not blanket policy.

### MCP Tool Enforcement (critical fix)
- **Explicit MCP tool calls** — all memory instructions now show exact
  `sage_memory_store(...)` and `sage_memory_search(...)` call syntax with parameters.
  Prevents agents from falling back to file-based memory or Claude Code's
  built-in memory system.
- **File fallback** — when MCP is not available, falls back to
  `.sage-memory/` files in project root. One file per entry, title as
  filename, tags in frontmatter.
- **MCP connection verification** — navigator's memory step calls
  `sage_memory_search` and checks for response. Reports clearly if sage-memory
  is not configured.
- **Config key renamed** — `sage setup memory` now uses `"sage-memory"`
  as the MCP config key instead of `"memory"` to avoid collision with
  Claude Code's built-in memory concept.

### Memory Enforcement
- **Navigator enforces memory** — recall is now a concrete process step
  in Read the Room, not a suggestion. One search, results categorized
  into knowledge, structure (ontology tag), and warnings (learning tag).
  Graceful degradation if sage-memory is not configured.
- **Navigator enforces store** — after significant work, the navigator
  evaluates what to store with proportional judgment and appropriate tags.
- **Unified knowledge facets** — memory, ontology, and self-learning are
  three facets of one knowledge system, distinguished by tags, not
  separate storage backends. One search returns all three.
- **`sage setup memory`** — prints platform-specific MCP config for
  sage-memory. Copy-paste setup, zero guesswork.
- **`sage init` detects memory** — shows setup hint when sage-memory
  is not configured.
- **`/learn` workflow** — deliberate knowledge capture. Broad scan
  (`sage learn`) or deep dive (`sage learn <path>`). Stores focused
  memories and generates knowledge report.

### Documentation
- **Skill authoring guide** — quality criteria and self-review documented
  as standard sections with examples and writing principles.
- **Skill contract** — quality criteria added as SHOULD requirement.
- **Design philosophy** — rationale for quality criteria in skills and
  the dedicated review workflow.
- **Skill philosophy** — why quality criteria close the loop between
  process compliance and output quality.

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
