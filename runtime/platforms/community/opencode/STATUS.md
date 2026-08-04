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
  (`setup/adapter-test.mjs`, 13/13), independent of opencode's model backend.
- **Scope judge ported (2026-08-04).** The same `scope_judge.py` runtime as
  claude-code, behind `scope_judge: true` (ships false): the adapter journals
  events, triggers the background cheap-model pass (`judge_cmd: auto` → a
  user-defined `sage-scope-judge` agent carrying a model — the explicit
  spend designation; soft-fail otherwise, nothing inferred), and delivers a
  drift correction by appending to the live tool result —
  `context-injection-midstream` attested with a planted-drift transcript
  (`docs/attestations/opencode-context-injection-midstream-2026-08-04.md`,
  expires 1.4). Capability only: E-JUDGE-1 never ran on opencode.
  Setup walkthrough (steps, artifact checks, cost shape):
  `docs/configuration.md` § "Enabling the judge, start to finish".
- **Reviewer model binding (2026-08-04, v1.3.13).** Independent reviews
  dispatch as the `sage-reviewer` agent — never `general`, which has no
  model binding and inherits the primary (observed live before the fix).
  Bind it in opencode config the same way as the judge; the dispatch note
  ships in generated AGENTS.md and the review-bearing commands, pinned by
  generation-smoke. Verified live: a task-tool dispatch bound the child
  session to the configured model.
- **The honest edge.** No native skill discovery (system skills are inlined into
  `AGENTS.md`), and opencode's model backend was flaky during the probe — which
  is why the load-bearing proof is the deterministic adapter test, not a single
  live session.

Maintainer: sage-core. Re-probe on opencode major version bumps (attestations
expire at release 1.5).
