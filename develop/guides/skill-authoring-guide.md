# Skill Authoring Guide

How to create a Sage pack that earns its context tokens.

## Two Paths

**Community Pack** — Shareable pack for a framework or domain. Goes through
full discovery, observation, and validation. Published for everyone.

**Project Overlay** — Customize an existing pack with YOUR team's conventions,
constraints, and preferences. Faster, project-specific, not shared.

Most people should start with a project overlay on an existing community pack.
Only create a community pack when no pack exists for your framework.

## Guided Workflow (Recommended)

The easiest way to build a pack is with the skill builder playbook. It walks
you through every step:

```
Tell your agent: "I want to create a pack for React Query"
→ The pack-builder playbook activates
→ Phase 1: Discovery — what to build, which path, what agents get wrong
→ Phase 2: Sources — gather and filter relevant materials
→ Phase 3: Observe — run prompts, record agent failures (community path)
→ Phase 4: Draft — generate pack files from evidence
→ Phase 5: Validate — run checker, measure improvement
```

See `skills/@sage/skill-builder/` for the full playbook.

## Manual Quick Start

If you prefer to work manually:

```bash
# Community pack: scaffold and build
bash .sage/tools/sage-new-pack.sh my-framework --layer 2
# Edit the generated files
bash .sage/tools/sage-check-pack.sh skills/@sage/my-framework

# Project overlay: create overrides for an existing pack
mkdir -p .sage/skills/@sage/react-query
# Create overrides.md with your project conventions
# Create SKILL.md manifest with type: overlay
```

## Before You Start

Ask yourself two questions:

1. **"Do agents get this wrong without my guidance?"** If agents already handle
   this topic well from training data, your skill adds noise, not value.
   Test this by giving an agent 3-5 prompts in your domain WITHOUT any special
   guidance. If the output is already good, you don't need a pack.

2. **"Is this judgment or knowledge?"** Packs provide opinions that correct
   agent mistakes. They don't provide documentation. If you're explaining HOW
   an API works, that's docs — the LLM can read docs. If you're explaining
   WHEN to use it and WHEN agents use it wrong, that's judgment — pack it.

## Pack Structure

```
skills/@sage/my-framework/
├── SKILL.md manifest                    # Manifest (required)
├── README.md                    # Overview for humans (required)
├── patterns/
│   └── my-framework-patterns.md # Patterns agents should follow (required)
├── anti-patterns/
│   └── my-framework-anti-patterns.md  # Mistakes agents make (required)
├── core/constitution/
│   └── my-framework.constitution-additions.md  # Non-negotiable principles
├── core/gates/
│   └── NN-my-framework.gate.md  # Quality gate (optional)
└── tests.md                     # Test prompts for effectiveness (required)
```

## Writing the Manifest (SKILL.md manifest)

```yaml
---
name: "@sage/my-framework"
description: "One sentence: what agent mistakes this pack corrects"
version: "1.0.0"
license: "MIT"
layer: 2                        # 1=domain, 2=framework, 3=stack

provides:
  skills: []                    # Usually empty — packs provide guidance, not skills
  gates: []                     # Optional gate file names
  constitution-additions: [my-framework.constitution-additions.md]
  templates: []
  agents: []

requires:
  sage-core: ">=1.0.0"
  packs: [web]                  # Layer dependencies (L2 requires L1, L3 requires L2)

activates-in: [fix, build, architect]

activates-when:
  detected: [my-framework]     # Package names in package.json, pubspec.yaml, etc.

framework-version: ">=5.0.0"    # What version this pack targets
last-verified: "2025-03-13"     # When accuracy was last checked
---
```

**Key fields:**
- `layer`: Determines token budget (L1: 1500, L2: 2000, L3: 2500)
- `requires.packs`: Layer dependencies — L2 must list its L1, L3 must list its L2
- `activates-when.detected`: Package names that trigger auto-loading
- `framework-version`: Semver range of the framework version this targets
- `last-verified`: Date of last accuracy check against official docs

## Writing Patterns

A pattern is a "do this" instruction that corrects a specific agent tendency.

### Pattern Anatomy

```markdown
# Pattern: Server Components for Data Fetching

**Why agents get this wrong:** Agents trained on pre-RSC React default to
useEffect + useState for data fetching. In App Router, this creates unnecessary
client components, loses streaming, and adds loading state complexity.

**Do this:**
Fetch data in Server Components using async/await directly:

\`\`\`tsx
// RIGHT — Server Component (default)
export default async function Users() {
  const users = await db.user.findMany();
  return <UserList users={users} />;
}
\`\`\`

**Not this:**
\`\`\`tsx
// WRONG — unnecessary client component for data fetching
'use client';
export default function Users() {
  const [users, setUsers] = useState([]);
  useEffect(() => { fetch('/api/users').then(r => r.json()).then(setUsers); }, []);
  return <UserList users={users} />;
}
\`\`\`
```

### Pattern Rules

1. **Start with WHY agents get it wrong.** This is the most important section.
   Without it, the pattern is just documentation.

2. **Show concrete code.** A code example is worth 100 words of prose.
   Show the right way AND the wrong way side by side.

3. **Be concise.** Each pattern entry should be ~80-120 tokens (3-4 sentences
   + optional code snippet). If you need more,
   you're explaining too much — the agent knows the language, it just needs
   the opinion.

4. **One concept per pattern.** "Use Server Components for data fetching" is
   one pattern. "Use Server Components for data fetching and also here's how
   caching works and also metadata API" is three patterns crammed into one.

5. **Be specific to this framework.** "Write clean code" is not a pattern.
   "Use Server Components by default in App Router" is a pattern. If the
   guidance applies to any framework, it belongs in L1, not L2.

6. **One level deep for references.** All pack content MUST be directly
   accessible from the main patterns file or anti-patterns file. Never
   chain references: patterns.md → advanced.md → details.md. Claude may
   partially read files referenced from other referenced files, resulting
   in incomplete information. If you need supporting detail, put it in a
   `reference/` directory and link directly from the main file.

### Degrees of Freedom

Match instruction rigidity to the task's fragility. Use these labels
consistently in patterns, anti-patterns, and constitution additions:

**MUST / MUST NOT** (low freedom — narrow bridge with cliffs):
Use for fragile operations where deviation causes breakage. Security
rules, data integrity, API contracts, framework-specific invariants.

```markdown
# Example: Low freedom
Server Components MUST NOT import useState or useEffect.
RLS policies MUST be added in the same migration as the table.
```

**SHOULD / SHOULD NOT** (medium freedom — preferred path with guardrails):
Use when a preferred pattern exists but context may justify alternatives.
Architectural guidance, performance recommendations, convention adherence.

```markdown
# Example: Medium freedom
Data fetching SHOULD happen in Server Components when possible.
Error boundaries SHOULD wrap each route segment.
```

**MAY / CONSIDER** (high freedom — open field):
Use when multiple valid approaches exist and context determines the best
choice. Style preferences, optional optimizations, tooling choices.

```markdown
# Example: High freedom
You MAY use Zustand or Jotai for client state; choose based on the
project's existing patterns.
```

The test: if deviation causes a bug or security vulnerability, use MUST.
If deviation causes suboptimal but working code, use SHOULD. If it's
genuinely a matter of preference, use MAY.

## Writing Anti-Patterns

An anti-pattern is a "don't do this" instruction based on observed agent mistakes.

### Anti-Pattern Anatomy

```markdown
# Anti-Pattern: useEffect for Data Fetching in App Router

**What agents do:** Generate client components with useEffect + fetch for data
that could be fetched server-side. This is the #1 agent mistake in Next.js
App Router projects.

**Why agents do this:** Training data contains millions of examples of this
pattern from the Pages Router and pre-RSC React era.

**Why it's wrong:** Creates unnecessary client-side JavaScript, loses SSR/streaming
benefits, requires manual loading and error states, can't use server-only APIs
(database, file system).

**Do instead:** Use Server Components (the default) with async/await. Only add
'use client' when you need interactivity (onClick, useState, etc.).
```

### Anti-Pattern Rules

1. **"What agents do" must be real.** You must have seen an agent actually produce
   this code. Don't list hypothetical mistakes — list observed ones.

2. **"Why agents do this" explains the root cause.** Usually stale training data,
   a common Stack Overflow pattern, or framework defaults that changed.

3. **Keep it concise.** Each anti-pattern entry should be ~60-90 tokens. Anti-patterns are
   they're warnings, not tutorials.

4. **Don't list more than 7 anti-patterns per pack.** If you have more, the skill
   is too broad — split it. Context is finite. The top 5-7 mistakes cover 90%
   of real failures.

## Writing Constitution Additions

Constitution additions are non-negotiable principles that the skill enforces.
They're loaded alongside the project's own constitution.

```markdown
# My Framework — Constitution Additions

## Principles

1. All data fetching MUST happen in Server Components unless the component
   requires client-side interactivity. useEffect for data fetching is forbidden
   in App Router.
2. Route handlers (route.ts) are for webhooks and external API consumers only.
   Internal data fetching uses Server Components, not API routes.
3. ...
```

### Constitution Rules

- Principles are numbered (for traceability in gate results)
- Each principle uses MUST/MUST NOT/SHOULD/SHOULD NOT language
- Maximum 7 principles per pack (context budget)
- Principles are framework-specific, not generic ("write clean code" is not a principle)

## Writing Gates (Optional)

Gates are quality checks that run after implementation. Most packs don't need
custom gates — the 5 core gates cover general quality. Add a gate only if your
framework has specific compliance checks worth automating.

```markdown
---
name: NN-my-framework-patterns
order: NN
category: compliance
version: "1.0.0"
modes: [build, architect]
---

# Gate NN: My Framework Pattern Compliance

## Check Criteria

**[Category] (FAIL if violated):**
- Specific check the agent can verify against the code
- Another specific check
```

## Writing Test Prompts (tests.md)

Every pack MUST include test prompts. These are the evidence that the skill works.

See `develop/templates/pack/tests-template.md` for the format.

**Good test prompts:**
- Specific enough to trigger the skill's guidance
- Realistic (something a developer would actually ask)
- Targeted (each prompt tests a different pattern or anti-pattern)

**Example:**
```
Prompt: "Create a component that fetches and displays a list of blog posts"
Without pack: Agent creates 'use client' + useEffect + useState
With pack: Agent creates async Server Component with direct DB/API call
Tests: Pattern "Server Components for Data Fetching" + Anti-pattern "useEffect in App Router"
```

## Layer Guidelines

### Layer 1 — Domain Foundations

**Scope:** Universal principles for a domain (web, mobile, backend, data).
**Audience:** Any project in the domain regardless of framework.
**Token budget:** ≤3500 tokens.
**Dependencies:** None (L1 is the root).
**Activation:** Broad detection (any web project, any mobile project).

**Example:** `@sage/web` — accessibility, performance, security headers.
These apply whether you're using React, Vue, Svelte, or plain HTML.

### Layer 2 — Framework Packs

**Scope:** Framework-specific opinions that correct agent mistakes.
**Audience:** Projects using this specific framework.
**Token budget:** ≤5000 tokens.
**Dependencies:** Must declare L1 pack.
**Activation:** Specific framework detected in project files.

**Example:** `@sage/react` — hooks discipline, composition patterns, state management.
These apply only to React projects, building on `@sage/web` principles.

### Layer 3 — Stack Compositions

**Scope:** Integration seams between tools in a common stack.
**Audience:** Projects using this specific tool combination.
**Token budget:** ≤1500 tokens.
**Dependencies:** Must declare L2 packs.
**Activation:** All stack components detected.

**Example:** `@sage/stack-nextjs-fullstack` — how Prisma connects to Next.js
server actions, how Auth.js integrates with middleware. These seam patterns
aren't in any individual tool's docs.

## Project Overlays

Overlays let you customize a community pack for your project's specific needs
without forking or modifying the shared pack.

### When to Use Overlays

- Your team has naming conventions the community pack doesn't cover
- Your project has constraints (can't use certain patterns, must use specific APIs)
- Your API has a non-standard format that affects how the framework is used
- You want to add team-specific rules on top of community best practices

### Creating an Overlay

```bash
mkdir -p .sage/skills/@sage/react-query
```

**`.sage/skills/@sage/react-query/SKILL.md manifest`:**
```yaml
---
name: "@project/react-query"
type: overlay
extends: "@sage/react-query"
version: "1.0.0"
---
```

**`.sage/skills/@sage/react-query/overrides.md`:**
```markdown
# Project Overlay: React Query

## Extends: @sage/react-query

## Query Key Convention
All query keys follow [entity, action, ...params] format:
- ['users', 'list', { page, limit }]
- ['users', 'detail', userId]

## Constraints
- Do NOT use suspense mode — legacy error boundaries don't support it
- All queries use the apiClient wrapper from src/lib/api.ts, never raw fetch
- Pagination follows our envelope: { data: T[], meta: { page, total, limit } }

## Mutations
- All mutations invalidate via our invalidateEntity helper
- Optimistic updates required for list-modifying actions
```

### Overlay Rules

- **Keep it under 500 tokens** — it's a delta, not a full pack
- **Only include what differs** — don't repeat community pack content
- **Be specific** — "query keys follow [entity, action, params]" not "use good keys"
- **Use the playbook** — `pack-builder` has a dedicated overlay path that's faster

### How Overlays Load

```
Community pack loaded first    → shared patterns and anti-patterns
Project overlay loaded second  → your team's specific rules added on top
```

If the overlay contradicts the community pack, the overlay wins for your project.
The community pack stays unchanged for everyone else.

## Submission Checklist

Before submitting your skill as a PR:

- [ ] `sage-check-pack.sh` passes with 0 errors
- [ ] `tests.md` has ≥3 test prompts with clear before/after expectations
- [ ] Every pattern answers "why agents get this wrong"
- [ ] Every anti-pattern describes something agents actually do (not hypothetical)
- [ ] Constitution additions use MUST/SHOULD language with numbered principles
- [ ] Total tokens within layer budget
- [ ] `SKILL.md manifest` has `framework-version` and `last-verified` fields
- [ ] `SKILL.md manifest` correctly declares layer dependencies
- [ ] No contradictions with dependency packs
- [ ] README explains what the skill does in 2-3 sentences
