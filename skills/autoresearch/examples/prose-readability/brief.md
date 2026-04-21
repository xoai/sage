---
type: autoresearch
goal: "Lower Flesch-Kincaid grade level to 8 or below"
metric:
  name: grade_level
  direction: lower
  target: 8
scope:
  writable: ["docs/**/*.md", "README.md"]
  frozen: ["docs/api/**", "CHANGELOG.md"]
verify: "bash .sage/work/20260421-readability/autoresearch.sh"
budget:
  per_run_seconds: 30
  max_iterations: 30
  termination: target
---

# Improve prose readability

Documentation is written at a graduate-school reading level (~14).
Target is grade 8 (readable by a 14-year-old). Simplify sentence
structure, replace jargon with plain language, break long paragraphs.
Do NOT remove technical accuracy — simplify the language, not the content.
