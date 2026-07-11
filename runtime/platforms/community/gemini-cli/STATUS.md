# gemini-cli — community-maintained (experimental)

**Tier:** community. Not a first-class Sage platform.

- **Generation-tested only.** CI checks that this platform's generator produces
  files and that its shell parses. It is not exercised end-to-end.
- **Quality chain unavailable.** The sub-agent reviews (auto-review, auto-QA,
  independent Gate 3) and the PreToolUse spec-gate hook are Claude Code only.
  On this platform, Rule 3 and Rule 5 are enforced by prose alone, and any
  skipped review degrades loudly (announced + logged). See the per-platform
  enforcement table in the root README.
- **First-class platforms** — full quality chain and end-to-end CI — are
  `claude-code` and `generic`.

Contributions welcome. If you rely on this platform, help keep its generator
current; the core team does not test it per release.
