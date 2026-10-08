# hermes — community-maintained, Tier A (2026-08-05)

**Tier:** A — the full quality chain is implemented by two deliberately
separate surfaces. The selected profile's shell-hook registry owns seven
fail-closed blockers and four observers. The Python plugin owns exactly four
lifecycle/context callbacks: `on_session_start`, `pre_llm_call`,
`transform_tool_result`, and `pre_verify`. Independent review routes through
Hermes-native `delegate_task`; Sage registers no replacement delegation or
Kanban worker service. Historical live evidence is recorded in
`docs/attestations/hermes-tier-a-2026-08-05.md`.

- **Mechanical gates stay mechanical.** The spec, TDD, bookkeeping, secrets,
  verify, config, and scope blockers are selected-profile shell hooks. The four
  observer scripts track verification, degradation, manifest state, and scope.
  The plugin intentionally does not duplicate those scripts with Python
  callbacks.
- **Plugin callbacks are profile-bound.** `on_session_start` validates the
  binding, `pre_llm_call` injects current bound context, `transform_tool_result`
  attaches corrective context to a tool result, and `pre_verify` surfaces the
  active quality policy. No gateway-only Sage bundle is installed.
- **No self-disarmament.** The hook config readers use the canonical first-wins
  policy and reject contradictory enforcement keys; the duplicate-key bypass
  remains covered by the gate probes.
- **Skills wired, scoped.** The 21 Hermes-platform skills register via
  `ctx.register_skill()` under an explicit allowlist. Hermes generates their
  `/sage-*` commands natively.
- **Independent review uses host ownership.** The workflow skills prescribe a
  fresh-context `delegate_task` review plus post-dispatch immutability checks.
  Sage does not claim that static capability metadata proves a child ran.
- **Honest limitation.** `context-injection-midstream` remains false in the
  platform contract; the supported corrective path is the explicit
  `transform_tool_result` callback before the next model turn.

Maintainer: rei-stewart. Re-probe on Hermes major version bumps (attestations
expire at release 1.5).
