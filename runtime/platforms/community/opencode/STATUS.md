# opencode — community-maintained, Tier A (2026-07-17)

**Tier:** A — mechanically enforced. `sage init` ships an enforcement adapter
(`.opencode/plugin/sage.js`) that vetoes edits, records the audit trail, and
dispatches independent subagent reviews, all through opencode's plugin API.

- **Enforced, not prose.** The adapter bridges `tool.execute.before` to Sage's
  gate scripts and `throw`s on exit 2 — opencode blocks the call. The spec-gate,
  tdd-gate, secrets-gate, config-gate and verify-gate all apply, including
  **inside dispatched subagents** (proven: the reviewer's own tool calls fire the
  hooks). Rules 3 and 5 are mechanical here, not advisory.
- **Proven.** Capabilities attested with an instrumented transcript
  (`docs/attestations/opencode-tier-a-2026-07-17.md`); the shipped adapter is
  tested deterministically against the real gates
  (`setup/adapter-test.mjs`, 5/5), independent of opencode's model backend.
- **The honest edge.** No native skill discovery (system skills are inlined into
  `AGENTS.md`), and opencode's model backend was flaky during the probe — which
  is why the load-bearing proof is the deterministic adapter test, not a single
  live session.

Maintainer: sage-core. Re-probe on opencode major version bumps (attestations
expire at release 1.5).
