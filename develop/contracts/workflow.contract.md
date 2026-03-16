# Workflow Contract

**Version:** 1.0.0
**Status:** Stable

A workflow is an orchestrated sequence of skills. Workflows define the ORDER and
CONDITIONS under which skills execute. They are the conductors — skills are the musicians.

Workflows reference skills by NAME, never by file path. If a skill is replaced,
the workflow keeps working without changes.

---

## Required File Structure

```
core/workflows/
├── <workflow-name>.workflow.md     # REQUIRED — Workflow definition
└── sub-core/workflows/                  # OPTIONAL — Reusable fragments
    └── <name>.workflow.md
```

Workflows are single files, not directories. They are lightweight by design — all
the substance lives in the skills they orchestrate.

---

## Required Frontmatter

```yaml
---
# REQUIRED FIELDS
name: <string>               # Unique workflow identifier, kebab-case
description: <string>        # What this workflow accomplishes
version: <semver>
mode: <string>               # Primary mode: fix, build, or architect
                             # A workflow belongs to exactly ONE mode.

# OPTIONAL FIELDS
replaces: <string>           # Name of the default workflow this replaces
extends: <string>            # Name of a workflow this builds upon
                             # Extended workflow's steps run first, then this workflow's additions
triggers: [<string>, ...]    # Conditions that auto-select this workflow
                             # e.g., ["bug report", "error message", "test failure"]
prerequisites: [<string>, ...]  # Documents that must exist before this workflow starts
                                # e.g., ["constitution"] or ["spec", "plan"]
produces: [<string>, ...]    # Documents this workflow creates
                             # e.g., ["spec", "plan", "implementation"]
---
```

---

## Workflow Body Structure

```markdown
---
(frontmatter)
---

# <Workflow Name>

<1-2 sentence summary.>

## Sequence

<Ordered list of steps. Each step references a skill by name.
Steps can be conditional, repeating, or parallel.>

## Overrides

<Conditions where steps are skipped or modified.
e.g., "Skip step 2 if a spec already exists.">

## Fallbacks

<What happens when a step fails.
e.g., "If implement fails → systematic-debug → retry.">

## Human Checkpoints

<Points where the workflow pauses for human approval.
e.g., "After step 3 (plan), show plan and wait for approval.">
```

---

## Step Syntax

Workflow steps use a simple declarative format:

### Basic Step
```markdown
1. **ELICIT** → `quick-elicit`
```
The name after → is a skill name. The framework resolves it to whatever active skill
has that name (default, override, or replacement).

### Conditional Step
```markdown
2. **PLAN** → `plan` (skip if .sage/work/*/plan.md exists)
```

### Repeating Step (Per-Task)
```markdown
5. **PER TASK:**
   a. `subagent-dispatch` → fresh subagent with task context
   b. `tdd` → red-green-refactor
   c. `implement` → write code
   d. `quality-gates` (sub-workflow)
   e. `semantic-commit`
   f. `session-bridge` → save progress
```

### Parallel Step
```markdown
3. **PARALLEL:**
   a. `research` → validate tech stack choices
   b. `codebase-scan` → understand existing patterns
```
Parallel steps can run simultaneously if the platform adapter supports it.
On Tier 2 platforms (no subagents), parallel steps run sequentially.

### Sub-Workflow Reference
```markdown
4. **QUALITY** → `quality-gates` (sub-workflow)
```
Sub-workflows are defined in `core/workflows/sub-core/workflows/` and reused across workflows.

### Human Checkpoint
```markdown
3. **PLAN** → `plan`
   🔒 CHECKPOINT: Show plan to human. Wait for approval before continuing.
```

---

## Behavioral Contract

Every workflow MUST:

1. **Belong to exactly one mode** (`fix`, `build`, or `architect`).
2. **Reference skills by name only** — never by file path.
3. **Include fallbacks** for critical steps. If a skill fails and no fallback is defined,
   the workflow MUST pause and escalate to the human.
4. **Include at least one human checkpoint** in BUILD and ARCHITECT modes.
   FIX mode MAY omit human checkpoints for fully autonomous operation.
5. **Declare prerequisites** honestly. If the workflow needs a spec, say so.
6. **Declare outputs** honestly. If the workflow produces code, say so.

Every workflow MUST NOT:

1. **Contain implementation logic**. Workflows orchestrate — they don't DO.
   All action happens inside skills.
2. **Hard-code platform behavior**. Use platform-agnostic skill references.
   Adapters handle platform-specific execution (parallel vs sequential, etc.).
3. **Skip gates**. If a workflow includes a quality-gates sub-workflow reference,
   the gates defined in `core/gates/` execute according to `gate-modes.yaml`.
   Workflows cannot selectively disable gates — only the project config can.
4. **Bypass the constitution**. Workflows cannot instruct skills to ignore governance.

---

## Override / Replacement Rules

Each mode has exactly one active workflow. To replace the default:

1. Create `<name>.workflow.md` with `replaces: <default-workflow-name>`.
2. Place it in `.sage/workflows/` (project) or `community/core/workflows/` (community).
3. The replacement MUST satisfy this contract.

Resolution order:
```
1. Project override    (.sage/workflows/)       — highest priority
2. Community           (community/core/workflows/)     — middle priority
3. Default             (core/workflows/)               — lowest priority
```

To extend (not replace) a workflow, use `extends: <workflow-name>`. The extended
workflow's sequence runs first, then the extending workflow's additions.

---

## Sub-Workflow Contract

Sub-workflows follow the same format but:
- Live in `core/workflows/sub-core/workflows/`
- Cannot declare `mode` (they inherit the parent workflow's mode)
- Cannot be entry points — they're only invoked by other workflows
- Are referenced by name in parent workflow steps

The primary sub-workflow is `quality-gates.workflow.md`, which orchestrates
the gate sequence defined in `core/gates/`.
