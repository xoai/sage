# Can codex and opencode enforce? — an investigation, not a verdict

**Date:** 2026-07-12 · **Question:** can Sage reach **Tier A** on codex or opencode?
**Answer:** **not proven. Both stay Tier C.**

Tier A requires `pre-tool-veto ∧ post-tool-events ∧ subagent-dispatch`, and under
ADR-11 a tier is *derived* from capabilities that something **checks**. This
document records what was checked, what was found, and what was not established —
because the temptation here was strong and specific, and it is worth writing down
exactly how close I came to shipping a false claim.

---

## The temptation

Both platforms look like they can do it, and the evidence is not weak:

**Codex.** Its native binary (codex-cli 0.130.0) contains a complete hook system.
`strings` on it yields 30 × `PreToolUse`, 25 × `PostToolUse`, `hook_event_name`,
`permissionDecision`, `SubagentStart`/`SubagentStop` — and this:

```
PreToolUse hook exited with code 2 but did not write a blocking reason to stderr
```

**That is Sage's contract, exactly.** Exit 2, reason on stderr. Its hook payload
(`tool_name`, `tool_input`, `cwd`) is the same shape Claude Code sends.

I verified, deterministically and offline, that **Sage's unmodified
`sage-spec-gate.sh` exits 2 when fed a codex-shaped payload.** Half the port is
already done and it required no code at all.

**OpenCode.** Its plugin API documents a veto plainly — `tool.execute.before`
throwing an `Error` blocks the tool call, with a working `.env`-protection example
in the official docs. It has native agents. It is not hidden behind a feature flag.

From all of that it would have been easy — and it would have felt justified — to
write `pre-tool-veto: true` for both and let the tier derive to A.

## What actually happened

### Codex: present in the binary, unreachable in practice

Seven configurations. None fired the hook — verified by an instrumented wrapper
that logged **every** invocation, so an empty log means "never called", not
"called and allowed".

| Attempt | Hook fired |
|---|---|
| `[hooks]` TOML in project `.codex/config.toml` | no |
| `hooks.json` in `.codex/`, project root, `~/.codex/` | no |
| `-c features.hooks=true` | no |
| `-c codex_hooks=true` | no |
| `-c experimental_hooks=true` | no |
| `-c features.codex_hooks=true` | no |
| `[features] hooks = true` as a real TOML table, user **and** project config, project marked `trusted` | no |

The feature exists in the shipped binary. I could not find the configuration that
activates it. **Unreachable is worth `false`.**

### OpenCode: the mechanism works; the veto is still unproven

This one got much further, and the intermediate findings are real:

1. **The plugin loads.** opencode's own debug log:
   `service=plugin path=file:///…/.opencode/plugin/sage.js loading plugin`
   (both `plugin/` and `plugins/` are scanned).
2. **`tool.execute.before` fires.** An instrumented pass captured every tool:
   `glob{pattern,path}`, `read{filePath,…}`, **`apply_patch{patchText}`**, `bash{command,…}`.
3. **Sage's gate ran** inside the hook, spawned from the plugin.
4. **And it correctly ALLOWED** — because opencode's editing tool is
   **`apply_patch`, whose only argument is `patchText`. There is no `filePath`.**
   My adapter handed the gate an empty `file_path`, and a gate given no file to
   gate allows. *That is not the veto failing. That is the adapter feeding it
   nothing.*
5. Rewriting the adapter to parse `*** Update File: <path>` out of the patch body
   caused opencode to produce **no output at all** — the plugin appears to break
   it at load. The investigation stopped there.

So for opencode the chain is proven up to the last link: plugin loads → hook fires
→ gate runs → gate receives a path. **Whether opencode honours the `throw` by
blocking the edit was never observed**, and that is the only claim that matters.

## The verdict, and why it is `false` and not `attested`

`attested` requires an **evidence transcript** of the thing working (C15). I have
transcripts of a hook *firing*. I have none of an edit being *blocked*. Those are
different claims and this project exists because Sage kept confusing them.

    codex     pre-tool-veto: false   — present in the binary, no reachable config
    opencode  pre-tool-veto: false   — mechanism confirmed, block never observed

Both remain **Tier C**.

## The part worth keeping

I nearly wrote "codex's hook contract is nearly identical to Claude Code's, so
Tier A is easy." It **is** nearly identical. And had I written `true` on that
basis, Sage would today be advertising mechanical enforcement **that does not
happen on any real codex session** — the precise failure ADR-11 was built to
prevent, committed by the person who built it, one release later.

Instrumentation caught it twice, and both times the naive check would have lied:

- Codex's **read-only sandbox** blocked the edit. Had I only asked "did the edit
  land?", I would have recorded a successful veto. The hook log was empty — the
  hook had never run.
- OpenCode's final runs produced **no output at all**, so the file was unchanged.
  "`multiply` absent" reads exactly like a block. Nothing had happened.

*Nothing-happened* and *correctly-blocked* are indistinguishable unless you
instrument the mechanism itself. That is the same lesson the hooks-in-subagents
probe taught (three false results before the true one), and the same lesson E9
taught (a truncated eval grades identically to a broken feature).

**Test the instrument before you trust the measurement.**

## For whoever picks this up

The remaining work is small and well-defined:

**Codex** — find the configuration that activates the hooks feature. Everything
else is done: Sage's gates already speak codex's payload and already exit 2 with a
reason on stderr, which is exactly what codex wants. Also worth trying: the binary
references `hooks/hooks.json`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` and
`anthropics/claude-plugins-official` — **codex appears to consume Claude-Code-style
plugins**, and Sage already ships one with `hooks/hooks.json` in exactly that
layout. That may be the whole port.

**OpenCode** — fix the adapter (parse the file paths out of `patchText`; find why
the rewrite kills the process), then run one probe against a `pre-spec` cycle. If
the edit does not land **and** the hook log shows the gate returning 2, that is the
transcript, and `pre-tool-veto` earns `attested` — and opencode derives to Tier A
if `post-tool-events` and `subagent-dispatch` also check out.

Neither is blocked on permission or on design. Both are blocked on one more day of
someone being suspicious of their own instruments.
