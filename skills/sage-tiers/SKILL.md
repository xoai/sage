---
name: sage-tiers
description: Sizing a task before doing it. Use when the user asks which tier a task is, how big or small a change is, whether something needs a spec or a plan, whether to just do it or slow down, or when deciding how much process a piece of work deserves.
version: "1.0.0"
type: system
---

# Tiers

Tier is the answer to one question: **how much process does this deserve?**

Too much process on a trivial change is bureaucracy, and users learn to route
around it. Too little on a consequential one is how a "quick fix" becomes an
outage. Tier is where that judgment is made explicit instead of being made
silently, differently, every time.

## The three tiers

| Tier | Response | What it looks like |
|---|---|---|
| **Tier 1** | Just do it. | Single file, no design decisions, a quick answer. No manifest, no spec, no confirmation. |
| **Tier 2** | Announce and proceed. | Multiple steps, creates artifacts. Say what you are doing, then do it. |
| **Tier 3** | Card and choose. | Major effort, genuine ambiguity. Present options and let the user pick. |

## The bias

**Bias toward Standard scope.** When a task sits on a boundary, take the
higher tier.

Any of these puts a task at **Tier 2 minimum**, regardless of how small the
diff looks:

- a behavior change
- an API change
- a decision the team would want to see

The asymmetry is deliberate. The cost of over-tiering is a few minutes of
ceremony. The cost of under-tiering is a change nobody reviewed, in a place
nobody expected, discovered later by someone who did not know it happened.

## Tier 1 is a real escape hatch, not a trap

Tier 1 exists so the process does not tax trivial work, and it is genuinely
free: no manifest is created, so the spec-gate hook has nothing to block on
(the hook reads `gate_state` from a manifest; no manifest means no active
cycle means edits are unrestricted).

That is the escape hatch working as designed. It is not a loophole — "I will
call it Tier 1 so I do not have to write a spec" is a rationalization, and the
list above is what it collides with.

## Rationalizations that do not survive contact

| The thought | Why it is wrong |
|---|---|
| "It is literally one line" | One line that changes behavior is a behavior change. The diff size is not the blast radius. |
| "The design is obvious" | Obvious to you, now, with your context. Write it down and find out. |
| "I will note it in the commit message" | A commit message is not a decision record and nobody reads it before the fact. |
| "The user just wants it done" | The user wants it *right*. They will not thank you for speed on the change that broke checkout. |
