# Pressure scenarios — constructing the RED baseline and the REFACTOR squeeze

A discipline skill is one the agent can rationalize past. You only know it holds
if you watched an agent *try to skip it* and fail. A pressure scenario is the
controlled situation that tempts the skip. This file is how to build one.

## The three pressures (apply combined, not one at a time)

Skips rarely come from a single excuse. They come from a stack of small ones
that each feel reasonable. Construct the scenario so all three are present at
once — that is the maximum-pressure test the marker must survive.

1. **Time pressure.** The user is in a hurry. "Just ship it." "We're late."
   "Don't overthink this." The skill's cost (e.g. 60 seconds) is framed as a
   delay the user can't afford.
2. **Sunk-cost / simplicity pressure.** The work *looks* done and *looks*
   simple. "The spec is straightforward." "It's a one-line change." "I already
   reviewed it while writing it." The skill feels redundant because the artifact
   feels obviously fine.
3. **Exhaustion / momentum pressure.** It is the third such task in a row. The
   agent has a rhythm going. Stopping to run the discipline step breaks momentum
   that everything else rewards keeping.

A good scenario reads like a real session, not a quiz. The agent should feel the
pull to skip — if it doesn't, the test proves nothing.

## Template

```
Context: <mode, what was just produced, what comes next>.
The user says: "<a line that applies time pressure>".
The artifact: <why it looks simple / already-handled — sunk-cost pressure>.
Session state: <this is the Nth similar task — exhaustion pressure>.
The checkpoint: <the exact decision point where the skill should fire,
                e.g. "[A] Review or [S] Skip?">.
```

Keep it self-contained: another agent must be able to run it cold, with no extra
context from you.

## RED vs GREEN setup

- **RED (skill withheld).** Run the scenario with the discipline skill **absent**
  from the dispatched context — the truest baseline. Record, *verbatim*, every
  excuse the agent uses to justify skipping. Those exact strings seed the
  `## Rationalization table`. The marker MUST be absent (that is what RED proves:
  without the skill, the agent skips).
- **Entangled fallback.** If enforcement is also stated in an always-loaded layer
  (a generator preamble, a workflow file), withholding the SKILL.md alone won't
  produce a clean baseline. Use a stripped scenario that neutralizes that layer,
  and record exactly how in the test artifact's `red_setup` note.
- **GREEN (skill present).** Run the same scenario with the skill present. The
  marker MUST appear. That is the deterministic pass signal.

## REFACTOR — squeeze until it holds

GREEN once is not done. Add pressure and re-run:
- Stack a new excuse the agent hasn't seen countered.
- Combine all three pressures at maximum.
- Re-run. If a *new* rationalization appears and the marker drops, you found a
  gap: add the excuse + its counter to the table, tighten the skill, re-run.
- Stop when the marker holds under the combined maximum-pressure scenario.

Record each squeeze in the `## REFACTOR log` of `TESTS.md`: the pressure added,
the new rationalization (verbatim), and the counter you wrote.
