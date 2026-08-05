# hermes — community-maintained, Tier B (2026-08-05)

**Tier:** B — mechanical gates, no subagent chain. `pre_tool_call` vetoes
edits before they happen, `post_tool_call` writes the R29 degradation audit,
`pre_llm_call` injects the eager core into CLI sessions, slash commands are
registered, and skills are discoverable via `skill_view("sage:<name>")`. The
only gap to Tier A is `subagent-dispatch` — Hermes has `delegate_task` but
the plugin doesn't wire independent reviewers into the review loop yet.

- **Enforced, not prose.** The `__init__.py` registers `pre_tool_call`,
  `post_tool_call`, and `pre_llm_call` via `ctx.register_hook()`. The veto
  returns `{"action": "block", "message": ...}` and Hermes blocks the call.
  The spec-gate, tdd-gate, secrets-gate, config-gate, verify-gate and
  bookkeeping-gate all apply. Rules 3 and 5 are mechanical here, not advisory.
- **CLI + Gateway context.** CLI sessions get the eager core via
  `pre_llm_call` returning `{"context": str}`. Gateway sessions get
  session-aware context via the `hooks/sage-session/` gateway hook writing
  `.sage/gates/session-pickup.md`.
- **Commands + skills wired.** `/sage`, `/build`, `/fix`, `/architect`,
  `/review`, `/learn`, `/reflect`, `/continue`, `/autoresearch` registered
  via `ctx.register_command()`. 21 bundled skills registered via
  `ctx.register_skill("sage:<name>", path)`.
- **Honest gap.** No subagent dispatch (`subagent-dispatch: false` —
  `delegate_task` exists in Hermes but not wired). The agent reviews its
  own code.

Maintainer: rei-stewart. Re-probe on Hermes major version bumps (attestations
expire at release 1.5).
