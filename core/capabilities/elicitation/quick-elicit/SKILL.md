---
name: quick-elicit
description: >
  Guided specification through 4 focused question rounds in ~3 minutes.
  Round 0 challenges problem framing before solutioning. Produces framing,
  intent, boundaries, and acceptance criteria. Use when the user wants to
  add a feature, build something new, implement functionality, create a
  component, or says "add", "build", "create", "implement". Do not use when
  a detailed spec already exists.
version: "1.1.0"
modes: [build]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [elicitation, specification, planning, requirements, framing]
inputs: [codebase]
outputs: [spec]
requires: []
-->

# Quick Elicit

Guide the human to articulate a high-quality specification through 4 focused
rounds of questions. Takes ~3 minutes, not 20.

**Core Principle:** The quality of output is determined by the quality of input.
The most expensive failure is building the wrong thing correctly. Round 0
challenges the framing BEFORE the other rounds capture requirements.

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

Before asking anything, scan the relevant codebase area to understand:
- What tech stack is in use?
- What patterns exist in the codebase?
- What does the area being changed look like?
- What conventions are established?

If a `codebase-scan` has been run previously, use its output. Otherwise,
scan the relevant files directly (read project config, entry points,
and the area being changed).

Also scan `.sage/docs/` for existing research artifacts (jtbd-*, ux-audit-*,
opportunity-*, user-interview-*). If research exists, note the known pain
for use in Round 0.

This determines WHAT TO ASK. Don't ask about things you can already see.

### Round 0: Framing (30 seconds)

**PURPOSE:** Challenge whether the request is framed around the right
problem BEFORE committing to a specification direction.

Ask ONE question:

**"What goes wrong today without this?"**

This is not "what does this feature do?" It's "what specific frustration,
failure, or friction makes this worth building?" The answer should be a
concrete struggling moment, not an abstract category.

- Good answer: "Sellers upload dark, cluttered photos and their listings
  don't sell. They blame the platform."
- Thin answer: "Users need to upload photos." (restates the request, not pain)
- Acceptable: "There's no way to add images right now." (genuine gap)

**If research context exists:** Reference the known pain instead of
asking open-ended: "Research identified [pain]. Is that still the driver,
or has something changed?"

**If the answer restates the feature instead of the pain**, probe once:
"Got it — but what's the actual problem that causes? What goes wrong
for the user?"

Do NOT probe more than once. If the pain remains unclear after one
follow-up, note it and proceed.

**The challenge:** Based on the pain + codebase scan, surface one or two
implicit premises the user is making:

```
Before we lock this in — I notice two assumptions worth checking:

1. [Premise]: [one sentence stating the assumption]
   → [one sentence describing why it might be wrong]

2. [Premise]: [one sentence stating the assumption]
   → [one sentence describing why it might be wrong]

Does the original framing still feel right, or should we adjust?
```

**What counts as an implicit premise:**
- "This needs a new screen" (maybe the existing screen can be extended)
- "This is a frontend problem" (maybe it's a data problem)
- "This is one feature" (maybe it's three, and only one matters now)
- "Users want this" (maybe they want something adjacent)
- "This needs to be built" (maybe it can be configured)

**What does NOT count** (don't waste time on these):
- Technical implementation choices (that's for planning)
- Architecture decisions (that's for spec or architect)
- Obvious facts about the codebase (already visible from scan)

**User responds in one of three ways:**

**"Framing is right."** → Proceed to Round 1 with the original request.
Note: `Framing: Original request confirmed. Pain: [stated pain].`

**"Let's adjust."** → User provides adjusted framing. Round 1 uses the
adjusted framing, not the original request.
Note: `Framing: Adjusted from [original] to [adjusted]. Pain: [pain].`

**"I don't know / let me think."** → Note uncertainty. Proceed with
original framing but flag it:
`Framing: Original request (low confidence). Pain: unclear.
Consider /research or /jtbd before building.`

**At Round 0 completion:** Prepend framing decision to `.sage/decisions.md`
BEFORE proceeding to Round 1:

```
### YYYY-MM-DD — Framing: [initiative]
[Chose framing]. Pain: [pain]. Challenged: [premise names].
(quick-elicit Round 0)
```

### Round 0 bypass conditions

Round 0 is skipped in exactly these cases:

1. **Lightweight scope** — Task classified as Lightweight. One component,
   no design decisions. Framing adds no value to "fix the typo."
2. **Spec already exists** — Framing was already considered.
3. **User says "just do it"** — Agent notes: "Skipping framing challenge.
   Spec inherits original request without challenge."
4. **FIX mode** — The bug report IS the spec. Pain is self-evident.

No other bypass conditions. Standard and Comprehensive ALWAYS get Round 0.

**Anti-rationalization contract for Round 0 skip:**
Do NOT skip Round 0 because:
- "The request is clear enough" — clarity of request ≠ correctness of framing
- "This is a small change" — Standard classification means framing matters
- "The user already explained the pain" — restate and verify, don't assume
- "We discussed this in a previous session" — disk is truth, not memory

### Round 1: Intent (30 seconds)

Ask TWO questions:

1. **"What should this do when it's working perfectly?"**
   Get the happy path. What does success look like from the user's perspective?

2. **"Who uses this, and when?"**
   Get the actor and trigger. This prevents building features nobody uses.

Wait for answers. Then draft a 3-5 sentence **intent statement** and show it:

```
INTENT: [feature name]
Framing: [original | adjusted | original (low confidence)]
Pain: [the struggling moment, from Round 0]
When [actor] does [trigger], the system [behavior].
This enables [value/outcome].
```

Ask: "Does this capture what you mean? Anything to adjust?"

**Note:** If Round 0 adjusted the framing, Round 1's questions are asked
about the ADJUSTED framing, not the original request.

### Round 2: Boundaries (60 seconds)

Ask up to THREE questions, adapting based on what you inferred from the codebase:

1. **"What should this explicitly NOT do?"**
   Boundaries prevent scope creep and gold-plating.

2. **"What existing code does this touch? Any concerns?"**
   Skip if the codebase scan already identified the impact area clearly.

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
user.id in response body." If the human gives vague criteria, make them specific.

### Output: Feature Spec

Combine all four rounds into a spec document saved to
`.sage/work/<YYYYMMDD>-<slug>/spec.md` using the minimal spec template.

The spec includes a `## Framing` section at the top (from Round 0),
followed by Intent, Boundaries, and Acceptance Criteria.

Show the complete spec. Ask: "Ready to plan implementation, or anything to adjust?"

## Compression Behavior

If the user is visibly impatient, compress to 1 round. The compressed
version merges pain + intent into one message:

"Before we spec this — what's the actual pain this solves? And then:
what should it do when working perfectly?"

One message, two questions. Infer boundaries and criteria from context.
Show the complete spec with a Framing section for validation.

**Even compressed, the framing question survives.** Round 0 can be
compressed but NEVER eliminated. A compressed Round 0 still produces
a Framing section in the spec.

## Rules

**MUST (violation = bad spec or lost trust):**
- MUST NOT ask more than 8 questions total across all rounds.
- MUST NOT ask about things the codebase scan already revealed.
- MUST NOT ask technical implementation questions (that's for planning, not spec).
- MUST show the drafted output after each round for validation.
- MUST make acceptance criteria testable and specific.
- MUST execute Round 0 for Standard+ tasks (see bypass conditions).
- MUST prepend framing decision to decisions.md before Round 1.
- MUST include a non-empty Framing section in spec output.

**SHOULD (violation = suboptimal experience):**
- SHOULD respect one-word answers — work with what you have, don't interrogate.
- SHOULD make a reasonable choice when the human says "you decide," and state it
  explicitly so they can override if it's wrong.
- SHOULD compress to 1 round if the human is visibly impatient.
- SHOULD reference existing research context in Round 0 if available.

**MAY (context-dependent):**
- MAY skip elicitation entirely if the human provides a detailed written spec.
- MAY recommend ARCHITECT mode if requirements are genuinely complex.

## Failure Modes

- **Human is impatient:** Compress to 1 round — merge pain + intent question,
  infer boundaries and criteria from context, show complete spec with Framing.
- **Human has already thought deeply:** Skip elicitation, help them write their
  thoughts into the spec template structure, then validate.
- **Requirements are genuinely complex:** Recommend switching to ARCHITECT mode
  for full elicitation with deep-elicit skill.
- **Conflicting requirements surface:** Don't resolve them yourself. Present the
  conflict clearly and ask the human to decide.
- **Low-confidence framing:** Include "Consider /research or /jtbd before
  building" in the Framing section. Surface at the checkpoint: "The pain behind
  this isn't fully clear. Want to proceed, or run research first?"
  This is advisory — do NOT block the user from proceeding.
