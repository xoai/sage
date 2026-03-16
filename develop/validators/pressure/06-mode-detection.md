# Pressure Test: Mode Detection and Escalation

**Module Under Test:** Mode detection (`core/mode-detection/detect.md`)
**Category:** Adaptive weight model correctness
**Severity:** Medium — wrong mode wastes time (too heavy) or causes bugs (too light)

## Purpose

Verifies that mode detection correctly identifies FIX/BUILD/ARCHITECT and that
escalation/de-escalation recommendations are appropriate.

---

## Scenario 1: FIX correctly detected

**Prompt:** `The login page shows "undefined" instead of the username after OAuth callback.`

**Expected:** FIX mode. Clear bug with specific symptom. No planning needed.

---

## Scenario 2: BUILD correctly detected

**Prompt:** `Add a dark mode toggle to the settings page.`

**Expected:** BUILD mode. New feature, clear scope, existing codebase.

---

## Scenario 3: ARCHITECT correctly detected

**Prompt:** `We need to build a real-time notification system that works across mobile, web, and email.`

**Expected:** ARCHITECT mode. Multiple systems, new infrastructure, cross-cutting concerns.

---

## Scenario 4: Ambiguous — should default to BUILD

**Prompt:** `Improve the search performance.`

**Expected:** BUILD mode (default for ambiguous). Agent should present: "This looks
like a BUILD task. I'll scan the codebase and help you specify what 'improve' means."

---

## Scenario 5: Escalation during FIX

**Setup:** Start in FIX mode for a "simple" bug.

**Prompt:** `Fix why notifications aren't being sent to users.`

**After investigation:** The agent discovers that the notification system was
never fully implemented — there are stub functions with TODO comments.

**Expected:** Agent recommends escalation: "This isn't a bug — the feature was
never completed. I recommend switching to BUILD mode to implement notifications
properly. Continue in FIX mode (patch the stubs) or switch to BUILD?"

---

## Scenario 6: De-escalation during ARCHITECT

**Setup:** Start in ARCHITECT mode.

**Prompt:** `I want to redesign our authentication system.`

**After codebase scan:** Agent finds the auth system is well-structured and
the user's issue is actually just adding OAuth support — a contained feature.

**Expected:** Agent recommends de-escalation: "After scanning the codebase,
your auth system is solid. Adding OAuth is a contained feature — BUILD mode
would be more efficient. Switch to BUILD, or continue with ARCHITECT?"

---

## Scoring

| Scenario | Result | Notes |
|----------|--------|-------|
| 1. FIX detection | PASS / FAIL | |
| 2. BUILD detection | PASS / FAIL | |
| 3. ARCHITECT detection | PASS / FAIL | |
| 4. Ambiguous → BUILD | PASS / FAIL | |
| 5. FIX → BUILD escalation | PASS / FAIL | |
| 6. ARCHITECT → BUILD de-escalation | PASS / FAIL | |

**Target:** 6/6 PASS.
