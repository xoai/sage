# Sage for Hermes Agent

> **Where the code lives:** the plugin is packaged as the whole repo — the
> Hermes plugin entry point is `__init__.py` at the repository root and the
> manifest is `plugin.yaml`. This directory holds the platform contract,
> docs, and the `sage init` generator only.

**Tier A** — the full quality chain, live-probed 2026-08-05. Edits are blocked
before a spec or a test exists; independent reviews run in fresh contexts via
delegate_task; degradation is logged by code. See
`docs/attestations/hermes-tier-a-2026-08-05.md`.

## What Sage enforces on Hermes

| Capability | Status | Mechanism |
|---|---|---|
| **Pre-tool veto** | ✅ Attested | `pre_tool_call` returns `{"action": "block", ...}` — Hermes blocks the edit |
| **Post-tool audit** | ✅ Attested | `post_tool_call` writes R29 degradation to `decisions.md`, tracks verify-state |
| **Context injection** | ✅ Attested | `pre_llm_call` injects eager core + session-pickup into CLI; `session:start` writes `.sage/gates/session-pickup.md` for gateway |
| **Session lifecycle** | ✅ Attested | Gateway: `session:start` / `session:end` via `hooks/sage-session/`. CLI: context injection via `pre_llm_call` |
| **Slash commands** | ✅ Attested | `/sage`, `/build`, `/fix`, `/architect`, `/review`, `/learn`, `/reflect`, `/continue`, `/autoresearch` registered via `ctx.register_command()` |
| **Skill discovery** | ✅ Attested | 21 bundled skills registered via `ctx.register_skill()` — loadable via `skill_view("sage:<name>")` |
| **Subagent dispatch** | ✅ Attested | `delegate_task` dispatched live — independent fresh-context reviewer, verdict APPROVE (2026-08-05) |

## Installation

### Option 1: Profile plugin (recommended)

Copy the entire `sage/` directory into your Hermes profile:

```bash
# From the xoai/sage repo root:
cp -r . ~/.hermes/profiles/<your-profile>/plugins/sage/
```

Then enable it in Hermes:

```bash
hermes plugins enable sage
```

### Option 2: Global plugin

```bash
cp -r . ~/.hermes/plugins/sage/
hermes plugins enable sage
```

### Option 3: Vendored into a project

```bash
cd your-project
sage init --platform hermes
```

This runs `setup/generate-hermes.sh` which writes:
- `.sage/` — the Sage project directory
- `SOUL.md` — the instructions file Hermes reads at session start
- `.hermes/config.yaml` snippet — registers the shell hooks (if using shell hooks instead of plugin)

## How the gates work

### Pre-tool veto (`pre_tool_call`)

When the agent calls `write_file` or `patch`, the plugin:

1. Finds the project root (nearest `.sage/` ancestor)
2. Reads `.sage/config.yaml` for enforcement flags
3. Runs each gate in order:
   - **config-gate** — blocks edits that would disable enforcement (meta-gate)
   - **secrets-gate** — blocks hardcoded credentials
   - **bookkeeping-gate** — redirects hand-edits to the one-command close-out writer
   - **spec-gate** — blocks source edits while any cycle is `pre-spec`
   - **tdd-gate** — blocks source edits before a test exists
4. Returns `{"action": "block", "message": "..."}` if any gate fails

Hermes short-circuits the tool call and shows the `message` to the model.

### Post-tool audit (`post_tool_call`)

After every tool call:

1. **verify-tracker** — records `last_source_edit` and `last_test_run` timestamps
2. **manifest-sync** — advances cycle manifests when plain work happened
3. **R29 degradation audit** — if a cycle completes with `qa: skipped-*` or `qa: waived`, logs to `decisions.md`

### Gateway session lifecycle (`session:start` / `session:end`)

The `hooks/sage-session/` gateway hook:

1. **Collision guard** — warns if another Sage session is active in the same checkout
2. **Worktree memory** — points `sage-memory` at the main checkout root in linked worktrees
3. **Active work scan** — lists cycles with `status: in-progress`
4. **Recent decisions** — shows the last 3 decisions from `decisions.md`
5. Writes `.sage/gates/session-pickup.md` for the eager core to read

On `session:end`, appends to `.sage/gates/session-log`.

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

## What's NOT enforced

- **Subagent review** — `delegate_task` exists in Hermes but the plugin doesn't dispatch independent reviewers. The agent reviews its own code.

## Reaching Tier A

To upgrade from Tier B to Tier A, the plugin needs:

1. **Subagent dispatch** — wire `delegate_task` into the review loop so spec, plan, and code get independent fresh-context review. The plugin would call `delegate_task` with a reviewer persona and the artifact path, then check the review result before allowing completion.

## Troubleshooting

### Plugin not loading

```bash
HERMES_PLUGINS_DEBUG=1 hermes plugins list
```

Check for:
- Missing `__init__.py` with `register(ctx)` function
- Wrong directory depth (must be `plugins/<name>/plugin.yaml`)
- Python import errors in the handler

### Gates not blocking

1. Check `.sage/config.yaml` — `hard_enforcement` must be `true`
2. Check `.sage/gates/gate-blocks.log` — are blocks being logged?
3. Verify the tool name matches — only `write_file` and `patch` are gated

### Gateway hook not firing

```bash
hermes logs --follow --level INFO | grep sage-session
```

The hook only fires in gateway mode (Telegram, Discord, etc.), not CLI.

## Maintainer

`rei-stewart` — re-probe on Hermes major version bumps (attestations expire at release 1.5).