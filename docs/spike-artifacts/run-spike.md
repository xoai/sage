# Running the Pi spike proof

**This has been run. It passes 4/4.** The transcript is `pi-veto-transcript.txt`.
These are the commands that produced it, so anyone can reproduce it.

| File | What it is |
|---|---|
| `pi-sage-spike.ts` | The PoC extension: eager-core injection (Q2), veto (Q1), audit log (Q3) |
| `pi-veto-proof.test.ts` | The proof — a negative control plus Q1/Q2/Q3 |
| `pi-veto-transcript.txt` | The committed evidence (§22), including the mutation check |

Throwaway, per 10-spec §21 R84 — nothing here merges into `runtime/` or `core/`.

## Why this is free

Pi ships a **faux model provider** (`packages/ai/src/providers/faux.ts`, publicly
re-exported) that lets you script the model's turns. Its `DEFAULT_BASE_URL` is
`http://localhost:0` and is never dialed. So the decisive question — can an extension
actually stop a tool call — is answerable **offline, deterministically, in ~2 seconds,
for $0**.

That means a Sage-on-Pi veto regression test can live in CI, needing no key, and catch
a breaking change the morning it lands. Given that Pi bumps **breaking changes in minor
releases** (see the verdict's risk section), that test is not optional.

## Reproduce

```bash
git clone https://github.com/earendil-works/pi
cd pi
npm install                     # lifecycle scripts stay blocked; that is fine

mkdir -p packages/coding-agent/spike
cp /path/to/sage/docs/spike-artifacts/pi-sage-spike.ts      packages/coding-agent/spike/
cp /path/to/sage/docs/spike-artifacts/pi-veto-proof.test.ts packages/coding-agent/spike/

cd packages/coding-agent
node ./node_modules/vitest/dist/cli.js --run spike/pi-veto-proof.test.ts
```

Expected:

```
✓ CONTROL: an allowed path is written (so an unwritten file MEANS something)
✓ Q1: BLOCKS a write to *.blocked.* and tells the model why
✓ Q2: the eager core reaches the model's context at session start
✓ Q3: completed tool calls are observable, with name + input + status

Tests  4 passed (4)
```

**Do not run the full vitest suite.** Pi's `AGENTS.md` warns it activates e2e tests
that hit real endpoints when auth env vars are present. Name the file.

## The two things that make this a proof rather than a green tick

**1. A negative control.** The `write` tool really writes. The CONTROL test sends it
to an *allowed* path and asserts the file appears — because a tool that is broken, or
never wired up, also leaves the file uncreated, and would look exactly like a
successful veto. Only once the tool is proven capable of writing does its failure to
write mean anything.

Not paranoia. Scar tissue. Twice this project came within a commit of recording a veto
that never happened: codex's read-only sandbox blocked an edit, and opencode's crashed
runs left the file unchanged.

**2. A mutation check.** Flip the extension's `{block: true}` to `{block: false}` and
Q1 fails — `expected true to be false`, because the tool then *executes and writes the
file*. The veto is what stops it. A test that cannot go red is not evidence.

## The trap that cost an hour

**`session_start` does not fire until `bindExtensions()` is called** — it is emitted
inside it, at `agent-session.ts:2197`, and Pi's test harness does not call it. The Q2
proof failed on its first run and appeared to say *"Pi cannot inject context at session
start."*

It says nothing of the sort. Nothing had ever asked it to.

`print-mode.ts:73` calls `session.bindExtensions({mode})` before driving a turn; the
proof now does the same, and Q2 passes. **A Sage-on-Pi port that forgets this will
inject nothing, report no error, and look exactly like a correctly-installed Sage** —
until an agent skips a test and nobody can explain why the constitution did not stop
it.
