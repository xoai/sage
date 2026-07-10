# Sage for Hermes Agent

This adapter installs Sage as a native Hermes integration.

The Claude Code install is the behavioral baseline: Sage still provides
workflow commands, skills, gate scripts, session context, and project state.
The file format is Hermes-native:

- `AGENTS.md` in the project root for always-on instructions.
- `$HERMES_HOME/plugins/sage/` for the Sage Hermes plugin.
- `$HERMES_HOME/plugins/sage/skills/` for plugin-bundled Sage workflow skills.
- `$HERMES_HOME/skills/` for direct Sage skills copied from `sage/skills/`.
- `$HERMES_HOME/hooks/` for shell hook scripts and Sage gate scripts.
- `$HERMES_HOME/config.yaml` for plugin enablement, shell-hook wiring, and
  Sage-owned quick-command aliases used by Hermes Desktop slash discovery.

Hermes plugin commands are registered in Python through
`ctx.register_command()`. Shell hooks are declared under `hooks:` in
Hermes config and receive JSON on stdin. Hermes owns `/status`, so the Sage
status workflow is exposed as `/sage-status`.

Hermes Desktop uses the same profile home, config, plugins, skills, sessions,
and memory as the CLI/gateway. Once this adapter updates the active
`HERMES_HOME`, desktop slash commands load from the same `plugins/sage` plugin;
the generated quick-command aliases make `/sage`, `/build`, `/fix`,
`/architect`, `/review`, and `/sage-status` visible in the desktop slash menu.

ACP editor sessions use Hermes' `hermes-acp` toolset. The generator adds an
`acp` entry under `platform_toolsets` with `hermes-acp`, `sage`, and
`delegation` so Sage gate tools are available when Hermes ACP resolves
per-platform toolsets.

## Install

From a project directory:

```bash
bash sage/bin/sage init --platform hermes
```

By default, Sage installs the Hermes plugin into `~/.hermes`. To install into
an explicit profile, set `HERMES_HOME` to that profile home:

```bash
HERMES_HOME="$HOME/.hermes/profiles/work" bash sage/bin/sage init --platform hermes
```

To install into both the default home and a profile, run the generator twice:

```bash
bash sage/bin/sage init --platform hermes
HERMES_HOME="$HOME/.hermes/profiles/work" bash sage/runtime/platforms/hermes/setup/generate-hermes.sh "$PWD"
```

For a scratch install:

```bash
mkdir -p /tmp/sage-hermes-project /tmp/sage-hermes-home
cd /tmp/sage-hermes-project
HERMES_HOME=/tmp/sage-hermes-home bash /path/to/sage/bin/sage init --platform hermes --no-memory
```

## Verification

```bash
bash sage/develop/validators/hermes-native-smoke.sh /path/to/sage
```

The smoke test creates a scratch project and scratch `HERMES_HOME`, runs
`sage init --platform hermes`, imports the generated plugin with
Hermes-compatible command conflict rules, checks desktop quick-command aliases,
and invokes the generated session hook with Hermes-style JSON.

The shared runtime adds validated advisory routing, neutral skill composition,
deterministic learning recall, structured candidate detection, and bounded
evidence reflection. Run its cross-platform smoke test separately:

```bash
bash sage/develop/validators/learning-lifecycle-smoke.sh /path/to/sage
```

Natural-language matches are advisory and are suppressed during an active run.
Only installed explicit commands are authoritative; inferred routes never arm a
mutation gate. `pre_llm_call` recalls scoped prevention rules and delivers
pending learning candidates. `post_tool_call` observes structured outcomes;
Hermes ignores observer return values, so undelivered candidates are claimed by
the next context-capable hook. The bounded `pre_verify` hook requests one
evidence-based reflection after coding work instead of verifying every edit.

Use one configured learning backend (`sage-memory` or OpenViking) and one recall
owner. Recall failures emit no context and never block work. See
[`docs/learning-lifecycle.md`](../../../docs/learning-lifecycle.md) and
[`docs/composition.md`](../../../docs/composition.md).

## Design Notes

Do not copy `.claude/commands/` or `.claude-plugin/` into Hermes. Those are
Claude-specific surfaces. Hermes uses `plugin.yaml`, `__init__.py`,
`ctx.register_command()`, `ctx.register_skill()`, and config-driven shell
hooks.
