---
name: manifest
type: manifest
version: "1.0.0"
description: >
  Cycle manifest — single source of truth for cycle state, context summary,
  and handoff guidance. Created at first checkpoint, updated at every gate.
  Read by /continue and Auto-Pickup for session resumption.
---

# Template

```markdown
---
cycle_id: "YYYYMMDD-slug"
workflow: build | architect | fix | research | design | analyze | reflect
phase: framing | brief | spec | plan | implement | quality-gates | review | complete
status: in-progress | paused | blocked | complete
created: YYYY-MM-DD
updated: YYYY-MM-DD HH:MM
---

# Cycle: {title}

## State

**Current phase:** {phase} — {what's happening in this phase}
**Next step:** {concrete next action when resumed}
**Artifacts:**
- brief.md: {exists | missing | not-required}
- spec.md: {exists | missing | not-required}
- plan.md: {exists | missing | not-required}
- implementation: {not-started | in-progress (N/M tasks) | complete}
- quality-gates: {not-run | passed | failed (which gate)}
- qa-report.md: {exists — verdict | not run}
- design-review.md: {exists — N issues, M warnings | not run}

## Context summary

{2-5 sentences. What a cold-start agent needs to know to resume
with good judgment, not just mechanical compliance.

Include:
- Why this cycle exists (the pain, from Round 0 framing)
- The key trade-off or design choice that shapes everything
- What the user cares about most
- Anything surprising or non-obvious about the approach

Exclude:
- Anything already in spec.md or plan.md (don't duplicate)
- Implementation details (the code speaks for itself)
- Generic statements ("The user wants high quality")

Max 200 words.}

## Decisions so far

{Bulleted list of key decisions from decisions.md for this cycle.
Not all entries — just the ones that affect how a resuming agent
should behave.}

## Open questions

{What's unresolved. What the previous agent was thinking about but
didn't get to decide. What the user seemed uncertain about.}

## Handoff guidance

{Specific instructions for the next agent. Not generic advice —
concrete guidance.

Examples:
- "The user wants to keep the API surface minimal. Push back if
  the plan generates unnecessary endpoints."
- "spec.md says 'TBD' for the caching strategy — resolve this
  before implementing task 3."
- "The user was leaning toward option B in the last exchange but
  didn't confirm. Ask before proceeding."

Max 150 words.}
```

# Rules

## Anti-lazy-manifest contract

Context summary MUST NOT be:
- A copy of the spec's title or description
- "See spec.md for details"
- Generic guidance ("Continue with implementation")

The context summary must contain information that is NOT already
present in spec.md, plan.md, or decisions.md. It captures
**judgment**, not facts.

## Size constraints

- Context summary: 2-5 sentences, max 200 words
- Handoff guidance: 1-4 bullet points, max 150 words

If summary is longer → it's trying to replace the spec.
If guidance is longer → the cycle needs a spec update, not notes.
