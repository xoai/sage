---
name: ux-plan-tasks
description: "Adds UX-specific tasks to the development plan — usability testing, review checkpoints, design validation"
version: "1.0.0"
modes: [architect]
category: planning
activation: auto
cost-tier: haiku
playbook: ux-design
inputs: [plan, ux-requirements, persona-profiles, journey-maps]
outputs: [ux-tasks]
---

# UX Plan Tasks

Adds UX-specific tasks to the development plan. Runs AFTER the core `plan`
skill completes. Only activates in ARCHITECT mode — BUILD mode plans are
lightweight and don't need separate UX tasks.

## Mode: ARCHITECT (full)

Review the plan and add these UX tasks at appropriate points in the task sequence.

### Pre-Implementation UX Tasks

Add before the first implementation task:

**Usability test the design (before code):**
- Task: "Conduct paper prototype / wireframe walkthrough with 3-5 users"
- Inputs: journey map, persona profiles, wireframes (if available)
- Method: Give users the core tasks from the journey map. Watch where they
  get stuck. Note confusion, hesitation, wrong turns.
- Output: Top 3 usability issues, prioritized by severity
- Time: 2-4 hours (including setup and debrief)
- Dependency: Blocks implementation of user-facing components

If real user testing isn't feasible, substitute:
- Expert walkthrough using the persona + journey map as evaluation lens
- Cognitive walkthrough: step through each task as the primary persona

### Mid-Implementation UX Checkpoints

Insert after every user-facing component is implemented:

**Heuristic spot-check:**
- Task: "Review [component] against the Critical Four heuristics"
- Check: feedback, user control, error prevention, error messages
- Time: 15-30 minutes per major component
- Dependency: Must complete before next component builds on this one

### Post-Implementation UX Tasks

Add after the final implementation task, before merge:

**Usability test the implementation (after code):**
- Task: "Conduct usability test on the implemented feature with 3-5 users"
- Method: Same core tasks as pre-implementation test
- Compare: Did we fix the issues found in the prototype test?
- New issues: Anything the real implementation reveals that the prototype didn't?
- Output: Findings report, prioritized fixes
- Time: 2-4 hours

**Accessibility audit:**
- Task: "Run automated accessibility checks + manual keyboard navigation test"
- Tools: axe-core, Lighthouse accessibility, manual tab-through
- Check: All interactive elements keyboard-reachable, ARIA labels present,
  contrast ratios met, screen reader announcements work
- Time: 1-2 hours

### Task Ordering

```
existing plan tasks...
+ [UX] Prototype usability test (before implementation)
  existing implementation tasks...
  + [UX] Heuristic spot-check on [component A]
  + [UX] Heuristic spot-check on [component B]
  existing implementation tasks...
+ [UX] Implementation usability test (after implementation)
+ [UX] Accessibility audit
existing verification tasks...
```

## References

- `usability-testing.md` — Krug's one-morning test protocol, key metrics
- `heuristic-evaluation.md` — The 10 heuristics and Critical Four subset
