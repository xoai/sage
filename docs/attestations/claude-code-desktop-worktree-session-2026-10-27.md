# Attestation — claude-code · a Claude Desktop worktree session

| Field | Value |
|---|---|
| **Platform** | `claude-code`, inside the Claude Desktop app's Code tab |
| **Capability** | Sage governs a Desktop session that works in an app-made worktree, and its checkpoints, progress and branch handling use the app (Desktop mode) |
| **Verdict** | **yes, with one fix and two open items** — see "What it found" |
| **Method** | two live, interactive `/build`s in Desktop worktree sessions (the second with sage-memory); transcripts read afterwards; one probe of the installed hooks; the memory store read directly |
| **Verified** | 2026-10-27, memory 2026-10-28 |
| **Platform version** | Claude Code 2.1.308–2.1.309 (session entrypoint `claude-desktop`), Claude Desktop 4.29.0 |
| **Expires** | release 1.4 |
| **Probed by** | feat/desktop-native (Phases A and B) |

## The setup

A scratch Node project (`calc.mjs`, `node --test`), `sage init --platform
claude-code` from this branch, with `.sage/` and the vendored `sage/`
gitignored — the layout where nothing Sage needs travels with git — and
`hard_enforcement: true`, `tdd_enforcement: true`. No Sage plugin enabled.

Claude Desktop started a Code session in its own worktree,
`.claude/worktrees/blissful-blackwell-ee5da4` on the app's branch
`claude/blissful-blackwell-ee5da4`, with the prompt `/build Add a divide(a, b)
function … throws a RangeError when b is 0, with tests`. The user answered
every checkpoint in the app.

## What happened

| Claim | Observed |
|---|---|
| `.worktreeinclude` carries Sage into an app-made worktree | The worktree had `sage/`, `CLAUDE.md`, `.sage/config.yaml` and `.sage/gates` — all gitignored, so none came through git. |
| Desktop mode switches on by itself | The SessionStart context carried the Desktop block (entrypoint `claude-desktop`, no `desktop_mode` key). |
| Checkpoints are asked as buttons | All 10 checkpoints were `AskUserQuestion` calls — spec, two review rounds, a design question, plan, plan review, resume, Gate 8, completion. No text footer was printed for any of them. |
| Progress goes to the app's task list | 9 task-list updates; no per-task progress lines in chat. |
| A worktree session keeps the app's branch | No branch question was asked; the agent ran `manifest.py close-out --branch claude/blissful-blackwell-ee5da4 --decision "worktree session branch kept for the initiative"` and committed `fb39ee8` there. |
| No `[M]` in a worktree session | The completion checkpoint offered `[A] Approve` and `[R] Revise` only; the branch was left unmerged. |
| The gates judge the worktree | Asked about an untested edit to `calc.mjs` in the worktree, the installed TDD gate returns a structured deny ("tests before code"); the pre-change hook allows the same edit, because from the main checkout the worktree's files sit under `.claude/` and are skipped. The session itself wrote the test before the code. |
| Cycle records survive the worktree | Every close-out copied the cycle to the main checkout's `.sage/worktree-records/blissful-blackwell-ee5da4/20261027-divide/`; at the end it holds the spec, plan, ledger, baseline and a manifest at `status: complete`, `gate_state: gates-passed`, `qa: passed`. |

## What it found

**Fixed — the session hook ran in the wrong checkout.** Claude Desktop runs a
worktree session's SessionStart hook with the MAIN checkout as its working
directory (`CLAUDE_PROJECT_DIR`), not the worktree. The hook read its own
cwd, so it reported the main checkout's state ("No active work") and gave the
non-worktree branch line. The gates were unaffected — they resolve from the
`cwd` in their input. The hook now reads the session's `cwd` from its
SessionStart input (hook test DM6c, red on the previous hook). The agent kept
the app's branch anyway, from git-discipline's "Worktree sessions" section.

**Open — a hand edit of `gate_state`.** Twice the agent advanced the
manifest's `gate_state` with `sed -i` rather than `manifest.py close-out`.
Shell writes into `.sage/` are not gated (the same gap E8 found on
2026-10-27); the bookkeeping gate only redirects Edit/Write.

**Open — a whole-command false block.** One command chained `review.py gate
… review-ledger.json` (the ledger's own writer) with a `sed -i` on the
manifest; the config gate's records rule, which matches the whole command,
blocked it. The agent re-ran `review.py` alone. The block also stopped a hand
edit, but the rule is coarse (a known limit of the config gate's shell
matching).

## Second run — sage-memory (2026-10-28)

Same project, after `sage setup memory` wrote `.mcp.json` (committed, so git
carries it into worktrees; `.worktreeinclude` lists it too for projects that
ignore it) and gitignored `.sage-memory/`. One convention was seeded into the
main checkout's store beforehand — that every calc function throws
`TypeError("calc: expected finite numbers")` on non-finite input — deliberately
untrue of the code, so following it or questioning it would both show it was
read. A second Desktop worktree session (`wonderful-poitras-ba57a7`) ran
`/build Add a modulo(a, b) function … with tests`, with no mention of memory.

| Claim | Observed |
|---|---|
| The memory server reaches a worktree session | The `sage-memory` tools were loaded; 7 searches, 5 stores, 4 links. |
| A worktree session reads the main checkout's store | The first search returned the seeded convention. The agent saw it contradicted `calc.mjs` and asked about it at the spec checkpoint (follow the code or the memory); the user chose the code. |
| A worktree session writes the main checkout's store | Three new memories landed in the main checkout's `.sage-memory/memory.db` — a correction of the seeded convention, a `%`/`-0` gotcha and a Gate 4 gotcha. No `.sage-memory/` was created in the worktree; the main checkout's is the only store. |

The agent never called `sage_memory_set_project`, though the session hook
suggests it in a linked worktree: the server resolved the main checkout's
store by itself (presumably launched from the main checkout, as Desktop runs
the SessionStart hook there). The call stays in the hook as the fallback for
hosts that launch the server inside the worktree. The run also repeated the
first run's open item: the agent advanced `gate_state` with `sed -i` once.

## Not covered

A Desktop session without a worktree (an ordinary checkout — the branch
gate's propose-confirm as buttons); `desktop_mode: off`; the plugin install
path; a project that tracks `.sage/`. The deterministic hook tests cover
those shapes (WT*, DM*); these probes are the live runs.
