# Multi-Agent — protocol

Sage's optional multi-agent capability augments the default build loop
with externally-invoked agents and Hermes-native execution. Roles are bound to agents in
`.sage/agents.toml`; the dispatcher `.sage/scripts/run-role.sh` is the
only thing that knows how to invoke each CLI.

Installed by `sage setup multi-agent`. Removed by
`sage setup multi-agent --remove`. Refreshed (framework-owned files
only) by `sage update`.

## Roles

| Role            | Default agent | Mode       | Writes to                                                  |
|-----------------|---------------|------------|------------------------------------------------------------|
| `planner`       | Current host       | interactive | `.sage/work/<slug>/{brief,spec,plan}.md`             |
| `spec_reviewer` | Codex CLI     | read-only  | `.sage/work/<slug>/reviews/<artifact>-spec_reviewer-*.md`  |
| `implementer`   | Kimi CLI      | yolo       | source tree (uncommitted) + `implementer-notes.md`         |
| `code_reviewer` | Codex CLI     | read-only  | `.sage/work/<slug>/reviews/diff-code_reviewer-*.md`        |

Change a binding by editing `.sage/agents.toml`. The slash commands and
scripts do not name tools.

## Hermes execution topology

Hermes installs the same `/build-x` command family in its Sage plugin and
requires an explicit execution topology:

- `--direct` uses the configured host/CLI roles.
- `--delegate` uses synchronous `delegate_task` fan-out for bounded lanes.
- `--kanban` keeps Phases 1-5 as the approved planning boundary, then loads the
  canonical `kanban-orchestrator` skill to create a durable, dependency-linked
  graph. Every dispatched card loads `kanban-worker` plus its relevant Sage
  skill and terminates with `kanban_complete` or `kanban_block`.

With no flag, Hermes proposes a topology for confirmation; it never creates
agents or cards from keyword matches. `HERMES_KANBAN_TASK` always selects worker
mode. The board remains the source of truth for task status, while Sage
manifests, gates, reviews, and learnings remain the method/evidence layer.

## Context passing

No agent reads any other agent's session memory. All handoffs are
file-based:

- The `spec_reviewer` sees: the artifact path passed in, plus any siblings
  under `.sage/work/<slug>/`.
- The `implementer` sees: `spec.md` + `plan.md` + the project tree +
  `CLAUDE.md`.
- The `code_reviewer` sees: spec, plan, and `git diff` of uncommitted
  changes.

Every reviewer run is timestamped (`-YYYYMMDD-HHMMSS.md`) so the loop
history is preserved. `.sage/decisions.md` logs each iteration's verdict.

## Reviewer output schema

Reviewer outputs MUST conform to a schema (see `.sage/scripts/validate-review.sh`):

1. Last non-empty line is exactly one of: `APPROVE`, `REVISE`, `REJECT`,
   `FIX_BEFORE_MERGE`, `REWORK`.
2. A `## Findings` section exists.
3. Every finding header is `### [BLOCKER]`, `### [MAJOR]`, or `### [MINOR]`.
4. Every finding has both `**Where:**` and `**Quote:**` lines.

Outputs that fail validation are flagged with a warning. The orchestrator
should surface the malformed output rather than acting on it.

## Iteration semantics

When a reviewer runs a second time on the same target, the dispatcher
injects the previous review into the prompt and instructs the reviewer
to: (a) confirm prior BLOCKERs/MAJORs are resolved or re-raise them,
(b) hunt for new issues introduced by the fix, (c) not soften standards.

A regressing review (round 2 misses what round 1 caught) is treated as
worse than no review. Conversely, the reviewer must not escalate trivia
to keep the loop alive: converging to only-MINOR findings is a
legitimate `APPROVE`. `/build-x` Phase 3 stops the loop on a
severity-gated basis (0 BLOCKER / 0 MAJOR), not on the verdict word.

## Sandbox guarantees

- The `spec_reviewer` and `code_reviewer` invoke their CLI with read-only
  flags (Codex: `--sandbox read-only`; Kimi: `--plan`). They cannot edit
  code or artifacts.
- The `implementer` invokes its CLI with edit-permitting flags (Kimi:
  `--print --yolo`). It is told not to commit. The uncommitted diff is
  the audit trail.
- Only the host (`planner`) writes to `.sage/work/<slug>/{spec,plan}.md`.

## Running the loop

- Full augmented cycle: `/build-x <task>`
- Spec review:          `/review-spec  <slug>`
- Plan review:          `/review-plan  <slug>`
- Implementation:       `/implement    <slug>`
- Code review:          `/review-code  <slug>`

## Integration with Sage core workflows

`/build-x` Phase 2 (spec) classifies the task and reuses Sage's
existing workflows where they fit:

| Task shape                                           | Workflow invoked | Artefacts consumed by spec.md          |
|------------------------------------------------------|------------------|----------------------------------------|
| Architecture-shaped (new module, cross-cutting)      | `/architect`     | ADRs under `.sage/work/<slug>/`        |
| Knowledge gap / unfamiliar domain                    | `/research`      | `.sage/docs/{jtbd,user-interview,…}-*` |
| UX-shaped (new flow, screen, accessibility)          | `/design`        | `.sage/docs/ux-*`                       |
| Mechanical (config tweak, rename sweep)              | none             | n/a                                     |

If you change the shape of `/architect`, `/design`, or `/research`
(e.g., where they write artefacts, what they produce), update
`prompts/planner.md` and `commands/build-x.md` in this template tree
in lockstep — otherwise `/build-x` will reference workflows that no
longer match reality.

## When Sage regenerates

`sage upgrade` updates the framework copy on your machine; `sage update`
applies template changes inside this project.

User-owned (NEVER touched by `sage update`):

- `.sage/agents.toml`
- `.sage/prompts/*.md`
- `.sage/work/`, `.sage/decisions.md`

Framework-owned (refreshed from `runtime/multi-agent/`; if you've
locally edited one, `sage update` prompts `[K]eep | [R]eplace | [D]iff`
before writing):

- `.sage/scripts/run-role.sh`
- `.sage/scripts/validate-review.sh`
- `.sage/docs/multi-agent.md`
- `.claude/commands/{build-x,review-spec,review-plan,implement,review-code}.md`
- `.claude/agents/{codex-reviewer,kimi-implementer}.md`
- Hermes: `~/.hermes/plugins/sage/skills/{build-x,review-spec,review-plan,implement,review-code}/`

Merged, not overwritten:

- `.claude/settings.json` — multi-agent bash patterns are added; your
  custom patterns are preserved.
- Hermes `config.yaml` — existing delegation, Kanban, profile, and board
  settings are preserved by the Sage platform generator.

If you want to extend further, follow the same naming rule: don't shadow
Sage's generated command names. Most extensions belong in `.sage/prompts/`
(prompt tuning) or in your own slash commands under names that don't
collide with `build-x`, `review-spec`, etc.
