# Crash Handling

## Crash Types

| Type | Signal | What happened |
|------|--------|-------------|
| **Timeout** | Duration ≥ budget | Verify command hung or is too slow |
| **Exit code** | Non-zero exit | Build/test failed |
| **No metric** | No METRIC line | Verify ran but didn't output metric |
| **Bad value** | nan/inf | Metric is unparseable |
| **Scope violation** | Frozen file touched | Agent modified out-of-scope files |

## Decision: Retry vs Skip

### Retry (return to IDEATE with context)

- **Build failed with clear error** — the agent made a syntax error
  or broke an import. Read the crash log, understand the error, and
  propose a fix in the next IDEATE.
- **Timeout on first occurrence** — the change might have made the
  build slower. Revert and try a different approach.
- **Scope violation** — the agent's change touched frozen files.
  The runtime already reverted. In next IDEATE, constrain to writable scope.

### Skip (count as crash, move on)

- **Same crash 3 times in a row** — something fundamental is wrong
  with this direction. Abandon it and try something different.
- **OOM/resource exhaustion** — the verify command needs more resources
  than available. This is not fixable by code changes.
- **Missing dependency** — the verify command requires something not
  installed. Flag to user.

## Crash Log Location

Every iteration's stdout + stderr is saved to:
```
.sage/work/<slug>/runs/NNNN-<description>.log
```

When a crash occurs, READ THE LOG before the next IDEATE. The error
message tells you what went wrong.

## Consecutive Crash Limit

If 5 consecutive iterations crash, the stuck recovery playbook
activates (same as 5 consecutive discards). See `stuck-recovery.md`.
