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

**Manifest-first path:** If manifest.md exists for a fix cycle, read it.
Resume at the phase indicated.

**Fallback path:** If no manifest but artifacts exist:
- Investigation in progress → resume at Step 2
- Root cause confirmed, no fix plan → resume at Step 3 (scope)
- Fix applied, not verified → resume at Step 5 (verify)

If not found: start new investigation at Step 1.

Read `.sage/decisions.md` for context — previous root cause analyses
and fix patterns may be relevant.

### Manifest Lifecycle (fix workflow)

**Surgical fixes:** No manifest. Too fast — completes in one session.
**Moderate fixes:** Create manifest when fix plan is written (Step 3).
**Systemic fixes:** Create manifest at escalation point.
**Update** at fix scope gate and close checkpoint.
**Session end ([N]):** Mandatory update for Moderate+ fixes.

## Phase Announcements

At each major phase transition, announce before doing any phase work:

```
Sage: Entering UNDERSTAND phase [cycle-id] — investigating root cause.
Sage: Entering PLAN phase [cycle-id] — scoping the fix.
Sage: Entering DELIVER phase [cycle-id] — implementing and verifying fix.
```

The cycle ID is the directory name under `.sage/work/` (e.g., `20260324-auth-bug`).
For Surgical fixes without a cycle directory, use the bug description as cycle ID.

## Step 1: Understand the Problem

**Upstream report check (before asking the user):**

Scan for recent reports that can serve as pre-diagnosed input:

1. **qa-report.md** in `.sage/work/*/` or `.sage/docs/`
2. **design-review.md** in `.sage/work/*/` or `.sage/docs/`

**If qa-report.md exists with bugs:**

```
Sage: Found QA report with {N} bugs:

[1] BUG-1: {title} — {severity} — suggested: {Surgical/Moderate/Systemic}
[2] BUG-2: {title} — {severity} — suggested: {classification}
[3] BUG-3: {title} — {severity} — suggested: {classification}
[A] Fix all — accept classifications and proceed
[R] Reclassify — I want to change some classifications

Pick 1-N/A/R, or tell me what to fix.
```

On selection: skip Steps 1-2 (root cause already diagnosed in QA report).
Use the QA report's reproduction steps and evidence. Proceed to Step 3
(scope the fix) with the QA bug's suggested classification.

**If design-review.md exists with mechanical findings:**

```
Sage: Found design review with {N} mechanical findings:

[1] {finding} — {severity} — /fix (mechanical)
[2] {finding} — {severity} — /fix (mechanical)
[M] Also found {K} design-decision findings (manual — not fixable by agent)
[A] Fix mechanical findings — accept and proceed

Pick 1-N/A, or tell me what to fix.
```

Design-decision findings are EXCLUDED from the fix pipeline. Show them
as a summary ("manual action needed: {K} findings") but do NOT attempt
to fix them. These require human judgment.

**If both reports exist:** Present QA bugs first (functional issues),
then design mechanical findings. User can choose to fix all or select.

**If no reports exist:** Proceed with standard fix flow below.

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

[A] Review — sub-agent verifies diagnosis, then proceed
[S] Skip review — approve without independent review
[R] Revise — investigate further
[K] Stuck — try a different approach (activates problem-solving)
[N] New session — type /fix to continue

Pick A/S/R/K/N, or tell me what to change.

**On [A]:** Run auto-review (root cause review prompt) before
proceeding. This catches weak diagnoses — symptom-level fixes that
will break again. See `sage/core/capabilities/review/auto-review/SKILL.md`.

Do not proceed to Step 3 until the user confirms the root cause.

## Step 3: Scope the Fix

**AFTER root cause is confirmed, BEFORE writing any fix code.**

Classify the fix by structural impact:

**Surgical:** 1-2 files changed, no interface changes, no new
abstractions. The fix follows directly from the confirmed root cause.
→ Present classification to user for confirmation, then proceed
  to Step 4 (implement fix). Even Surgical fixes require the user
  to see and confirm the scope before implementation begins.

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

[A] Review — sub-agent reviews fix plan, then implement
[S] Skip review — approve without independent review
[R] Revise — adjust the approach
[E] Escalate — type /build or /architect instead
[N] New session — type /fix to continue

Pick A/S/R/E/N, or tell me what to change.

**On [A]:** Run auto-review (fix plan review prompt) before
implementing. See `sage/core/capabilities/review/auto-review/SKILL.md`.

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

## Step 5: Verify and Quality Gates

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

**Self-learning trigger:** If you return to Step 2 more than once
(i.e., 2+ failed fix attempts), this is a MANDATORY `gotcha` trigger.
Before attempting the next fix, store what you learned via
sage_memory_store with `[LRN:gotcha]` title, `self-learning` tag,
and four-part content (what happened, why wrong, what's correct,
prevention rule). Do NOT wait until the fix succeeds — capture the
learning NOW so future sessions benefit even if this session fails.

**Quality gates:** After tests pass, run quality gates per
`sage/core/workflows/sub-workflows/quality-gates.workflow.md`.
Read `.sage/gates/gate-modes.yaml` for fix mode activation —
Gate 3 (code quality review) and Gate 8 (auto-QA) run as optional
gates to catch low-quality fixes before they ship. Findings are
advisory but surfaced to the user.

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
Decision: [root cause + fix approach]. (prepend to .sage/decisions.md)

[A] Approve — commit and close
[R] Revise — something's not right
[V] Verify — type /review for independent check

Pick A/R/V, or tell me what to change.

**On approval — Post-Flight (Rule 7):**
1. Prepend root cause and fix to `.sage/decisions.md`
2. Update artifact frontmatter if relevant
3. Store root cause and fix in memory (tagged `self-learning`)
   with WHEN/CHECK/BECAUSE prevention rule
4. **Wiring check:** Verify the fix is fully connected — if you changed
   an interface, check all callers. If you added error handling, verify
   the error path is wired end-to-end. Incomplete wiring is the #1
   cause of fixes that need re-fixing.
5. **Ontology update (if sage-memory available):** If the fix changed
   module dependencies or interfaces (e.g., a service now calls a
   different service, a dependency was added/removed), update ontology
   relations. Most Surgical fixes won't need this — only update when
   the codebase's structural relationships changed.
4. **Next steps (Zone 3):**

Next steps:
  /reflect — review what went wrong, prevent recurrence
  /review  — independent evaluation of the fix
  /build   — spec → plan → implement (if fix revealed a feature need)

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
