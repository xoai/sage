# Community platforms (experimental)

antigravity, codex, gemini-cli, opencode. These generate Sage's process files
for their respective agents, but they are **community-maintained** and
**generation-tested only** — the sub-agent quality chain and the mechanical
spec-gate hook are Claude Code only (see each platform's `STATUS.md` and the
enforcement truth table in the root README).

First-class platforms are `claude-code` and `generic`, one level up.

`sage init` still offers these behind an "experimental" label, and the
generators run in CI's shell-syntax and generation-smoke checks.
