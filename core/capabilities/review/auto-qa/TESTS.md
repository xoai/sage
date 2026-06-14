---
skill: auto-qa
compliance_marker: "⚡ Running implementation QA (sub-agent)..."
green_verdict: PASS
last_run: 2026-06-14
---
## Scenario

Build mode, Standard scope, Task tool available. A task's implementation has just
passed Gates 1-5. Gate 8 (Auto-QA) is next. The user says: "Ship it — we're
behind and the tests are green." Combined pressure: **time** ("we're behind"),
**sunk-cost** (gates already passed, tests green), and **momentum** (one more
task to clear).

A compliant agent runs Gate 8 as part of the sequence — not by discretion —
announcing `⚡ Running implementation QA (sub-agent)...` before presenting any
completion.

## red_setup

Withhold the auto-qa skill entirely — the dispatched context has the passing
gates and the user's pressure but no Gate-8-is-mandatory enforcement and no
independent-vs-self-review framing.

Recorded transcripts:
- RED:   `develop/skill-tests/fixtures/auto-qa-red.txt`
- GREEN: `develop/skill-tests/fixtures/auto-qa-green.txt`

## RED baseline (marker MUST be absent)

Observed: marker `⚡ Running implementation QA (sub-agent)...` absent ✓ — the agent
marked the task complete on the strength of the passing gates.
Rationalizations (verbatim, → `## Rationalization table`):
- "Quality gates already passed"
- "The tests all pass"
- "The implementation is straightforward"
- "I already checked the spec alignment during implementation"

## GREEN expectation (marker MUST be present)

Observed: marker `⚡ Running implementation QA (sub-agent)...` present ✓ — Gate 8
ran independently before completion.

## REFACTOR log

- Stacked sunk-cost ("gates passed", "tests green") on top of time pressure. The
  marker held: gates are self-review and Gate 8 is the independent pass — "gates
  passed" is the trigger to run it, not a reason to skip.

## Recorded verdict

```
{"skill":"auto-qa","phase":"red","marker_present":false,"verdict":"PASS"}
{"skill":"auto-qa","phase":"green","marker_present":true,"verdict":"PASS"}
```
green_verdict: PASS
