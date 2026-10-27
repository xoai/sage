# Attestation — claude-code · structured PreToolUse deny

| Field | Value |
|---|---|
| **Platform** | `claude-code` |
| **Capability** | PreToolUse `hookSpecificOutput.permissionDecision: "deny"` with `permissionDecisionReason` |
| **Verdict** | **partly** — the deny blocks the call and the reason reaches the model without the hook's command line; the result is still labelled `PreToolUse:<Tool> hook error` |
| **Method** | live headless probe, the same edit under both hook outputs |
| **Verified** | 2026-10-27 |
| **Platform version** | Claude Code 2.1.289 |
| **Expires** | release 1.4 |
| **Probed by** | P2 (review 2026-10-26, C6) |

## The claim under test

The review found that a correct Sage block "renders as `PreToolUse:Edit hook
error`" and reads to users as Sage being broken, and proposed returning Claude
Code's structured deny instead of exit 2. Every Sage gate now does that when
the hook input names `hook_event_name: "PreToolUse"` (callers without it — the
opencode adapter, the hook tests — keep exit 2).

## The probe

A scratch project from `sage init --platform claude-code`, one in-progress
cycle in `pre-spec` on `master` (so the spec gate and the branch gate both
block), and one headless call:

```
claude -p "Use the Edit tool to change x = 1 to x = 2 in src/app.js. Make
exactly one Edit attempt …" --output-format stream-json --verbose
```

A logging hook confirmed the input Claude Code sends carries
`hook_event_name: "PreToolUse"` (plus `cwd`, `session_id`, `tool_input`,
`tool_name`, `tool_use_id`, `transcript_path`, `permission_mode`, `effort`,
`prompt_id`).

The tool result the model received, under each hook output:

| Hook output | `tool_result` (is_error: true) |
|---|---|
| exit 2 + stderr (before) | `PreToolUse:Edit hook error: [bash "$CLAUDE_PROJECT_DIR/.claude/hooks/sage-branch-gate.sh"]: Sage: implementation does not start on the default branch (master) …` |
| structured deny (now) | `PreToolUse:Edit hook error: Sage: implementation does not start on the default branch (master) …` |

In both, the edit did not happen, and with two gates denying, one reason was
shown.

## What it means

- The structured deny is honored and is the better channel: the model gets
  the reason alone, not a shell command line that reads like a script failing.
- The `PreToolUse:<Tool> hook error` label is Claude Code's, for every hook
  block, in headless mode at this version; no hook output changes it. The
  review's "would read as a normal refusal" does not hold here. Interactive
  rendering was not probed.
- Re-probe on a Claude Code upgrade; the label may change.
