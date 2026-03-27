---
name: auto-qa
description: >
  Automatic sub-agent code verification after quality gates pass.
  Independent context window. Checks spec-implementation alignment,
  test coverage, error handling, boundary conditions, and integration
  consistency. 30 seconds, code-only, advisory.
version: "1.0.0"
modes: [build, architect]
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
Gate 6 (browser) and Gate 7 (design). 30 seconds max. Code-only.
Advisory — never blocks.

## When to Run

Auto-QA runs as Gate 8 in the quality-gates workflow. The gate
sequence triggers it — the agent does not decide whether to run it.

**Activation conditions (checked by quality-gates workflow):**

1. **Task tool is available.** If not (e.g., Antigravity), skip
   silently. No self-review fallback.

2. **Scope is Standard or Comprehensive.** Lightweight tasks skip.

3. **Config allows it.** Check `.sage/config.yaml` for `auto_qa`.
   If `auto_qa: false`, skip with one-line note:
   "Auto-QA disabled. Run /qa for manual testing."
   If `auto_qa: true` or absent (default), proceed.

If ANY condition is false → skip silently (except config disabled
which shows one-line note).

Gate 8 runs AFTER Gates 1-5 pass. Gates catch structural issues;
Gate 8 catches semantic issues (spec drift, missing handlers,
boundary gaps, integration mismatches).

## Time Budget

30 seconds max. If the sub-agent doesn't respond within 30 seconds,
skip with: "Auto-QA timed out. Consider /qa for manual testing."

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
- MINOR: Improvement opportunity. Can fix later.

FORMAT (strict):
VERDICT: PASS | NEEDS FIXES | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR: [list or "None"]

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

After every auto-QA (any verdict), append to `.sage/decisions.md`:

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

Blocked rationalizations:
- "Quality gates already passed" — gates are self-review, auto-QA
  is independent review
- "The implementation is straightforward" — straightforward code
  still has integration gaps
- "The tests all pass" — tests passing doesn't mean the RIGHT
  things are tested
- "I already checked this during implementation" — self-check is
  not independent check

## Failure Modes

- **Task tool not available:** Skip silently. Do NOT self-review.
- **Sub-agent times out:** Skip with note. Do NOT block workflow.
- **Sub-agent returns malformed output:** Present raw output to user
  with note: "QA format was unexpected. Please interpret."
- **Config says disabled:** Show one-line note, skip.
- **Fix-recheck loops > 2:** Surface remaining findings to user,
  offer /fix for deeper investigation.
