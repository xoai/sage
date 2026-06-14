---
name: skill-no-tests
description: >
  Fixture discipline skill with a marker but NO sibling TESTS.md. The harness
  must exit 2 (setup error) because there is no scenario to dispatch.
version: "1.0.0"
modes: [build]
skill_type: discipline
compliance_marker: "⚡ Running spec review (sub-agent)..."
---

# skill-no-tests (fixture)

A discipline skill missing its TESTS.md. The harness cannot run without a
scenario, so it must exit 2 rather than fabricate one.

## Rationalization table

| The excuse (observed) | Why it's wrong | The rule |
|---|---|---|
| "fixture" | n/a | n/a |
