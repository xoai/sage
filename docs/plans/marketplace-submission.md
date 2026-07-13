# Official marketplace submission — a maintainer checklist (R129)

**Status:** not submitted. This is a decision for a human, not an agent — listing Sage
in Anthropic's official directory is an outward-facing act, and the honest case for it
is mixed. Read the "should we?" section before the "how".

## How it works

External plugins are **not** submitted by pull request. `anthropics/claude-plugins-official`
says:

> Third-party partners can submit plugins for inclusion in the marketplace. External
> plugins must meet quality and security standards for approval. To submit a new
> plugin, use the [plugin directory submission form](https://clau.de/plugin-directory-submission).

So the mechanics are: fill in the form, and be judged on quality and security. There is
no checklist published beyond that sentence, which means the honest preparation is not
"tick their boxes" but "be able to answer the obvious questions truthfully".

## Sage's own install path already works, and needs no one's approval

```
/plugin marketplace add xoai/sage-marketplace
/plugin install sage@sage-marketplace
```

**Verified, not assumed** — those two commands were run against the live repo and the
resulting plugin inventoried: v1.3.2, 28 skills, 5 agents, 3 hook events, ~2,064
always-on tokens. The official directory would add discoverability. It would not add a
capability.

## Should we submit?

**The case for.** The framework is real, the plugin installs cleanly, the hooks are
mechanical rather than advisory, and the whole thing is MIT with no telemetry and no
network calls of its own.

**The case against, and it is the one worth reading.** Sage publishes an eval suite
that measures its own value, and **the answer is narrower than a directory listing
implies**:

- On four of five short-task scenarios, there is **no measurable difference** from a
  bare frontier agent.
- The long-horizon claim — the one Sage is *for* — **did not hold**. A bare agent given
  the same files matched or beat it on both multi-session scenarios, at a third of the
  cost.
- What does hold is what has been made **mechanical**: test-first measures 3/3 against
  a bare agent's 0/3, because a hook blocks the edit until the test exists.

A directory listing invites a user to install a framework. Sage's own numbers say that
what they will get is *the hooks*, and roughly nothing else, at ~1.6× the context. That
is a defensible thing to ship — it is arguably the most honest agent framework on the
shelf, and it says so on its own front page — but it is a strange thing to *market*,
and nobody should submit it while imagining the numbers say otherwise.

**Recommendation:** submit only if we are comfortable that the README's candour travels
with the listing. If the directory shows a one-line description and no link to
`docs/eval-baseline-v2.md`, we are advertising a claim we have ourselves falsified.

## If we do submit — what to have ready

The form will ask for the obvious. These are true today:

| | |
|---|---|
| **Marketplace** | `xoai/sage-marketplace` — live, and both documented commands verified |
| **Plugin source** | `git-subdir` at `xoai/sage.git`, path `tools/sage-claude-plugin`, ref `plugin-dist` — a branch, so installs always get the current release |
| **License** | MIT |
| **Security: network** | The plugin makes none of its own. `sage add` fetches packs on request, verifies sha256 against the release's `checksums.txt`, and **fails closed** |
| **Security: hooks** | 4 shell hooks. They read the payload, consult the cycle manifest, and exit 0/2. They do not phone home |
| **Security: unpacking** | `sage add` refuses tar members that escape the extraction directory, and refuses symlink members |
| **Telemetry** | None |
| **Token cost** | ~2,064 always-on, measured and published (`docs/context-budget.md`) |
| **Evidence** | `docs/eval-baseline-v2.md` — including the results that do *not* flatter it |

## Before submitting

- [ ] Decide the question in "Should we submit?" above. It is a judgment call, and it
      is not the agent's to make.
- [ ] Confirm `python3 runtime/tools/release.py --dist-status` is green (it checks the
      marketplace pin against this repo's, and fails on drift).
- [ ] Re-run the two install commands against a clean machine.
- [ ] Make sure whatever blurb goes in the form is one we would still stand behind
      after someone reads the eval baseline.
