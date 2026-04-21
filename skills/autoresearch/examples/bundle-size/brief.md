---
type: autoresearch
goal: "Reduce JavaScript bundle size below 200KB"
metric:
  name: bundle_kb
  direction: lower
  target: 200
scope:
  writable: ["src/**/*.ts", "src/**/*.tsx", "src/**/*.js"]
  frozen: ["package.json", "pnpm-lock.yaml", "tsconfig.json"]
verify: "bash .sage/work/20260421-bundle/autoresearch.sh"
budget:
  per_run_seconds: 120
  max_iterations: 50
  termination: target
---

# Reduce bundle size

The main JS bundle is 340KB. Target is under 200KB without
breaking functionality. Focus on code splitting, tree-shaking,
and lazy loading — NOT dependency changes (package.json is frozen).
