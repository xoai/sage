# Running Multiple Sessions in Parallel — Comprehensive Guide

A complete reference for developing several things at once with Sage:
when a branch is enough and when you need a worktree, how the
`sage worktree` launcher works, how the collision guard protects you,
and the details that bite (gitignored `.sage/`, WSL, cleanup).

If you're skimming, the [Quickstart](#quickstart) is enough to start
your first parallel session. The rest is for when you want to
understand *why* it works the way it does, or to debug.

> **Status:** v1.1.8. The config switch and `sage worktree` launcher
> are platform-agnostic; the in-session collision warning is Claude
> Code (a session-init hook).
> **Required:** a git repository. In a non-git project none of this
> applies — every workflow runs exactly as it would without it.

---

## TL;DR

- **One task at a time → a branch is enough.** Every `/build`, `/fix`,
  `/architect`, `/build-x` already branches per initiative and merges
  only when you say so. Nothing to configure.
- **Two tasks at once → use a worktree.** Run `sage worktree <slug>`,
  then `cd` into the printed directory and launch `claude` there. Each
  parallel task is its own directory + branch + session.
- **The one rule:** never run two `claude` sessions in the *same*
  directory. They share one working tree and clobber each other. Sage
  warns you if you do.

---

## Why branches aren't enough for parallel work

A git **branch** is a label on history. It records *which commits
belong to which line of work*. That is exactly what you want when you
do one thing at a time: your feature's commits don't interleave with
`main`, and you get a clean PR.

But a branch does **not** give you a second workspace. In one clone
there is one **working tree** (the files on disk) and one **HEAD** (the
branch you're on). So if you open two `claude` sessions in the same
directory:

- Both read and write the **same files**. Session A's edit to
  `payment.ts` and session B's edit to the same file race on disk.
- `git checkout -b feat/b` in session B moves **HEAD for session A
  too** — A's uncommitted work is suddenly "on" B's branch.

No amount of branch discipline fixes this, because the conflict is on
the working tree, not in history. The only git-native way to have two
live workspaces at once is a **worktree** (or a second clone).

| | Isolates | Use when |
|---|---|---|
| **Branch** | History (commits) | One session at a time, sequential initiatives |
| **Worktree** | The working tree (files on disk) | Multiple sessions running **simultaneously** |

A worktree *includes* a branch — `git worktree add -b` creates both at
once — so "use a worktree" never means "give up branch hygiene." It
means "add a second workspace."

---

## The constraint that shapes everything

**A Claude Code session is bound to the directory it was launched in.**
Its file tools, the `.sage/work/` paths, the `CLAUDE.md` loaded at
startup, the `.claude/commands/` — all rooted at that directory. A
running session can *create* a worktree (it can run any git command),
but it **cannot move itself into it**.

The practical consequence: there is no "open `claude` in your repo, run
`/build`, and have it silently isolate you in a worktree" path. To get
a session *inside* a worktree, a session has to be *started* there —
and starting an interactive program in a directory is something only
you can do from your shell.

This is not a Sage limitation. With raw git you'd `git worktree add`
and then `cd` in and open your editor. Sage's job is to make that one
unavoidable action a **single command** (`sage worktree`) and to make
forgetting it **loud** (the collision guard) instead of silent.

---

## Quickstart

From inside your repo:

```bash
sage worktree payment-retry
```

You'll see something like:

```
  Sage — Worktree
  Branch: feat/payment-retry  from main
  Dir:    /path/to/your-repo-payment-retry
  Preparing worktree (new branch 'feat/payment-retry')
  ✓ Copied gitignored runtime into the worktree.

  Open an isolated session there:
    cd "/path/to/your-repo-payment-retry" && claude
```

Open that session and work normally — `/build`, `/fix`, etc. branch and
commit in place because the session is *already* isolated. When you're
done and ready to merge, do it from the worktree (or the main checkout)
with the workflow's `[M]` option.

Run as many as you want — one worktree per concurrent task:

```bash
sage worktree fix-login --prefix fix     # ../your-repo-fix-login on fix/fix-login
sage worktree new-dashboard              # ../your-repo-new-dashboard on feat/new-dashboard
```

---

## Making it the default: `isolation: worktree`

By default `.sage/config.yaml` has:

```yaml
isolation: branch        # sequential — branch in place
```

Leave it as `branch` if you usually work one session at a time:
workflows branch in place, nothing changes.

Set it to `worktree` if you routinely run parallel sessions:

```yaml
isolation: worktree
```

Now when a delivery workflow (`/build`, `/fix`, `/architect`,
`/build-x`) starts in the **main checkout**, it offers a guided menu
before branching in place:

```
This project uses isolation: worktree.
[1] Set up an isolated worktree (recommended for parallel) — run sage worktree <slug>
[2] Proceed here in the shared checkout (not isolated)
[3] Sequential, this once
```

It is a **menu, never a refusal** — a lone sequential session can
always pick `[2]` and proceed. When a workflow is already running
*inside* a worktree, there's no menu; it just branches in place, since
the session is already isolated.

`isolation` is read with a safe default: an absent key, an empty value,
or anything other than `worktree` resolves to `branch`. Existing
projects without the key behave exactly as before.

---

## `sage worktree` reference

```
sage worktree <slug> [--from <ref>] [--prefix feat|fix|arch] [--launch]
sage worktree list
sage worktree prune
```

**Create** (`sage worktree <slug>`):

1. **Git gate.** Errors cleanly (exit 2) if you're not in a git repo.
2. **Default branch.** Resolves the base via the same chain the
   workflows use: `origin/HEAD` → `init.defaultBranch` (if that branch
   exists locally) → a local `main`/`master` → otherwise the current
   branch (with a notice). Override with `--from <ref>`.
3. **Branch name.** `<prefix>/<slug>` — `--prefix` chooses
   `feat` (default), `fix`, or `arch`. A name collision appends
   `-2`, `-3`, …
4. **Directory.** A sibling: `../<repo>-<slug>`. A path collision
   appends `-2`, `-3`, …; an existing directory is **never** deleted.
5. **Create.** `git worktree add -b <branch> <dir> <base>` — branch and
   worktree in one atomic step.
6. **Runtime copy** (only when needed — see
   [the two `.sage/` worlds](#the-two-sage-worlds)).
7. **Launch line.** Prints `cd <dir> && claude`. With `--launch`, it
   `cd`s and `exec`s `claude` for you (use this when you run the
   command in a fresh terminal you want to become the session).

| Flag | Effect |
|---|---|
| `--from <ref>` | Base the worktree on `<ref>` instead of the resolved default branch |
| `--prefix feat\|fix\|arch` | Branch prefix (default `feat`) |
| `--launch` | `cd` into the worktree and `exec claude` instead of just printing the line |

**`sage worktree list`** — shows your worktrees (`git worktree list`).

**`sage worktree prune`** — runs `git worktree prune` (clears
bookkeeping for directories you deleted manually) and reminds you that
a worktree with uncommitted changes is never auto-removed.

Exit codes: `0` success, `2` not-a-git-repo / bad arguments, `3`
`git worktree add` failed (a partial worktree is cleaned up).

---

## The collision guard

If you forget the worktree and just open a **second** `claude` in a
directory that already has an active session, Sage's session-init hook
injects a warning at the top of the new session:

```
⚠ Another Sage session appears active in this checkout. Parallel
sessions in one directory clobber each other. For an isolated
session: sage worktree <name>
```

How it knows, briefly: each session's hook writes a small
`.sage/.session-lock` recording the hook's parent process id (`$PPID`,
which is the Claude session process) and the checkout path. A new
session warns only if the lock belongs to a **different, still-running**
process (`kill -0`) in the **same** checkout. A lock from an exited
session is ignored (a 6-hour staleness backstop covers a recycled pid).
The lock is always gitignored and never blocks anything — the guard
only *warns*. In a non-git project the guard is skipped entirely.

The warning is a Claude Code feature (a `SessionStart` hook). On other
platforms you get the config switch and the launcher but not the
injected warning.

---

## The two `.sage/` worlds

Whether the launcher copies anything into the new worktree depends on
whether your `.sage/` (and platform runtime) are **tracked by git** or
**gitignored**.

**Tracked `.sage/`** (you commit `.sage/`). The worktree gets
everything through git automatically — `.sage/`, `.claude/`, `CLAUDE.md`
are all present in the new checkout. The launcher copies **nothing**.

**Gitignored `.sage/`** (common — e.g. Sage's own repo ignores
`.sage/`, `.claude/`, and `CLAUDE.md`). Those files don't travel with a
checkout, so a fresh worktree would be empty of them. The launcher
copies them in — the shared runtime (`.sage/config.yaml`,
`.sage/constitution.md`, `.sage/gates/`), the multi-agent runtime if
present (`.sage/agents.toml`, `.sage/prompts/`, `.sage/scripts/` — only
after `sage setup multi-agent`), plus the platform directory and
instructions file for the platforms in your `platforms:` config
(`.claude/` + `CLAUDE.md` for Claude Code, etc.). Per-initiative state
under `.sage/work/` is **not** bulk-copied — a fresh worktree starts a
fresh initiative.

Two details worth knowing:

- **Real copies, never symlinks.** The copy is `cp -R`. This is
  deliberate: on WSL with the repo on a Windows drive (`/mnt/...`,
  drvfs), POSIX symlinks fail, so a symlinked runtime wouldn't work
  there. Plain copies always do.
- **Copies don't auto-sync.** If you later edit a skill or command in
  the main checkout, a long-lived worktree's copy goes stale. Treat
  worktrees as **short-lived** — create one per task, remove it after
  merge, re-create next time. (When `.sage/` is tracked this is a
  non-issue; git carries updates.)

---

## Per-initiative state, so parallel branches don't collide

Two parallel branches both appending to one shared file is a guaranteed
merge conflict. So checkpoint decisions go to the **initiative's** log,
`.sage/work/<slug>/decisions.md`, not the global `.sage/decisions.md`
(which is reserved for cross-initiative decisions like constitution
choices). Readers check the initiative log first and fall back to the
global one, so older projects and in-flight initiatives keep working.

This is why two worktrees on two branches can run at once without their
bookkeeping fighting: each writes to its own work directory.

---

## A typical parallel day

```bash
# In your main checkout, on main / your default branch.

# Bug came in — spin up an isolated session for it:
sage worktree login-timeout --prefix fix
cd ../myapp-login-timeout && claude
#   → in that session: /fix, work the bug, [M] Merge when green.

# Meanwhile, in another terminal, start the feature you were planning:
sage worktree saved-views
cd ../myapp-saved-views && claude
#   → in that session: /build, spec → plan → implement, [M] when done.

# The two sessions never touch the same files — separate directories.
# Merge each from its own worktree when ready (always user-gated).

# Clean up after merging:
git worktree remove ../myapp-login-timeout
git worktree remove ../myapp-saved-views
sage worktree prune     # tidy bookkeeping
```

---

## Merging and cleanup

Merging is always **your** action. At a workflow's completion
checkpoint, `[M] Merge to <default>` runs the protocol: the test suite
(gated on its own exit code), a clean working tree, a non-empty branch,
`--no-ff`. Conflicts stop and hand control back to you. Nothing pushes
or opens a PR automatically.

After a merge, Sage **offers** branch deletion (never performs it), and
only at initiative completion — so a multi-milestone `/architect` run
keeps its branch across milestones.

For the worktree directory itself, remove it when you're done:

```bash
git worktree remove ../myapp-saved-views   # refuses if there are uncommitted changes
sage worktree prune                        # clears bookkeeping for any you rm'd manually
```

---

## Troubleshooting

**"I ran two `claude` in the same folder and they conflicted."**
That's the one thing not to do. Use `sage worktree <slug>` for the
second task. The collision guard warns you, but it can't stop you, and
it can't move a running session.

**The warning didn't appear.** It's a Claude Code `SessionStart` hook —
it only fires on Claude Code, and only in a git project. A session that
exited without firing leaves a stale lock that's ignored after 6 hours,
so a much-later second session might not warn; that degrades to today's
behavior (no false blocks).

**`sage worktree` says "Not a git repository."** Worktrees need git.
Run `git init` (and at least one commit) first, or work without
isolation.

**The new worktree has no `/build` command / no `CLAUDE.md`.** Your
`.sage/`/`.claude/` are gitignored *and* the copy didn't include your
platform. Re-run with the platform listed in `.sage/config.yaml`'s
`platforms:`, or run `sage update` inside the worktree to regenerate
the platform files there.

**A worktree's skills/commands are out of date.** Copies don't
auto-sync. Remove and re-create the worktree, or (tracked `.sage/`)
pull the latest. Keep worktrees short-lived.

**On WSL, copies into `/mnt/...` are slow but work; symlinks fail.**
Expected — the launcher uses `cp -R` precisely so it works on drvfs.
For best performance, keep repos on the native Linux filesystem
(`~/...`) when you can.

---

## How it fits the rest of Sage

- **Single source of truth.** Naming, the user-gated merge protocol,
  worktrees, and cleanup are all defined once in
  `core/capabilities/execution/git-discipline/SKILL.md`; the workflows
  cite it.
- **Degrades silently without git.** Every behavior is gated on
  `git rev-parse --git-dir`.
- **Opt-in for parallelism.** `isolation: branch` (the default) leaves
  sequential work untouched; `isolation: worktree` turns on the bounce.
- **Works with multi-agent.** A `/build-x` cycle branches at Phase 1
  and gates its merge the same way; when `.sage/` is gitignored,
  `sage worktree` also copies the multi-agent runtime
  (`.sage/agents.toml`, `.sage/prompts/`, `.sage/scripts/`) into the
  worktree so the dispatcher works there — present only if you've run
  `sage setup multi-agent`.
