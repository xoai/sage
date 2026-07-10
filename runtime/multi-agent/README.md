# `runtime/multi-agent/` — source tree for the Multi-Agent capability

This directory is the **template** for Sage's optional multi-agent build
cycle. Files here are copied into a user's project by `sage setup
multi-agent` (see [`bin/sage`](../../bin/sage) → `sage_setup_multi_agent`).

End-user docs live elsewhere — this README is for contributors editing
the framework.

## Audience

- Read this if you're changing the multi-agent install behavior, the
  reviewer schema, the dispatcher, or any of the role prompts.
- If you're a user who wants to try the feature, run
  `sage setup multi-agent` in a Sage project and read
  `.sage/docs/multi-agent.md` after install.

## Layout

```
runtime/multi-agent/
├── agents.toml.template      Role → agent binding (deployed to .sage/agents.toml)
├── prompts/                  Role prompts (deployed to .sage/prompts/)
│   ├── _shared.md            Prepended to every role
│   ├── planner.md            Charter for the current host agent
│   ├── spec_reviewer.md      Adversarial spec/plan reviewer
│   ├── implementer.md        Behavior contract for the implementer
│   └── code_reviewer.md      Adversarial post-implementation reviewer
├── scripts/                  Dispatcher + schema validator
│   ├── run-role.sh           Reads agents.toml, invokes the configured CLI
│   └── validate-review.sh    Schema check on reviewer output
├── commands/                 Host commands (Claude `.claude/`; Hermes Sage plugin)
│   ├── build-x.md            Augmented build cycle
│   ├── review-spec.md        Run the spec_reviewer on spec.md
│   ├── review-plan.md        Run the spec_reviewer on plan.md
│   ├── implement.md          Run the implementer
│   └── review-code.md        Run the code_reviewer on the diff
├── agents/                   Claude Code sub-agents (deployed to .claude/agents/)
│   ├── codex-reviewer.md     Isolates reviewer stdout from main context
│   └── kimi-implementer.md   Isolates implementer stdout from main context
├── docs/
│   └── multi-agent.md        End-user protocol doc (deployed to .sage/docs/)
├── settings.snippet.json     Bash patterns merged into .claude/settings.json
└── manifest.json             Content hashes for `sage update` drift detection
```

## Framework-owned vs user-owned

This split is enforced by `sage setup multi-agent` and `sage update`.
Editing the wrong column has predictable consequences.

| Deployed path                            | Owner       | What `sage update` does |
|------------------------------------------|-------------|--------------------------|
| `.sage/agents.toml`                       | **user**    | Never touched            |
| `.sage/prompts/*.md`                      | **user**    | Never touched            |
| `.sage/scripts/run-role.sh`               | framework   | Refreshes from template  |
| `.sage/scripts/validate-review.sh`        | framework   | Refreshes from template  |
| `.sage/docs/multi-agent.md`               | framework   | Refreshes from template  |
| `.claude/commands/build-x.md`             | framework   | Refreshes from template  |
| `.claude/commands/review-*.md`            | framework   | Refreshes from template  |
| `.claude/commands/implement.md`           | framework   | Refreshes from template  |
| `.claude/agents/codex-reviewer.md`        | framework   | Refreshes from template  |
| `.claude/agents/kimi-implementer.md`      | framework   | Refreshes from template  |
| `.claude/settings.json`                   | merged      | Multi-agent bash patterns added; user patterns preserved |
| Hermes Sage plugin command skills         | framework   | Refreshed without replacing Hermes Kanban/profile config |
| `.sage/config.yaml :: multi_agent.*`      | framework   | `installed_version` bumped |

User-owned files surface "tune-the-loop" levers. If a change you want
to make is universal, change the template here. If it's project-
specific, change it under `.sage/` in the user's project.

## Testing changes locally

```bash
# 1. Make your edit under runtime/multi-agent/.
# 2. Bump the version hash for any framework-owned file you touched:
python3 runtime/multi-agent/scripts/regen-manifest.py     # see Phase 0
# 3. In a throwaway project, simulate an upgrade:
SAGE_HOME=/tmp/sage-test sage upgrade  # if installed globally
# Or run locally from this repo's bin/:
./bin/sage setup multi-agent --remove
./bin/sage setup multi-agent
# 4. Confirm the deployed file matches your edit.
```

## Reviewer output schema

Every reviewer file under `.sage/work/<slug>/reviews/` MUST satisfy:

1. Last non-empty line is exactly one of: `APPROVE`, `REVISE`, `REJECT`,
   `FIX_BEFORE_MERGE`, `REWORK`.
2. A `## Findings` section exists.
3. Every finding header matches `^### \[(BLOCKER|MAJOR|MINOR)\] `.
4. Every finding has `- **Where:**` and `- **Quote:**` lines.

`scripts/validate-review.sh` enforces this. If you change the schema,
update both the validator and `prompts/{spec_reviewer,code_reviewer}.md`
in lockstep, or the validator and prompts will disagree silently.

## Adding a new reviewer-class role

1. Write a prompt at `prompts/<role>.md`.
2. Add `[roles.<role>]` to `agents.toml.template` with a sensible
   default agent.
3. If the role needs a new slash command, add it under `commands/`
   following the pattern of `review-spec.md`.
4. Re-run the manifest regenerator.
5. Update `docs/multi-agent.md` so end users know the role exists.

The dispatcher (`scripts/run-role.sh`) already handles arbitrary role
names — it reads them from `agents.toml`. No script changes needed
unless the role's output schema differs from the reviewer schema.

## Adding a new agent (CLI)

Edit `agents.toml.template`. Add a `[agents.<name>]` block following
the existing Codex / Kimi examples. Required fields:

- `kind = "cli"`
- `command` — binary on PATH
- `prompt_style` — `argv`, `flag`, or `stdin`
- `flags`, `model_flag`, `output_flag`
- `modes.<name>` — one or more modes a role can select

The dispatcher's invocation logic is data-driven from these fields.
A new CLI usually does not need any script edits.
