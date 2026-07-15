---
name: quality-gates
description: >
  Orchestrates the quality gate sequence after task implementation.
  Gates run in order. A FAIL at any gate triggers fix-and-retry or
  escalation. All mandatory gates must pass before the task is complete.
  Judgment gates 1-3 reach an independent verdict via one combined reviewer
  by default (gate_review); on resume close-out, one combined review replaces
  re-running the whole ceremony. Script gates run --quiet.
version: "1.2.0"
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
mandatory; spec-compliance, code-quality, and auto-QA optional;
constitution-compliance skipped).

### How the judgment gates dispatch — `gate_review` (default: `combined`)

Read `gate_review` from `.sage/config.yaml` (absent → `combined`). It controls
how the three judgment gates (1 spec, 2 constitution, 3 quality) reach an
*independent* verdict — the property the eval says actually works (enforcement
by construction, not by self-persuasion). It does NOT touch the deterministic
script gates (1-script, 4, 5); those always run.

- **`combined`** (default) — Gates 1–3 run as **one** adversarial sub-agent
  dispatch (the combined reviewer, § Performance). One independent context
  judges spec + constitution + quality together. This is the balance the
  2026-07-15 resume profile bought: the review is still independent and still
  adversarial, at one dispatch's context cost instead of three or four.
- **`per-gate`** — each of Gates 1–3 dispatches its own reviewer. Maximal
  separation, maximal cost. Choose it when a project's constitution review is
  heavy enough to warrant its own context.
- **`off`** — self-review only, no sub-agent. The honest fallback when the Task
  tool is unavailable, or an explicit low-cost opt-out. Self-review is weaker;
  `off` is a choice, never a silent default.

Legacy `independent_gate3: false` still means "self-review Gate 3"; when
`gate_review` is unset it forces Gate 3 to `off`. If both are set, `gate_review`
wins.

**Whichever mode, the deterministic script gates still run** (`--quiet`, § Rules):
spec-check, hallucination-check, verify. A sub-agent's judgment never replaces the
scripts' evidence, and the scripts' green never replaces the sub-agent's judgment.

## Sequence

### Gate 1: Spec Compliance

Does the implementation match the task specification? Nothing missing,
nothing extra.

**Script first:** Run `bash .sage/gates/scripts/sage-spec-check.sh --quiet [plan-path] [task-number]`
Exit 1 → the gate FAILS regardless of agent assessment.
Exit 2 → UNVERIFIABLE; see "Unverifiable Gate Handling" below. Never a pass.
(`--quiet` collapses the PASS banner to one line; a FAIL still prints in full.)

**Agent review:** Under `gate_review: combined` (default) this gate's judgment is
folded into the one combined reviewer (§ Performance) — do not dispatch it
separately. Under `per-gate`, read
`sage/core/capabilities/review/spec-review/SKILL.md` and dispatch it on its own.
Either way, be adversarial: do not trust your own report — verify independently
that every spec requirement is implemented and tested.

### Gate 2: Constitution Compliance

Does the implementation violate any project/org principles? Are
mandated patterns followed?

**Agent review:** Check each principle in the active constitution
(base + preset). No script for this gate — it requires judgment. Under
`gate_review: combined` (default) it is folded into the combined reviewer;
under `per-gate` it runs on its own.

### Gate 3: Code Quality (independent review — sub-agent when Task tool available)

Is the code clean, secure, maintainable, and performant? Security
issues are always critical.

**Gate 3's verdict must be independent when the Task tool is available.** How it
dispatches follows `gate_review` (§ "How the judgment gates dispatch"):

- `combined` (default) → **do not dispatch Gate 3 on its own.** Its quality
  verdict is one of the three the combined reviewer returns (§ Performance).
  Read `sage/core/capabilities/review/quality-review/SKILL.md` for the criteria
  the combined reviewer applies.
- `per-gate` → Announce "⚡ Running code quality review (sub-agent)...", read
  `sage/core/capabilities/review/quality-review/SKILL.md`, spawn a dedicated
  sub-agent with its code-review prompt, present findings as the Gate 3 result.
- `off`, or Task tool unavailable → self-review using the same capability.
  Announce "Self-review — Task tool not available" (or "Self-review — gate_review
  off"). Self-review is the fallback, not a choice made silently when a sub-agent
  was available.

Security issues found here are ALWAYS critical — they cause FAIL regardless of
which mode surfaced them.

### Gate 4: Hallucination Check

Are all imports, APIs, methods, and version numbers real? Does the
implementation actually do what the comments say?

**Script first:** Run `bash .sage/gates/scripts/sage-hallucination-check.sh --quiet [target-dir] [project-root]`
Exit 1 → the gate FAILS.
Exit 2 → UNVERIFIABLE; see "Unverifiable Gate Handling" below. Never a pass.
(`--quiet` keeps the truthful counters and any failure detail; it drops only banners.)

**Agent review:** Check for non-obvious hallucinations the script
can't catch — phantom API methods, wrong function signatures,
incorrect version-specific behavior.

### Gate 5: Verification

Run the tests. Run the feature. Show evidence. Don't trust claims.

**Script first:** Run `bash .sage/gates/scripts/sage-verify.sh --quiet [project-root]`
Exit 1 → the gate FAILS.
Exit 2 → UNVERIFIABLE; see "Unverifiable Gate Handling" below. A project with
no tests does NOT pass this gate.
(`--quiet` prints one PASS summary line; a FAIL still pastes the last 40 lines
of test output as evidence.)

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

### Gate 8: Auto-QA (sub-agent, advisory)

Independent sub-agent verification of implementation against spec.
Runs as part of the gate sequence, not by agent discretion.

**On resume close-out** (a cycle resumed via `manifest.py resume`): Gate 8 is
**folded into the one combined reviewer** — its independent-verification-against-spec
job is exactly the combined reviewer's Gate 1, and dispatching a second sub-agent
to re-check the same thing is the duplication the resume profile flagged. Do not
spawn a separate Auto-QA sub-agent on resume close-out; the combined reviewer
carries the spec-verification verdict. (First-session builds still run Gate 8 as
below — that session has no prior independent read to fold into.)

**Activation conditions (ALL must be true):**
1. Task tool is available
2. Scope is Standard or Comprehensive (Lightweight tasks skip)
3. `auto_qa` ≠ false in `.sage/config.yaml`
4. NOT a resume close-out (see above — folded into the combined reviewer there)

Skip handling — a skipped QA that leaves no trace reads as a QA that passed,
so a Task-tool skip is LOUD (R29):
- Condition 1 false (Task tool unavailable) AND scope is Standard+ → announce
  `Sage: auto-QA skipped — Task tool unavailable on this platform. Quality
  chain is degraded.` and append one line to the initiative's `decisions.md`.
- Condition 2 false (Lightweight scope) → skip, no announcement (nothing to QA).
- Condition 3 false (`auto_qa: false`) → skip with the one-line "disabled" note.

**When active:**
1. Announce: "⚡ Running implementation QA (sub-agent)..."
2. Read `sage/core/capabilities/review/auto-qa/SKILL.md`.
3. Gather changed file list, spec path, plan path, test files.
4. Spawn sub-agent with the Implementation QA prompt.
5. Present findings inline.

**Advisory.** Gate 8 findings are warnings and recommendations.
A failure does NOT block the build — it produces findings with
[R] Fix / [P] Proceed / [D] Discuss options. But findings MUST
be presented to the user before Step 8.

**Fix-and-recheck:** If user picks [R], fix the specific issues
(file:line provided), then re-run Gate 8 (max 2 iterations).

## Rules

- Script-based gates (1, 4, 5) run FIRST, invoked with `--quiet`. Script
  failure = gate failure. `--quiet` trims only the PASS banners — every FAIL
  and every UNVERIFIABLE still prints its full evidence.
- Agent review runs SECOND. It catches what scripts can't.
- Security issues in Gate 3 are ALWAYS critical — they cause FAIL.
- The judgment gates (1–3) reach an INDEPENDENT verdict when the Task tool is
  available — as one combined reviewer (default) or per-gate. Self-review
  (`gate_review: off`, or no Task tool) is the announced fallback, never a
  silent default.
- Gate 8 (Auto-QA) is advisory — findings don't block, but MUST be
  presented to the user.
- Gate failures trigger fix-and-retry (max 3), then escalate to human.
- Never skip mandatory gates. They are mandatory, not suggestions.

## Resume close-out: one combined review, not the whole ceremony again

When this gate sequence runs at the **close-out of a RESUMED cycle** — a session
that started from `manifest.py resume` and is finishing the last task(s) — the
first session already ran per-task gates on everything it built. Re-running the
full adversarial suite from scratch is where the 2026-07-15 profile found ~24% of
the resume session's spend going: named dispatches like "Gate 1 adversarial spec
review", "Gates 2+3 review", "Adversarial Gate 3 review", and "Re-verify gates on
fixed HEAD" — the same work, reviewed twice.

On resume close-out:

1. **Run the deterministic script gates** (spec-check on the finished tasks,
   hallucination, verify) over the change — `--quiet`. Cheap, and they are the
   evidence base. Always.
2. **Dispatch exactly ONE combined reviewer** (Gates 1–3, § Performance) over the
   **whole cycle diff** — the delta this session added, seen in the context of
   the branch as a whole. Not one reviewer per gate; not one reviewer per task
   already reviewed. The whole-change view is the reliability anchor (per-task
   review can't see across tasks — that is exactly what a resuming session is
   assembling), and one dispatch is the cost the profile targeted.
3. **If that reviewer finds something**, fix it and **re-review only the fix**,
   not the whole suite again (the quality-locked cap in `sage_flags.py` governs
   the loop). Do not spawn a fresh "re-verify gates on fixed HEAD" pass — the
   script gates re-run over the fix and the reviewer re-reads the fix; that is
   the re-verification.

`gate_review: per-gate` overrides this to separate dispatches even on resume;
`off` drops to self-review. Combined is the default because it keeps the
independent whole-change review — the thing that catches real defects — while
paying for it once.

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

### Unverifiable Gate Handling

A gate script exits `2` when it could not run its check at all: nothing to
examine, or the tooling is absent. That is neither a pass nor a failure — the
gate produced no evidence, and evidence is the only thing it is for.

**Never auto-pass an exit 2.** Never re-run and hope. Stop and present:

```
⚠️  Gate <N> UNVERIFIABLE — <reason from the script>

    Nothing was checked. This is not a pass.

    [P] Proceed unverified — record a waiver in .sage/decisions.md
    [F] Fix verification setup — <the script names the missing tool>
```

On `[P]`: append to `.sage/decisions.md` — the gate, the reason, the timestamp,
and who approved it — then continue. A cycle that completes with waived gates
says so in its manifest.

On `[F]`: the user installs the runner or toolchain; re-run the same gate.

Exit 2 is common and legitimate: a docs-only change has no tests, a CLI project
has no browser, a Python project may have no type-checker. Treating those as
failures trains users to ignore gate output, which is the failure mode this
whole layer exists to prevent. Treating them as passes is a lie.

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

### The combined reviewer (default — Tier 1 platforms with Task tool)

This is what `gate_review: combined` dispatches, and it is the default. Gates 1–3
(judgment) run as ONE sub-agent, concurrently with Gates 4–5 (scripts) in the
main session. One dispatch, three verdicts — the cost the resume profile targeted,
without giving up an independent adversarial read.

**Main agent dispatches Gates 1-3 to a single reviewer sub-agent:**

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

**Main agent runs Gates 4-5 concurrently (`--quiet`):**
- Gate 4: `bash .sage/gates/scripts/sage-hallucination-check.sh --quiet`
- Gate 5: `bash .sage/gates/scripts/sage-verify.sh --quiet`

**Merge results:** After both complete, combine findings. Any FAIL
from either path = gate failure. Present unified result to user.

**`per-gate` opt-in:** When `gate_review: per-gate`, dispatch Gates 1, 2, and 3
as separate reviewers instead of the one combined dispatch. Costs more; buys a
dedicated context per gate. Everything else (the concurrent script gates, the
merge) is identical.

**Fallback:** If Task tool is unavailable or the sub-agent fails to
spawn, run all gates sequentially in the main session (self-review for 1–3).

### Sequential Execution (Tier 2 platforms)

All gates run sequentially in the same session. Adversarial prompting
still applies — the agent reviews its own work with explicit
instructions to be skeptical of its own output.
