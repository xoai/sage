---
name: skill-no-marker
description: >
  Fixture discipline skill that is MISSING its compliance_marker. The harness
  must exit 2 (setup error) when asked to run this.
version: "1.0.0"
modes: [build]
skill_type: discipline
---

# skill-no-marker (fixture)

A discipline skill with no declared compliance marker. Used to assert the
harness refuses to run (exit 2) rather than guessing a verdict.

## Rationalization table

| The excuse (observed) | Why it's wrong | The rule |
|---|---|---|
| "fixture" | n/a | n/a |
