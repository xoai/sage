# Platform Contract

**Version:** 1.0.0
**Status:** Stable

A platform makes Sage work on a specific AI coding tool or IDE. The core framework
is platform-agnostic — adapters handle the platform-specific glue: how commands are
registered, how skills are presented, how subagents are dispatched (or not).

---

## Required Directory Structure

```
runtime/platforms/<platform-name>/
├── platform.yaml              # REQUIRED — Adapter manifest declaring capabilities
├── README.md                 # REQUIRED — Setup instructions for this platform
├── INSTALL.md                # REQUIRED — Step-by-step installation guide
│
└── ...                       # Platform-specific files (plugin manifests, configs, etc.)
```

The internal structure varies by platform. A Claude Code adapter has a `.claude-plugin/`
directory. A Cursor adapter has rules files. A generic adapter has a CLAUDE.md-style
system prompt. The platform.yaml manifest is the universal interface.

---

## Required Manifest (platform.yaml)

```yaml
---
# REQUIRED FIELDS
name: <string>                 # Platform identifier, kebab-case
description: <string>          # Which tool/IDE this adapter supports
version: <semver>
tier: <integer>                # 1 or 2 (see Tier Model below)

# REQUIRED: Capability declarations
capabilities:
  subagents: <boolean>         # Can dispatch independent subagents?
  parallel-execution: <boolean> # Can run multiple tasks simultaneously?
  worktrees: <boolean>         # Can manage git worktrees?
  hooks: <boolean>             # Can run pre/post hooks on events?
  slash-commands: <boolean>    # Can register custom slash commands?
  skill-auto-activation: <boolean>  # Can skills trigger automatically from description?
  file-system-access: <boolean>     # Can read/write project files?

# REQUIRED: How commands appear in this platform
command-prefix: <string>       # e.g., "/sage" or "sage:"
install-method: <string>       # "plugin-marketplace", "manual-copy", "cli", "fetch-instructions"

# OPTIONAL
supported-os: [<string>]       # e.g., ["linux", "macos", "windows"]. Default: all.
min-version: <string>          # Minimum platform version required
---
```

---

## Tier Model

### Tier 1: Full Power
Platforms with subagent support. The complete Sage experience.

- Subagent-driven development (fresh subagent per task)
- Parallel task execution
- Two-stage adversarial review with separate reviewer subagents
- Git worktree isolation
- Hook-based skill activation

Examples: Claude Code, Codex, platforms with Task primitives.

### Tier 2: Guided
Platforms with slash commands but no subagent dispatch. Workflows run sequentially
in a single agent session.

- Same workflows, same skills, same gates
- Sequential execution instead of subagent dispatch
- Quality gates run as sequential checks within the agent
- No worktree isolation (uses standard branches)
- Skills trigger via slash commands or description matching

Examples: Cursor, Copilot, Gemini CLI, Windsurf, Amp, OpenCode.

### Graceful Degradation

When a workflow step requires a Tier 1 capability on a Tier 2 platform:

| Tier 1 Feature | Tier 2 Fallback |
|----------------|-----------------|
| Subagent dispatch | Same agent executes sequentially |
| Parallel tasks | Sequential execution |
| Adversarial review subagent | Self-review with explicit adversarial prompt |
| Git worktree | Standard feature branch |

Workflows and skills MUST NOT fail on Tier 2 platforms. They degrade gracefully.
Skills can check platform capabilities and adjust behavior:

```markdown
## Process
...
If subagents are available (Tier 1), dispatch a fresh subagent for this task.
Otherwise (Tier 2), execute within the current session with a context reset.
```

---

## Behavioral Contract

Adapters MUST:

1. **Accurately declare capabilities**. The framework uses these declarations to choose
   execution strategies. Lying about capabilities causes failures.
2. **Provide installation instructions** that a developer can follow in under 5 minutes.
3. **Register Sage commands** in whatever format the platform requires.
   At minimum: `/sage fix`, `/sage build`, `/sage architect`, `/sage help`.
4. **Handle context loading** according to the context loader's instructions.
   The platform is responsible for injecting the constitution and relevant skill content
   into the agent's context using whatever mechanism the platform provides.
5. **Degrade gracefully**. Tier 2 adapters must handle Tier 1 workflow steps without errors.

Adapters MUST NOT:

1. **Add platform-specific skills or workflows**. If behavior differs by platform,
   the skill handles it through capability checks, not the platform.
2. **Modify core contracts**. Adapters translate — they don't interpret.
3. **Skip gates**. On Tier 2 platforms, gates run sequentially instead of in subagents,
   but they still run.

---

## Minimum Command Set

Every adapter MUST register these commands (using the platform's command mechanism):

| Command | Maps To |
|---------|---------|
| `{prefix} fix <description>` | FIX mode workflow |
| `{prefix} build <description>` | BUILD mode workflow |
| `{prefix} architect <description>` | ARCHITECT mode workflow |
| `{prefix} review` | Code review sub-workflow |
| `{prefix} debug <description>` | Systematic debugging skill |
| `{prefix} rescue` | Legacy rescue workflow |
| `{prefix} help` | Show available commands and current project status |
| `{prefix} status` | Show progress, active mode, installed extensions |
