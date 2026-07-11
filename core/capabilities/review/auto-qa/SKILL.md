---
name: auto-qa
description: >
  Use after implementation passes the quality gates, when a change needs an
  independent pass over the code before it ships, or when the user asks to
  "QA this", "check the implementation", or "verify it matches the spec".
  Applies to Standard and Comprehensive scopes with the Task tool available;
  Lightweight tasks skip.
version: "1.2.0"
modes: [build, architect, fix]
skill_type: discipline
compliance_marker: "⚡ Running implementation QA (sub-agent)..."
---

<!-- sage-metadata
cost-tier: haiku
activation: auto
tags: [qa, verification, sub-agent, quality, implementation]
inputs: [spec, plan, code, tests]
outputs: [findings]
requires: [Task tool]
-->

# Auto-QA

Quick independent verification of implementation against spec via
sub-agent delegation. Runs as **Gate 8** in the quality gates
sequence — positioned after Gate 5 (verification), alongside
Gate 6 (browser) and Gate 7 (design). 60 seconds max. Code-only.
Advisory — never blocks.

## When to Run

Auto-QA runs as Gate 8 in the quality-gates workflow. The gate
sequence triggers it — the agent does not decide whether to run it.

**Activation conditions (checked by quality-gates workflow):**

1. **Task tool is available.** If not (e.g., Antigravity), there is no
   self-review fallback — self-review shares the author's blind spots, which is
   the entire thing auto-QA exists to avoid. So the review is skipped.

   **Declare the skip in the cycle manifest. Do not log it — the log is taken.**

   ```yaml
   qa: skipped-no-subagent    # or: passed | skipped-disabled | skipped-timeout | waived
   ```

   Two mechanisms then act on that, and neither is your discretion (R29):

   - The **spec-gate hook refuses to let the cycle reach `complete`** while `qa:`
     is still `pending`. A completion that says nothing about independent QA is
     not possible. You will be blocked, and told exactly what to write.
   - The **degradation-log hook writes the `decisions.md` line itself**, once,
     the moment you declare anything but `passed`.

   Announce it in the conversation too — `Sage: auto-QA skipped (no sub-agent
   dispatch). Quality chain is degraded.` — but understand what changed: the
   announcement is courtesy, the manifest field is the requirement, and the
   durable record is no longer your job.

   This used to be prose asking you to remember. Phase 4 measured the result:
   the `decisions.md` line got written in **one run out of three**. A rule the
   model must remember is a rule the model will forget, so it stopped being one.

2. **Scope is Standard or Comprehensive.** Lightweight tasks skip.

3. **Config allows it.** Check `.sage/config.yaml` for `auto_qa`.
   If `auto_qa: false`, skip with one-line note:
   "Auto-QA disabled. Run the QA command for manual testing."
   If `auto_qa: true` or absent (default), proceed.

When the scope is Standard+ and auto-QA cannot run because the Task tool is
absent, announce and log per condition #1 — a skipped QA that leaves no trace
reads as a QA that passed. (A config-disabled skip shows its one-line note; a
Lightweight-scope skip needs no announcement — there is nothing to QA.)

Gate 8 runs AFTER Gates 1-5 pass. Gates catch structural issues;
Gate 8 catches semantic issues (spec drift, missing handlers,
boundary gaps, integration mismatches).

## Time Budget

60 seconds max. If the sub-agent doesn't respond within 60 seconds,
skip with: "Auto-QA timed out. Run the QA command manually for full testing."

## Gathering Context for the Sub-Agent

Before spawning the sub-agent, gather:

1. **Spec path** — `.sage/work/*/spec.md`
2. **Plan path** — `.sage/work/*/plan.md`
3. **Changed files** — from build-loop task tracking. List all files
   created or modified during implementation.
4. **Test files** — any files matching `*test*`, `*spec*`, `*.test.*`,
   `*.spec.*` in the changed file list or in test directories.

Pass all four to the sub-agent prompt.

## Sub-Agent Prompt

```
You are a QA reviewer. You were NOT involved in writing this code.
Review the implementation with fresh eyes. Be specific. Be brief.

CRITICAL: You are READ-ONLY. Do NOT modify any files. Do NOT use
Edit or Write tools. Do NOT modify specs, plans, or code. Your job
is to REPORT findings, not fix them. The user decides what to do.

INPUTS:
- Spec: {SPEC_PATH}
- Plan: {PLAN_PATH}
- Changed files: {FILE_LIST}
- Test files: {TEST_FILE_LIST}

CHECK THESE 5 THINGS:

1. SPEC-IMPLEMENTATION ALIGNMENT: Read each acceptance criterion in
   the spec. Does corresponding code exist for each? Is anything
   implemented that the spec doesn't mention?

2. TEST-CRITERIA COVERAGE: Do tests verify the spec's acceptance
   criteria? Or do they only test implementation details? Flag any
   acceptance criterion with no test.

3. MISSING ERROR HANDLING: Scan changed files for: API calls without
   catch, form submissions without validation, state mutations
   without guards, async operations without loading/error states.
   Be specific — name the file, the line, the risk.

4. BOUNDARY CONDITIONS: Read the spec's boundaries and limits.
   Is each boundary enforced in code? Flag stated limits with no
   code enforcement.

5. INTEGRATION CONSISTENCY: If multiple modules were changed, do
   their interfaces match? Response shapes, event contracts, shared
   types. Flag mismatches.

6. CODING PRINCIPLES: Do changed files follow universal quality
   principles? Check for: magic numbers, swallowed errors, unclear
   names, functions doing multiple things, unnecessary global state,
   missing input validation. Flag clear violations, not style
   preferences.

CLASSIFY each finding:
- CRITICAL: Will break in production. Must fix.
- MAJOR: Will cause problems. Should fix before shipping.
- MINOR-substantive: Improvement opportunity. Affects readability,
  maintainability, or future behavior. Can fix later.
- MINOR-cosmetic: Style/naming/formatting with equally valid
  alternatives. No behavior change.

FORMAT (strict):
VERDICT: PASS | NEEDS FIXES | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. Every finding must name a specific file and what's wrong.
No generic observations. No praise. Just findings.
```

## Presentation Format

### Clean pass

```
⚡ Running implementation QA (sub-agent)...
✓ Auto-QA: PASS — no issues found.
Proceeding to completion.
```

### Issues found (no CRITICAL)

```
⚡ Running implementation QA (sub-agent)...

⚠ Auto-QA found {N} issues:

  MAJOR: {file:line — specific finding}
  MINOR: {file:line — specific finding}

[R] Fix issues — address findings before completing
[P] Proceed — ship as-is, I'll track these
[D] Discuss — let's talk about these findings

Pick R/P/D, or tell me what to change.
```

### Critical findings

```
⚡ Running implementation QA (sub-agent)...

🔴 Auto-QA found a CRITICAL issue:

  CRITICAL: {file:line — specific finding with impact}

[R] Fix — this will break in production
[D] Discuss — let's look at this
[P] Proceed anyway — I understand the risk
```

[P] Proceed is ALWAYS available. The user decides, not the gate.

## Fix-and-Recheck Flow

When the user picks [R] Fix:

1. The main agent reads the auto-QA findings
2. For each CRITICAL and MAJOR finding, the agent fixes directly
   (findings include file:line — no root cause investigation needed)
3. After fixes, re-run auto-QA sub-agent (same prompt, fresh context)
4. If still failing after 2 iterations, surface to user:
   "Auto-QA still finding issues after 2 fix attempts. Remaining:
   {findings}. [P] Proceed / [F] Route to /fix for deeper investigation"

Max 2 re-checks. This keeps the loop bounded.

## Decision Logging

After every auto-QA (any verdict), prepend to `.sage/decisions.md`:

```
### YYYY-MM-DD — Auto-QA: implementation
Verdict: {PASS|NEEDS FIXES|FAIL}. {findings summary if any}.
User chose: {R|P|D}. (auto-qa sub-agent)
```

## Enforcement

### The producing agent MUST NOT filter findings

Present ALL findings to the user exactly as the sub-agent returned
them. Do NOT remove, downgrade, or dismiss findings.

### Do NOT skip because gates passed

See the Rationalization table — these are the excuses observed when Gate 8 gets
skipped, each with the rule that overrides it.

## Rationalization table

Derived from the RED baseline in `TESTS.md`. Gate 8 runs as part of the sequence
when its conditions hold; the marker `⚡ Running implementation QA (sub-agent)...`
MUST appear — it is not the agent's discretion.

| The excuse (observed) | Why it's wrong | The rule |
|---|---|---|
| "Quality gates already passed." | Gates 1-5 are self-review; Gate 8 is the *independent* pass that catches semantic drift the structural gates can't. | Gate 8 runs after the gates pass, not instead of running. |
| "The implementation is straightforward." | Straightforward code still has integration gaps, missing handlers, and boundary holes. | Simplicity is not a skip condition. |
| "The tests all pass." | Passing tests don't mean the *right* things were tested against the spec's criteria. | Green tests do not substitute for independent verification. |
| "I already checked this during implementation." | Self-check shares the author's blind spots — it is not independent. | Independent context is the point; your own check doesn't count. |

## Failure Modes

- **Task tool not available:** No self-review fallback (it shares the author's
  blind spots). Skip the sub-agent and set `qa: skipped-no-subagent` in the cycle
  manifest — see Activation condition #1. The `decisions.md` line is written for
  you by the degradation-log hook, and the spec-gate will not let the cycle
  complete until you have declared *something*. Silence is not an available
  option any more; it used to be, and it was taken 2 times in 3.
- **Sub-agent times out:** Skip with note. Do NOT block workflow.
- **Sub-agent returns malformed output:** Present raw output to user
  with note: "QA format was unexpected. Please interpret."
- **Config says disabled:** Show one-line note, skip.
- **Fix-recheck loops > 2:** Surface remaining findings to user,
  offer /fix for deeper investigation.
