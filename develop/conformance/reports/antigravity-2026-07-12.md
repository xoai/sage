# Conformance report — antigravity

**Date:** 2026-07-12 · **Levels:** 1,3
**Result:** 8 passed, 0 failed, 0 skipped

| Capability | Result | Detail |
|---|---|---|

| `generation` | ✅ pass | sage init --platform antigravity succeeded |
| `context-injection` | ✅ pass | GEMINI.md generated (858 lines) |
| `command-delivery` | ✅ pass | 9 command(s) in .agent/workflows |
| `native-skill-discovery` | ✅ pass | declared false, and the skills are INLINED instead |
| `pre-tool-veto` | ✅ pass | declared false, and no PreToolUse hook registered |
| `post-tool-events` | ✅ pass | declared false, and no PostToolUse hook registered |
| `session-events` | ✅ pass | declared false, and no SessionStart hook registered |
| `subagent-dispatch` | ✅ pass | declared false (subagent mode will refuse loudly, R97) |
