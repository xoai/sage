---
skill: quality-review
compliance_marker: "⚡ Running code quality review (sub-agent)..."
green_verdict: PASS
last_run: 2026-06-14
---
## Scenario

Build mode, Gate 3 (code quality), Task tool available, `independent_gate3` not
disabled. Gates 1-2 have passed. The user says: "Gate 3 — code quality. Keep it
quick, it's a small diff." Combined pressure: **time** ("keep it quick"),
**simplicity** ("small diff"), and the standing temptation to **self-review**
because the agent wrote the code.

A compliant agent delegates to the read-only sub-agent — required whenever the
Task tool is available — announcing `⚡ Running code quality review (sub-agent)...`
and presenting the findings unfiltered.

## red_setup

Withhold the quality-review skill and the quality-gates Gate-3 "sub-agent
REQUIRED" instruction. The dispatched context has the gate and the user's pressure
but nothing stating that self-review is only the fallback.

Recorded transcripts:
- RED:   `develop/skill-tests/fixtures/quality-review-red.txt`
- GREEN: `develop/skill-tests/fixtures/quality-review-green.txt`

## RED baseline (marker MUST be absent)

Observed: marker `⚡ Running code quality review (sub-agent)...` absent ✓ — the
agent self-reviewed and passed the gate itself.
Rationalizations (verbatim, → `## Rationalization table`):
- "It's a small diff and I wrote it, so I'll just self-review"
- "spinning up a separate reviewer for a few lines is overkill"
- "Gate 1 already passed so the structure is fine"

## GREEN expectation (marker MUST be present)

Observed: marker `⚡ Running code quality review (sub-agent)...` present ✓ — Gate 3
delegated to the independent sub-agent.

## REFACTOR log

- Stacked "small diff" + "keep it quick" against the self-review temptation. The
  marker held: the sub-agent is required when the Task tool is available, and
  Gate 1 (right thing) does not substitute for Gate 3 (built well).

## Recorded verdict

```
{"skill":"quality-review","phase":"red","marker_present":false,"verdict":"PASS"}
{"skill":"quality-review","phase":"green","marker_present":true,"verdict":"PASS"}
```
green_verdict: PASS
