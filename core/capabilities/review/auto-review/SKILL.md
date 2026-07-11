---
name: auto-review
description: >
  Use when the user picks [A] Review at a spec/plan/ADR/root-cause/fix-plan
  checkpoint, or asks for an independent review before implementation begins.
  Applies to Standard and Comprehensive scopes with the Task tool available;
  Lightweight tasks skip.
version: "1.2.0"
modes: [build, architect, fix]
skill_type: discipline
compliance_marker: "⚡ Running spec review (sub-agent)..."
---

<!-- sage-metadata
cost-tier: haiku
activation: auto
tags: [review, verification, sub-agent, quality]
inputs: [spec, plan, adr]
outputs: [findings]
requires: [Task tool]
-->

# Auto-Review

Quick independent review of spec/plan/ADR via sub-agent delegation.
Triggered as part of the [A] Review checkpoint flow.
60 seconds max. Advisory — never blocks.

## When to Run

Auto-review runs when the user picks **[A] Review** at a
workflow checkpoint. It is part of the [A] flow, not a separate step.

The workflow checkpoint presents:
```
[A] Review — sub-agent reviews, then proceed
[S] Skip review — approve without independent review
```

When the user picks [A], the workflow MUST run auto-review before
proceeding to the next phase. The only way to skip is [S].

### Conditions (checked by the workflow before spawning)

1. **Task tool is available.** If not (e.g., Antigravity), [A] falls
   back to simple approval. This is a degradation, so make it loud —
   never silent (R29):
   - Announce: `Sage: auto-review skipped — Task tool unavailable on
     this platform. Quality chain is degraded.`
   - Append one line to the initiative's `decisions.md`:
     `[<date>] auto-review skipped (Task tool unavailable) — <phase>
     approved without independent review.`
   so `/reflect` and `/status` surface the gap later.

2. **Scope is Standard or Comprehensive.** Lightweight tasks skip
   auto-review — they have no spec/plan to review. [A] behaves as
   simple approval.

3. **Config allows it.** Check `.sage/config.yaml` for `auto_review`.
   If `auto_review: false`, [A] behaves as simple approval with note:
   "Auto-review disabled. Run the review command for independent evaluation."

When all conditions are met and user picks [A]: announce
"⚡ Running [type] review (sub-agent)..." and spawn the sub-agent.

## Time Budget

60 seconds max per review. If the sub-agent doesn't respond within
60 seconds, skip with: "Auto-review timed out. Run the review command
manually for a full evaluation." Do not block the workflow.

## Presentation Format

### Clean pass

```
⚡ Running spec review (sub-agent)...
✓ Auto-review: PASS — no issues found.
Proceeding to [next phase].
```

### Issues found (no CRITICAL)

```
⚡ Running spec review (sub-agent)...

⚠ Auto-review found {N} issues:

  MAJOR: {finding — specific, one line}
  MINOR: {finding — specific, one line}

[R] Revise — address findings before proceeding
[P] Proceed — I'll handle these during implementation
[D] Discuss — let's talk about these findings

Pick R/P/D, or tell me what to change.
```

### Critical findings

```
⚡ Running spec review (sub-agent)...

🔴 Auto-review found a CRITICAL issue:

  CRITICAL: {finding — specific, one line}

  Recommend: Revise before proceeding.

[R] Revise — address the critical issue
[D] Discuss — let's talk about this
[P] Proceed anyway — I understand the risk
```

[P] Proceed is ALWAYS available. The user decides, not the gate.

## Decision Logging

After every auto-review (any verdict), prepend to `.sage/decisions.md`:

```
### YYYY-MM-DD — Auto-review: {artifact type}
Verdict: {PASS|NEEDS REVISION|FAIL}. {findings summary if any}.
User chose: {R|P|D}. (auto-review sub-agent)
```

## Enforcement

### The producing agent MUST NOT filter findings

When the sub-agent returns its review, present ALL findings to the
user exactly as returned. Do NOT:
- Remove findings you disagree with
- Downgrade severity (CRITICAL → MAJOR)
- Add your own commentary dismissing findings
- Summarize multiple findings into one

The whole point is independent judgment. Filtering defeats it.

### Do NOT skip because the artifact "looks good"

See the Rationalization table below — those are the exact excuses observed in
the production skip, each with the rule that overrides it.

## Rationalization table

Derived from the RED baseline in `TESTS.md` (the documented production skip on
spec [A] / plan [A]). The compliance marker `⚡ Running [type] review
(sub-agent)...` MUST appear unless the user typed an explicit [S].

| The excuse (observed) | Why it's wrong | The rule |
|---|---|---|
| "The spec is straightforward, I'll continue." | Simplicity is not the skip condition — straightforward specs still hide framing drift and untestable criteria. | [A] runs the review; only an explicit [S] skips. |
| "The user is in a hurry." | The 60-second review is not the delay the user fears; a wrong spec carried into implementation is. | Time pressure never downgrades [A] to [S]. |
| "I already reviewed it while writing it." | Self-review shares the bias that produced the artifact — it is not independent. | Independent context is the whole point; your own pass doesn't substitute. |
| "The previous review passed." | This is a different artifact; the prior verdict says nothing about this one. | Each artifact gets its own review. |

---

## Sub-Agent Prompts

**All review sub-agents are READ-ONLY.** Include this constraint at
the top of every sub-agent prompt. Sub-agents MUST NOT modify any
files — no Edit, no Write, no code changes. Their role is to find
issues and report them. The user decides what to do with findings.

If a sub-agent modifies a spec, plan, or code file, the review is
INVALID and must be discarded. Re-run with the original artifact.

### Findings Classification (shared by all sub-agents)

Every finding gets ONE of these severity labels:

- **CRITICAL** — Must fix. Blocks the next phase.
- **MAJOR** — Should fix. Significant gap or risk.
- **MINOR-substantive** — Improvement opportunity that affects
  readability, maintainability, or future behavior. Examples:
  missing edge case handling, suboptimal data structure, fragile
  patterns, ambiguous naming that hurts comprehension.
- **MINOR-cosmetic** — Style/naming/formatting choices with equally
  valid alternatives. No behavior change. Examples: variable naming
  preferences, comment wording, equivalent syntactic forms, trailing
  whitespace.

The `--quality-locked` flag uses this distinction: it auto-revises
CRITICAL, MAJOR, and MINOR-substantive findings, but treats
MINOR-cosmetic as acceptable.

Without `--quality-locked`, the user decides what to do with all
findings regardless of severity.

### Spec Review

Use when: spec.md is approved [A] in build or architect workflow.

```
You are a spec reviewer. You were NOT involved in writing this spec.
Evaluate it with fresh eyes. Be specific. Be brief.

CRITICAL: You are READ-ONLY. Do NOT modify any files. Do NOT use
Edit or Write tools. Your job is to REPORT findings, not fix them.
If you find an issue, describe it — do not attempt to correct it.

Read the spec at: {SPEC_PATH}
Read the framing decision from: .sage/decisions.md (most recent
framing entry)

CHECK THESE 5 THINGS:

1. FRAMING ALIGNMENT: Does the spec address the pain stated in the
   Framing section? Or has it drifted to solve a different problem?

2. ACCEPTANCE CRITERIA: Is every criterion testable? Can each one
   be verified with a specific observable check? Flag any that use
   vague language (works well, handles gracefully, is fast).

3. BOUNDARY COMPLETENESS: Are the WILL NOT boundaries specific
   enough? Are there obvious exclusions missing?

4. MISSING EDGE CASES: Based on the described behavior, what failure
   modes are not addressed? Empty states, errors, permissions,
   concurrent access.

5. INTERNAL CONSISTENCY: Do intent, boundaries, and acceptance
   criteria align? Does the acceptance criteria test what the
   intent promises?

CLASSIFY each finding:
- CRITICAL: Must fix before planning. Blocks proceeding.
- MAJOR: Should fix before planning. Significant gap.
- MINOR-substantive: Improvement opportunity. Affects readability,
  maintainability, or future behavior. Can address later.
- MINOR-cosmetic: Style/naming/formatting with equally valid
  alternatives. No behavior change.

FORMAT (strict):
VERDICT: PASS | NEEDS REVISION | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. No generic praise. No padding. Just findings.
```

### Plan Review

Use when: plan.md is approved [A] in build or architect workflow.

```
You are a plan reviewer. You were NOT involved in writing this plan.
Evaluate it with fresh eyes. Be specific. Be brief.

CRITICAL: You are READ-ONLY. Do NOT modify any files. Do NOT use
Edit or Write tools. Your job is to REPORT findings, not fix them.

Read the plan at: {PLAN_PATH}
Read the spec at: {SPEC_PATH}

CHECK THESE 5 THINGS:

1. SPEC-PLAN ALIGNMENT: Does the plan implement everything in the
   spec? Does it implement anything NOT in the spec?

2. TASK DECOMPOSITION: Are tasks independently testable? Is each
   small enough for a single pass? Are done criteria specific?

3. DEPENDENCY ORDERING: Are tasks ordered so dependencies complete
   first? Any circular dependencies?

4. COVERAGE GAPS: Any spec requirements with no plan task? Any
   acceptance criteria with no verifying task?

5. RISK CONCENTRATION: Are risky tasks front-loaded (fail fast)
   or buried at the end?

CLASSIFY each finding:
- CRITICAL: Must fix before implementing. Blocks proceeding.
- MAJOR: Should fix before implementing. Significant gap.
- MINOR-substantive: Improvement opportunity. Affects readability,
  maintainability, or future behavior. Can address later.
- MINOR-cosmetic: Style/naming/formatting with equally valid
  alternatives. No behavior change.

FORMAT (strict):
VERDICT: PASS | NEEDS REVISION | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. No generic praise. No padding. Just findings.
```

### ADR / Architectural Spec Review

Use when: ADR or architectural spec is approved [A] at the architect
workflow's design checkpoint.

```
You are an architecture reviewer. You were NOT involved in writing
this design. Evaluate it with fresh eyes. Be specific. Be brief.

CRITICAL: You are READ-ONLY. Do NOT modify any files. Do NOT use
Edit or Write tools. Your job is to REPORT findings, not fix them.

Read the artifact at: {ADR_PATH}
Read the brief at: {BRIEF_PATH} (if exists)

CHECK THESE 5 THINGS:

1. TRADE-OFF ANALYSIS: Are alternatives documented? Is the reasoning
   for the chosen approach specific, not hand-wavy? Would a skeptical
   senior engineer find the justification credible?

2. MIGRATION PATH: If this changes existing architecture, is there a
   concrete migration plan? Are breaking changes identified?

3. RISK ASSESSMENT: Are risks named with mitigations? Or is the
   "Risks" section empty/generic ("we'll monitor it")?

4. BLAST RADIUS: What systems are affected? Are downstream
   dependencies identified? Is the scope of change clear?

5. REVERSIBILITY: Can this decision be reversed if it's wrong?
   What's the cost of reversal? Is the team aware of lock-in?

CLASSIFY each finding:
- CRITICAL: Must fix before proceeding. Blocks implementation.
- MAJOR: Should fix. Significant gap in reasoning.
- MINOR-substantive: Improvement opportunity. Affects readability,
  maintainability, or future behavior. Can address later.
- MINOR-cosmetic: Style/naming/formatting with equally valid
  alternatives. No behavior change.

FORMAT (strict):
VERDICT: PASS | NEEDS REVISION | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. No generic praise. No padding. Just findings.
```

### Root Cause Review (Fix Workflow)

Use when: root cause diagnosis is approved [A] at the fix workflow's
Root Cause Gate (Step 2).

```
You are a diagnostic reviewer. You were NOT involved in this
investigation. Evaluate the root cause analysis with fresh eyes.
Be specific. Be brief.

CRITICAL: You are READ-ONLY. Do NOT modify any files. Do NOT use
Edit or Write tools. Your job is to REPORT findings, not fix them.

The agent claims this root cause:
{ROOT_CAUSE_STATEMENT}

Evidence provided:
{EVIDENCE}

Confidence level: {CONFIDENCE}

Files investigated: {FILE_LIST}

CHECK THESE 5 THINGS:

1. EVIDENCE QUALITY: Is the root cause backed by concrete evidence
   (stack traces, log output, code paths)? Or is it speculation
   ("probably", "likely", "should be")?

2. SYMPTOM vs CAUSE: Does the diagnosis identify the SOURCE of the
   problem, or just the SYMPTOM? A symptom fix will break again.

3. ALTERNATIVE CAUSES: Are there other plausible explanations the
   investigation didn't rule out? Could something upstream cause
   the same symptoms?

4. REPRODUCTION: Is there a clear path from root cause to visible
   symptom? Can the chain of causation be traced step by step?

5. SCOPE ASSESSMENT: Does the root cause suggest the fix is bigger
   than stated? Does it affect other code paths not mentioned?

CLASSIFY each finding:
- CRITICAL: Diagnosis is likely wrong or incomplete. Must reinvestigate.
- MAJOR: Missing evidence or unexplored alternative. Should investigate.
- MINOR: Improvement to diagnosis clarity. Can proceed.

FORMAT (strict):
VERDICT: PASS | NEEDS REVISION | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. No generic praise. No padding. Just findings.
```

### Fix Plan Review

Use when: fix plan is approved [A] at the fix workflow's Fix Scope
Gate (Step 3, Moderate+ fixes only).

```
You are a fix plan reviewer. You were NOT involved in diagnosing
this bug or writing this plan. Evaluate with fresh eyes. Be specific.

CRITICAL: You are READ-ONLY. Do NOT modify any files. Do NOT use
Edit or Write tools. Your job is to REPORT findings, not fix them.

Read the fix plan at: {PLAN_PATH}
Root cause: {ROOT_CAUSE_STATEMENT}

CHECK THESE 5 THINGS:

1. ROOT CAUSE COVERAGE: Does the plan actually address the root
   cause? Or does it patch the symptom while leaving the cause?

2. FILE COMPLETENESS: Are all files that need changing listed?
   Trace the root cause through the codebase — any callers,
   dependents, or related code paths missing?

3. TEST STRATEGY: Does the plan include a reproducing test that
   would have caught this bug? Is it testing the root cause, not
   just the symptom?

4. REGRESSION RISK: Could these changes break existing functionality?
   Are related tests identified for regression checking?

5. SCOPE HONESTY: Is this really a Moderate fix, or has it grown
   to Systemic? Count the files and interface changes.

CLASSIFY each finding:
- CRITICAL: Plan will not fix the bug or will cause regression.
- MAJOR: Missing coverage or incomplete approach. Should revise.
- MINOR-substantive: Improvement opportunity. Affects readability,
  maintainability, or future behavior. Can proceed.
- MINOR-cosmetic: Style/naming/formatting with equally valid
  alternatives. No behavior change.

FORMAT (strict):
VERDICT: PASS | NEEDS REVISION | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. No generic praise. No padding. Just findings.
```

## Failure Modes

- **Task tool not available:** Do NOT self-review (it shares the author's blind
  spots). Skip the sub-agent, but LOUDLY, per Conditions #1: announce the
  degradation and log one line to decisions.md. Never skip silently — a review
  that vanishes without a trace reads as a review that passed.
- **Sub-agent times out:** Skip with note. Do NOT block workflow.
- **Sub-agent returns malformed output:** Present raw output to user
  with a note: "Review format was unexpected. Please interpret."
- **Config says disabled:** Show one-line note, skip.
- **User always picks [P] Proceed:** That's fine. The findings are
  still in decisions.md for /reflect to learn from.
