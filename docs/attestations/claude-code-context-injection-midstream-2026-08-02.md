# Attestation — claude-code · `context-injection-midstream`

| Field | Value |
|---|---|
| **Platform** | `claude-code` |
| **Capability** | `context-injection-midstream` (PostToolUse `hookSpecificOutput.additionalContext`) |
| **Verdict** | **true** — context injected by a PostToolUse hook reaches the model mid-session |
| **Method** | live headless canary probe + documentation contract check |
| **Verified** | 2026-08-02 |
| **Platform version** | Claude Code 2.1.220 (docs state the field requires ≥ 2.1.196) |
| **Expires** | release 1.4 |
| **Probed by** | Scope Guard implementation, resolving the pack's [V1] verification item |

## The claim under test

The scope judge's entire delivery channel (SG-16) is one JSON envelope
returned on a PostToolUse hook's stdout:

```json
{"hookSpecificOutput": {"hookEventName": "PostToolUse",
                        "additionalContext": "..."}}
```

If the platform ignores it, the judge is verdicts-on-disk only — detection
with no correction. ArchAstro/scopey demonstrates the channel live on Claude
Code and Codex (prior art, credited per C18), but Sage does not borrow other
people's attestations: an `attested` value needs our own evidence file.

## Result: the canary came back

A scratch project registered a PostToolUse hook (matcher `Bash`) whose only
output is the envelope above with `additionalContext: "The magic token is
MAGIC-TOKEN-4711."`. A headless run (`claude -p`, haiku) was asked to run one
Bash command and then report any system-injected mention of a magic token —
a token that exists NOWHERE in the project, the prompt, or the transcript
except through the injection channel.

The final output:

```
MAGIC-TOKEN-4711
```

The model can only produce that string if the hook's `additionalContext` was
delivered into its context after the tool call. It was.

Documentation cross-check (code.claude.com/docs/en/hooks, fetched
2026-08-02): the envelope shape is a documented API — `hookSpecificOutput`
with camelCase `hookEventName`/`additionalContext` on output (hook INPUT uses
snake_case `hook_event_name`), available from Claude Code 2.1.196.

The same fetch resolved the pack's [V2]: hook input inside a Task subagent
carries documented `agent_id`, `agent_type`, and `parent_tool_use_id` fields —
the markers `scope_judge.py` uses for SG-11's subagent suppression.

## Why this expires

The field is documented, but the judge's use of it (delivery timing relative
to the NEXT model turn, behavior under -p headless mode) is platform behavior
that can shift with any release. Re-probe each minor (C15); the probe costs
one haiku call.
