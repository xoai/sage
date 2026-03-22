---
name: fix
version: "1.2.0"
mode: fix
produces: ["Root cause diagnosis with evidence", "Reproducing test", "Minimal patch"]
checkpoints: 3
scope: "Single session for surgical, multi-session for systemic"
user-role: "Confirm root cause, approve fix scope, approve fix"
---

# Fix Workflow

Diagnose, then scope, then fix. Never skip steps.

## Auto-Pickup

Scan `.sage/work/` for fix-related directories with `status: in-progress`.
This scan is MANDATORY — check the DISK.

If found: read the root cause analysis and current phase.
- Investigation in progress → resume at Step 2
- Root cause confirmed, no fix plan → resume at Step 3 (scope)
- Fix applied, not verified → resume at Step 5 (verify)
- Report: "Sage: Resuming fix for [problem]. [Phase]."

If not found: start new investigation at Step 1.

Read `.sage/decisions.md` for context — previous root cause analyses
and fix patterns may be relevant.

## Step 1: Understand the Problem

Ask for or identify: what's broken, when it started, error messages,
steps to reproduce. If the user already provided details, confirm
your understanding before proceeding.

If the problem description is vague (no error message, no steps to
reproduce, no specific behavior described), ask for specifics before
investigating. Don't guess — misdiagnosis from vague reports wastes
more time than one clarifying question.

Sage: Here's what I understand:
- [Problem summary]
- [Expected vs actual behavior]

[C] Correct — start debugging  |  Or clarify what I got wrong

## Step 2: Investigate Root Cause

**NO FIXES BEFORE THIS STEP COMPLETES.** Read the relevant code.
Trace the error. Gather evidence. The goal is UNDERSTANDING, not
a fix.

For systematic debugging methodology, read
`sage/core/capabilities/debugging/systematic-debug/SKILL.md`.

**Track investigation approaches.** When changing hypothesis or
investigation direction, log it:

Append to `.sage/work/[fix-initiative]/scratch.md`:
```
approach-[N]: [hypothesis tried] — [what the evidence showed]
```

If scratch.md has 3+ approaches, this is a `gotcha` trigger — store
the finding via self-learning with WHEN/CHECK/BECAUSE format.

Produce a root cause statement with evidence:

Sage: Root cause identified.

  Cause: [what's actually wrong — the source, not the symptom]
  Evidence: [what you observed that confirms this]
  Chain: [how the root cause leads to the visible symptom]
  Confidence: [high / medium / low]

If multiple potential causes exist:

Sage: I found two possible causes:

[1] [Cause A] — in [file:line] — [evidence for this]
[2] [Cause B] — in [file:line] — [evidence for this]

Which should I investigate first?

**Red flags — STOP and return to investigation if you catch
yourself thinking:**
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "Should work now" (without evidence)

**If stuck after 3+ attempts:** Activate the `problem-solving` skill.

🔒 **ROOT CAUSE GATE:**
Sage: Root cause analysis complete.

  Cause: [root cause statement]
  Evidence: [what confirms it]
  Confidence: [high/medium/low]

[A] Approve diagnosis — continue to fix scoping
[R] Revise — investigate further
[S] Stuck — try a different approach (activates problem-solving)
[N] New session — type /fix to continue

Pick A/R/E/N, or tell me what to change.

Pick A/R/S/N, or tell me what to change.

Do not proceed to Step 3 until the user confirms the root cause.

## Step 3: Scope the Fix

**AFTER root cause is confirmed, BEFORE writing any fix code.**

Classify the fix by structural impact:

**Surgical:** 1-2 files changed, no interface changes, no new
abstractions. The fix is obvious from the root cause.
→ Proceed directly to Step 4 (implement fix).

**Moderate:** 3-5 files changed, OR test infrastructure changes,
OR error handling pattern changes. The fix is clear but touches
multiple components.
→ MUST write a fix plan before implementing:
  Save to `.sage/work/[fix-initiative]/plan.md`:
  - Files to change and what changes in each
  - Tests to add or modify
  - Rollback approach if fix doesn't work
  Present [A]/[R] → wait for approval.

**Systemic:** 5+ files changed, OR interface/API changes, OR new
abstractions needed, OR architectural implications. This is no
longer a fix — it's a redesign.
→ MUST escalate:

Sage: This fix is systemic — it requires [interface changes /
new abstractions / architectural changes].

Root cause: [summary]
Impact: [N files, M interfaces, architectural concern]

[1] Escalate to /build — write spec for the fix as a feature
[2] Escalate to /architect — the root cause is architectural
[3] Proceed as fix anyway — I accept the risk of a large unplanned change

If the user chooses [3], write a fix plan (same as Moderate)
and record the decision in decisions.md.

**Escalation signals** (any ONE makes it Moderate or above):
- Fix touches more than 2 files
- Fix changes a function signature or API contract
- Fix requires a new abstraction (new class, new module, new pattern)
- Fix changes error handling in a way other code depends on
- Fix requires database migration
- You realize "the real fix is to restructure X"

**Anti-downgrade:** Do NOT classify as Surgical to skip the plan.
If you find yourself thinking "I'll just quickly change these 5
files," that's Moderate. If you're thinking "the real problem is
the architecture," that's Systemic. Trust the signals, not your
optimism about how fast the fix will be.

🔒 **FIX SCOPE GATE (Moderate+ only):**
Sage: Fix scope: [Moderate/Systemic]

  Files: [list of files to change]
  Changes: [summary of what changes]
  Tests: [what tests to add/modify]
  Risk: [what could go wrong]

[A] Approve plan — start implementing
[R] Revise — adjust the approach
[E] Escalate — type /build or /architect instead
[N] New session — type /fix to continue

Pick A/R/E/N, or tell me what to change.

Pick A/R/S/N, or tell me what to change.

## Step 4: Implement Fix

Write a failing test that reproduces the bug. Confirm the test fails
for the right reason (the root cause, not a setup issue). Fix the
code. Verify the test passes.

**For Moderate+ fixes:** Follow the plan. Check off each file as
you change it. Do NOT change files not in the plan — if you discover
additional changes are needed, update the plan first.

**Scope guard during fix:** If the fix starts growing beyond the
plan, STOP:

Sage: The fix is expanding beyond the plan.
Originally: [N files, M changes]
Now: [N+X files, M+Y changes]

[1] Update the plan and continue
[2] Escalate to /build
[3] Revert to original plan and accept limitations

## Step 5: Verify

**Run the verification command. Read the output. THEN report.**

For detailed verification process, read
`sage/core/capabilities/debugging/verify-completion/SKILL.md`.

1. Run the project's test suite (full or relevant subset)
2. Read the actual output — don't summarize from memory
3. Confirm: zero failures, zero errors
4. If any test fails, diagnose and fix before proceeding —
   do NOT present the checkpoint with failing tests

Sage: Verification results:

  Test suite: [command that was run]
  Result: [X passed, 0 failed] ← paste actual output
  Regression check: [any related tests that also pass]

**If tests fail after the fix:** Return to Step 2. The root cause
analysis was incomplete — either the diagnosis was wrong, or the
fix introduced a new issue.

## Step 6: Close

**Self-check before presenting (FILE CHECKS):**
- [ ] Root cause was presented and approved by user (Step 2 gate)
- [ ] For Moderate+ fixes: plan.md exists in .sage/work/
- [ ] Test output is PASTED in this response (not summarized)
- [ ] Fix is contained to planned files (no scope creep)
If ANY fails → go back. Do NOT present the checkpoint.

Sage: Fix verified.
- Root cause: [what was wrong]
- Scope: [Surgical/Moderate/Systemic]
- Change: [what was changed, in which files]
- Tests: [X passed, 0 failed — from actual output]
Decision: [root cause + fix approach]. (append to .sage/decisions.md)

[A] Approve — commit and close
[R] Revise — something's not right
[V] Verify — type /review for independent check

Pick A/R/V, or tell me what to change.

**On approval — Post-Flight (Rule 7):**
1. Append root cause and fix to `.sage/decisions.md`
2. Update artifact frontmatter if relevant
3. Store root cause and fix in memory (tagged `self-learning`)
   with WHEN/CHECK/BECAUSE prevention rule
4. **Next steps (Zone 3):**

Next steps:
  /review — independent evaluation of the fix
  /build  — spec → plan → implement (if the fix revealed a feature need)
  /analyze — audit related areas for similar issues

Type a command, or describe what you want to do next.

## Quality Criteria

**Communication style:** Diagnostic precision. State root cause clearly,
explain the chain of causation, describe the fix scope assessment,
and verify with evidence.

Good fix output:
- Root cause identified with evidence, not just symptoms addressed
- Fix scope classified honestly (not downgraded to skip the plan)
- A reproducing test exists before the fix is applied
- Verification output is pasted (not summarized)
- If the bug has related patterns elsewhere, those are flagged
- The fix is minimal — no unrelated refactoring mixed in

## Rules

- Root cause before fix (Step 2 gate). DO NOT fix before root cause
  is confirmed with evidence.
- Scope before implementing (Step 3). Classify impact honestly.
- For Moderate+ fixes: plan.md MUST EXIST before implementation.
  "I know what to change" is NOT a plan file.
- Tests before code (Base Principle 1). Write failing test first.
- Verify with evidence (Rule 5). PASTE actual test output.
- Capture corrections (Rule 6). Store as self-learning.
- Minimal change: fix the bug, don't refactor the neighborhood.
- If stuck, use problem-solving skill. Don't retry the same approach.
- If the fix reveals a systemic issue, ESCALATE. Do not scope-creep
  a fix into a rebuild. Offer /build or /architect.

## Failure Modes

- **Agent skips root cause investigation:** Red flags section catches
  this pattern. The ROOT CAUSE GATE blocks proceeding.
- **Agent underestimates fix scope:** Escalation signals list catches
  the most common patterns. Anti-downgrade language blocks "I'll just
  quickly change these 5 files."
- **Fix grows during implementation:** Scope guard in Step 4 detects
  when the fix expands beyond the plan and forces a decision.
- **Agent claims tests pass without running them:** Self-check
  requires PASTED output. No paste = checkpoint not ready.
