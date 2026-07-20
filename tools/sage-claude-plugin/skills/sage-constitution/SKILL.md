---
name: sage-constitution
description: The project's engineering principles and non-negotiable process rules. Use when asking whether something is allowed, what the project's principles or conventions are, why a rule exists, or when a decision seems to conflict with the constitution.
version: "1.0.0"
type: system
---

# The constitution

The eager layer carries each principle as one line naming the mechanism that
enforces it. This carries the reasoning, and the rules that have no mechanism
behind them.

## Engineering principles

The base set, present in every project:

| # | Principle | Enforced by |
|---|---|---|
| 1 | **Tests before code** — every behavior has a test before implementation | `sage-tdd-gate.sh` (PreToolUse — blocks the edit) |
| 2 | **No silent failures** — errors handled, logged, or propagated | Gate 3 (judgment) |
| 3 | **Secrets never in code** — env vars or a secret manager | Gate 3 (judgment) |
| 4 | **Dependencies explicit** — declared, pinned | Gate 4 (`sage-hallucination-check.sh`) |
| 5 | **Changes reversible** — migrations reversible, deploys rollbackable | Gate 3 (judgment) |

Principles 6+ come from the project's preset and its own
`.sage/constitution.md`. They are appended by the generator, numbered
continuously, and they carry exactly the same weight as the base five. A
project addition is not a suggestion.

**Read the project's own additions before assuming the base five are the whole
story.** They are in `.sage/constitution.md`, and they are where the rules that
actually bite in *this* codebase live.

## The distinction that matters

Three of the five principles above are enforced by a *judgment* gate — which
means they are enforced by a reviewer noticing, and reviewers are exactly as
reliable as their attention. Two are enforced by a script that blocks the tool
call, and those two hold whether or not anyone is paying attention.

That is not a criticism of the three. Some rules genuinely cannot be checked
mechanically ("no silent failures" requires knowing what a silent failure looks
like *here*). But it is worth being honest about which rules are load-bearing
and which are aspirational, because the eval that produced this version of Sage
found that the mechanically-enforced rules moved behavior and the prose ones,
on their own, did not.

If a principle matters and has no mechanism, that is a gap in the mechanism —
not a reason to write the prose more forcefully.

## Process rules with no script behind them

These are enforced by the model reading them, which is a real but weaker thing.

**Rule 2 — Skills before assumptions.** If a Sage skill exists for the task at
hand, read it and follow it. Do not fall back on general training when a skill
provides a specific methodology. (This is the dispatcher rule, and it is in the
eager layer for a reason: if it fails to fire, nothing else here loads.)

**Rule 3 — Document decisions.** Decisions that affect the project get
recorded — for agents *and* for the humans who arrive later. Specs, plans,
ADRs, and briefs go to `.sage/work/` or `.sage/docs/`. Even a Tier 2 task
leaves a record of what was decided and why. Partially mechanical: the
spec-gate hook blocks source edits while a cycle is `pre-spec`, so the *spec*
half has teeth. The rest is on you.

## Rationalizations

| The thought | Why it fails |
|---|---|
| "This principle does not apply to test code" | Test code is code. It is also the code you will trust the most and read the least. |
| "The project preset does not mention it, so it is optional" | The base five apply everywhere. Presets add; they do not subtract. |
| "I will follow the principle, just not right now" | The commit is the artifact. "Later" does not appear in it. |
| "It is a prototype" | Prototypes ship. That is what makes them prototypes rather than sketches. |
