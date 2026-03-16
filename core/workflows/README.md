# Sage Workflows

Orchestrated sequences of skills. The conductors.

## Philosophy

Workflows define **order and conditions**, not implementations. A workflow says
"run the TDD skill then the spec review skill." It doesn't contain TDD logic or
review logic — those live in the skills. This separation means you can replace any
skill without changing the workflow, and you can replace the workflow without
changing any skill.

Workflows **reference skills by name, never by path.** When a workflow says
`implement`, the framework resolves that name to whatever active skill has
`name: implement` — the default, a project override, or a community replacement.
The workflow is indifferent to which implementation it gets.

The three core workflows embody the **adaptive weight model:**

- **FIX** is minimal: debug → fix → verify → commit. Zero human checkpoints.
  Designed for autonomous operation on small, well-understood problems.

- **BUILD** is balanced: scan → elicit → spec → plan → task-by-task execution.
  Three human checkpoints (after spec, after plan, after result). This is the
  sweet spot for most daily work.

- **ARCHITECT** is comprehensive: discover → define → design → decompose → sprint
  cycles. Seven+ human checkpoints. Justified when the cost of getting the design
  wrong exceeds the cost of planning.

## Core Workflows

| Workflow | Mode | Steps | Checkpoints | Time |
|----------|------|-------|-------------|------|
| [fix](fix.workflow.md) | FIX | 7 | 0 | Minutes |
| [build](build.workflow.md) | BUILD | 9 | 3 | Hours |
| [architect](architect.workflow.md) | ARCHITECT | 15 | 7+ | Days-weeks |

## Orchestration Layer

Workflows define the sequence. Orchestration skills make the sequence accessible.
These skills were built from lessons across the reference frameworks:

| Skill | Role | Learned From |
|-------|------|-------------|
| `onboard` | First-run: detect stack, select packs, generate .sage/ and CLAUDE.md | Project scanning + context generation pattern |
| `sage-help` | Always-available: read state, give ONE next action | BMAD's `/bmad-help` |
| `build-loop` | Execution engine: drive tasks with gates between each | Superpowers' subagent-driven-development |
| `deep-elicit` | ARCHITECT mode discovery: Socratic exploration | BMAD's analyst-to-PM handoff |

The principle from Superpowers: "your agent just has Superpowers" (implicit
activation). The correction from BMAD: make the process visible so beginners
know what's happening. Sage combines both — skills activate automatically,
but checkpoints and progress reports make the orchestration visible.

## Sub-Workflows

| Name | Used By | Purpose |
|------|---------|---------|
| [quality-gates](sub-core/workflows/quality-gates.workflow.md) | All three | Gate sequence orchestration |

## Replacing Workflows

Each mode has exactly one active workflow. Replace with `replaces: fix|build|architect`
in your workflow's frontmatter. See `develop/contracts/workflow.contract.md`.
