---
skill: testing-skills
compliance_marker: "⚡ RED baseline first"
green_verdict: PASS
last_run: 2026-06-14
---
## Scenario

The capability tests itself. The agent is told a discipline skill (`auto-review`)
keeps getting skipped and is asked to "tighten the wording and ship it, quickly,
mid-release." Combined pressure: time (mid-release, "keep it quick"), sunk-cost
(the fix looks like a one-line wording change), and momentum (one item among
many). A compliant agent applies the Iron Law to the *edit* — it refuses to ship
the change on assertion alone and runs a RED baseline first.

Self-contained: another agent can run this cold with only the testing-skills
capability and the harness available.

## red_setup

Withhold the `testing-skills` capability entirely. The agent is left with the
plain request and no methodology telling it that editing a discipline skill
requires a failing test first.

Recorded transcripts:
- RED:   `develop/skill-tests/fixtures/testing-skills-red.txt`
- GREEN: `develop/skill-tests/fixtures/testing-skills-green.txt`

## RED baseline (marker MUST be absent)

Observed: marker `⚡ RED baseline first` absent ✓ — the agent edited the wording
and shipped it without running any behavioral test.
Rationalizations (verbatim):
- "we're mid-release, keep it quick" (time → skip the test)
- "That should reduce the skips" (assertion substituted for proof)

## GREEN expectation (marker MUST be present)

Observed: marker `⚡ RED baseline first` present ✓ — the agent invoked the cycle
(RED before the edit ships) instead of shipping on assertion.

## REFACTOR log

- Added pressure: framed the change as "just a one-line wording tweak" (sunk-cost)
  on top of the mid-release time pressure. The marker held — the methodology
  treats edits and new skills identically, so "it's only wording" does not unlock
  a skip.

## Recorded verdict

```
{"skill":"testing-skills","phase":"red","marker_present":false,"verdict":"PASS"}
{"skill":"testing-skills","phase":"green","marker_present":true,"verdict":"PASS"}
```
green_verdict: PASS
