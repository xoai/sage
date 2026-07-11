---
name: 52-ux-heuristic-review
order: 52
category: quality
version: "1.0.0"
modes: [build, architect]
source: "play-ux-design"
---

# Gate 52: UX Heuristic Review

Evaluates the implementation against core usability heuristics derived from
Nielsen, Norman, and Krug. This gate complements Gate 03 (code quality) with
a user-experience lens.

## Check Criteria

### Critical Four (BUILD + ARCHITECT — always check)

**Feedback (Heuristic 1):**
- Every button/link/action produces visible response
- Loading states exist for all async operations
- Success and failure states are communicated clearly
- No action results in silence (no response = broken to the user)

**User Control (Heuristic 3):**
- User can undo or cancel actions
- Modals/dialogs have a clear close mechanism
- Back button works (no broken navigation state)
- Destructive actions require confirmation

**Error Prevention (Heuristic 5):**
- Input constraints where possible (datepicker, dropdown, type validation)
- Dangerous options visually distinct from safe options
- Inline validation before form submission
- Impossible states made unreachable (disabled controls, not hidden)

**Error Messages (Heuristic 9):**
- Written in user language, not developer language
- State what went wrong specifically
- Suggest what to do next
- Don't expose technical details (HTTP codes, stack traces, field names)

### Full Ten (ARCHITECT only — comprehensive review)

In addition to the Critical Four, evaluate:

**System Status (1):** User knows what state they're in at all times.
**Real-World Match (2):** Labels, terms, and concepts use user language.
**Consistency (4):** Same actions called the same thing, behave the same way.
**Recognition over Recall (6):** All available actions visible, formats shown.
**Flexibility (7):** Expert shortcuts exist alongside discoverable defaults.
**Minimalism (8):** No unnecessary text, visual clutter, or competing elements.
**Help (10):** Contextual help available for complex features.

## Failure Response

On FAIL: Identify the specific heuristic violated, the user impact (what goes
wrong for the user), and the recommended fix with a concrete code change.

Severity levels:
- **Catastrophic:** User loses data or can't complete their primary task. MUST fix.
- **Major:** User is significantly confused or frustrated. SHOULD fix before ship.
- **Minor:** User notices something odd but can work around it. Fix in next iteration.
- **Cosmetic:** Violates principle but minimal user impact. Note for polish.

## Adversarial Guidance

The implementer may claim:
- "The error handling is handled by the framework" → Check: does the framework's
  default error UI actually help the user, or does it show a generic crash screen?
- "Users will figure it out" → Apply Krug's First Law: if they have to figure it
  out, the design has failed.
- "We'll add loading states later" → Loading states are not polish. They're
  feedback. Without them, the system appears broken.
- "It's an internal tool, UX doesn't matter" → Internal users have even less
  tolerance for bad UX because they're forced to use it daily.
