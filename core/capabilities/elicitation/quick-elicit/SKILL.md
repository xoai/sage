---
name: quick-elicit
description: >
  Guided specification through 3 focused question rounds in ~2 minutes.
  Produces intent, boundaries, and acceptance criteria. Use when the user
  wants to add a feature, build something new, implement functionality, create
  a component, or says "add", "build", "create", "implement". Do not use when
  a detailed spec already exists.
version: "1.0.0"
modes: [build]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [elicitation, specification, planning, requirements]
inputs: [codebase]
outputs: [spec]
requires: [codebase-scan]
-->

# Quick Elicit

Guide the human to articulate a high-quality specification through 3 focused
rounds of questions. Takes ~2 minutes, not 20.

**Core Principle:** The quality of output is determined by the quality of input.
A blank template produces vague specs. Targeted questions produce precise specs.
But heavy persona-driven interrogation loses people. Three rounds. Focused. Done.

## When to Use

BUILD mode, before planning. When the human describes something they want to build,
add, or change — and no specification exists yet.

Do NOT use when:
- A spec already exists in `.sage/work/` (skip to planning)
- The human has provided a detailed written spec (accept it, don't re-elicit)
- FIX mode (the bug report IS the spec)
- The human says "just do it" (respect their autonomy, note the risk)

## Process

### Pre-Elicit: Infer What You Can

Before asking anything, use `codebase-scan` to understand:
- What tech stack is in use?
- What patterns exist in the codebase?
- What does the area being changed look like?
- What conventions are established?

This determines WHAT TO ASK. Don't ask about things you can already see.

### Round 1: Intent (30 seconds)

Ask TWO questions:

1. **"What should this do when it's working perfectly?"**
   Get the happy path. What does success look like from the user's perspective?

2. **"Who uses this, and when?"**
   Get the actor and trigger. This prevents building features nobody uses.

Wait for answers. Then draft a 3-5 sentence **intent statement** and show it:

```
INTENT: [feature name]
When [actor] does [trigger], the system [behavior].
This enables [value/outcome].
```

Ask: "Does this capture what you mean? Anything to adjust?"

### Round 2: Boundaries (60 seconds)

Ask up to THREE questions, adapting based on what you inferred from the codebase:

1. **"What should this explicitly NOT do?"**
   Boundaries prevent scope creep and gold-plating.

2. **"What existing code does this touch? Any concerns?"**
   Skip if codebase-scan already identified the impact area clearly.

3. **"Any security, performance, or compatibility constraints?"**
   Skip if the change is purely internal with no user-facing impact.

Draft **boundary conditions** and show them:

```
BOUNDARIES:
- This feature WILL: [list]
- This feature WILL NOT: [list]
- Constraints: [any non-functional requirements]
- Affected areas: [files/modules identified]
```

Ask: "Anything missing or wrong here?"

### Round 3: Verification (30 seconds)

Ask ONE question:

**"How will we know this works? What would you test manually?"**

The answer becomes acceptance criteria. Draft them and show:

```
ACCEPTANCE CRITERIA:
1. [testable criterion]
2. [testable criterion]
3. [testable criterion]
```

Each criterion MUST be testable — not "works well" but "returns 200 OK with
user.id in response body." If the human gives vague criteria, make them specific:

```
Human: "It should be fast"
Agent: "I'll set the criterion as: 'API response time < 200ms at p95.'
        Does that match your expectation, or is there a different threshold?"
```

### Output: Feature Spec

Combine all three rounds into a spec document saved to
`.sage/work/<YYYYMMDD>-<slug>/spec.md` using the minimal spec template.

Show the complete spec. Ask: "Ready to plan implementation, or anything to adjust?"

## Rules

**MUST (violation = bad spec or lost trust):**
- MUST NOT ask more than 7 questions total across all rounds.
- MUST NOT ask about things the codebase scan already revealed.
- MUST NOT ask technical implementation questions (that's for planning, not spec).
- MUST show the drafted output after each round for validation.
- MUST make acceptance criteria testable and specific.

**SHOULD (violation = suboptimal experience):**
- SHOULD respect one-word answers — work with what you have, don't interrogate.
- SHOULD make a reasonable choice when the human says "you decide," and state it
  explicitly so they can override if it's wrong.
- SHOULD compress to 1 round if the human is visibly impatient.

**MAY (context-dependent):**
- MAY skip elicitation entirely if the human provides a detailed written spec.
- MAY recommend ARCHITECT mode if requirements are genuinely complex.

## Failure Modes

- **Human is impatient:** Compress to 1 round — ask just the intent question,
  infer boundaries and criteria from context, show the complete spec for validation.
- **Human has already thought deeply:** Skip elicitation, help them write their
  thoughts into the spec template structure, then validate.
- **Requirements are genuinely complex:** Recommend switching to ARCHITECT mode
  for full elicitation with deep-elicit skill. Don't try to squeeze complexity
  into 2 minutes.
- **Conflicting requirements surface:** Don't resolve them yourself. Present the
  conflict clearly and ask the human to decide.
