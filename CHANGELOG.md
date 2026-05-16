# Changelog

All notable changes to Sage will be documented in this file.

## [1.1.5] — Project-level defaults for workflow flags

### Config Defaults
- `quality_locked: true` and `autonomous: true` keys in
  `.sage/config.yaml` now act as project-level defaults for the
  workflow flags. Set once, applied to every `/build`, `/architect`,
  and `/fix` invocation. No flag needed per run.
- **Strict-match contract:** only `<key>: true` (exact whitespace,
  lowercase) is honored. Variants like `True`, `"true"`, `yes` are
  rejected as "no default" — ensures Python and Bash parsers agree
  byte-for-byte. Documented in flag-parser/SKILL.md.

### New Override Flags
- `--no-quality-locked` and `--no-autonomous` force their respective
  mode off, overriding any config default for a single run.
- Conflict detection: passing both `--X` and `--no-X` in the same
  invocation produces a clear error and stops the workflow.

### Source Visibility
- Workflow announcement now labels the source of each active mode:
  `Modes: --quality-locked (from .sage/config.yaml), --autonomous (from flag)`
- Auto-pick logging records flag sources in both manifest.md
  (`auto_picked_checkpoints[].flag_sources`) and decisions.md (in the
  "Flags active" line). The override hint in decisions.md adapts to
  source: "config" → "pass --no-X"; "flag" → "omit --X".

### Precedence (highest wins)
1. `--no-X` flag (force off, source "flag")
2. `--X` flag (force on, source "flag")
3. `X: true` in `.sage/config.yaml` (default on, source "config")
4. nothing (off, source null — implicit default)

Flag source label is always `"flag"` when a flag (positive or `--no-`)
influenced the result, even when the value matches config. This makes
the audit trail show explicit user intent.

### Three-layer Parser Updated
- **Python primary** (`core/flag_parser/parser.py`,
  `core/flag_parser/config_loader.py`): new `defaults` parameter on
  `parse()`, source fields in `ParseResult`, conflict detection.
- **Bash fallback** (`core/flag_parser/parse.sh`): same JSON contract,
  reads config via `grep -Eq '^<key>: true$'` (no eval).
- **Prose fallback** (`flag-parser/SKILL.md`): precedence table and
  config lookup section.

### Tests
- 79 flag_parser tests passing (up from 26):
  - 28 parser unit tests (14 new for defaults, `--no-*`, conflicts, sources)
  - 22 config_loader tests (new file; covers all strict-match rejections)
  - 29 parity tests (17 new for config-aware paths)

### Documentation
- `core/capabilities/orchestration/flag-parser/SKILL.md` — precedence
  table, strict-match contract, source field semantics
- `core/capabilities/orchestration/autonomous/SKILL.md` — Logging
  contract updated with `flag_sources`, per-flag override hint rule
- Manifest template — `auto_picked_checkpoints[].flag_sources` shape
  documented
- README — new "Project-level defaults" subsection under Workflow Flags
- Workflow preambles (Claude Code + Antigravity) — invoke parser with
  `--config-path .sage/config.yaml`; announcement instructions reference
  the new source fields

### Compatibility
Pre-v1.1.5 projects (no `quality_locked:` or `autonomous:` in config)
behave identically to today. Adding the keys is opt-in; `sage init`
does not set them.

## [1.1.4] — Auto-pick [A] Review when --autonomous + --quality-locked combined

### Auto-Pick at Checkpoints
- When BOTH `--autonomous` AND `--quality-locked` are active, agent
  auto-picks `[A] Review` at normal approval checkpoints (spec, plan,
  ADR, root cause, fix plan) instead of prompting the user. The combined
  flags already signal "decide yourself + don't stop until clean", and
  `[A]` is the only checkpoint option consistent with both signals.
- **Exception checkpoints still require user input** (no auto-pick):
  - quality-locked cap-reached prompt (10 iterations without convergence)
  - quality-locked stuck-escalation prompt (3 iterations no improvement)
  - autonomous unconfident-decision questions (`[Q1]/[Q2]` block)
  - sub-agent unavailable warnings (degraded mode notice)

### Full Audit Trail (per Auto-Pick)
Every auto-picked checkpoint is logged to TWO locations BEFORE the
review action runs, so the trail survives crashes or interruption:
- **manifest.md frontmatter** — `auto_picked_checkpoints: []` array with
  `phase`, `checkpoint`, `decision`, `timestamp`, `reason` for each entry
- **decisions.md** — human-readable entry per Rule 7 (newest-first prepend)
  documenting which flags were active and how to override

### Manifest Template
- Added `auto_picked_checkpoints: []` field to frontmatter
- Extended Flag state section to summarize auto-picked checkpoints when
  both flags are active

### Documentation
- `core/capabilities/orchestration/autonomous/SKILL.md` — new
  "Auto-Pick at Checkpoints" section with rules, exceptions, logging
  contract, and rationale
- `core/capabilities/orchestration/quality-locked/SKILL.md` — cross-reference
  to the autonomous skill's auto-pick rules
- Build, fix, architect preambles (Claude Code + Antigravity generators)
  include the AUTO-PICK rule pointing at the autonomous SKILL

### Bug Fixes
- **`sage update` silent-exit on pre-v1.1.3 projects** — `set -euo pipefail`
  trap triggered when `grep '^platforms:' .sage/config.yaml` returned 1
  (no match). The bare assignment of the failing pipeline propagated to
  errexit and silently exited the script. Added `|| true` to the pipeline.

## [1.1.3] — Multi-Platform Support: Codex, Opencode, Gemini CLI

### Three New Platforms
- **Codex (OpenAI)** — AGENTS.md (read by Codex as system prompt) +
  `.codex/agents/*.toml` for sub-agents. Native sub-agent support
  via TOML definitions with `name`, `description`, `developer_instructions`.
  32 KiB AGENTS.md cap respected (Sage's output is ~15 KB).
- **Opencode** — AGENTS.md + `.opencode/commands/*.md` (markdown with
  YAML frontmatter) + `.opencode/agents/*.md` for sub-agents. Native
  `@agent-name` invocation. Permission system used to enforce READ-ONLY
  on review sub-agents (`permission.edit: deny`, `permission.bash: deny`).
- **Gemini CLI** — GEMINI.md + `.gemini/commands/*.toml` (TOML format
  with `prompt` + `description`, `{{args}}` placeholder). Subdirectories
  produce namespaced commands (`/sage:build`, `/sage:fix`) when
  `command_prefix: true`. Sub-agent format not documented in v1 — falls
  back to single-pass review with a session notice.

### Multi-Platform Installation
- **Up to 5 platforms can coexist** in one project. AGENTS.md is shared
  between Codex and Opencode; GEMINI.md is shared between Antigravity
  and Gemini CLI. Each platform's commands/agents directory is
  independent.
- **`--platform <list>` flag** — comma-separated platform list, or
  `all` for all 5. Works on `sage init` and `sage update`.
- **`platforms:` persisted in .sage/config.yaml** — sage update reads
  this list and regenerates for each platform. The list is set during
  `sage init` from detection or the `--platform` flag.
- **Ambiguity handling** — when only AGENTS.md exists (no `.codex/`,
  no `.opencode/`), `sage init` asks the user once and persists the
  choice. Same logic for GEMINI.md → Antigravity vs Gemini CLI.

### Shared Generation Infrastructure
- **`runtime/platforms/_shared/instructions-body.sh`** — single source
  of truth for the instructions-file body (Rules 0-7, routing table,
  workflow gates, learning triggers). All 5 platform generators source
  it; each platform's generator sed-substitutes platform-specific
  terminology.
- **`runtime/platforms/_shared/preambles.sh`** — workflow preambles
  (the 14 compliance-rule blocks prepended to each command) extracted
  into `emit_preamble(workflow_name)`. Used by Claude Code, Opencode,
  and Gemini CLI generators.
- **CLAUDE.md output remains byte-identical** to pre-refactor (verified
  with MD5 parity check).

### Sub-Agent Behavior Matrix
- Claude Code, Antigravity, Codex, Opencode: full sub-agent reviews
  via independent context windows
- Gemini CLI: single-pass fallback in v1 (sub-agent format pending docs)
- Auto-review / auto-qa / quality-locked all work cross-platform; the
  fallback for sub-agent-less sessions surfaces a clear notice

### Bug Fixes
- **Shell quoting in preambles** — `'<JSON of past iterations>'` inside
  a single-quoted bash string caused bash to interpret `<JSON` as a
  redirect. Replaced with `"<JSON of past iterations>"`. This bug
  silently broke the `build` and `architect` command generation for
  workflows after `analyze`.

### Documentation
- README Platforms section expanded to 5+ platforms with sub-agent
  column
- `runtime/platforms/{codex,opencode,gemini-cli}/notes.md` document
  platform-specific quirks
- bin/sage `--help` updated with `--platform` flag

## [1.1.2] — Workflow Flags: --quality-locked and --autonomous

### Workflow Flags
- **`--quality-locked` flag** for `/build` and `/architect`. At every
  review checkpoint, loops review/revise until findings reach a clean
  bar (no Critical, no Major, only cosmetic Minor) or the iteration cap
  (10) is reached. Use when you want Sage to push for clean output.
- **`--autonomous` flag** for `/build` and `/architect`. Skips
  user-facing elicitation rounds. Agent makes brief/spec/plan decisions
  by reading memory, codebase patterns, constitution principles, and
  prior cycles. Every decision cites its source via a Rationale block.
  Unconfident substantive decisions fall back to asking specific
  questions (not the whole elicitation).
- **Combinable.** `/build --quality-locked --autonomous "<goal>"` means
  "decide the best approach yourself, deliver it, and don't stop until
  the quality gates are clean."
- **Manifest persists flag state.** `/continue` restores both modes
  across sessions.

### Cosmetic vs Substantive Findings
- **Review sub-agent prompts** (all 7 prompts in auto-review, auto-qa,
  quality-review SKILLs) now classify Minor findings as either:
  - **MINOR-cosmetic** — style/naming/formatting with equally valid
    alternatives, no behavior change
  - **MINOR-substantive** — improvement opportunity affecting
    readability, maintainability, or future behavior
- This enables `--quality-locked` to auto-revise the substantive issues
  while accepting cosmetic ones (same code is "clean enough").

### New Capabilities
- **`flag-parser` capability** — defines the shared parsing contract for
  `--quality-locked` and `--autonomous`. Both workflows reference it.
- **`quality-locked` capability** — defines the review-revise loop:
  clean bar, iteration cap, per-iteration logging, cap-reached prompt,
  architecture escalation heuristic.
- **`autonomous` capability** — defines the pre-flight context
  gathering (memory + codebase + constitution + prior work), decision
  protocol with confidence threshold, rationale block format, and
  question-fallback rules.

### Workflow Updates
- `/build` Step 3 (Brief), Step 4 (Spec), Step 5 (Plan) — each respects
  `autonomous_mode` and produces a Rationale block when active.
- `/build` spec and plan checkpoints — each respects
  `quality_locked_mode` and runs the review loop when active.
- `/architect` Step 2 (Deep Elicitation), Step 3 (Design), Step 4
  (Milestone Plan) — same updates for both flags.
- Generator preambles (Claude Code and Antigravity) include flag
  parsing instructions for `/build` and `/architect`.

### Manifest Template
- Added `flags`, `quality_locked_history`, and `autonomous_decisions`
  fields to manifest frontmatter.
- Added "Flag state" section to manifest template body (omitted when
  no flags are active).

## [1.1.1] — Autoresearch, Enforcement Hardening, Quality of Life

### Autoresearch
- **`/autoresearch` workflow** — autonomous iteration toward a measurable
  outcome. Modify → commit → verify → keep or revert → repeat. Based on
  Karpathy's autoresearch pattern, native to Sage.
- **Python runtime** (`core/autoresearch/`, stdlib only) — 8-phase state
  machine, METRIC line parser, git branch management, subprocess timer
  with SIGTERM/SIGKILL budget, JSONL logging, TSV rendering.
- **Scope enforcement** — writable/frozen glob matching with `**` recursive
  support. Frozen files can't be touched; out-of-scope changes auto-revert.
- **Stuck recovery** — detects 5+ consecutive discards/crashes, builds
  recovery context with near-miss analysis, surfaces playbook.
- **Session resume** — crash recovery via PhaseState persistence. Dirty
  tree detection. Cross-platform resume (Claude Code ↔ Antigravity).
- **Memory integration** — session-end summaries stored to sage-memory,
  session-start priors injected into IDEATE context.
- **Three worked examples** — bundle size reduction, test coverage
  improvement, prose readability (Flesch-Kincaid grade level).
- **`--keep-on-tie` flag** — keep iterations that match current best
  (default: discard ties per Karpathy's simpler-is-better principle).
- **Navigator routing** — optimization-shaped requests (reduce, increase,
  minimize, maximize, improve, iterate until) auto-route to `/autoresearch`.
- **31 unit tests + 4 integration tests** — harness parsing, results
  tracking, scope enforcement, memory formatting, baseline creation,
  dirty-tree refusal.

### /map Workflow
- **Dedicated ontology builder** — scans codebase and creates typed
  knowledge graph entities (modules, services, APIs) with relationships
  (depends_on, calls, part_of) in sage-memory.
- **Three modes** — broad scan (project-level), deep dive (specific module),
  refresh (update stale entities, remove deleted modules).
- **Mermaid diagrams** — presents discovered structure visually before
  storing. Checkpoint for user approval.
- **Navigator routing** — map/ontology/graph/dependencies/structure keywords
  auto-route to `/map`.

### Enforcement Hardening
- **Rule 1A: Memory Before Work** — mandatory sage_memory_search before
  writing specs, plans, ADRs, or starting investigations. Added to
  constitution, CLAUDE.md, and build/fix preambles. The counterpart to
  Rule 6 (capture corrections) — without both, memory is write-only.
- **Anti-deferral (Rule 4)** — agent must not defer, skip, or deprioritize
  planned work without explicit user consent. Must not mark initiative
  complete with tasks remaining. Added to constitution and build workflow.
- **Fix workflow gates hardened** — root cause gate no longer skippable for
  "obvious" bugs. Surgical fixes now require user scope confirmation before
  implementation. Explicit: "Do NOT skip this gate for ANY reason."
- **Fix workflow gains auto-review** — root cause diagnosis and fix plan
  reviewed by sub-agent. Two new review prompts: root cause review (5
  checks) and fix plan review (5 checks).
- **Fix workflow gains quality gates** — Gate 3 (code quality) and Gate 8
  (auto-QA) now run as optional/advisory for fixes. Previously skipped.
- **Self-learning trigger** — fix workflow now stores `[LRN:gotcha]` after
  2+ failed fix attempts, before the next attempt (don't wait for success).
- **Read-only sub-agents** — all 6 review sub-agent prompts include explicit
  "READ-ONLY: do NOT modify any files" constraint. Prevents sub-agents from
  editing specs during review.
- **Sage-memory over native memory** — Rule 6 now explicitly prohibits
  Claude's native MEMORY.md for corrections and learnings. Sage has its
  own memory system.
- **Ontology wiring checks** — build/fix close steps verify new components
  are connected (imports, routes, handlers) and update ontology when
  structural relationships change.

### Decisions.md Improvements
- **Newest-first ordering** — all decision writes now prepend (insert after
  header, before existing entries). Recent context read first, no wasted
  tokens on old entries.
- **Archive rotation** — when decisions.md exceeds ~200 lines, keep 20 most
  recent, move rest to `decisions-{YYYY-MM-DD}.md`. Archives are read-only.
- Updated across all 8 workflows, 6 capabilities, constitution Rule 7.

### Command Prefix Support
- **`--prefix` flag** — `sage init --prefix` namespaces all commands as
  `sage:build`, `sage:fix`, `sage:review`, etc. Avoids conflicts with
  other plugins. `/sage` stays unprefixed.
- **Config persistence** — `command_prefix: true/false` in `.sage/config.yaml`.
  `sage update --prefix` toggles it. Generator reads config on every run.
- **Routing table prefixed** — CLAUDE.md keyword routing, command files,
  and skill loaders all respect the prefix setting.

### Quality of Life
- **Sub-agent timeout 30s → 60s** — auto-review and auto-QA sub-agents
  now have 60 seconds instead of 30. Reduces false timeouts.
- **Animated CLI spinner** — `sage init`, `sage update`, `sage upgrade`
  show braille spinner animation during long operations.
- **Checkpoint labels simplified** — `[A] Review` / `[S] Skip review`
  replaces redundant `[A] Approve & review`.
- **MCP parameter types documented** — pseudo-code function call syntax
  replaced with natural language + explicit type hints (arrays must be
  arrays, integers must be integers). Fixes agent passing stringified JSON.

### Bug Fixes
- **`--prefix` flag persistence** — flag now updates `.sage/config.yaml`
  for existing projects and during `sage update` (was silently ignored).
- **`cmd_name` unbound variable** — moved variable assignment before the
  redirect block in `generate-claude-code.sh`.
- **Autoresearch `git reset`** — discard/crash now resets to `HEAD~1`
  (was resetting to `HEAD`, a no-op). Crash recovery uses exact
  pre-iteration SHA for multi-commit scenarios.
- **Autoresearch scope violations logged** — scope gate crashes now appear
  in JSONL/TSV results (were silently dropped).
- **Autoresearch iteration count** — `max_iterations` now counts actual
  attempts, excluding the baseline measurement.
- **`.gitignore` corruption** — `__pycache__/` entry was appended without
  newline, breaking the CLAUDE.md ignore rule.

## [1.1.0] — Auto-Review + skills.sh Integration

### Auto-Review Sub-Agent
- **Automatic independent review** of spec and plan after user approval [A].
  Sub-agent gets a fresh context window — no self-bias from the producing agent.
- **Three review prompts:** spec review (5 checks: framing alignment, criteria
  testability, boundary completeness, edge cases, internal consistency), plan
  review (5 checks: spec-plan alignment, task decomposition, dependency ordering,
  coverage gaps, risk concentration), ADR review (5 checks: trade-off analysis,
  migration path, risk assessment, blast radius, reversibility).
- **Build workflow:** auto-review fires after spec [A] and plan [A] for
  Standard+ tasks. Lightweight tasks skip.
- **Architect workflow:** auto-review fires after design checkpoint [A] (ADR
  review) and plan checkpoint [A].
- **Advisory, not blocking:** user can always [P] Proceed. Findings surface
  with [R] Revise / [P] Proceed / [D] Discuss options.
- **Config toggle:** `auto_review: false` in `.sage/config.yaml` disables
  auto-review. Default is `true`.
- **60-second timeout:** if sub-agent doesn't respond, skip with note.
- **Task tool required:** if Task tool is not available (e.g., Antigravity),
  auto-review skips silently. No self-review fallback.
- **Findings logged:** all review verdicts appended to decisions.md for
  /reflect to learn from.

### skills.sh Integration
- **`sage find`** now searches the skills.sh catalog (90K+ skills, ranked by
  install count). Replaces the old private index.
- **`sage add`** supports multi-skill repos. `sage add vercel-labs/agent-skills`
  discovers all skills in the repo, presents an interactive picker, downloads
  selected skills individually via GitHub API (no git clone needed).
- **Five source formats:** GitHub shorthand (`owner/repo`), GitHub URL, GitHub
  deep link (`/tree/main/skills/react`), local path (`./my-skills`), and
  well-known protocol (`https://example.com`).
- **Platform-aware deploy:** `sage add` deploys to both Claude Code (loader
  stub in `.claude/skills/`) and Antigravity (full copy in `.agent/skills/`).
  `sage remove` cleans up all platform paths.
- **`--skill` flag** for non-interactive single skill install:
  `sage add vercel-labs/agent-skills --skill frontend-design`
- **`--all` flag** to install all skills from a repo.
- **`--audit` flag** for optional security check via skills.sh audit API.
- **Enhanced skills.json** tracks source, path in repo, and install count.
- **Atomic writes** for skills.json (write to temp, rename).
- Removed old private registry/index code and bundled seed files.

### Auto-QA Sub-Agent
- **Automatic code verification** after quality gates pass in /build.
  Sub-agent with fresh context checks implementation against spec.
- **5 checks:** spec-implementation alignment, test-criteria coverage,
  missing error handling, boundary condition enforcement, integration
  consistency between modules.
- **Build workflow:** auto-QA fires after quality gates pass for
  Standard+ tasks, before Step 8 (completion).
- **Architect workflow:** auto-QA fires after each milestone's build
  gates pass.
- **Fix-and-recheck:** when user picks [R] Fix, agent fixes the
  specific issues (file:line provided), then re-runs auto-QA.
  Max 2 iterations before surfacing to user.
- **Config toggle:** `auto_qa: false` in `.sage/config.yaml` disables
  auto-QA independently from auto-review. Default is `true`.
- **Code-only:** no browser needed. /qa remains the manual deep-dive
  with browser testing via Lightpanda.

### Code Quality Standard
- **7 universal coding principles** loaded during implementation:
  clarity over cleverness, fail loudly / recover gracefully, guard
  the boundaries, smallest scope / shortest lifetime, make the right
  thing easy, consistency beats perfection, test what matters.
- **coding-principles capability** loaded by build-loop before every
  task. Shapes code AS it's written, not reviewed after.
- **Gate 3 upgraded to sub-agent** when Task tool is available.
  Independent code quality review — the agent that wrote the code
  no longer reviews its own quality.
- **Self-review fallback** when Task tool is not available, announced
  as self-review. No silent downgrade.
- **Config toggle:** `independent_gate3: false` in `.sage/config.yaml`
  to disable sub-agent Gate 3. Default is `true`.
- **Auto-QA gains 6th check:** coding principles adherence (magic
  numbers, swallowed errors, unclear names, multi-purpose functions).
- Language-agnostic — applies to Python, TypeScript, Go, Rust, anything.
  Stack skills add language-specific idioms on top.

### Bug Fixes
- **macOS Bash 3.2 compatibility:** fixed `REMAINING_ARGS[@]` unbound variable
  error under `set -u` when running `sage init` with no extra arguments.
- **macOS `date +%s%N` fix:** macOS outputs literal "N" instead of nanoseconds.
  New `_sage_now()` helper strips non-digits and pads to nanosecond scale.

## [1.0.9] — Clarity

### Framing Round
- **quick-elicit v1.1.0:** gains Round 0 — pain question + premise
  challenge before solutioning. 3 rounds → 4 rounds, budget 7 → 8.
- **deep-elicit** Vision round gains premise challenging (2-3 premises).
- **Spec template** includes Framing section (original request, pain,
  premises challenged, chosen framing).
- **Anti-rationalization contracts** block skipping Round 0 for Standard+.
- **Compression** merges pain + intent into one question. Even compressed,
  framing question survives — can be compressed but never eliminated.
- **Research integration:** Round 0 references existing JTBD/research
  findings when available.

### Session Resilience
- **Cycle manifest** (manifest.md) captures state, context summary,
  decisions, open questions, and handoff guidance at every checkpoint.
- **`/continue` command** resumes any active cycle — reads manifest,
  routes to correct workflow, preserves judgment context.
- **Manifest-first Auto-Pickup** in build, architect, fix workflows.
  Falls back to file-scan for pre-v1.0.9 cycles (backward compatible).
- **Anti-lazy-manifest contracts:** summary must contain judgment, not
  "see spec.md." Context summary max 200 words, handoff max 150 words.
- **Context budget pressure:** manifest updated before session break
  to capture judgment that's about to be lost.

### /qa Workflow
- **Browser-based functional testing** via Lightpanda MCP (optional).
- **Code-only fallback:** diff analysis for integration issues when
  no browser available.
- **5-step process:** prerequisites → scope → route testing →
  interaction testing → QA report.
- **QA report** with bugs, severity, reproduction steps, evidence,
  and /fix classification (Surgical/Moderate/Systemic).
- **browser-check capability** in quality gates (Gate 6, advisory,
  invisible when Lightpanda absent or no frontend files).
- **Enforcement:** no fake testing, report completeness, advisory only,
  no fixing in /qa (/fix fixes).

### /design-review Workflow
- **Layer 1 — General quality** (always): typography, spacing, hierarchy,
  interactive states, color/contrast, AI slop detection (10 patterns).
- **Layer 2 — Design system compliance** (when DESIGN.md, design skill,
  or CSS tokens detected): token, component, layout compliance.
- **Browser audit** via Lightpanda (optional, invisible when absent).
- **Findings classified:** /fix (mechanical) vs manual (design decision).
- **design-check capability** in quality gates (Gate 7, advisory,
  invisible when no frontend files).
- **AI slop indicators** are warnings, not issues. Count, not grade.

### /fix Integration
- **/fix reads qa-report.md:** presents bugs with suggested classifications,
  user can accept or reclassify, skips re-diagnosis.
- **/fix reads design-review.md:** mechanical findings route to fix pipeline,
  design-decision findings excluded ("manual action needed" summary).

### Shared Infrastructure
- **Lightpanda setup reference** (core/references/lightpanda-setup.md):
  install guides for macOS, Linux/WSL, Docker + MCP config.
- **Manifest template** (develop/templates/manifest-template.md).
- **15 workflow commands** total: sage, build, fix, architect, research,
  design, analyze, reflect, continue, qa, design-review, status,
  review, learn, plus individual skill commands.

## [1.0.8] — Intelligent Routing

### Three-Layer Routing
- **Keyword routing table** in CLAUDE.md/GEMINI.md Rule 0. Deterministic
  matching checked BEFORE any LLM judgment. Keywords like "audit,"
  "research," "design" map directly to workflows. Handles 60-70%
  of requests with zero LLM involvement.
- **Sub-agent classifier.** When keywords don't match, a focused
  sub-agent classifies into UNDERSTAND/ENVISION/DELIVER with a
  single-task prompt (~150 tokens). Independent context window
  eliminates helpfulness bias.
- **In-context fallback.** For platforms without sub-agent support,
  same three-way classification runs in the main agent's context.

### Interaction Zones
- **Four zones with mandatory footers.** Every response expecting
  input ends with exactly ONE zone footer telling the user what
  inputs are valid:
  - Zone 1 (Choice): `Pick 1-N, type / for commands, or describe what you need.`
  - Zone 2 (Approval): `Pick A/R/N, or tell me what to change.`
  - Zone 3 (Next Step): `Type a command, or describe what you want to do next.`
  - Zone 4 (Open): `Describe what you want to work on, or type / to see commands.`
- **Chain visibility.** Every Zone 1 option shows the skill chain
  with → notation and step count. No time estimates.
- **All 7 workflows updated** with consistent zone footers at every
  checkpoint and completion.

### Non-Tech Workflows
- **`/research` workflow.** Chains user-interview → JTBD →
  opportunity-map. Scope selection (users, opportunity, experience,
  comprehensive). Findings checkpoint with quality gate. Suggests
  /design or /build at completion.
- **`/design` workflow.** Chains ux-brief → ux-specify → ux-writing.
  Auto-loads research context from `.sage/docs/` when available.
  Produces specs with handoff field for /build. Suggests /research
  first when no research context exists for complex designs.
- **`/analyze` workflow.** Chains ux-audit → ux-evaluate. Severity
  classification (Critical/Major/Minor) on all findings. Prioritized
  output. Suggests /design or /fix at completion.

### Skill Deployment
- **37 skills deployed as platform commands.** During `sage init`,
  lightweight loader SKILL.md files are created at `.claude/skills/`
  (CC) or `.agent/skills/` (AG). Each loader is ~50 bytes with
  frontmatter and a redirect to the full skill.
- **Every skill is now a slash command** (`/jtbd`, `/ux-audit`, etc.)
  AND auto-activates from free input via platform skill discovery.
- **Progressive disclosure preserved.** Only frontmatter loads at
  startup. Full SKILL.md loads on activation. 37 loaders ≈ 2KB,
  well under the 16K skill budget.

### Cross-Chain Handoff
- **Artifacts are the handoff.** `/research` produces findings in
  `.sage/docs/`. `/design` auto-scans for them and announces:
  "Found research context — using as design input." `/build`
  scans for both design specs and research/analysis context.
- **Every workflow completion uses Zone 3** to suggest the logical
  next workflow with chain visibility.

### UNDERSTAND → ENVISION → DELIVER → REFLECT Pipeline
- **`/reflect` workflow.** Reviews the full cycle (artifacts,
  decisions, approaches tried), asks for real-world feedback,
  extracts WHEN/CHECK/BECAUSE learnings, stores with `reflect`
  tag, and seeds the next cycle with concrete recommendations.
- **11 workflow commands.** `/sage`, `/build`, `/fix`, `/architect`,
  `/research`, `/design`, `/analyze`, `/status`, `/review`,
  `/learn`, `/reflect` — the complete guided path.
- **Four-phase pipeline.** Reflect closes the loop: learnings from
  /reflect feed into the next /research via Rule 0 memory search.
- **Natural flow:** /research → /design → /build → /review →
  /reflect. Each phase produces artifacts that inform the next.
  Users can enter at any point.

## [1.0.7] — State, Learning & Coordination

### Anti-Rationalization Enforcement (all workflows)

Every enforcement rule across all workflows converted from action
instructions ("MUST do X") to observable conditions ("file MUST
EXIST on disk"). Named rationalization loopholes explicitly rejected.

**Build workflow:**
- Rule 3 rewritten as file check: spec.md MUST EXIST at path.
- Named loopholes: "design is clear," "user described what they want,"
  "this is straightforward" — each followed by "→ NOT a spec file."
- Self-check converted to file checks at every checkpoint.
- Anti-downgrade: "if you're thinking 'simple enough to skip the
  spec,' that thought is the signal to NOT skip."
- Quality gates marked mandatory with named skip rationalizations.
- Auto-pickup: "The disk is the source of truth. Not your memory."

**Fix workflow (v1.2.0) — major rewrite:**
- **New Step 3: Scope the Fix.** After root cause confirmation,
  classify: Surgical (1-2 files, proceed), Moderate (3-5 files,
  write fix plan first), Systemic (5+ files or interface changes,
  ESCALATE to /build or /architect).
- **Fix Scope Gate** with [A]/[R]/[E] escalate option.
- **Scope guard during implementation** — detects when fix grows
  beyond plan and forces decision: update plan, escalate, or revert.
- **Escalation signals** (any ONE makes it Moderate+): touches 3+
  files, changes function signatures, requires new abstractions,
  changes error handling patterns, requires DB migration.
- **Anti-downgrade:** "Do NOT classify as Surgical to skip the plan."
- Fix preamble: "I know what to change" is NOT a plan file.

**Architect workflow (v1.1.0) — hardened:**
- **Elicitation Gate** with file check: brief.md MUST EXIST before
  design. Each round produces visible artifact.
- Named loopholes: "I understand the system" → NOT a brief file.
  "User described the system clearly" → NOT three-round elicitation.
- **Do NOT compress** 3 rounds into 1 response.
- **Design checkpoint** with observable file checks: brief.md,
  spec.md, and decision-*.md must all exist.
- **Milestone enforcement:** each milestone MUST follow build
  workflow gates independently. Do NOT batch-implement.

**Review workflow — hardened:**
- **Delegation mandatory** when Task tool is available. Self-review
  is NOT independent review. Named: "I can review this myself" →
  NOT independent.
- **Severity classification** in sub-agent prompt: Critical (blocks
  proceeding), Major (should fix), Minor (can fix later).
- **Critical findings block approval** — if Critical issues found,
  [R] Revise is presented before [A] Accept.

**Learn workflow — hardened:**
- **Findings quality checklist:** Specific? Insight not inventory?
  Actionable? Agent verifies BEFORE presenting to user.
- "The quality gate is YOUR responsibility, not the user's."

### State Model Redesign
- **progress.md eliminated.** State is now derived from artifact
  frontmatter scanning — always current because artifacts ARE the
  work product. No separate state file to keep in sync.
- **journal.md → decisions.md.** Replaced artifact index table
  (never updated) with a shared decision log where both the agent
  and human write. Agent appends decisions at checkpoints; humans
  add context anytime. One meaningful write replaces three
  housekeeping updates.
- **`/status` computes from artifacts.** Status workflow fully
  rewritten to scan `.sage/work/` frontmatter and present state.
  Always correct because computed at read time.
- **Session hook rewritten.** Scans artifacts + reads recent
  decisions. Zero dependency on progress.md.
- **Migration.** `sage update` migrates journal.md → decisions.md
  (strips artifact table, preserves change log). Leaves progress.md
  untouched — just stops reading it.

### Slash Command UX
- **Auto-pickup.** Every slash command scans `.sage/work/` on
  startup and resumes from the right phase. `/build` with an
  existing spec starts at planning, not scope assessment.
- **Checkpoints suggest next slash command.** Every phase-transition
  checkpoint includes `[N] New session — type /build to continue`.
  Guides users to the reliable slash command path organically.
- **Persona loading in preambles.** `/build` loads developer,
  `/fix` loads debugger, `/architect` loads architect, `/review`
  loads reviewer. One consistent instruction per command.

### Self-Learning Improvements
- **WHEN/CHECK/BECAUSE format.** Prevention rules now use a
  structured template that makes vague rules structurally impossible.
  Quality checklist: specific? pre-condition? standalone?
- **Rule 0 memory search.** CLAUDE.md/GEMINI.md Rule 0 now
  instructs: before any Standard+ task, search sage-memory for
  self-learning entries with specific function call syntax.
- **Scratch counter for approach tracking.** Build-loop and fix
  workflow log approaches to scratch.md. 3+ approaches = automatic
  gotcha trigger based on file content (external signal), not
  self-assessment.

### Multi-Agent Coordination
- **Sub-Agent Delegation Protocol.** Structured context package:
  persona + artifacts + decisions + learnings + task + return format.
  Replaces generic sub-agent prompts with project-aware delegation.
- **Agent handoff protocol.** Completed artifacts get a `handoff`
  frontmatter field with key decisions, open questions, risks, and
  guidance for the next agent. Auto-pickup reads this field.
- **Parallel gate dispatch.** On platforms with Task tool, Gates 1-3
  (judgment-based) dispatch to a reviewer sub-agent while Gates 4-5
  (scripts) run concurrently. Merge results before presenting.
- **Cross-agent memory sharing.** All agents share project-scoped
  sage-memory. Documented in self-learning skill and delegation
  protocol.

### IDE Integration
- **Atomic write for settings.local.json.** Uses temp file + mv
  to avoid transient 404 errors from file watcher during update.
- **IDE restart messaging.** `sage update` shows "⚠ Restart your
  IDE to pick up updated hook configuration."
- **Error handling.** Write failures show clear message with
  remediation steps instead of cryptic errors.

### Terminal UX
- **Rich output helpers.** Section borders, step timing, green/red/
  yellow indicators, braille spinner for long operations.
- **Structured output for all commands.** `sage init`, `sage update`,
  and `sage new` show organized sections with elapsed time.

## [1.0.6] — Make It Real

### Capability Compatibility Audit
- **14 capability files audited and fixed** for v1.0.5 compatibility.
  Removed all per-task state tracking references, unfenced interaction
  blocks, softened hard dependencies on codebase-scan.
- **build-loop** — checkpoint-only plan updates, unfenced status and
  failure interaction blocks, bracket notation for escalation options.
- **session-bridge** — state architecture rewritten: artifacts as
  ground truth (not plan checkboxes), progress.md as pointer,
  checkpoint-only saving, recovery logic updated.
- **implement** — checkpoint-only plan updates.
- **quick-elicit** — codebase-scan made optional with graceful fallback.
- **plan** — codebase-scan dependency removed.
- **spec-review, quality-gates** — per-task language softened.

### Gate Bash Scripts Wired
- **Deterministic verification deployed** — `sage-spec-check.sh`,
  `sage-hallucination-check.sh`, `sage-verify.sh` copied to
  `.sage/gates/scripts/` during init. The only enforcement that
  doesn't rely on agent self-assessment.
- **quality-gates v1.1.0** — gates invoke scripts FIRST (deterministic),
  agent review SECOND (judgment). Script failure = gate failure
  regardless of agent opinion.
- **gate-modes.yaml deployed** — configurable gate activation per
  workflow mode (build: all mandatory, fix: reduced set). Users can
  customize which gates run.

### `sage update` with Migration
- **Stale pattern migration** — `sage update` removes `tasks-total`
  and `tasks-done` from plan frontmatter automatically. Reports
  how many files were migrated.
- Update already preserved .sage/ state and community skills.

### Constitution Preset Selection
- **Interactive preset selection** during `sage init` — base, startup,
  enterprise, opensource, or none.
- **`--preset` flag** — `sage init --preset enterprise` for
  non-interactive use.
- **Dynamic constitution merging** in generators — base principles +
  preset principles + project additions merged into CLAUDE.md /
  GEMINI.md. Stored in `.sage/constitution.md`.
- **Enterprise preset** adds 7 principles (auth, audit trails, input
  validation, service layers, reproducible deploys, migration plans,
  postmortems).
- **Startup preset** adds 4 principles (ship small, one way, logs
  over dashboards, monolith first).

### README Updated
- Hybrid loading architecture explained (eager vs lazy layers).
- Quality gates section updated with deterministic script verification.
- Get Started section includes presets, `sage update`, and `sage upgrade`.

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
