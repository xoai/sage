# The rationalization table — format and how to derive it

A discipline skill resists the excuses the agent *actually* used, not the ones
you imagined. The `## Rationalization table` is where those observed excuses go,
each paired with why it's wrong and the rule that overrides it. It lives **inside
SKILL.md** so it loads with the skill and confronts the agent at the moment of
temptation.

## Format

```markdown
## Rationalization table

| The excuse (observed) | Why it's wrong | The rule |
|---|---|---|
| "The spec is straightforward, I'll continue." | Simplicity is not the skip condition — straightforward specs still hide framing drift and missing edge cases. | [A] means review runs; only an explicit [S] skips. |
| "The user is in a hurry." | 60 seconds is not the delay the user is worried about; a wrong spec shipped is. | Time pressure never downgrades [A] to [S]. |
| "I already reviewed it while writing it." | Self-review is not independent review — it shares the bias that produced the artifact. | Independent context is the point; your own pass doesn't substitute. |
```

Three columns, always:
1. **The excuse (observed)** — verbatim from a RED transcript. Not paraphrased.
   The agent recognizes its own words and that is what disarms them.
2. **Why it's wrong** — the specific flaw in the excuse, not a restatement of the
   rule. Name the thing the excuse overlooks.
3. **The rule** — the short, non-negotiable line that wins. Ideally the exact
   condition (e.g. "only [S] skips") so there is no wiggle room.

## How to derive entries

1. Run the RED baseline (skill withheld) under combined pressure
   (`pressure-scenarios.md`).
2. Copy each justification the agent emitted, **word for word**, into column 1.
   Do not clean them up — the literal phrasing is the point.
3. For each, write column 2 (the flaw) and column 3 (the overriding rule).
4. Re-run under REFACTOR pressure. Every *new* excuse that drops the marker
   becomes a new row. Keep going until the marker holds.

## Rules

- **Observed, not invented.** Every row traces to a real transcript. A table of
  imagined excuses tends to miss the one the agent actually reaches for.
- **One excuse per row.** Don't merge "it's simple and I'm in a hurry" — they are
  two different pressures with two different counters.
- **The seed row.** For review/QA discipline skills, the empirically-confirmed
  first entry is *"the spec/implementation is straightforward"* — the excuse
  behind the original `auto-review` skip. Start there, then add what your own RED
  runs surface.
