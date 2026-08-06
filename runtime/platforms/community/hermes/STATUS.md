# hermes — community-maintained, Tier A (2026-08-05)

**Tier:** A — the full quality chain. `pre_tool_call` vetoes edits before
they happen, `post_tool_call` writes the R29 degradation audit,
`pre_llm_call` injects the eager core into CLI sessions, skills are
discoverable via `skill_view("sage:<name>")`, and independent review
dispatches through Hermes-native `delegate_task`. Live-probed 2026-08-05
(`develop/conformance/probes/hermes-gates-probe.py`), attested in
`docs/attestations/hermes-tier-a-2026-08-05.md`.

- **Enforced, not prose.** The `__init__.py` registers `pre_tool_call`,
  `post_tool_call`, and `pre_llm_call` via `ctx.register_hook()`. The veto
  returns `{"action": "block", "message": ...}` and Hermes blocks the call.
  The spec-gate, tdd-gate, secrets-gate, config-gate, verify-gate and
  bookkeeping-gate all apply. Rules 3 and 5 are mechanical here, not advisory.
- **No self-disarmament, including the duplicate-key form.** Both config
  readers (the main gate dispatcher and the config-gate) read first-wins,
  matching the canonical `sage-config-gate.sh`; `contradictory_flag()` blocks
  a config where an enforcement key holds both values. Maintainer review
  2026-08-05 found the duplicate-append bypass in the first port; the fix is
  covered by probes 10–13 of the gate probe.
- **CLI + Gateway context.** CLI sessions get the eager core via
  `pre_llm_call` returning `{"context": str}` (honest about the project's
  actual enforcement state). Gateway sessions get session-aware context via
  the `hooks/sage-session/` gateway hook writing
  `.sage/gates/session-pickup.md`.
- **Skills wired, scoped.** The 21 hermes-platform skills register via
  `ctx.register_skill()` under an explicit allowlist; the framework's own
  domain skills (api, web, nextjs, ...) stay out of the Hermes surface.
  Hermes generates the `/sage-*` skill slash commands natively.
- **Independent review, for real.** The review loop dispatches a
  fresh-context reviewer via `delegate_task` (read-only is prompt-enforced;
  the skill instructs verifying `git status` unchanged before accepting a
  verdict). Attested live, delegation `deleg_1f066fc7`, APPROVE.
- **Honest false.** `context-injection-midstream` is false: Hermes's
  `post_tool_call` is observer-only (return values discarded), so no
  post-tool hook can inject context mid-session. `pre_llm_call` is
  turn-boundary, not the SG-16 channel.

Maintainer: rei-stewart. Re-probe on Hermes major version bumps (attestations
expire at release 1.5).
