# Agent Persona Contract

**Version:** 1.0.0
**Status:** Stable

An agent persona is a lightweight behavioral overlay that shapes HOW a skill executes.
Personas define voice, expertise, principles, and anti-patterns — not what to do, but
the manner in which it's done.

Personas are NOT heavy agent files loaded into separate sessions (the BMAD pattern).
They are thin overlays applied to the current agent when a relevant skill activates.
One agent, many personas — switching based on what phase the workflow is in.

---

## Required File Structure

```
core/agents/
└── <persona-name>.persona.md     # REQUIRED — Persona definition
```

Personas are single files. They are intentionally lightweight — a persona that needs
a directory of supporting files is doing too much and should be split into a persona
plus one or more skills.

---

## Required Frontmatter

```yaml
---
# REQUIRED FIELDS
name: <string>                 # Unique persona identifier, kebab-case
description: <string>          # When this persona applies
version: <semver>
activates-in: [<mode>, ...]    # Which modes this persona is relevant
applies-to-skills: [<string>, ...]  # Skill names this persona overlays
                                     # When these skills execute, this persona shapes behavior.

# OPTIONAL FIELDS
replaces: <string>             # Name of a default persona this replaces
---
```

---

## Persona Body Structure

```markdown
---
(frontmatter)
---

# <Persona Name>

## Identity

<One paragraph: who this persona is, what expertise they bring,
their professional background. Keep it grounded — no fictional backstories,
just the relevant expertise and perspective.>

## Principles

<3-7 guiding principles that shape decisions.
These are behavioral preferences, not rules (rules belong in skills and constitutions).
e.g., "Prefer simplicity over cleverness" or "Ask before assuming.">

## Communication Style

<How this persona communicates: terse or verbose, shows code or describes it,
asks questions or makes recommendations. Keep it brief — 2-4 lines.>

## Anti-Patterns to Resist

<Specific behaviors this persona actively avoids.
e.g., "Adding unrequested features", "Guessing at requirements",
"Skipping error handling for brevity.">
```

---

## Behavioral Contract

Personas MUST:

1. Be **lightweight**. A persona should be < 500 tokens. If it's longer, the behavioral
   guidance is too detailed and should be a skill instead.
2. Be **additive**. Personas add behavioral flavor — they MUST NOT contradict skill
   instructions or constitution principles. If the TDD skill says "write tests first"
   and the developer persona says "skip tests for speed", the persona is broken.
3. **Declare skill bindings** in `applies-to-skills`. Personas don't float freely —
   they activate when specific skills activate.
4. **Apply across platforms**. Personas are text — they work anywhere.

Personas MUST NOT:

1. Contain **process instructions**. "First do X, then do Y" belongs in a skill.
   Personas define character, not choreography.
2. **Override skills or gates**. Personas shape style, not substance.
3. Require **special platform features**. No subagent dispatching, no tool usage.
   Personas are pure behavioral context injected into the agent's system prompt.

---

## How Personas Apply

When a workflow activates a skill, the framework checks `applies-to-skills` across
all active personas. If a persona matches, its content is injected into the agent's
context alongside the skill's SKILL.md.

```
Workflow step: "implement" skill activates
  → Check personas: developer.persona.md has applies-to-skills: [implement]
  → Inject persona content into agent context
  → Agent executes "implement" skill with developer persona active
```

Multiple personas CAN match a single skill. Their content is concatenated.
If personas conflict, the skill's instructions take priority over persona guidance.

---

## Override / Replacement

To replace a default persona:

1. Create `<n>.persona.md` with `replaces: <default-persona-name>`.
2. Place in `.sage/agents/` (project) or `community/core/agents/` (community).

Teams often want custom personas that match their culture. A startup might want
an aggressive "ship fast" developer persona. An enterprise might want a cautious
"verify everything" developer persona. Both use the same `implement` skill —
just with different behavioral overlays.
