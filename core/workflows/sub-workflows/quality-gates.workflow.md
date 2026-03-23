---
name: quality-gates
description: >
  Orchestrates the quality gate sequence after task implementation.
  Gates run in order. A FAIL at any gate triggers fix-and-retry or
  escalation. All mandatory gates must pass before the task is complete.
version: "1.1.0"
---

# Quality Gates Sub-Workflow

Run after implementation (per-task in build-loop, or at completion
for simpler workflows). Gates are sequential and cumulative —
a failure at Gate 1 means Gates 2-5 don't run until Gate 1 passes.

## Before Running Gates

Read `.sage/gates/gate-modes.yaml` for gate activation. For the
current workflow mode (build/fix/architect), check each gate's
status: `mandatory` (must pass), `optional` (run but warn only),
or `skipped` (don't run).

If `gate-modes.yaml` doesn't exist, default to all mandatory for
build/architect and reduced set for fix (hallucination + verification
mandatory, spec-compliance optional, others skipped).

## Sequence

### Gate 1: Spec Compliance

Does the implementation match the task specification? Nothing missing,
nothing extra.

**Script first:** Run `bash .sage/gates/scripts/sage-spec-check.sh [plan-path] [task-number]`
If the script fails (exit code non-zero), the gate FAILS regardless
of agent assessment.

**Agent review:** Read `sage/core/capabilities/review/spec-review/SKILL.md`
for adversarial verification. Do not trust your own report — verify
independently that every spec requirement is implemented and tested.

### Gate 2: Constitution Compliance

Does the implementation violate any project/org principles? Are
mandated patterns followed?

**Agent review:** Check each principle in the active constitution
(base + preset). No script for this gate — it requires judgment.

### Gate 3: Code Quality

Is the code clean, secure, maintainable, and performant? Security
issues are always critical.

**Agent review:** Read `sage/core/capabilities/review/quality-review/SKILL.md`
for the 5-dimension review (readability, error handling, security,
performance, conventions).

### Gate 4: Hallucination Check

Are all imports, APIs, methods, and version numbers real? Does the
implementation actually do what the comments say?

**Script first:** Run `bash .sage/gates/scripts/sage-hallucination-check.sh [target-dir] [project-root]`
If the script fails, the gate FAILS.

**Agent review:** Check for non-obvious hallucinations the script
can't catch — phantom API methods, wrong function signatures,
incorrect version-specific behavior.

### Gate 5: Verification

Run the tests. Run the feature. Show evidence. Don't trust claims.

**Script first:** Run `bash .sage/gates/scripts/sage-verify.sh [project-root]`
If the script fails, the gate FAILS.

**Agent review:** Read `sage/core/capabilities/debugging/verify-completion/SKILL.md`
for acceptance criteria verification beyond what the script checks.

### Extension Gates (order: 50+, if enabled)

Domain-specific checks from installed extensions.
e.g., OWASP security scan, accessibility audit, performance budget.

### Gate 6: Browser Check (optional, advisory)

Read `sage/core/capabilities/verification/browser-check/SKILL.md`.

**Activation conditions (ALL must be true):**
1. Lightpanda MCP tools are available (tool discovery succeeds)
2. The change touches user-facing code (frontend, API with UI consumers)
3. A running URL is known or obtainable

If ANY condition is false → skip INVISIBLY. No output, no warning.

**When active:** Navigate to the primary affected route, check for
JS errors, verify non-empty content, verify key elements. 30 seconds max.

**Advisory only.** A failure produces a warning and recommends /qa
or /fix. It does NOT block the build. Hard-blocking on an optional
external dependency would break Sage for users without Lightpanda.

### Gate 7: Design Check (optional, advisory)

Read `sage/core/capabilities/verification/design-check/SKILL.md`.

**Activation conditions (ALL must be true):**
1. The diff contains frontend files (.html, .css, .jsx, .tsx, .vue, .svelte, etc.)
2. Does NOT require Lightpanda (code-only analysis)

If no frontend files in diff → skip INVISIBLY.

**When active:** Scan for hardcoded colors (if design system exists),
missing interactive states, AI slop indicators. 15 seconds max.

**Advisory only.** Warnings/notes, never blocks.

## Rules

- Script-based gates (1, 4, 5) run FIRST. Script failure = gate failure.
- Agent review runs SECOND. It catches what scripts can't.
- Security issues in Gate 3 are ALWAYS critical — they cause FAIL.
- Gate failures trigger fix-and-retry (max 3), then escalate to human.
- Never skip mandatory gates. They are mandatory, not suggestions.

## Fallbacks

### Gate Failure Handling

Gate returns FAIL + fix-and-retry:
→ Agent fixes the specific issue identified
→ Gate re-runs (same gate, not from Gate 1)
→ Maximum retries: 3 per gate
→ After 3 retries: escalate to human

Gate returns FAIL + escalate-to-human:
→ Workflow pauses immediately
→ Present findings to human with full context
→ Human decides: fix manually, change approach, or waive

Gate returns PASS:
→ Proceed to next gate

## Mode-Specific Defaults

If `.sage/gates/gate-modes.yaml` is missing, use these defaults:

**FIX mode:**
Mandatory: hallucination-check, verification
Optional: spec-compliance
Skipped: constitution-compliance, code-quality

**BUILD mode:**
Mandatory: ALL five gates
Optional: extension gates
Skipped: none

**ARCHITECT mode:**
Mandatory: ALL five gates
Optional: extension gates + cross-artifact consistency
Skipped: none

## Performance

### Parallel Dispatch (Tier 1 platforms with Task tool)

On platforms supporting sub-agents (Claude Code Task tool), Gates 1-3
(judgment-based) can run in parallel with Gates 4-5 (script-based):

**Main agent dispatches Gates 1-3 to reviewer sub-agent:**

Use the Sub-Agent Delegation Protocol from the navigator. The context
package for gate review:
```
PERSONA: sage/core/agents/reviewer.persona.md
ARTIFACTS: [implementation files] + [spec file]
DECISIONS: [last 3 from decisions.md]
LEARNINGS: [sage_memory_search for this domain]
TASK: Run Gates 1-3 (spec compliance, constitution, code quality).
  For each gate: PASS or FAIL with specific findings.
  Be adversarial — do not trust the implementing agent's claims.
RETURN: Structured findings per gate to stdout.
```

**Main agent runs Gates 4-5 concurrently:**
- Gate 4: `bash .sage/gates/scripts/sage-hallucination-check.sh`
- Gate 5: `bash .sage/gates/scripts/sage-verify.sh`

**Merge results:** After both complete, combine findings. Any FAIL
from either path = gate failure. Present unified result to user.

**Fallback:** If Task tool is unavailable or sub-agent fails to
spawn, run all gates sequentially in the main session.

### Sequential Execution (Tier 2 platforms)

All gates run sequentially in the same session. Adversarial prompting
still applies — the agent reviews its own work with explicit
instructions to be skeptical of its own output.
