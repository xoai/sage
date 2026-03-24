---
name: ux-specify
description: "Enriches feature specifications with UX requirements — error states, user flows, accessibility, five-planes analysis"
version: "1.0.0"
modes: [build, architect]
category: planning
activation: auto
cost-tier: sonnet
playbook: ux-design
inputs: [specification, user-context-notes, persona-profiles, journey-maps]
outputs: [ux-requirements]
---

# UX Specify

Enriches a feature specification with UX requirements that implementation must
satisfy. Runs AFTER the core `specify` skill completes.

## Mode: BUILD (light)

Review the spec and add these UX sections if missing. Don't rewrite the spec —
append UX requirements.

**Error States Inventory:**
For each user action in the spec, ask: "What happens when this fails?"
Add to the spec:
- Network failure during this action → what does the user see?
- Invalid input → what message, where, how to fix?
- Permission denied → what explanation, what recovery path?
- Timeout → what feedback, what retry mechanism?

**UX Acceptance Criteria:**
Add 3-5 acceptance criteria grounded in usability principles:
- "Error messages must state what went wrong and what to do next"
- "Form data is preserved on validation failure"
- "Loading state is visible within 100ms of user action"
- "User can undo/cancel this action before it's finalized"

**Accessibility Notes:**
Flag any accessibility considerations specific to this feature:
- Keyboard navigation requirements
- Screen reader announcement needs (dynamic content, errors, status changes)
- Color contrast requirements for any new visual elements

## Mode: ARCHITECT (full)

Run the complete UX specification enrichment using Garrett's Five Planes as the
analytical framework.

### Five-Planes Analysis

Review the spec through each plane, bottom to top:

**Strategy Plane:**
- Is the user need clearly stated (not just the business goal)?
- Is the primary persona identified?
- Are success metrics defined from the USER's perspective (task completion,
  satisfaction), not just business metrics (conversion, revenue)?

**Scope Plane:**
- Are functional requirements complete? (what the user CAN do)
- Are content requirements stated? (what information the user SEES)
- Is the boundary clear? (what's deliberately EXCLUDED)
- Is every requirement traceable to a user need or pain point from discovery?

**Structure Plane:**
- Is the interaction model defined? (what happens when the user does X)
- Is the information architecture clear? (how content is organized)
- Are ALL error states designed? (Apply Norman's error taxonomy: slips and mistakes)
- Is the navigation model consistent with the rest of the product?

**Skeleton Plane:**
- Is the visual hierarchy defined? (most important content most prominent)
- Are interface patterns consistent with the product's existing patterns?
- Is the form design specified? (field types, labels, validation, error placement)

**Surface Plane:**
- Are there visual design constraints? (brand, existing design system)
- Are loading states, empty states, and transition animations specified?

### Journey-Grounded Requirements

Using the journey map from discovery, verify:
- Every step in the journey has a corresponding requirement in the spec
- Every pain point has a designed mitigation
- Transition moments (entering and leaving the feature) are designed
- The emotional arc is considered (don't show cheerful copy during error recovery)

### Produce: ux-requirements artifact

A structured document appended to or linked from the main specification:
- Error state inventory (complete)
- UX acceptance criteria (testable)
- Accessibility requirements (specific to this feature)
- Five-planes gaps identified and addressed
- Journey coverage verification

## References

- `five-planes.md` — Garrett's five planes framework
- `usability-principles.md` — Krug's laws and Norman's principles
- `error-and-recovery-design.md` — Norman's error taxonomy and design checklist

## Quality Criteria

**Communication style:** Requirements language. Be precise and testable.
Every requirement should be verifiable by QA. Describe behavior, not
implementation.

Good UX specification output:
- Every journey step has a corresponding requirement
- Every pain point has a designed mitigation
- Error states are inventoried completely, not just happy paths
- Accessibility requirements are specific to this feature
- UX acceptance criteria are testable — you can verify pass/fail
- Transition moments (entering and leaving the feature) are designed
- The emotional arc is considered — copy and interaction tone match context

## Self-Review

Before presenting your output, check each quality criterion above.
For each, confirm it's met or note what's missing. Present your
findings AND your self-assessment:

"Self-review: [X/Y criteria met]. [Note any gaps and why they exist.]"
