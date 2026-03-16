# Sage Design Philosophy

This document captures the reasoning behind every major design decision in Sage.
Read this to understand WHY the framework is built the way it is — not just WHAT
it does.

---

## Why Adaptive Weight

**The problem:** Every framework we studied has one weight setting. BMAD is always
heavy (full agile ceremony for every change). Superpowers always runs the same
brainstorm → plan → execute cycle. Spec-Kit always goes through constitution →
specify → plan → tasks → implement. None of them ask: "does this task actually
need all that process?"

A developer fixing a typo doesn't need a Product Requirements Document. But that
same developer starting a new payment system shouldn't skip architecture. The
disconnect between process weight and task weight is where developers abandon
frameworks — they skip the process for "small" changes, then those small changes
accumulate into debt.

**Our answer:** Three modes that match process weight to task weight. FIX mode
strips away everything except debugging discipline and TDD. BUILD mode adds
guided elicitation and planning. ARCHITECT mode adds the full agile ceremony.
The framework detects which mode fits, the human confirms or overrides, and the
right amount of process is applied.

The key insight: every mode still enforces quality gates. The gates just get
lighter in FIX mode (2 of 5) and heavier in ARCHITECT mode (all 5 + consistency).
You never skip quality — you only skip planning overhead.

### Why Modes Are Universal (Not Code-Specific)

FIX/BUILD/ARCHITECT sound like tech terms, but the principle underneath them is
universal: **match process overhead to task complexity.** This works for any
discipline:

- **FIX:** I know what needs to change. Make a targeted correction to an existing
  artifact. Minimal ceremony. A PM fixing opportunity scores after new survey data.
  A UX designer correcting a heuristic evaluation after usability test findings.
  A developer patching a bug.

- **BUILD:** I need to produce a defined deliverable with standard quality. Follow
  the structured process without over-engineering it. A PM writing a JTBD analysis
  for a specific feature. A UX designer creating a design brief. A developer
  building a component.

- **ARCHITECT:** The problem is complex enough that cutting corners on process will
  produce bad output. Full rigor, nothing skipped. A PM analyzing the entire
  product strategy across multiple segments. A UX designer running full discovery
  with research. A developer designing a multi-component system.

The three modes work because they map to a universal cognitive pattern:
targeted correction → standard production → comprehensive design.

**What changes between disciplines is the behavior per mode, not the modes
themselves.** Sage core provides the mode system (three modes, adaptive weight
principle, mode detection from user intent, escalation suggestions). Each
playbook defines what FIX/BUILD/ARCHITECT means for its discipline-specific
skills.

For code skills:
- FIX: skip elicitation, skip spec, diagnose and fix, basic gates
- BUILD: quick-elicit, full spec, TDD loop, all gates
- ARCHITECT: deep-elicit, spec + decision records, full plan + checkpoints, all gates + review

For PM skills (as an example of non-code):
- FIX: update specific claims in an existing analysis with new evidence
- BUILD: produce the deliverable with standard depth (quick job framing, light
  PRD, focused interview guide)
- ARCHITECT: comprehensive analysis with full rigor (complete JTBD with scoring,
  full PRD with traceability, research package with analysis framework)

The mode system is the same. The behaviors are playbook-specific. No new modes
needed for non-code disciplines.

**Who decides the mode?** The user proposes by how they phrase the request. The
framework helps by observing scope signals during early steps: "This looks like
it affects multiple segments and needs dependency analysis. Want to escalate from
BUILD to ARCHITECT?" The user makes the final call. The framework suggests, the
human decides.

---

## Why No Commands (Yet)

**The question:** Many AI frameworks use slash commands (`/build`, `/status`,
`/skip`) to trigger specific behaviors. Should Sage?

**The tension:** Commands provide precision, composability, and debuggability —
when you type `/status`, you know exactly what happens. Natural language
provides zero learning curve and leverages what LLMs are good at — when you
say "where are we?", the agent figures it out. Commands solve disambiguation
at the cost of a vocabulary the user must learn. Natural language solves
accessibility at the cost of occasional misinterpretation.

**Our decision: reserve the space, don't fill it yet.**

We don't have enough real usage to know where natural language fails
dangerously in Sage. Designing commands now would be architectural
speculation — inventing solutions for problems we haven't experienced. Every
command is a permanent API commitment (once published, it can never be removed
without breaking users). Premature commands are permanent debt.

The architecture supports commands if needed: skills are invoked through
intents, and a command parser would be just another input adapter feeding the
same dispatch mechanism (the same insight the Gang of Four, Cutler, and Uncle
Bob would give — separate mechanism from interface). Adding commands later
requires no architectural changes.

**When a command earns its place:**

1. Natural language is genuinely ambiguous for this specific operation — not
   just occasionally misinterpreted, but structurally ambiguous
2. The cost of misinterpretation is high — wrong file overwritten, wrong mode
   applied to a large initiative, state corrupted
3. The operation is Sage-system-level — affects how the framework behaves,
   not what the user is trying to accomplish in their domain
4. The operation is frequent enough that users would actually learn the command

**When a command does NOT earn its place:**

- The agent can ask for clarification cheaply (10-second correction)
- The operation is domain-specific (skill invocation — use natural language)
- It duplicates what natural language already handles well
- It would be used less than once per project

If real usage reveals operations that meet all four criteria, we add them —
one at a time, with permanent commitment awareness. Until then, we invest in
better trigger phrases, better disambiguation prompts, and better sage-help
discoverability.

---

## Why Contracts Over Inheritance

**The problem:** Frameworks that use inheritance (extend BaseAgent, override onTask)
create tight coupling. If the base class changes, all derivatives break. Contributors
need to understand the framework's internals to add anything. This is why most AI
frameworks have a handful of contributors — the barrier to entry is the framework
codebase itself.

**Our answer:** Contracts define the socket shape. Implementations define the plug.
A skill contributor reads `skill.contract.md`, sees the required frontmatter and
structure, and builds their skill without touching any framework code. A workflow
references skills by name — it doesn't know or care what's inside them. You can
replace any module by creating a new one with `replaces: <original-name>` in its
frontmatter.

This also makes the framework future-proof. When AI coding practices evolve and
today's TDD skill becomes obsolete, someone writes a better one, sets `replaces: tdd`,
and the framework switches without any migration. The contract stays the same.
The implementation changes.

---

## Why Skills Are Laws

**The problem:** Every framework that makes skills "optional" or "suggested" finds
that agents ignore them. Superpowers documented this extensively — agents will
rationalize skipping any step that isn't enforced. "This is too simple to test."
"I'll add tests later." "The deadline is tight." Every rationalization sounds
reasonable. Every one leads to bugs.

**Our answer:** Skills marked as `mandatory` cannot be bypassed by the agent.
The TDD skill, scope guard, spec review, and quality review are all mandatory.
The only way to skip them is an explicit human override (`skip-tdd`), which is
logged in progress.md as a waiver.

We also adopt Superpowers' approach to rationalization resistance: the TDD skill
includes a table of common rationalizations with pre-written counters. The agent
sees its own rationalization listed as "invalid" before it can convince itself
the rationalization is reasonable.

---

## Why Guided Elicitation (Not Blank Templates)

**The problem:** Spec-Kit gives you a blank template and says "describe what you
want." BMAD gives you a 20-minute persona-driven interrogation. Both miss the
sweet spot.

Blank templates produce vague specs because humans don't naturally think in
acceptance criteria and boundary conditions. Heavy elicitation produces great
specs but people skip it for anything that isn't a major project.

**Our answer:** Adaptive elicitation that asks only what can't be inferred.

In BUILD mode, `codebase-scan` runs first. It identifies the tech stack, patterns,
conventions, and affected areas. Then `quick-elicit` asks only what the scan couldn't
determine — typically: what should this do (intent), what should it not do (boundaries),
and how will we know it works (acceptance criteria). Three rounds, seven questions
maximum, about two minutes.

The adaptation is the key. If you're adding a feature to a Next.js project, the
agent doesn't ask "what framework are you using?" — it already knows. It asks about
behavior, not infrastructure. This respects the developer's time while still
producing a spec good enough to prevent downstream confusion.

In ARCHITECT mode, the elicitation goes deeper with Socratic questioning and
persona-driven exploration. This is justified because the planning cost is small
relative to the implementation cost for major projects.

---

## Why Three-Tier Constitutions

**The problem:** Spec-Kit has one constitution per project. This is too flat for
organizations with multiple projects that share standards. A security team mandating
"all APIs require authentication" has to manually add that principle to every project.
If they saget one, the principle doesn't apply.

**Our answer:** Three tiers that inherit:

```
Tier 1: Organization (~/.sage/constitution.md)
  → Applies to ALL projects by this team/company
  → "All APIs require authentication"
  → Cannot be removed by lower tiers

Tier 2: Project (.sage/constitution.md)
  → Extends Tier 1 with project-specific principles
  → "This project uses PostgreSQL only"
  → Cannot remove Tier 1 principles

Tier 3: Feature (.sage/work/*/context.md)
  → Extends Tier 2 with feature-specific constraints
  → "This feature must support offline mode"
  → Cannot remove Tier 1 or Tier 2 principles
```

The context loader merges all three tiers at session start. Waivers are the ONLY
mechanism to exempt a principle — and waivers require explicit documentation with
reason, scope, approver, and expiration.

The merged constitution is always in context. It's the only document guaranteed
to be loaded in every mode, every session, every action.

---

## Why Adversarial Review

**The problem:** Self-review doesn't work. An agent that writes code then reviews
its own code will find what it expects to find. It wrote the code intending it to
work, so it reads the code and concludes it works. This is the same cognitive bias
humans have — the author is the worst reviewer.

**Our answer:** Adversarial review with institutional distrust.

On Tier 1 platforms (Claude Code, Codex), the spec reviewer and quality reviewer
are separate subagents with fresh context. They receive the task specification and
the implementation. They do NOT receive the implementer's self-review or description.

The spec reviewer's prompt explicitly says: "The implementer finished suspiciously
quickly. Their report may be incomplete, inaccurate, or optimistic. You MUST verify
everything independently." This adversarial framing forces the reviewer to read
the code rather than trust the description.

On Tier 2 platforms without subagents, the same adversarial prompts apply — the
agent reviews its own work but with explicit instructions to be skeptical of its
own claims. Less effective than separate subagents, but significantly better than
uncritical self-review.

---

## Why Extensions Are Judgment, Not Knowledge

**The problem:** Every framework that encodes framework knowledge in static files
faces the same decay problem. Next.js 14 patterns become wrong in Next.js 15.
React class component patterns become wrong when hooks arrive. You end up
maintaining documentation for every framework — a losing game against the
framework teams who have dedicated doc writers.

**Our answer:** Extensions encode two things:

1. **Opinionated judgment that changes slowly.** "Prefer server components in Next.js.
   Don't use useEffect for data fetching. Don't add `use client` to every component."
   These opinions are stable across minor versions. They're the wisdom that official
   docs don't provide because official docs describe features, not opinions about when
   to use them.

2. **Anti-patterns from stale training data.** "Don't use `getServerSideProps` — that's
   Pages Router, the old pattern. Don't use `class MyComponent extends React.Component` —
   that's pre-hooks React." These corrections address the specific failure mode of LLMs:
   they were trained on years of Stack Overflow answers and blog posts that represent
   OLD best practices. Extensions tell the agent what NOT to do.

What extensions explicitly do NOT encode: API specifics, method signatures, configuration
option names, version compatibility details. These change fast and are better served by
MCP connections to official documentation (future version) or by the agent's own training
data plus web search for current details.

This keeps each extension at roughly 15-20 files and 1,500-2,000 lines — small enough
that a framework expert can maintain it, and small enough that context windows aren't
overwhelmed.

---

## Why Platform Portability Matters

**The problem:** Many frameworks lock into a single platform. Superpowers works on
3 platforms but most others target only Claude Code. The AI coding tool landscape
is fragmented and evolving fast. Locking into one platform means your methodology
dies when the platform changes or a better one arrives.

**Our answer:** Two-tier platform model.

Tier 1 (subagent support): Claude Code, Codex. Full power — fresh subagent per task,
adversarial review with separate reviewers, parallel execution, git worktrees.

Tier 2 (slash commands / system prompts): Cursor, Copilot, Windsurf, Gemini CLI,
and 15+ others. Same workflows, same skills, same gates — but sequential execution
and self-review instead of subagent dispatch.

The framework never fails on Tier 2. It degrades gracefully — parallel becomes
sequential, separate reviewers become self-review with adversarial prompts,
worktrees become standard branches. The quality gates still run. The TDD skill
is still mandatory. The constitution is still always loaded.

This portability comes from a design decision: workflows reference skills by name,
not by platform mechanism. The platform translates. A workflow step that says
"dispatch fresh subagent" becomes "execute sequentially with context reset" on
Tier 2. The skill doesn't know which platform it's on.

---

## Why Bundles Group Related Skills

**The problem:** Building software isn't only about code. UX design, product
strategy, game design, data science — each is a discipline with its own
structured process, artifacts, and evaluation criteria. These aren't just
"thinking frameworks" you can encode as reference files. They're processes
with sequence, depth, and real work products.

We initially tried to handle this with "methodology packs" that enriched
existing skills with deeper references. But a UX design process in ARCHITECT
mode isn't a "deeper reference" — it's a 5-phase discovery process that
produces personas, journey maps, and a pain point inventory. That's not a
nudge to an existing skill. That's its own process with its own skills.

**Why not extensions?** Extensions are technology-specific. UX design applies
whether you build in React or Flutter. If you put UX guidance into `@sage/react`,
Vue users lose it. The litmus test holds: "If I switch my tech stack, does this
still apply?" Yes → playbook. No → extension.

**Why not skills?** A skill is atomic — one job, 2-5 minutes. A UX discovery
process has 5 phases, 3 artifacts, and takes 30-60 minutes in ARCHITECT mode.
Skills are building blocks. Playbooks are structured processes.

**Why not sub-workflows?** A UX process touches discovery, specification,
planning, AND review — four different workflow phases. It's not one sub-workflow
inserted at one point. It's a cross-cutting discipline that weaves into
multiple phases of the main workflow.

**Our answer:** Playbooks — a new module type that contains its own
discipline-specific skills, integrates at defined workflow phases, and respects
the adaptive weight model (light in BUILD, full in ARCHITECT).

The key architectural decisions:

- **Playbooks have their own skills.** `ux-discovery`, `ux-specify`,
  `ux-heuristic-review` are real skills that satisfy the skill contract.
  They just live inside the playbook rather than in the core capabilities directory.

- **Integration points, not insertion points.** Playbooks declare which
  workflow phases they touch and whether they run "alongside" or "after"
  the core skill at that phase. The workflow executor weaves them in.

- **Multiple playbooks compose.** When both UX and product playbooks are
  active, their skills run in sequence at each integration point. Each
  enriches the output of the previous one. No conflicts.

- **Areas split naturally.** Security has both a playbook (`play-security`:
  threat modeling, risk assessment — tech-agnostic) and a domain extension
  (`@sage/security`: OWASP patterns — web-specific). The playbook decides
  WHAT threats to model. The extension decides HOW to prevent them in the
  specific stack.

---

## Why We Test With Pressure, Not Just Correctness

**The problem:** Traditional tests verify that skills work when the agent follows
them. But the real failure mode is agents NOT following them — rationalizing why
this particular case is an exception, finding creative interpretations that
technically satisfy the letter while violating the spirit.

**Our answer:** Pressure tests from Superpowers' TDD-for-skills methodology.

Each pressure test is a scenario designed to tempt the agent into cutting corners.
"It's a simple change" (skip TDD). "The deadline is tight" (skip process). "I
already wrote the code" (tests-after instead of tests-first). "It's just a
refactor" (skip verification).

The test documents what the agent SHOULD do and what it ACTUALLY does. If the
agent finds a rationalization that the skill doesn't counter, the skill has a
gap. We close the gap, add the rationalization to the counter-table, and re-test.

This is RED-GREEN-REFACTOR applied to documentation:
1. RED: Watch the agent fail without the skill (or with a gap in the skill)
2. GREEN: Fix the skill to address the failure
3. REFACTOR: Find new rationalizations, close them, re-test

The pressure tests are the most important tests in the framework. Contract
validators catch structural problems. Pressure tests catch behavioral problems —
which are the ones that cause real bugs in real projects.

---

## Why Progressive Disclosure for Skills

**The problem:** Anthropic's Skills Guide quantifies the cost: every skill's
metadata (~100 tokens) loads into the system prompt at startup. If you have
16 skills with 10 YAML fields each, that's 1600+ tokens of metadata before
anything useful happens. The context window is a public good shared between
system prompt, conversation history, skill instructions, and the actual task.

**What we learned:** Anthropic uses a three-level loading model: Level 1
(YAML frontmatter, always loaded, ~100 tokens), Level 2 (SKILL.md body,
loaded when triggered), Level 3 (referenced files, loaded as needed). They
explicitly say: "Claude is already very smart — only add context it doesn't
already have."

**Our answer:** Split skill frontmatter into two parts. The YAML block
(name, description, version, modes) is what Claude reads for discovery — ~100
tokens per skill. Everything else (cost-tier, activation, tags, inputs, outputs,
requires) moves to a `<!-- sage-metadata -->` HTML comment block that Sage
tooling reads but Claude's system prompt ignores.

For packs, the same principle applies through token budgets: L1 packs get
3,500 tokens, L2 gets 5,000, L3 gets 1,500. The `sage-check-pack.sh` tool
enforces these budgets. Every token must earn its place.

The rule for pack content: "Does Claude really need this explanation? Can I
assume Claude knows this? Does this paragraph justify its token cost?" If the
answer is no, cut it.

---

## Why Trigger Phrases in Descriptions

**The problem:** A skill with a description like "Guided elicitation that
produces high-quality specifications" tells a human what the skill does. But
Claude doesn't choose skills by understanding concepts — it matches against
trigger phrases. If no one says "guided elicitation" in conversation, the
skill never activates.

**What we learned:** Anthropic's guide is emphatic: the description MUST include
specific phrases users actually say. Their examples always end with "Use when
user says..." followed by 3-5 natural-language triggers. They also require
third-person voice because the description is injected into Claude's system
prompt, and first-person creates inconsistency.

**Our answer:** Every Sage skill description now follows the pattern:
"[What it does in third person]. Use when [situations and user phrases]."
Example: "Guided specification through 3 focused question rounds. Use when
the user wants to add a feature, build something new, or says 'add', 'build',
'create', 'implement'."

This is the single highest-impact change from the Anthropic guide. A skill
with perfect instructions but a vague description is a skill that never loads.

---

## Why Deterministic Gate Scripts

**The problem:** Gate 5 (Verification) used to say: "Run all tests. Show the
output. Prove it works." This is a language instruction that requires Claude to
interpret "run all tests" — figure out the test runner, construct the command,
execute it, parse the output, and determine pass/fail. Every step is a point
where interpretation can go wrong.

**What we learned:** Anthropic's Skills Guide explicitly recommends: "Prefer
scripts for deterministic operations. Code is deterministic; language
interpretation isn't." They cite the official Office skills as examples —
validation is done by scripts, not language instructions.

**Our answer:** Three bash scripts in `core/gates/scripts/` that handle the
deterministic parts of quality gates:

- `sage-verify.sh` — auto-detects test runner (vitest, jest, pytest, flutter
  test, go test), runs all tests, checks the build compiles, scans for
  TODO/FIXME markers. Returns exit code 0/1.

- `sage-hallucination-check.sh` — verifies relative imports resolve to real
  files, checks packages exist in package.json, runs TypeScript compilation
  check, detects common phantom APIs (useServer, Pages Router in App Router).

- `sage-spec-check.sh` — extracts task spec from plan file, verifies all
  listed files exist, checks test files exist for each source file.

The gate files now say: "ALWAYS run the script first. Language-based checking
is supplementary." The script handles WHAT exists and passes; Claude handles
WHETHER the code is semantically correct. Clean separation of deterministic
verification from judgment-based review.

---

## Why Degrees of Freedom (MUST / SHOULD / MAY)

**The problem:** Our skill Rules sections used to mix critical safety rules
with style preferences in a flat list of NEVER/ALWAYS bullets. "NEVER skip TDD"
(violation = untested code) sat next to "ALWAYS show progress between tasks"
(violation = the user wonders what's happening). An agent treating both with
equal weight either over-constrains (paralyzed by style rules) or under-constrains
(rationalizing past safety rules because other rules are flexible).

**What we learned:** Anthropic's guide introduces "degrees of freedom" — high
freedom (multiple valid approaches), medium freedom (preferred path), low
freedom (exact instructions, no deviation). They use the analogy: narrow bridge
with cliffs vs. open field with no hazards.

**Our answer:** Three-tier freedom labels in every skill's Rules section:

- **MUST** (low freedom): Violation causes bugs, lost work, or security issues.
  "MUST NOT skip TDD." "MUST update the plan file after each task."

- **SHOULD** (medium freedom): Violation causes suboptimal but working results.
  "SHOULD follow existing conventions." "SHOULD show progress between tasks."

- **MAY** (high freedom): Context determines the best approach.
  "MAY split a commit into smaller commits." "MAY skip final review for 1-2
  task plans."

The decision test: if deviation causes a bug or security vulnerability, use MUST.
If deviation produces suboptimal but working code, use SHOULD. If it's genuinely
a matter of preference, use MAY. This gives agents clear signal about where they
have room to adapt and where they absolutely do not.

---

## Why Old Patterns in Collapsible Sections

**The problem:** Anti-patterns tell agents what NOT to do. But agents trained
on years of Stack Overflow answers sometimes generate deprecated code that
they don't recognize as deprecated. Saying "don't use getServerSideProps"
corrects the behavior. But agents also benefit from knowing WHAT to use instead —
a migration table that maps old pattern → new pattern.

Including full migration tables in the main anti-patterns content would bloat
the token budget. Not including them means agents encountering deprecated code
in existing projects have no quick reference.

**What we learned:** Anthropic's guide recommends an "old patterns" section
using HTML `<details>` tags for deprecated approaches. The content is there
when needed but collapsed by default, so it doesn't consume attention (or
tokens, in Claude's case) when the agent is working on new code.

**Our answer:** Packs with significant deprecated API surfaces now include
collapsible "Old Patterns (Deprecated Reference)" sections at the end of
their anti-patterns files. Each contains a migration table mapping deprecated
API → current replacement.

Currently applied to: @sage/nextjs (Pages Router → App Router, Class →
Hooks), @sage/react-native (Bridge → New Architecture, Navigation v4 → v7),
@sage/react (Class Components → Hooks, Legacy Context → createContext).

These sections are reference material, not behavioral instructions. The
anti-patterns tell agents what to avoid; the old patterns sections help
agents migrate existing code when they encounter it.

---

## Why Visible Orchestration

**The problem:** Superpowers makes skills trigger automatically — "you don't
need to do anything special, your agent just has Superpowers." This is elegant
for experienced developers who trust the process. For beginners, it's opaque.
If the brainstorming skill doesn't trigger, the beginner doesn't know it
exists. If it does trigger, the beginner doesn't know why or what comes next.

BMAD solves this with `/bmad-help` — a single command that tells you exactly
what to do next. But BMAD's orchestration is heavy (21 agents, 50+ workflows)
and the help system has to navigate all that complexity.

**Our answer:** Visible but not burdensome orchestration. Three mechanisms:

1. **`sage-help` skill:** Reads `.sage/progress.md`, determines current state,
   gives ONE specific next action in 3-8 lines. Not documentation — direction.

2. **`onboard` skill:** First-run setup that makes the invisible visible. Shows
   the detected stack, selected packs, and generated configuration. The user sees
   what Sage will do before it does it.

3. **Checkpoints in workflows:** Three mandatory human approvals (spec, plan,
   result) are SHOWN, not hidden. The agent says "Here's the spec. Ready to
   plan, or adjustments needed?" — making the process step explicit.

The principle: a beginner should never wonder "what is happening?" or "what
should I do next?" The process is visible at every step, but the user only
needs to say "go" to proceed. Show the rails, don't require driving the train.

---

## Why Three Rings (Core / Skills / Runtime+Develop)

**The problem:** The original repo had 14 top-level directories mixing engine
internals (skills, workflows, gates) with extensibility points (packs, playbooks)
with contributor tools (templates, tests, contracts) with execution plumbing
(tools, platforms, CLI). A new contributor saw everything at once and couldn't
tell where to start. A user saw framework internals they'd never touch.

**What we learned:** Werner Vogels' principle — each component should have one
clear owner and one clear purpose. Dave Cutler's principle — minimize moving
parts visible to the user. The user sees CLAUDE.md and .sage/. The contributor
sees develop/. The framework team sees core/. Nobody needs to see everything.

**Our answer:** Three concentric rings.

**Ring 1 — Core:** The engine. 18 capabilities, 3 workflows, 6 gates,
constitution, agents, context loader. Changes rarely and deliberately. Framework
team maintains this. The user never touches it. Contributors rarely touch it.

**Ring 2 — Packs and Playbooks:** The extensibility surface. This is where
community value grows. Packs provide framework-specific judgment. Playbooks
provide discipline-specific processes. Both are top-level because they're the
primary value proposition — a developer browsing the repo sees skills/@sage/ immediately
and knows "this has guidance for my framework."

**Ring 3 — Runtime and Develop:** Supporting infrastructure. Runtime holds
execution plumbing (tools, MCP client, platform adapters). Develop holds
contributor tooling (contracts, guides, templates, validators). Docs holds
philosophy. These serve the rings above them.

The mental model is three sentences: Core is the engine. Packs and Playbooks
are the extensions. Everything else supports them.

---

## Why Packs Are Judgment, Not Knowledge (The Three-Layer Information Model)

**The problem:** Every framework that encodes API reference in static files
fights a losing battle against staleness. Next.js 15 docs become wrong when
Next.js 16 ships. If the pack says "use `revalidateTag()`" and the API changes,
the pack gives confidently wrong advice.

Meanwhile, MCP servers like Context7 provide current API reference on demand.
And the LLM's own training data covers language syntax and basic patterns.
So what does the pack actually need to provide that neither MCP nor training
data covers?

**The answer:** Judgment. The opinionated "when to use this, when to avoid that,
why your instinct will be wrong" layer.

This insight led to the three-layer information model:

- **MCP / Context7 = Knowledge:** Current API syntax, version-specific details,
  configuration options. Changes every release. Delivered via tool calls.

- **Packs = Judgment:** When to prefer server components over client components.
  Why useEffect for data fetching is wrong in App Router. Which patterns from
  training data are stale. Changes slowly (major framework versions). Delivered
  via CLAUDE.md principles and .sage/skills/@sage/ detail files.

- **Gates = Verification:** Do tests pass? Do imports resolve? Is there mobile
  overflow? Evidence-based, deterministic. Changes rarely. Delivered via bash
  scripts with exit codes.

Each layer has a different update cadence, delivery mechanism, and failure mode.
Collapsing them — trying to make packs do knowledge (API reference) or gates do
judgment (design quality) — creates the wrong tool for the job.

Pack rules are persuasion at the moment of decision. They work because LLMs
respond well to reasoning: "Your training data will push you toward X because
7 years of Stack Overflow answers show that pattern. Do Y instead because Z."
This isn't a lint rule. It's a compelling argument that changes the agent's
behavior at the decision point.

---

## Why Context-Aware Loading (Threshold-Based CLAUDE.md Generation)

**The problem:** Anthropic says keep CLAUDE.md under ~500 lines. BMAD learned
this the hard way — their agents consumed 67%+ of the context window during
activation. One developer measured their CLAUDE.md optimization and achieved a
54% reduction by separating always-loaded triggers from on-demand skill content.

But pack content IS valuable. When it's in context, the agent follows framework
rules correctly. When it's not, the agent reverts to training data instincts
(which are often wrong for modern frameworks). The question isn't "should we
load pack content" — it's "how much, and when."

**What we learned from BMAD v6:** Their "step-file architecture" achieved a
74-90% token reduction by sharding workflows into per-step files loaded fresh
when needed. The key insight: artifacts live on disk. When you need one, read
the file fresh — don't rely on it persisting in degrading conversation memory.

**What we took:** The artifact-on-disk principle. The "read before you act"
instruction pattern. Phase-appropriate context loading.

**What we didn't take:** Session boundaries as the context management mechanism
(breaks BUILD mode's single-session flow). Sharded workflow step files (our 3
workflows are already lean). The module/agent/sidecar complexity (proportional
to a problem we don't have).

**Our answer:** Threshold-based mode selection. the context loader measures total pack
content and automatically chooses:

- Under 10K tokens → inline everything (proven to work, no added complexity)
- 10K-25K tokens → principles always loaded, details on disk with file references
- 25K-40K tokens → compressed principles, everything else on disk
- Over 40K tokens → same + warning to prune unused packs

The plan skill generates tasks with "Read first" fields naming which pack files
to read before implementing — surgical context loading at the moment of decision.

This means the agent always knows the MUST rules (principles in CLAUDE.md) and
loads the HOW details (patterns, examples, migration tables) only when working
on code that needs them. Pack guidance that's irrelevant to the current task
doesn't consume context that could be used for reasoning.

**Evolution (v1.0):** The threshold-based approach evolved into a
three-layer architecture formalized in
`core/capabilities/context/context-loader/SKILL.md`:

- Layer 1 (always-on): Process constitution + commands (~700 tokens)
- Layer 2 (on-demand): Navigator, skills, references — loaded when needed
- Layer 3 (strategy): Decision framework for platform generators

Platform generators read the strategy and produce platform-specific output.
The principle remains the same: load the minimum context needed for the
current action. The mechanism became cleaner — generators follow explicit
rules rather than measuring token thresholds at install time.

---

## Why "Read Before You Act" in Task Plans

**The problem:** In summary and compact modes, detailed pack content lives on
disk, not in the CLAUDE.md. The agent needs to read the right files at the right
moment. But "read relevant pack files" is vague — which files? When?

If the agent reads all pack files at session start, we've recreated the context
bloat problem. If it never reads them, the guidance doesn't apply. The timing
must be precise: read the Next.js patterns before writing Next.js code, not
before and not after.

**What we learned from BMAD v6:** Their step files explicitly name which
artifacts to load at each step: "Before implementing, read architecture.md
and the relevant story file." This is specific, auditable, and survives
compaction — because the instruction is in a file on disk, not in degrading
conversation memory.

**Our answer:** The plan skill generates tasks with a "Read first" field:

```
- [ ] Task 3: Build auth middleware
  - Read first: .sage/skills/@sage/nextjs/patterns/nextjs-patterns.md (middleware),
    .sage/skills/@sage/stack-nextjs-supabase/integration/stack-integration.md
  - Files: src/middleware.ts
  - Action: ...
```

This solves three problems: the agent knows exactly what to read (specific file
paths, not vague "relevant patterns"). The instruction survives compaction (it's
in the plan file on disk). And it's auditable — you can see what guidance the
agent was told to consult for each task.

The CLAUDE.md also includes a "Context Refresh" section that tells the agent to
re-read relevant pack files when starting implementation. This is the fallback
for when the plan doesn't specify files — the agent uses its judgment about
which packs are relevant, guided by the principles already in context.

---

## Why Deliverable Types (Growing Beyond Code)

**The problem:** Sage was built for coding — TDD, git commits, import
verification, test runners. But the process underneath (understand → define →
plan → produce → verify) is universal. A product manager writing a PRD follows
the same process. So does an SEO specialist auditing a website, a content
strategist creating a content calendar, or a security analyst producing a
threat model. The process fits. The assumption that "produce = write code"
doesn't.

**What we considered and rejected:**

*Abstract workflow interfaces (Approach B):* Make the core workflow generic:
UNDERSTAND → DEFINE → PLAN → PRODUCE → VERIFY → DELIVER. Each discipline
implements the abstract phases. The problem: premature abstraction. We have one
working discipline (code) and zero evidence about what PM, SEO, or security
workflows actually need. The abstraction would be shaped by our assumptions,
not by real discipline practitioners. And premature abstraction is worse than
no abstraction — it creates a structure the first real non-code discipline
doesn't fit.

*Workflow variants (Approach C):* Let playbooks substitute the entire
workflow — a PM playbook replaces the code BUILD workflow with a PM BUILD
workflow. The problem: every future core change must be tested against both
the default workflow AND every variant. That's a permanent development tax
for a feature with zero current users. It also creates a detection problem:
if both a UX playbook (enriches code workflow) and a PM playbook (replaces
code workflow) are active, which "wins"?

*Playbooks-as-frameworks (Approach A):* Each discipline playbook builds its
own workflow, gates, and output handling. The problem: Sage stops being a
framework and becomes a naming convention. Each playbook reinvents quality
verification independently. Nothing composes.

**What we built instead:** One field in the spec. `Deliverable: code | document | mixed`.

The insight: the process is already general. The specify skill asks what to
build and why. The plan skill breaks work into tasks. The gates verify quality.
The only code-specific assumption was in HOW tasks execute and HOW gates verify.

For code tasks: TDD → implement → commit → all 6 gates.
For document tasks [DOC]: draft → review against criteria → save → gates 1-2 only.
For mixed: each task marked with its type, appropriate workflow per task.

This is the minimum adaptation that makes Sage work for non-code disciplines
without abstracting prematurely, without creating parallel workflows, and
without making playbooks rebuild framework infrastructure. The plan skill
reads one field and adjusts its task template. The gates read a [DOC] marker
and skip code-specific checks. That's it.

**The strategic vision:**

Phase 1 (active): Enriching playbooks for disciplines that enhance code —
security (threat modeling + OWASP checks), accessibility (WCAG + axe-core),
SEO (audit + fixes), performance (Lighthouse + budgets). These add skills
alongside the code workflow. No deliverable-type changes needed.

Phase 2 (active — evidence confirmed): Non-code playbooks for pure document
disciplines. The product management playbook (4 skills, 3,800+ lines) proved
this works: JTBD analysis, opportunity mapping, user interview design, and
PRDs — all producing document deliverables without touching the code workflow.
Key learnings from building the first non-code playbook:

- **Playbook phases are discipline-specific.** The PM playbook organizes
  skills into Discovery → Planning → Delivery. A UX playbook might use
  Research → Design → Evaluate. A security playbook might use Assess →
  Remediate → Verify. The phase structure lives in the `playbook.yaml`
  manifest, not in Sage core. Each discipline speaks its own language.

- **Skills form chains, not just lists.** In the PM playbook, JTBD produces
  outcomes → opportunity-map assesses which to pursue → PRD defines
  requirements for the chosen opportunity. Each skill's output is the next
  skill's input. The chain validates itself: weak JTBD → weak opportunity
  map → weak PRD. This output-feeds-input pattern is a natural property of
  structured disciplines and doesn't need framework enforcement.

- **Research skills feed back, not just forward.** The user-interview skill
  sits alongside the chain, not at a fixed position. It takes low-confidence
  claims from ANY phase and produces research plans to validate them. Findings
  flow back to update the JTBD or opportunity map. This feedback loop is
  inherent to PM work and emerged naturally from the skill design.

- **Reference tiers may be needed as playbooks multiply.** The PM playbook
  has 9 reference files. Some (research-methods.md, interview-methodology.md)
  would be useful to other playbooks (UX design also conducts interviews).
  We've identified three potential tiers — shared across playbooks, playbook-
  level, skill-specific — but deferred building the shared tier until a second
  playbook actually needs the same reference. Build what evidence demands.

Phase 3 (if evidence demands): The playbook contract gains
`integration-mode: enriches | replaces`. Enriching playbooks add skills
alongside the workflow. Replacing playbooks substitute the production phase.
Only built when multiple non-code playbooks exist and the enriching model
proves insufficient.

The principle: **build what evidence demands, not what theory predicts.** Each
phase is triggered by real usage, not by architectural speculation.

---

## Why Sage Is a Process Framework, Not a Coding Framework

The deepest architectural principle, arrived at through building 18 capabilities,
12 packs, 3 playbooks (including 1 non-code), and running the Prep homepage
redesign end-to-end:

**Sage encodes a process for producing quality output with AI assistance.**

The process: understand the context → define what to produce → plan the work →
produce it with discipline → verify quality → deliver. This process applies
whether the output is a React component, a PRD, a competitive analysis, or a
security audit report.

The product management playbook proved this concretely: a PM using Sage moves
through understand (JTBD analysis) → plan (opportunity mapping, research
design) → define (PRD) → verify (validation planning). The same process, no
code involved. The discipline-specific parts live in playbook skills and
references, not in the core framework.

The code-specific parts (TDD, git, import verification, test runners) are
specializations of the general process, not the process itself. They live in
the task templates and gate scripts, not in the workflow or the process model.
A new discipline plugs in by providing its own task template (what "produce"
means in that discipline) and its own verification criteria (what "quality"
means for that output type).

Packs provide judgment for technology choices. Playbooks provide process for
discipline-specific work. The deliverable type field connects them to the
core workflow. Three extension points, one process, any output type.

---

## Why a Project Journal (State Management for Long-Running Work)

**The problem:** In a long-running project (weeks or months), artifacts
accumulate. JTBD analyses, opportunity maps, research findings, PRDs, specs,
decision records — after 8 weeks, a project might have 30-50 files. The agent starting
session 10 faces two questions it can't answer cheaply: "Which of these files
matter right now?" and "What happened since session 1 that I need to know?"

BMAD's approach — generate individual files for every epic, user story, and
artifact — produces the right content but the wrong lifecycle. After 3 months,
a team has 200 files with no way to know which are current, which are
superseded, and which are historical reference. The file system becomes
a graveyard of equally-weighted documents.

Plan.md with checkboxes (Principle #6) solves task-level state: what's done,
what's next. But it doesn't solve project-level state: what decisions have
been made, what was learned, how the project's understanding evolved.

**What we considered and rejected:**

*Checkpoint artifacts:* Discrete summary documents at milestones. Creates file
proliferation — the same problem we're solving. Each checkpoint is another
file to track.

*Complex state management system:* Automated archiving, file indexing, knowledge
graphs. Over-engineered. Convention with templates solves 80% of the pain with
10% of the complexity.

*Richer plan.md:* Embed project history into the task list. Mixes two concerns
(task tracking + project history) into one file that does neither well.

**What we built instead:** A project journal — one file with two parts.

The **living index** (top of journal.md) is a maintained snapshot of what
artifacts exist and their current status: Active (being worked on), Reference
(done, still relevant), or Archived (superseded). This is the agent's "page
table" — at session start, read the index to know what to load.

The **change log** (bottom of journal.md) is an append-only chronological
record. Each entry records a significant event: what was produced, what changed,
what was learned, what's next. Entries are short (5-8 lines). The log is an
index that points to artifacts, not a narrative that duplicates them.

This mirrors the git model: HEAD (living pointer to current state) plus commit
history (append-only record of how we got here). One mechanism, two functions.

**The two-folder convention:**

Project artifacts live in two folders organized by purpose:

`docs/` — WHY: analyses, decisions, evidence, rationale. Project-level
artifacts that inform multiple features. JTBD analyses, opportunity maps,
research findings, decision records.

`work/` — WHAT: deliverables organized by initiative. PRDs, specs,
implementation artifacts. Scoped to a specific unit of work.

Two folders. The journal indexes both. Simple enough to remember, structured
enough to navigate. A flat `docs/` folder works because project-level
artifacts are few (under 20). `work/` uses numbered subdirectories because
per-initiative artifacts are naturally grouped.

**Why convention, not tooling:** The journal is maintained by the agent
following a template, not enforced by scripts. When a skill completes, the
agent appends a change log entry and updates the living index. No validation
gates, no automated archiving. This keeps the mechanism flexible — different
project management styles can adapt the convention without breaking tooling.

The convention is documented in `docs/philosophy/project-state-convention.md`.
The template is at `develop/templates/journal-template.md`.

---

## Why the PRD Is the Handoff Artifact (Bridging Problem and Solution Space)

**The problem:** The PM playbook produces PRDs in the problem space (WHAT and
WHY). The code workflow operates in the solution space (HOW). Between them is
a translation gap: the PRD says "users want personal spending thresholds" but
doesn't say "build a batch job computing weighted medians stored in Redis."
How does Sage bridge this gap?

**What we considered and rejected:**

*BMAD's epic/story breakdown:* Break the PRD into epics and user stories, each
with its own file, each independently deliverable. The advantage: incremental
delivery (ship story by story). The disadvantages: file proliferation (the
BMAD problem we already solved), fragmented context (bad for AI — each story
is a partial view), and emergent architecture (story N might invalidate
story 1's technical approach). Sage optimizes for engineering coherence and
AI-assisted work, where the agent benefits from seeing the full picture.

*Detailed technical spec as a separate playbook skill:* A new "technical spec"
skill in the PM playbook that translates PRDs into architecture documents.
Premature — we haven't proven this gap exists in real usage. The code
workflow's existing specify skill already produces technical specs.

**What we built instead:** The PRD IS the handoff artifact. The code workflow's
specify skill detects PRDs and uses them as input, skipping elicitation
(the requirements are already defined). The specify skill's job becomes:
resolve open questions + design technical architecture addressing each
requirement.

**Three conventions bridge the gap:**

*1. Lean task templates (from Superpowers, refined by advisory board):*

```markdown
[ ] Task N: [Title]
    Read first: [specific file sections]
    Done: [1-2 line acceptance criteria]
    Scope: [what this task does NOT touch]
```

Advisory board consensus (Torvalds, Uncle Bob, Gamma): tasks should be thin
pointers, not self-contained micro-specs. "Read first" loads context. Copying
content into tasks duplicates information and creates staleness when the
source changes. Three fields beyond the title are sufficient.

*2. Value milestones (from BMAD's incremental delivery, simplified):*

```markdown
## Milestone 1: [What's demoable]
[ ] Task 1-3...
🔒 CHECKPOINT: [What to verify]
```

Groups tasks into shippable value increments. If the team runs out of time
after milestone 2, they have useful improvements shipped and 1 deferred.
Milestones provide BMAD's incremental delivery benefit without the story
file proliferation.

*3. Spec update protocol (from Spec-Kit's living spec, with hierarchy):*

When implementation reveals the spec needs to change:
- Pause → classify: implementation-level (HOW changed) or domain-level
  (WHAT/WHY changed)
- Implementation-level → update spec, log in journal, continue
- Domain-level → flag to PM, pause implementation, await PRD revision
- After spec update → review remaining tasks for impact, adjust if needed

Strict hierarchy of truth (Knuth): PRD defines WHAT (stable — PM controls).
Spec defines HOW (living — engineering controls, changes logged). Plan defines
ORDER (regenerable from spec). Code implements plan (verified by gates).
Information flows one direction. Backward flow is flag-and-escalate.

**Customer-centric requirements format:**

Each requirement in the PRD uses a format designed to keep the customer
perspective front and center throughout the chain:

```markdown
#### R1: [Title] (Priority — Opp: [score])
**Job story:** When [situation], [performer] wants to [outcome], so that...
**Why this priority:** [Evidence-based justification]
**Delivers value independently:** [Yes — users can... / No — enables R2, R3]
**Acceptance scenarios:**
1. Given..., when..., then...
2. Given [edge case]..., when..., then...
```

The job story leads because the requirement exists to serve a customer need.
"Why this priority" forces evidence-based justification. "Delivers value
independently" maps directly to implementation milestones — requirements
that deliver value alone are natural ship points. The Given/When/Then
scenarios are directly translatable to test cases.

**Additional conventions adopted from Spec-Kit and BMAD:**

*Inline clarification markers (from Spec-Kit):* Unresolved decisions are
marked ⚠️ NEEDS CLARIFICATION (Q[N]) inline where the ambiguity lives, not
just in the Open Questions table. A developer reading a requirement sees
the uncertainty immediately instead of discovering it in a different section.

*Functional requirements alongside job stories (from Spec-Kit):* System-level
constraints (performance thresholds, accuracy targets, processing windows)
are written as "System must [capability]" statements, separate from job
stories. Job stories describe what users experience. Functional requirements
constrain how the system delivers it.

*No forward dependencies in plan tasks (from BMAD):* Tasks must be completable
based only on previous tasks. A task must never require a future task to
function. This prevents blocked work and maps to BMAD's strict story
dependency rule.

*Task sizing for AI sessions (from BMAD):* Plan tasks should be sized for
what an AI agent can accomplish in a single session. If a task requires more
context than fits in one session, split it. This is guidance, not a hard rule.

*Edge cases as a cross-cutting section (from Spec-Kit):* Boundary conditions
that span multiple requirements get their own section, rather than being
forced into individual requirement scenarios.

**Human readability as a design principle:**

Sage artifacts are read by both humans and agents. PRDs are shared with
stakeholders. JTBD analyses are discussed in meetings. Opportunity maps
inform leadership decisions. Research briefs are reviewed by research teams.

Write for the human reader first: clear language, customer perspective,
evident reasoning. A PM, designer, or stakeholder should understand any
Sage artifact without knowing what Sage is. The structure simultaneously
serves agents: Given/When/Then translates to tests, inline markers flag
unresolved decisions, "Delivers value independently" maps to milestones,
traceability tables enable automated checking.

The principle: **artifacts should be as useful in a meeting as they are in
a context window.**

## Why `docs/` and `work/` (Not `reasoning/` and `features/`)

Sage generates files throughout a project's lifecycle. These files need names
that every team member understands instantly. We chose terms by applying a
simple test: can a new person guess what's inside WITHOUT reading documentation?

- `reasoning/` → **`docs/`**. "reasoning" is a cognitive process, not a container.
  Nobody says "put it in reasoning." Everyone says "put it in docs."
- `features/` → **`work/`**. Not everything is a feature — redesigns, migrations,
  refactors, research projects all live here. "work" is the broadest accurate term.

Advisory board was unanimous: name things by what they contain, not by the
cognitive process that produced them. (Torvalds: "I `ls` the folder and I know
what's in there." Ritchie: "short, lowercase, obvious." Evans: "Use the words
people naturally say.")

## Why `brief.md` / `spec.md` / `plan.md`

Three files per initiative, named for how people naturally refer to them:

- **`brief.md`** — WHAT to build and WHY. The requirements, job stories,
  acceptance scenarios. People say "I wrote the brief" not "I created the PRD."
  (PRD is jargon that product managers know but designers and engineers may not.)
- **`spec.md`** — HOW to build it. Technical design, component architecture,
  data model, resolved decisions. "Check the spec" is universal.
- **`plan.md`** — In what ORDER. Milestones, tasks, checkboxes for progress.
  "Look at the plan" needs no explanation.

## Why `YYYYMMDD-slug` for Work Folders

Three-digit prefixes (`001-`, `002-`) suggest sequential ordering that doesn't
match reality — initiatives are parallel, revisited, and abandoned. Date prefixes
solve three problems: (1) chronological sort for free, (2) support for revisiting
(`20260315-baseline` then `20260901-baseline-v2`), (3) immediate context about
when work started.

## Why "Decision" Not "ADR"

Architecture Decision Records are valuable. The abbreviation is not. "ADR" requires
a glossary entry for anyone outside senior engineering. "Decision" is what everyone
calls it: "What was the decision on auth?" The format (context → options → choice →
consequences) is identical. Only the label changed.

## Why Skill Prefixes in `docs/`

Files in `docs/` use the producing skill's name as prefix: `jtbd-product-analysis.md`,
`ux-writing-voice-and-tone.md`, `decision-auth-provider.md`. This provides natural
alphabetical grouping without subfolders — all JTBD analyses cluster, all decisions
cluster. When the folder grows, the prefixes act like virtual subdirectories.

## Why the Sage Navigator (Not a Rigid Orchestrator)

Every framework we studied solves orchestration as a routing problem: user says
something → framework routes to the right skill. Superpowers enforces compliance
via session hooks. BMAD routes through an orchestrator agent. Spec-Kit requires
explicit commands. AI Dev-Kit uses phase templates.

Sage chose a different approach: **judgment over routing**. The sage-navigator
doesn't just detect "is this a BUILD or FIX task?" — it reads the full project
state, assesses what exists and what's missing, and recommends the path that
produces the best outcome. This includes proactive gap detection: if a user asks
to "build the login page" but there's no brief or spec for a complex auth system,
the navigator recommends creating them — explaining the value, respecting the
user's right to decline.

The intent spectrum (UNDERSTAND → ENVISION → DELIVER) replaced rigid modes as
the primary routing mechanism because Sage is not just for code. A JTBD analysis
is UNDERSTAND, not BUILD. A voice & tone guide is ENVISION, not ARCHITECT.
The three engineering modes (FIX/BUILD/ARCHITECT) remain as shortcuts but are
no longer the primary way the navigator thinks about tasks.

## Why Two Layers (Constitution + Navigator)

The process constitution is a thin, always-on rule that ensures Sage is never
bypassed. Five rules, ~200 words, loaded before every response. It doesn't
contain workflow logic — it just ensures the agent always checks for Sage
skills, reads project state, and uses Sage's planning instead of the
platform's default.

The navigator is a thick, intelligent skill that contains all the judgment:
intent detection, scope assessment, gap analysis, workflow recommendation.
It activates when needed, not on every response.

This separation means: the constitution is cheap (always in context, minimal
tokens) and the navigator is smart (loaded on demand, substantial logic).
Neither alone is sufficient — the constitution without the navigator just
enforces "use skills" without knowing which ones. The navigator without the
constitution could be bypassed when the platform's default behavior kicks in
before the skill activates.

## Why "Navigator" Not "Master" or "Orchestrator"

The name reflects the relationship with the user. A navigator reads the
terrain, suggests the best route, warns about hazards — but the user decides
where to go. "Master" implies hierarchy. "Orchestrator" implies control.
"Navigator" implies partnership. Sage advises. The user decides.

## Why Proactive Gap Detection

Most frameworks only do what you ask. Sage does what you ask AND recommends
what you haven't asked for but would improve the outcome. If Sage has a
JTBD skill and the user is about to build a feature without understanding
user needs, staying silent would be a disservice.

The calibration: proportional to scope. Small tasks get no recommendations.
Medium tasks get one suggestion ("a quick spec would help"). Large tasks
get the full analysis ("here's the discovery → design → delivery path").
The user always has the right to decline. Sage always has the obligation
to suggest what's right.
