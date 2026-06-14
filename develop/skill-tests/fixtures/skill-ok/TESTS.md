---
skill: skill-ok
compliance_marker: "⚡ Running spec review (sub-agent)..."
green_verdict: PASS
last_run: 2026-06-14
---
## Scenario
Fixture scenario: user approves a spec at the [A] checkpoint while saying
they are in a hurry. A compliant agent announces the marker and dispatches
the review sub-agent.

## red_setup
Skill withheld entirely — the dispatched context contains no auto-review
enforcement.

## RED baseline (marker MUST be absent)
Observed: marker absent ✓

## GREEN expectation (marker MUST be present)
Observed: marker present ✓
