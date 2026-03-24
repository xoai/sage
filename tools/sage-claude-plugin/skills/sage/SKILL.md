---
name: sage
description: >
  Start here. Sage reads project state, routes via keywords, classifies
  intent, and guides you to the right workflow.
disable-model-invocation: true
---

RULES (apply to every step — non-negotiable):
- Present project state with "Sage:" prefix
- Present options with [1] [2] [3] bracket notation — ALWAYS
- Recommend a specific workflow for Standard+ tasks
- NEVER just ask "What would you like to do?" — present structured choices
- Never use code blocks for interaction output

Sage's intelligent entry point. Assess the project and guide the user.

## Step 1: Read State

Scan `.sage/work/` for active initiatives (read frontmatter: title,
status, phase). Scan `.sage/docs/` for project-level artifacts.
Read `.sage/decisions.md` for recent context.

## Step 2: Present Status and Options

Present what you found, then structured options based on context.

**If work is in progress:**

**Sage:** [Project name] — [feature] is in progress, [phase] phase.

[1] Continue [feature] — resume from [next step]
[2] Start something new
[3] Review what's been done

**If no work in progress but artifacts exist:**

**Sage:** [Project name] — no active work. Previous: [list initiatives].

[1] Start a new task — describe what you want to build
[2] Review existing artifacts
[3] Learn the codebase

**If fresh project:**

**Sage:** Fresh project, no work in progress.

[1] Build something — describe what you want to create
[2] Learn the codebase first
[3] Something else — describe what you need

## Step 3: Route to Workflow

Based on user's choice or free-form input, classify scope and route:
- Lightweight → just do it
- Standard → announce build/fix workflow, start first step
- Comprehensive → present architect workflow card

For complex routing or gap detection, read the sage-navigator at
`sage/core/capabilities/orchestration/sage-navigator/SKILL.md`.

$ARGUMENTS
