---
name: ux-heuristic-review
description: "Evaluates implementation against usability heuristics — Nielsen's 10, Norman's principles, Krug's laws"
version: "1.0.0"
modes: [build, architect]
category: review
activation: mandatory
cost-tier: sonnet
playbook: ux-design
inputs: [implementation, ux-requirements, specification]
outputs: [heuristic-assessment]
---

# UX Heuristic Review

Evaluates the implementation against usability heuristics. Runs ALONGSIDE the
core `quality-review` skill at the review phase. When installed, this review
is mandatory — it cannot be skipped by the agent.

## Mode: BUILD (light) — Critical Four

Evaluate the implementation against the four heuristics most likely to catch
user-facing failures. Takes ~2 minutes per task.

### H1: Feedback — Visibility of System Status

- Does every button/action produce visible response?
- Are there loading indicators for async operations?
- Does the user know if their action succeeded or failed?
- Is there any action that results in silence?
→ Silence after user action = FAIL

### H3: Control — User Control and Freedom

- Can the user undo or cancel actions?
- Can they dismiss modals and dialogs?
- Does the back button work correctly?
- Are destructive actions protected by confirmation?
→ No undo on destructive action = FAIL

### H5: Prevention — Error Prevention

- Are inputs constrained where possible (dropdowns, datepickers, type validation)?
- Does inline validation catch errors before submission?
- Are dangerous options visually distinct from safe ones?
→ Free text where a constrained input would prevent errors = FAIL

### H9: Recovery — Help Users Recognize and Recover from Errors

- Are error messages in user language (not developer jargon)?
- Does each error message say what went wrong AND what to do next?
- Is form data preserved on validation failure?
- No HTTP status codes, field names, or stack traces in user-facing messages?
→ Technical error message shown to user = FAIL

## Mode: ARCHITECT (full) — All Ten Heuristics

Evaluate against all 10 Nielsen heuristics plus Norman's design principles.
Takes ~10 minutes per major feature.

### Additional Heuristics (beyond the Critical Four)

**H2: Real-World Match** — Does the interface use the user's language? Are
icons and metaphors recognizable? Is information organized the way users think?

**H4: Consistency** — Are the same actions called the same thing everywhere?
Do similar elements behave the same way? Does it follow platform conventions?

**H6: Recognition over Recall** — Are all available actions visible? Do forms
show expected formats? Can users see previous selections when making new ones?

**H7: Flexibility** — Are there keyboard shortcuts for frequent actions? Can
expert users bypass introductory steps? Does it remember preferences?

**H8: Minimalism** — Is there unnecessary text? Are visual elements serving a
purpose? Is the visual hierarchy clear?

**H10: Help** — Is contextual help available for complex features? Are tooltips
concise and useful?

### Norman's Principles Check

In addition to Nielsen's heuristics, check:
- **Affordances:** Do interactive elements look interactive?
- **Signifiers:** Is it clear what's clickable, draggable, editable?
- **Mapping:** Do control positions correspond to what they affect?
- **Conceptual Model:** Does the interface communicate how the system works?

## Severity Classification

Each finding gets a severity:

| Severity | Definition | Action |
|----------|-----------|--------|
| **Catastrophic** | User loses data or can't complete primary task | MUST fix before merge |
| **Major** | User significantly confused or frustrated | SHOULD fix before merge |
| **Minor** | User notices oddity but works around it | Fix in next iteration |
| **Cosmetic** | Violates principle but minimal user impact | Note for polish |

## Produce: heuristic-assessment artifact

```
## UX Heuristic Review: [feature name]
Date: [date]
Mode: [BUILD light / ARCHITECT full]

### Findings

1. [H9 - MAJOR] Error message on login form says "401 Unauthorized"
   → Should say: "Wrong email or password. Check your details and try again."
   → Fix: Update error handler in login-form.tsx

2. [H1 - CATASTROPHIC] No loading state on payment submission
   → User clicks "Pay" and sees no response for 3-5 seconds
   → Fix: Add loading spinner to submit button, disable during processing

### Summary
- Catastrophic: 1 (must fix)
- Major: 1 (should fix)
- GATE RESULT: FAIL (catastrophic finding blocks merge)
```

## References

- `heuristic-evaluation.md` — Full heuristic descriptions and checkpoints
- `usability-principles.md` — Krug's laws and Norman's principles
- `error-and-recovery-design.md` — Error taxonomy for H5/H9 evaluation
