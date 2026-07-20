---
name: plan-standard
type: plan
variant: standard
version: "2.0.0"
description: >
  Implementation plan with built-in progress tracking. Each task has a checkbox
  that serves as the source of truth for completion status. The plan file IS the
  progress tracker — no separate state file needed.
sections: [constitution-constraints, tech-decisions, task-breakdown]
---

# Implementation Plan: {feature_name}

**Spec:** {link_to_spec}
**Mode:** {build_or_architect}
**Status:** not-started
**Started:** {?timestamp}
**Last updated:** {?timestamp}

[SECTION: constitution-constraints]
## Constitution Constraints

<!-- GUIDANCE: List every constitution principle that applies to this work.
These are non-negotiable — the implementation must respect all of them.
Pull from the merged constitution (org + project + feature). -->

{applicable_principles}
[/SECTION]

[SECTION: tech-decisions]
## Technology Decisions

<!-- GUIDANCE: In BUILD mode, this is usually "Using existing stack" with a
brief note on established patterns. In ARCHITECT mode, include decision records for
every significant decision. -->

{technology_decisions_or_adrs}
[/SECTION]

[SECTION: task-breakdown]
## Tasks

<!-- GUIDANCE: Read the spec's Deliverable field to determine task style.

For CODE tasks:
  - Each task is 2-5 minutes of focused work
  - Tests come before implementation (TDD)
  - [P] marks tasks that can run in parallel

For DOCUMENT tasks:
  - Mark with [DOC] after the task name
  - Use Criteria instead of Test (checklist, not commands)
  - Use Output instead of Files (document path, not source code)
  - Gates 04-06 skip for [DOC] tasks

For MIXED deliverables:
  - Mark each task as code (default) or document ([DOC])
  - Apply appropriate template and gates per task

PROGRESS TRACKING: The checkboxes below ARE the source of truth for progress.
When a task is completed:
  1. Check the box: [ ] → [x]
  2. Add the completion marker: ✅ DONE (commit: abc1234)
  3. Add gate results if applicable

When a task is in progress:
  - Add: 🔄 IN PROGRESS

When a task is blocked:
  - Add: 🚫 BLOCKED: [reason]

The next session reads this file to know exactly where to resume. -->

<!-- Code task template -->
- [ ] **Task 1:** {name}
  - **Read first:** {pack files relevant to this task, or "(pack content already loaded)"}
  - **Files:** {exact_file_paths}
  - **Action:** {what_to_do}
  - **Test:** {what_test_to_write_first}
  - **Verify:** {command_to_confirm_completion}
  - **Depends on:** none

<!-- Document task template -->
- [ ] **Task 2:** {name} [DOC]
  - **Read first:** {playbook reference files relevant to this section}
  - **Output:** {document_file_path}
  - **Action:** {what_to_write — scope, structure, expected sections}
  - **Criteria:** {checklist of what "done" looks like}
  - **Depends on:** Task 1

{additional_tasks}

## Gate Log

<!-- GUIDANCE: After each task's quality gates run, record the result here.
This provides an audit trail and helps the next session know what passed. -->

| Task | Gate 1 (Spec) | Gate 2 (Constitution) | Gate 3 (Quality) | Gate 4 (Hallucination) | Gate 5 (Verify) |
|------|:---:|:---:|:---:|:---:|:---:|
| Task 1 | | | | | |
| Task 2 | | | | | |

[/SECTION]
