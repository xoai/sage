---
name: qa
version: "1.0.0"
mode: qa
produces: ["QA report with bugs, severity, and fix classification"]
checkpoints: 1
scope: "Single session"
user-role: "Provide URL, confirm test scope, review findings"
---

# QA Workflow

Browser-based functional testing. Finds integration failures that
live in the gap between "code is correct" and "product works."

Report only — /qa does NOT fix bugs. /fix fixes.

## Step 1: Prerequisites (Zone 1)

**Check Lightpanda MCP availability.** Attempt to call a Lightpanda
MCP tool (e.g., `goto` with `about:blank`).

**If available:** Ask for URL:

```
Sage → qa workflow. Lightpanda browser connected.
What URL is the application running on?
(e.g., http://localhost:3000, https://staging.myapp.com)
```

Verify URL is reachable via `goto`. If not, report and offer to
wait or proceed with code-only.

**If not available:**

```
Sage: Lightpanda MCP is not connected. /qa needs a browser to test
your application.

Setup: See sage/core/references/lightpanda-setup.md for install guide.

[B] Set up browser — I'll install Lightpanda
[C] Continue without browser — code-only QA
[X] Cancel

Pick B/C/X, or tell me what you need.
```

**Code-only fallback** (no browser): Analyze the diff, identify
affected routes, review code for common integration issues:
- Mismatched API contracts (frontend expects shape X, backend returns Y)
- Missing error handlers (happy path only, no error/loading states)
- Untested flows (code paths with no test coverage)
- State management gaps (state written but never read, or vice versa)

Report notes: "Browser testing: not available — code-analysis only."

## Step 2: Scope Analysis (Zone 1)

**If invoked after /build** (cycle context exists):
Read the cycle's spec.md and plan.md. Identify affected routes,
user flows, and acceptance criteria to verify.

**If invoked standalone** (no cycle context):

```
Sage: What should I test?

[1] Everything — full app smoke test (I'll discover routes)
[2] Specific flow — describe what to test
[3] Specific URL — point me at a page

Pick 1-3, type / for commands, or describe what you need.
```

Produce and present a test scope:

```
TEST SCOPE:
Routes to test:
- /dashboard (modified: added new widget)
- /settings/notifications (new page)

Flows to test:
- Dashboard loads with new widget visible
- Navigate to notification settings
- Toggle preference → verify API → verify UI update

Acceptance criteria to verify:
- [from spec] Toggle persists across page reload
- [from spec] Widget shows unread count
```

Ask: "Does this scope look right, or should I add/remove anything?"

## Step 3: Route Testing

For each route in scope:

1. **Navigate** (`goto`) to the route
2. **Check page health:**
   - `evaluate`: check for JS console errors
   - `markdown`: verify page renders content (not blank/error)
   - `semantic_tree`: verify expected structural elements
3. **Record:** status (pass/fail/warning), details if fail

## Step 4: Interaction Testing

For each flow in scope:

1. **Discover** interactive elements (`interactiveElements`)
2. **Execute** the flow step by step:
   - `click` buttons, links, toggles
   - `fill` form fields
   - After each: check errors (`evaluate`), verify state (`semantic_tree`)
3. **Test edge cases** from acceptance criteria:
   - Reload after state change → persists?
   - Empty form submit → validation fires?
   - Navigate away and back → state survives?
4. **Record:** status, steps executed, where flow broke

## Step 5: QA Report (Zone 2)

Save report to `.sage/work/[cycle-id]/qa-report.md` (if cycle context)
or `.sage/docs/qa-report-[topic].md` (if standalone).

Use the report template from `develop/templates/qa-report-template.md`.

🔒 **QA REPORT CHECKPOINT:**

```
Sage: QA complete.

Tested: {N} routes, {M} flows
Results: {pass} pass, {fail} fail, {warn} warning
Verdict: {PASS | FAIL | PASS WITH WARNINGS}

Bugs found: {count}
  Critical: {count} — [brief descriptions]
  Major: {count}
  Minor: {count}

Report: .sage/[path]/qa-report.md

[A] Approve report  [R] Revise — retest something
[F] → /fix to address bugs  [N] New session

Pick A/R/F/N, or tell me what to change.
```

**Next steps (Zone 3):**

```
Next steps:
  /fix            — diagnose → scope → fix → verify (reads qa-report)
  /design-review  — design quality audit
  /reflect        — review the cycle, extract learnings

Type a command, or describe what you want to do next.
```

## Quality Criteria

Good QA output:
- Every route in scope was actually tested (not claimed-as-tested)
- Bugs have concrete reproduction steps, not vague descriptions
- Each bug includes suggested fix classification (Surgical/Moderate/Systemic)
- Evidence is included (console output, element state, response content)
- Untested routes are noted as untested, NOT claimed as pass

## Enforcement Contracts

**No fake browser testing:** If Lightpanda is not available, do NOT
fabricate browser test results. Code-only analysis is honest about
what it can and cannot verify.

**Report completeness:** Untested routes must be listed as "not tested"
in the report. Do NOT claim a route passes if you didn't load it.

**Advisory only:** /qa reports. It does NOT fix bugs. If the agent
catches itself thinking "I'll just fix this real quick" — STOP.
Save the finding to the report and let /fix handle it.

**No fixing in /qa:** The separation between find and fix is deliberate.
An agent that finds AND fixes has incentive to minimize findings.
/qa's only job is thoroughness.

## Rules

- /qa reports, /fix fixes. Never combine.
- Code-only fallback is honest about its limitations.
- Every bug gets a severity AND a fix classification.
- Evidence is mandatory for fail/warning findings.
- Update manifest.md if cycle context exists.
