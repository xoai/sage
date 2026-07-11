# Conformance report — claude-code

**Date:** 2026-07-12 · **Levels:** 1,3
**Result:** 8 passed, 0 failed, 1 skipped

| Capability | Result | Detail |
|---|---|---|

| `generation` | ✅ pass | sage init --platform claude-code succeeded |
| `context-injection` | ✅ pass | CLAUDE.md generated (177 lines) |
| `command-delivery` | ✅ pass | 9 command(s) in .claude/commands |
| `native-skill-discovery` | ✅ pass | 19 skills emitted for on-demand discovery |
| `pre-tool-veto` | ✅ pass | PreToolUse hook registered in the generated project |
| `post-tool-events` | ✅ pass | PostToolUse hook registered in the generated project |
| `session-events` | ✅ pass | SessionStart hook registered in the generated project |
| `subagent-dispatch` | ○ skipped | not provable from generated output — needs a level-2 probe |
