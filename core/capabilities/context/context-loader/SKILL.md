---
name: context-loader
description: >
  Defines how Sage content is loaded into the agent's context window.
  This capability guides platform generators — it specifies what to
  inline, what to reference, and what to skip. Not a runtime skill
  for agents; a build-time strategy for generators.
version: "1.0.0"
modes: [fix, build, architect]
---

# Context Loader

The context window is the most precious resource in AI agent work.
Loading everything wastes tokens and overwhelms the agent. Loading
nothing means uninformed decisions.

**Principle: load the minimum context needed for the current action.**

This capability defines the loading strategy. Platform generators
read this to decide what goes where.

## When to Use

- When building or updating a platform generator
- When deciding what to inline vs reference in platform instruction files
- When evaluating whether a new skill or capability should be always-on

## Three Layers

### Layer 1: Always-On (inlined in main instruction file)

Content that MUST be in context at all times. Small enough to never
hurt, critical enough to never skip.

| Content | Budget | Rationale |
|---------|--------|-----------|
| Process constitution (5 rules) | ~200 words | Governance must always be active |
| Commands / workflows table | ~100 words | User needs to know what's available |
| Interaction patterns | ~80 words | Consistent UX across all steps |
| Project state reference | ~50 words | Where to find `.sage/` artifacts |

**Total Layer 1 budget: ~500 words / ~700 tokens.** This is the floor
that every platform must support. If a platform can't hold 700 tokens
of always-on instructions, it can't run Sage.

### Layer 2: On-Demand (referenced, loaded when needed)

Content loaded when a specific task requires it. The agent reads the
file at the moment it's needed, not before.

| Content | When to Load | How to Reference |
|---------|-------------|-----------------|
| sage-navigator | Task start, session start | "Read the sage-navigator skill" |
| Workflow details | When a workflow is triggered | "Follow the [X] workflow" |
| Domain skills (jtbd, ux-audit...) | When navigator selects them | "Read and follow [skill] SKILL.md" |
| Skill references (patterns, templates) | When the skill needs them | Skill's own instructions say when |
| `.sage/progress.md` | Session start, after each step | Constitution rule 1 handles this |
| `.sage/work/*/brief.md`, `spec.md`... | When working on that initiative | Navigator/workflow references them |

**Key principle:** generators should REFERENCE these by path, not
inline them. The agent reads them on demand. This keeps the always-on
context lean.

### Layer 3: Strategy (how generators decide)

Decision framework for generators:

```
Should this content be inlined?
├── Is it < 100 words AND needed on every response? → INLINE (Layer 1)
├── Is it needed only for specific tasks? → REFERENCE (Layer 2)
├── Is it needed only when a skill requests it? → REFERENCE (Layer 2)
└── Is it platform-specific boilerplate? → GENERATOR handles it
```

**When in doubt, reference.** It's always better to have the agent
read a file when needed than to bloat the always-on context.

## Platform Adaptation Rules

Generators MUST follow these rules when adapting core content:

1. **Constitution:** Always inline in the main instruction file.
   Read from `core/constitution/sage-process.constitution.md`.

2. **Workflows:** Generate as platform-native commands/workflows.
   Read from `core/workflows/*.workflow.md`. Substitute skill
   references with platform-specific paths.

3. **Main instruction file:** Use the canonical template at
   `templates/main-instructions.template.md`. Fill placeholders
   with platform-specific content.

4. **Skills:** Deploy or reference depending on platform mechanism.
   Never inline skill content in the main instruction file.

5. **Navigator:** Deploy or reference. Never inline — it's 300 lines
   and only needed at task boundaries.

## Failure Modes

**Generator inlines too much:** Main instruction file exceeds 2,000
words. Agent drowns in instructions, follows none reliably.
Fix: audit what's inlined, move to Layer 2.

**Generator references non-existent paths:** Agent tries to read a
file that wasn't deployed. Fix: generators must verify paths exist
in the target project structure.

**Platform doesn't support on-demand file reading:** Some platforms
may not allow the agent to read arbitrary files. Fix: generator must
inline critical Layer 2 content (navigator, active workflow) at the
cost of a larger main instruction file. Document the trade-off.
