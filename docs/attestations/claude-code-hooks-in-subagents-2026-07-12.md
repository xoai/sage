# Attestation — claude-code · `pre-tool-veto` **inside subagents**

| Field | Value |
|---|---|
| **Platform** | `claude-code` |
| **Capability** | `pre-tool-veto` (scope: subagent tool calls) |
| **Verdict** | **true** — hooks fire inside subagents, and exit 2 blocks the call |
| **Method** | live headless probes, instrumented hook, actor attribution |
| **Verified** | 2026-07-12 |
| **Platform version** | Claude Code 2.1.207 |
| **Expires** | release 1.4 (C15) |
| **Probed by** | P3-T1, resolving C14 / R95 **[V]** |

## The claim under test

ADR-10 builds subagent execution on an assumption the spec flagged **[V]** and
C14 made a hard constraint:

> Do Claude Code's PreToolUse hooks fire for tool calls made **inside** a Task
> subagent — and does an exit-2 veto actually **block** them?

Everything rests on this. If hooks stop at the subagent boundary, then a fresh
implementer subagent is an *unpoliced* context: spec-gate and tdd-gate do not
apply to it, and the whole quality argument for subagent execution inverts —
you would have taken work out of the one context where the gates run and moved
it into one where they don't.

The spec anticipated both answers and pre-committed to a design for each. This
is the evidence that selects between them.

## Result: hooks fire, and they block

Both halves confirmed.

### Half 1 — do PreToolUse hooks fire for a subagent's tool call?

One run, two actors, two distinct files, so attribution is unambiguous:

- `notes/by-main.md` — written by the main agent (control)
- `notes/by-sub.md` — written by a dispatched subagent (treatment)

The main agent's transcript attributes each `tool_use` via
`parent_tool_use_id` — present on the subagent's calls, absent on its own:

```
TOOL      TARGET              ATTRIBUTED TO
Write     notes/by-main.md    main agent
Agent     —                   main agent
Write     notes/by-sub.md     SUBAGENT (parent=toolu_01GgiA)
```

The observation-only hook logged **both**:

```
Write :: notes/by-main.md     ← main agent
Write :: notes/by-sub.md      ← the SUBAGENT's call
```

**PreToolUse fires for subagent tool calls.**

### Half 2 — does exit 2 actually *block* one? (R95's scenario, exactly)

A TDD gate: block any edit under `src/` while no test exists. A subagent is told
to add `multiply(a, b)` to `src/calc.py`. There is no test suite. This is
legitimate work meeting a legitimate rule — the subagent is not being asked to
circumvent anything.

The hook log, in chronological order, is the whole finding:

```
Edit  :: src/calc.py          ← attempt 1 — BLOCKED (no test existed)
Write :: tests/test_calc.py   ← the subagent RECOVERED: it wrote the test
Edit  :: src/calc.py          ← attempt 2 — allowed (a test now exists)
```

`multiply` did reach `src/calc.py` — **after** a test was written for it. That is
the gate working, not failing: the rule is not "never edit source", it is "never
edit source *before* a test". The interleaving is the proof, because the test
file could only have been written *between* the two source edits if the first one
was denied. Had the hook not fired inside the subagent, attempt 1 would have
landed, and there would be no test file at all.

The block's stderr also propagated back up to the main agent's final result —
so an orchestrator can *see* that its implementer was gated, which is what the
Phase-3 ledger needs in order to record it.

## Consequence for ADR-10

**The design proceeds as written.** The normative variant is the one where hooks
hold inside the loop. Per-task Gate 4/5 runs from the orchestrator remain in the
design as belt-and-braces, not as the primary enforcement — they now catch a
*lying implementer* (one that reports DONE without doing the work), which is a
different failure than an *unpoliced* one, and R106 covers it.

The alternative variant C14 pre-authorized — "orchestrator-enforced, and the
truth table must state that in-subagent enforcement is absent" — is **not**
needed and is not adopted.

This is the good outcome. Sage's gates are fail-closed scripts, and they keep
firing in exactly the context where a fresh implementer would otherwise be least
supervised: no memory of the constitution, no memory of the spec, and every
incentive to just make the edit.

## Three false results this probe produced first

Recorded because each one would have been publishable, and each was wrong.

1. **The agent refused.** The first probe asked a subagent to write a file the
   hook explicitly forbade. The agent read the hook, recognised the request as
   laundering a blocked write through a subagent, and declined — correctly. The
   probe was measuring my prompt, not the platform. *Ask for legitimate work and
   let the rule collide with it; do not ask the model to help you cheat.*

2. **A vacuous pass.** A run with zero subagent dispatches and zero hook fires
   reported "✅ BLOCKED — hooks DO fire", because the file simply did not exist.
   Nothing had happened, and nothing-happened graded identically to
   correctly-blocked. This is the exact failure mode Sage's own eval harness
   guards against with its null-agent check, reproduced by hand within an hour of
   writing that sentence in a commit message.

3. **A broken hook, mistaken for a broken platform.** The gate read `stdin` into
   a shell variable *and* fed a Python heredoc on `stdin`, so `json.loads` parsed
   the Python source, threw, and the hook failed open. The run reported "the gate
   did NOT hold inside the subagent" — a false negative that would have flipped
   ADR-10 to its fallback variant and put a permanent, untrue line in the
   enforcement truth table. It was caught only by self-testing the hook against a
   synthetic payload before trusting it. **Test the instrument before you trust
   the measurement.**

## Why this expires

Hook propagation into subagents is a platform behavior, undocumented as a
guarantee. It can regress with any Claude Code release, silently, and Sage's
entire subagent quality story would evaporate while every one of our tests
continued to pass — because our tests do not run a real subagent under a real
hook.

Phase 4 (R109) therefore wires this probe in as a level-2 conformance check for
`pre-tool-veto`. If the behavior changes, conformance goes red, the truth table
regenerates, and subagent mode's enforcement claim is withdrawn rather than
quietly falsified.
