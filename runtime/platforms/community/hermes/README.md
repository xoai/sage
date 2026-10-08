# Sage for Hermes Agent

> **Where the code lives:** the selected profile's `plugins/sage/` directory is
> a complete, updateable Sage framework tree: CLI, core, runtime, skills, hooks,
> packs, docs, installer, and platform adapters. `runtime/tools/build_plugin.py
> --target hermes` copies the canonical tracked/release tree there, adds the two
> Hermes-native projection files, emits a per-file framework manifest, and also
> packages the profile shell hooks separately under artifact `hooks/`.

**Tier A** — the full quality chain is covered by the current platform
validators and two-profile lifecycle probe. Edits are blocked before a spec or
a test exists; independent reviews route through Hermes-native `delegate_task`;
degradation is logged by code. Historical probe evidence remains in
`docs/attestations/hermes-tier-a-2026-08-05.md`.

## What Sage enforces on Hermes

| Capability | Status | Mechanism |
|---|---|---|
| **Pre-tool veto** | ✅ Verified | 7 fail-closed blockers and 4 observers are configured as selected-profile shell hooks; Hermes owns hook execution and blocking |
| **Post-tool audit** | ✅ Verified | Four observer hooks track verification, degradation, manifest state, and scope without blocking the completed tool call |
| **Plugin lifecycle** | ✅ Verified | `on_session_start`, `pre_llm_call`, `transform_tool_result`, and `pre_verify` bind context and policy to one profile workspace |
| **Slash commands** | ✅ Verified | 16 slash commands are registered from validated bound-runtime skill bytes |
| **Skill discovery** | ✅ Verified | 21 bound runtime skills are registered via `ctx.register_skill()` |
| **Native tools** | ✅ Verified | 8 Sage tools cover deterministic gates and strict project memory |
| **Delegation** | ✅ Attested | Sage routes review policy through Hermes-native `delegate_task`; it registers no replacement delegation, Kanban, or worker service |

## Installation

Run the complete Sage framework from the exact selected profile workspace. Both
the collection root and one profile name are mandatory before any write:

```bash
sage init --platform hermes --hermes-home <collection> --hermes-profile <name>
```

The receipt-bound lifecycle uses the same explicit selection:

```bash
sage update --platform hermes --hermes-home <collection> --hermes-profile <name>
```

```bash
sage migrate hermes-profile --platform hermes --hermes-home <collection> --hermes-profile <name>
```

```bash
sage migrate hermes-profile --rollback --platform hermes --hermes-home <collection> --hermes-profile <name>
```

```bash
sage recover hermes-profile <operation-id> --platform hermes --hermes-home <collection> --hermes-profile <name>
```

```bash
sage doctor --platform hermes --hermes-home <collection> --hermes-profile <name>
```

```bash
sage uninstall --platform hermes --hermes-home <collection> --hermes-profile <name>
```

`uninstall` removes only valid receipt-owned bytes and exact Sage hook/consent
records. It preserves durable project state, identity, databases, user files,
and unrelated hooks.

`migrate hermes-profile` adopts a legacy Sage surface into the transactional
profile layout; `--rollback` restores a completed migration from its external
backup. If the process is interrupted while an install, update, or migration
child transaction is still incomplete, use `recover hermes-profile`. The
operation ID is the filename stem of an `incomplete` journal under
`.sage/install-runs/`. Recovery validates the rollback pack and known receipt
hashes before restoring the prior managed/config/receipt bytes; unexpected
post-crash edits fail closed instead of being overwritten.

The transaction writes or manages:

- `.sage/` — the Sage project directory
- `.hermes.md` — the workspace instructions Hermes reads
- `sage/` — the complete bound project runtime
- `.sage-memory/` — strict project-only memory state
- `<profile>/hooks/` — the Sage shell-hook scripts
- `<profile>/config.yaml` — registers the profile shell hooks
- `<profile>/plugins/sage/` — the complete profile-scoped Sage framework/plugin
  tree, including its update manifest and all canonical runtime/framework files
- `<profile>/skills/` — receipt-managed optional packs only

It never writes profile identity such as `SOUL.md`.

## Portable host boundary

Production Sage resolves Hermes only as an opaque command: JSON argv in
`SAGE_HERMES_COMMAND`, or `hermes` from `PATH`. It does not import `hermes_cli`,
inspect a virtual environment, or discover a source checkout.

Install, update, doctor, and uninstall ask the host for fresh CLI and Gateway
proof through this public command shape:

```text
hermes --profile <name> hooks activation-proof --surface <cli|gateway> --expectation-file <path>
```

The proof validates plugin discovery, callbacks, exact approved hook topology,
policy behavior, context delivery, and strict memory binding. `sage doctor` is
the normal user-facing entry point.

## How the gates work

Hermes receives one immutable target plan per tool call. The selected profile's
shell-hook registry contains these exact blockers:

1. `sage-spec-gate.sh`
2. `sage-tdd-gate.sh`
3. `sage-bookkeeping-gate.sh`
4. `sage-secrets-gate.sh`
5. `sage-verify-gate.sh`
6. `sage-config-gate.sh`
7. `sage-scope-gate.sh`

The four observers are `sage-verify-tracker.sh`, `sage-degradation-log.sh`,
`sage-manifest-sync.sh`, and `sage-scope-journal.sh`. The plugin intentionally
does **not** duplicate those mechanics with `pre_tool_call` or `post_tool_call`
callbacks.

Plugin callbacks provide profile-bound lifecycle/context behavior on both CLI
and Gateway surfaces. No gateway-only Sage bundle is installed.

## Configuration

### `.sage/config.yaml`

```yaml
hard_enforcement: true    # master switch — gates are inert when false
tdd_enforcement: true     # tdd-gate (Rule 1)
secrets_gate: true        # secrets-gate (no hardcoded credentials)
verify_gate: true         # verify-gate (verify-before-claiming)
bookkeeping_gate: true    # bookkeeping-gate (one-command close-out)
```

All gates are **opt-in** — a project without `.sage/config.yaml` or with
`hard_enforcement: false` gets zero enforcement. The plugin never surprise-blocks.

## Ownership boundary

Hermes owns `delegate_task`, child lifecycle, workspaces, the Kanban dispatcher
and database, and goal-mode judging. Sage owns workflow instructions, flags,
quality gates, bound context, and its narrow pre-verification policy. The
plugin's runtime inventory reports replacement delegation and Kanban
registration as false by design.

### Native Kanban execution

Use a Hermes-native card rather than a Sage-owned worker or dispatcher:

```yaml
workspace_kind: dir
workspace_path: <absolute-target-repository>
skills:
  - sage:sage-build
goal_mode: true
body: |
  Execute the preloaded Sage build workflow.
  Invocation arguments: --autonomous --quality-locked
  Goal: <requested work>
  Run all Sage gates and independent reviews before completion.
```

Skill preloading does not supply invocation flags, so the card body must carry
`--autonomous --quality-locked` explicitly. The current plugin does not
intercept Hermes-native `kanban_complete`: `pre_verify` supplies advisory
quality context and goal mode supplies the host judge, but neither independently
proves current-byte Sage receipts. The runtime inventory and `platform.yaml`
therefore declare the completion-policy bridge false until that separate
initiative exists.

## Troubleshooting

### Plugin not loading

```bash
HERMES_PLUGINS_DEBUG=1 hermes --profile <name> plugins list
```

Check for:
- Missing `__init__.py` with `register(ctx)` function
- Wrong directory depth (must be `plugins/<name>/plugin.yaml`)
- Python import errors in the handler

### Gates or callbacks not active

Run the receipt-aware doctor command above. It distinguishes present,
registered, discovered, executed, context-delivered, and behaviorally-verified
states without mutating the profile. Doctor states: `failed`, `present`,
`registered`, `discovered`, `executed`, `context-delivered`,
`behaviorally-verified`.

## Maintainer

`rei-stewart` — re-probe on Hermes major version bumps (attestations expire at release 1.5).