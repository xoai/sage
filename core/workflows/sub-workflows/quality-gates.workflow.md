---
name: quality-gates
description: >
  Orchestrates the quality gate sequence after each task implementation.
  Gates run in order. A FAIL at any gate triggers fix-and-retry or
  escalation. All mandatory gates must pass before the task is complete.
version: "1.0.0"
---

# Quality Gates Sub-Workflow

Run after every task implementation. Gates are sequential and cumulative —
a failure at Gate 1 means Gates 2-5 don't run until Gate 1 passes.

## Sequence

1. **Gate 1** → `spec-compliance` (order: 01)
   Does the implementation match the task specification?
   Nothing missing, nothing extra.

2. **Gate 2** → `constitution-compliance` (order: 02)
   Does the implementation violate any project/org principles?
   Are mandated patterns followed?

3. **Gate 3** → `code-quality` (order: 03)
   Is the code clean, secure, maintainable, and performant?
   Security issues are always critical.

4. **Gate 4** → `hallucination-check` (order: 04)
   Are all imports, APIs, methods, and version numbers real?
   Does the implementation actually do what the comments say?

5. **Gate 5** → `verification` (order: 05)
   Run the tests. Run the feature. Show evidence. Don't trust claims.

6. **Extension gates** (order: 50+, if enabled)
   Domain-specific checks from installed extensions.
   e.g., OWASP security scan, accessibility audit, performance budget.

## Fallbacks

### Gate Failure Handling

```
Gate returns FAIL + fix-and-retry:
  → Agent fixes the specific issue identified
  → Gate re-runs (same gate, not from Gate 1)
  → Maximum retries: 3 per gate (from project config)
  → After 3 retries: escalate to human

Gate returns FAIL + escalate-to-human:
  → Workflow pauses immediately
  → Present findings to human with full context
  → Human decides: fix manually, change approach, or waive

Gate returns PASS:
  → Proceed to next gate
```

## Mode-Specific Gate Activation

Controlled by `core/gates/_config/gate-modes.yaml`:

```
FIX mode:
  Mandatory: hallucination-check, verification
  Optional:  spec-compliance
  Skipped:   constitution-compliance, code-quality

BUILD mode:
  Mandatory: ALL five gates
  Optional:  extension gates
  Skipped:   none

ARCHITECT mode:
  Mandatory: ALL five gates
  Optional:  extension gates + cross-artifact consistency
  Skipped:   none
```

## Performance

On Tier 1 platforms (subagent support):
- Gates 1-3 can run as separate reviewer subagents (adversarial review)
- Gates 4-5 run in the main session (need code execution)

On Tier 2 platforms:
- All gates run sequentially in the same session
- Adversarial prompting still applies (the agent reviews its own work
  with explicit instructions to be skeptical)
