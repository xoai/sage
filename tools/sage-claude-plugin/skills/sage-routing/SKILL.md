---
name: sage-routing
description: Choosing which Sage workflow fits a request. Use when the user asks what to run, which command or workflow to use, where to start, or when a request is ambiguous or spans multiple surfaces and needs to be routed to build, fix, architect, review, learn, reflect, or continue.
version: "1.0.0"
type: system
---

# Routing depth

The eager layer carries the keyword map — the trigger. This carries the rest:
what to do when the keyword map misses, how to present the choice, and what
routing looks like when it is done well.

## The three-layer chain

**Layer 1 — Keyword routing (deterministic, checked first).** The map in the
eager layer. One match → confirm. Multiple matches → present them as options.
No match → Layer 2.

**Layer 2 — Sub-agent classifier.** If the Task tool is available, spawn a
classifier sub-agent:

> Classify this request as UNDERSTAND (/research or /review --ux),
> ENVISION (/design or /architect), or DELIVER (/build or /fix).

Use the response to select the workflow → confirm. No Task tool → Layer 3.

**Layer 3 — In-context classification (fallback).**

| Shape of the request | Category | Workflow |
|---|---|---|
| Question, evaluation, "why" | UNDERSTAND | `/research`, `/review --ux` |
| Future, "should", "let's create" | ENVISION | `/design`, `/architect` |
| Action, "add", "implement" | DELIVER | `/build`, `/fix` |
| Ambiguous | — | present options from all matching categories |

## Confirmation (Zone 1)

Always, except for explicit slash commands and Tier 1 tasks:

```
Sage → [workflow]. [One-line rationale].

[1] [Workflow] — [skill → chain → arrows] ([N] steps)
[2] [Alternative] — [chain] ([N] steps)
[3] [Alternative] — [chain]

Pick 1-3, type / for commands, or describe what you need.
```

Show the chain and the step count. No time estimates — they are guesses
wearing a number's clothing.

## Worked examples

**"audit our checkout UX"** — keyword `audit` → `/review --ux`.

> Sage → review workflow. Evaluating the checkout experience.
>
> [1] Review — UX audit → evaluation (2 steps)
> [2] Research — interview → JTBD → opportunity map (3 steps)
> [3] Build — spec → plan → implement → verify
>
> Pick 1-3, type / for commands, or describe what you need.

**"the checkout page is throwing 500 errors"** — keyword `error` → `/fix`.
Single match, no ambiguity, so confirm and go:

> Sage → fix workflow. Investigating 500 errors on checkout.

**"improve our onboarding conversion rate"** — `conversion` → review,
`improve` → build. Two matches, so do not pick for the user:

> Sage: This could go two ways:
>
> [1] Review — UX audit → evaluation (2 steps)
> [2] Build — spec → plan → implement → verify
> [3] Research — interview → JTBD → opportunity map (3 steps)
>
> Pick 1-3, type / for commands, or describe what you need.

**"change the button color to blue"** — Tier 1. Just change it. Routing a
one-line change through a confirmation menu is the process becoming the point.

## The failure this prevents

The routing chain exists because the alternative is an agent that treats every
request as a DELIVER request — the default failure mode, and the one that ships
a fix for a problem nobody diagnosed. If a request is a question, answering it
with an implementation is not efficiency. It is a wrong answer that took work.
