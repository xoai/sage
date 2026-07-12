# Running the Pi spike proof

Two files here, both throwaway (10-spec §21 R84 — nothing from the spike merges
into `runtime/` or `core/`):

| File | What it is |
|---|---|
| `pi-sage-spike.ts` | The PoC extension: eager-core injection (Q2), veto (Q1), audit log (Q3) |
| `pi-veto-proof.test.ts` | The Q1 proof, driven by Pi's faux provider — no network, no API key, no spend |

## Why this is free

Pi ships a **faux model provider** (`packages/ai/src/providers/faux.ts`, publicly
re-exported from `packages/ai/src/index.ts`) that lets you script the model's turns
directly. Its `DEFAULT_BASE_URL` is `http://localhost:0` and is never dialed. So the
decisive question of this spike — can an extension actually stop a tool call —
is answerable **offline, deterministically, and for $0**.

That is unusual and worth saying out loud. It means Sage could keep a Pi-veto
regression test in CI that runs in seconds with no key, and catch a breaking API
change at upgrade time rather than in production. Pi bumps breaking changes in
*minor* releases (see the verdict's risk section), so that test is not optional.

## Steps

```bash
git clone https://github.com/earendil-works/pi
cd pi
npm install                                    # installs the monorepo's deps

# Drop the two spike files into the coding-agent package
mkdir -p packages/coding-agent/spike
cp /path/to/sage/docs/spike-artifacts/pi-sage-spike.ts      packages/coding-agent/spike/
cp /path/to/sage/docs/spike-artifacts/pi-veto-proof.test.ts packages/coding-agent/spike/

cd packages/coding-agent
node ../../node_modules/vitest/dist/cli.js --run spike/pi-veto-proof.test.ts
```

**Do not run the full vitest suite.** Pi's `AGENTS.md` warns that it activates e2e
tests which hit real endpoints when auth env vars are present. Name the file.

## What a pass proves

The test is hostile by construction: the `write` tool's `execute()` **throws**. If
the veto does not fire, the tool runs, the throw escapes, and the test fails. There
is no way for it to pass while the block quietly does nothing.

That property is the whole point, and it is not paranoia — it is scar tissue.
Twice, a naive check would have reported success when *nothing had happened at
all*: codex's read-only sandbox blocked an edit (which would have been recorded as
a veto), and opencode's crashed runs left the file unchanged (same). An unchanged
file is not evidence of a veto. An unexecuted tool is.

## The one thing not yet done

At the time the verdict was written, this test had **not been executed** — running
it requires `npm install` inside a third-party checkout, which executes that repo's
lifecycle scripts, and the spike had no authorization to do that. The verdict says
so plainly and does not launder the gap.

Everything Q1 claims is traced to source and to Pi's *own* passing test
(`packages/coding-agent/test/suite/agent-session-model-extension.test.ts:117-160`,
"allows extension tool_call handlers to block tool execution" — whose tool also
throws if executed). That is a stronger foundation than documentation, which is
what misled us on codex. It is still not the same as having run it ourselves.

Run the command above and paste the output into the verdict. It takes a minute and
it converts the last inference into an observation.
