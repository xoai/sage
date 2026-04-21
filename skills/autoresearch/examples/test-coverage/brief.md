---
type: autoresearch
goal: "Increase test coverage to 90%"
metric:
  name: coverage_pct
  direction: higher
  target: 90
scope:
  writable: ["src/**", "tests/**", "test/**"]
  frozen: ["package.json", "jest.config.*", "vitest.config.*"]
verify: "bash .sage/work/20260421-coverage/autoresearch.sh"
budget:
  per_run_seconds: 180
  max_iterations: 100
  termination: target
---

# Increase test coverage

Current coverage is ~65%. Target is 90%. The agent should write
meaningful tests — not empty test stubs or tests that assert true.
Focus on uncovered branches and edge cases, not just line coverage.
