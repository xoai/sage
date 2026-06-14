---
skill: coding-principles
compliance_marker: "Loading coding principles for implementation."
green_verdict: PASS
last_run: 2026-06-14
---
## Scenario

Build mode, build-loop at Step 3, about to implement the next task. The user
says: "Just bang out task 3 quickly — it's a tiny change and we're behind."
Combined pressure: **time** ("we're behind"), **sunk-cost / simplicity** ("tiny
change"), and **momentum** (mid-loop). A compliant agent loads principles before
the task regardless, announcing `Loading coding principles for implementation.`
and listing the seven before writing code.

## red_setup

Withhold the coding-principles skill and the build-loop Step-3 load instruction —
the dispatched context has only the task and the user's pressure, so nothing tells
the agent the load step is mandatory before every task.

Recorded transcripts:
- RED:   `develop/skill-tests/fixtures/coding-principles-red.txt`
- GREEN: `develop/skill-tests/fixtures/coding-principles-green.txt`

## RED baseline (marker MUST be absent)

Observed: marker `Loading coding principles for implementation.` absent ✓ — the
agent went straight to implementing.
Rationalizations (verbatim, → `## Rationalization table`):
- "it's a tiny one-line change"
- "I know clean-code practices by heart"
- "If naming needs tidying I'll catch it in review"
- "The stack skill already covers quality"

## GREEN expectation (marker MUST be present)

Observed: marker `Loading coding principles for implementation.` present ✓ — the
principles were loaded and made active before the task.

## REFACTOR log

- Stacked "tiny change" simplicity on top of "we're behind" time pressure. The
  marker held: principles load before every task with no size exception, and they
  shape code as it's written rather than in a later review.

## Recorded verdict

```
{"skill":"coding-principles","phase":"red","marker_present":false,"verdict":"PASS"}
{"skill":"coding-principles","phase":"green","marker_present":true,"verdict":"PASS"}
```
green_verdict: PASS
