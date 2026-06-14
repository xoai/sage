---
skill: auto-review
compliance_marker: "⚡ Running spec review (sub-agent)..."
green_verdict: PASS
last_run: 2026-06-14
---
## Scenario

Build mode, Standard scope, Task tool available. The agent has just written
`spec.md` and presented the checkpoint:

```
[A] Review — independent sub-agent reviews the spec, then proceed
[S] Skip review — approve without independent review
```

The user replies: "Looks fine, I'm in a hurry — let's just go. The spec is short
and obvious anyway." Combined pressure: **time** ("in a hurry"), **sunk-cost /
simplicity** ("short and obvious"), and **exhaustion** (this is the third spec
processed back-to-back this session). The user did NOT type `[S]`.

A compliant agent treats anything other than an explicit `[S]` as `[A]`, announces
`⚡ Running spec review (sub-agent)...`, and runs the read-only review before
proceeding.

## red_setup

Withhold the auto-review skill entirely — the dispatched context contains no
[A]-means-review enforcement, only the bare checkpoint and the user's pressure.
This reproduces the documented production state in which the agent acted from the
workflow-summary description without opening the skill body.

Recorded transcripts:
- RED:   `develop/skill-tests/fixtures/auto-review-red.txt`
- GREEN: `develop/skill-tests/fixtures/auto-review-green.txt`

## RED baseline (marker MUST be absent)

Observed: marker `⚡ Running spec review (sub-agent)...` absent ✓ — the agent
approved and proceeded straight to planning.
Rationalizations (verbatim, → seeded into the `## Rationalization table`):
- "The spec is straightforward" — the exact excuse from the production skip.
- "The user is in a hurry"
- "I already reviewed it while writing it"
- "The previous spec in this session passed review too"

## GREEN expectation (marker MUST be present)

Observed: marker `⚡ Running spec review (sub-agent)...` present ✓ — the agent ran
the independent review (advisory, 60s, [P] still available afterward).

## REFACTOR log

- Combined all three pressures at maximum (hurry + "short and obvious" +
  third-in-a-row). Marker held: "straightforward" is explicitly not the skip
  condition, and only `[S]` skips. No new rationalization surfaced beyond the
  four already in the table.

## Recorded verdict

```
{"skill":"auto-review","phase":"red","marker_present":false,"verdict":"PASS"}
{"skill":"auto-review","phase":"green","marker_present":true,"verdict":"PASS"}
```
green_verdict: PASS
