# Skill Contract

**Version:** 1.0.0
**Status:** Stable

A skill is a self-contained capability that an agent can invoke. Skills are the atoms
of Sage — each does ONE thing well. Workflows compose skills into sequences.
Gates verify skill outputs. Agents apply personas while executing skills.

---

## Required Directory Structure

```
core/capabilities/<category>/<skill-name>/
├── SKILL.md              # REQUIRED — Skill definition with YAML frontmatter
├── README.md             # REQUIRED — Human-readable explanation for contributors
└── ...                   # OPTIONAL — Any supporting files the skill needs
```

### Common Optional Files

```
├── references/           # Background knowledge the skill may load on-demand
│   └── *.md
├── prompts/              # Subagent prompts (for skills that dispatch subagents)
│   └── *.md
├── develop/templates/            # Output templates the skill produces
│   └── *.md
├── examples/             # Usage examples
│   └── *.md
├── scripts/              # Helper scripts (bash/python)
│   └── *.sh
└── develop/validators/                # Pressure tests                # Pressure tests for the skill
    ├── scenarios.md      # Test scenarios (what to try)
    └── expected.md       # Expected behaviors (what should happen)
```

---

## Required Frontmatter (SKILL.md)

Every SKILL.md MUST begin with YAML frontmatter. The frontmatter is loaded into
Claude's system prompt at startup (~100 tokens per skill), so keep it minimal.

### Primary Fields (in YAML — Claude reads these)

```yaml
---
name: <string>              # Unique skill identifier, kebab-case (e.g., "systematic-debug")
description: <string>       # Trigger-rich description for auto-activation and discovery.
                            # MUST be written in third person ("Processes..." not "I process...").
                            # MUST include both WHAT the skill does and WHEN to use it.
                            # MUST include trigger phrases matching what users actually say.
                            # Example: "Use when the user says 'fix this', 'it's broken',
                            # or 'debug the error'."
                            # Maximum 1024 characters. No XML tags.
version: <semver>           # Semantic version (e.g., "1.0.0")
modes: [<mode>, ...]        # Which modes this skill activates in: fix, build, architect
---
```

### Extended Fields (in sage-metadata comment — Sage tooling reads these)

Optional metadata that Sage tooling uses but Claude doesn't need for discovery.
Place after the closing `---` in an HTML comment block:

```markdown
<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [testing, quality]
inputs: [spec, plan]
outputs: [implementation, test-suite]
requires: [tdd, scope-guard]
-->
```

| Field | Purpose | Default |
|-------|---------|---------|
| `cost-tier` | Recommended model: haiku, sonnet, opus | sonnet |
| `activation` | auto (agent decides), manual (/sage invocation), mandatory (always on) | auto |
| `tags` | Categorization for discovery | [] |
| `inputs` | Document types needed before running | [] |
| `outputs` | Document types this skill produces | [] |
| `requires` | Soft dependencies on other skills | [] |
| `replaces` | Name of default skill this overrides | none |

### Frontmatter Rules

1. `name` MUST be unique across all active skills (including extensions and overrides).
2. `name` MUST be kebab-case: lowercase, hyphens, no spaces.
3. `description` MUST be written for agent consumption — include action verbs, trigger
   phrases, and specific situations. A vague description means the skill never activates.
4. `modes` MUST contain at least one mode.
5. `version` MUST follow semver.
6. `replaces` — if set, this skill takes priority over the skill it replaces.
   Only one skill can replace a given name. Conflicts are resolved by load order:
   project override > community replacement > default.

---

## SKILL.md Body Structure

After the frontmatter, the SKILL.md body contains the instructions that the AI agent
follows when the skill is activated. The body is free-form markdown but SHOULD follow
this structure:

```markdown
---
(frontmatter)
---

# <Skill Name>

<1-2 sentence summary of what this skill does and when to use it.>

## When to Use

<Specific triggers, situations, patterns that should activate this skill.
Be concrete — "when the user reports a bug" not "when appropriate.">

## Process

<Step-by-step instructions the agent follows. This is the core of the skill.
Be prescriptive — tell the agent exactly what to do, in what order.
Include decision points and what to do at each branch.>

## Rules

<Non-negotiable constraints. Things the agent MUST or MUST NOT do.
Organize rules by freedom level using three tiers:>

**MUST** (low freedom — violation causes bugs, lost work, or security issues):
<Critical rules where deviation breaks things.>

**SHOULD** (medium freedom — preferred path with guardrails):
<Recommended practices where context may justify alternatives.>

**MAY** (high freedom — context determines the best approach):
<Optional practices where multiple valid approaches exist.>

The test: if deviation causes a bug or security vulnerability, use MUST.
If deviation causes suboptimal but working code, use SHOULD. If it's
genuinely a matter of preference, use MAY.

## Failure Modes

<What can go wrong and what to do about it.
"If X fails, do Y" not "X might fail.">

## Examples

<At least one concrete usage example showing input → skill activation → output.
More examples = better agent compliance.>
```

---

## README.md Requirements

The README.md is for HUMANS (contributors, reviewers), not agents. It MUST contain:

1. **Purpose**: What problem does this skill solve? Why does it exist?
2. **Design Rationale**: Why is the skill designed this way? What alternatives were considered?
3. **Replacement Guide**: How would someone write a better version?
   What would they need to preserve for compatibility?
4. **Test Guide**: How to verify the skill works. What pressure scenarios to run.
5. **Changelog**: Notable changes by version.

---

## How Skills Connect to Other Modules

```
                    ┌──────────────┐
                    │   Workflow    │ References skill by NAME
                    └──────┬───────┘
                           │ activates
                    ┌──────▼───────┐
  ┌──────────┐     │    Skill     │     ┌──────────┐
  │  Agent   ├────►│   SKILL.md   │────►│   Gate   │
  │ Persona  │     │              │     │  Checks  │
  └──────────┘     └──────┬───────┘     └──────────┘
   applies style          │ may load
                    ┌──────▼───────┐
                    │  references/ │ On-demand knowledge
                    │  develop/templates/  │ Output shapes
                    │  prompts/    │ Subagent dispatching
                    └──────────────┘
```

- **Workflows** reference skills by `name`. The skill's internal structure is invisible to workflows.
- **Agents** apply a persona overlay when executing a skill. The skill doesn't know which persona is active.
- **Gates** run after a skill completes. The skill doesn't call gates — the workflow does.
- **References/develop/templates/prompts** are internal to the skill and loaded only when the skill needs them.

---

## Behavioral Contract

Every skill MUST:

1. Be **self-contained**. A skill MUST work even if its `requires` dependencies are missing
   (with degraded capability and a clear warning, not a silent failure).
2. Be **idempotent** where possible. Running the skill twice should not cause harm.
3. **Declare its inputs and outputs** honestly. If a skill needs a spec to exist, say so in
   `inputs`. If it produces test files, say so in `outputs`.
4. **Fail gracefully**. If a skill cannot complete, it MUST explain why and suggest next steps.
   It MUST NOT silently produce partial or incorrect output.
5. **Respect mode boundaries**. A skill that declares `modes: [architect]` MUST NOT activate
   in FIX or BUILD mode, even if the agent thinks it would be helpful.
6. **Respect the constitution**. Skills MUST NOT instruct the agent to violate constitution
   principles. If a skill's instructions conflict with the constitution, the constitution wins.

Every skill MUST NOT:

1. **Depend on a specific platform**. Skills are platform-agnostic. Platform-specific behavior
   belongs in adapters. A skill MAY reference platform capabilities (e.g., "if subagents are
   available, dispatch; otherwise, execute sequentially").
2. **Hard-code file paths**. Use document types ("the spec", "the plan") not paths.
   The context loader resolves types to actual paths.
3. **Call gates directly**. Quality gates are orchestrated by workflows, not skills.
4. **Modify other skills**. Skills are isolated. If Skill A needs Skill B's output, it
   declares `requires: [skill-b]` and reads Skill B's output through the context system.

---

## Override / Replacement Rules

To replace a default skill:

1. Create a new skill with `replaces: <default-skill-name>` in its frontmatter.
2. The replacement MUST satisfy the same contract (same required frontmatter, same structural rules).
3. The replacement SHOULD be compatible with workflows that reference the replaced skill's name.
   If it changes inputs/outputs, document the incompatibility in README.md.
4. The replacement MUST include tests that verify it handles the same scenarios as the original.

Resolution order when multiple skills claim the same name:
```
1. Project override    (.sage/skills/<name>/)        — highest priority
2. Community replacement (community/skills/<name>/)    — middle priority
3. Extension skill     (skills/<pack>/skills/<name>/) — middle priority
4. Default skill       (skills/<category>/<name>/)     — lowest priority
```

To disable a skill without replacing it, add its name to `disabled` in `.sage/config.yaml`.

---

## Testing Requirement

Skills that are submitted to `community/` or promoted to default MUST include tests
following the Superpowers TDD-for-skills methodology:

1. **Document failure without the skill**: What does an agent do wrong without this skill?
2. **Pressure scenarios**: Situations where an agent is tempted to skip or shortcut the skill.
3. **Expected behaviors**: What the agent MUST do when the skill is active.
4. **Verification method**: How to confirm the skill is working (automated or manual).

See `core/capabilities/_meta/test-skill/` for the testing skill that helps with this process.
