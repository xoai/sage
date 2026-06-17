---
name: git-discipline
description: >
  Branch-per-initiative git discipline for all delivery workflows.
  Defines branch naming by workflow, the propose-confirm creation
  protocol, dirty-tree and detached-HEAD handling, the always
  user-gated merge protocol, worktree support for parallel sessions,
  and abandonment cleanup. Activates only in git repositories —
  silently inactive everywhere else. Use when starting /build, /fix,
  /architect, or /build-x at Standard+ scope, when resuming an
  initiative, when offering a merge at a completion checkpoint, or
  when the user wants a second concurrent initiative.
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: haiku
activation: auto
tags: [git, branching, worktree, merge, discipline, parallel-sessions]
inputs: [initiative-slug, workflow-mode]
outputs: [initiative-branch, manifest-branch-record]
-->

# Git Discipline

One branch per initiative. Merge only when the user says so.

This capability is the **single source of truth** for branch naming,
creation, merging, worktrees, and cleanup. Workflows cite it — they
never restate its rules. If a workflow's text and this file disagree,
this file wins; flag the workflow as the defect.

## Branch vs worktree — the decision rule

These solve different problems; pick by how many sessions run at once:

- **Branch** isolates *history* — one initiative's commits don't
  interleave with the default branch. A branch is **sufficient for
  one session at a time** (sequential initiatives). This is the
  default (`isolation: branch` in `.sage/config.yaml`).
- **Worktree** isolates the *working tree* — its own directory on
  disk. A worktree is **required for simultaneous sessions**: two
  `claude` processes in one checkout share one working tree and one
  HEAD, so they clobber each other's files regardless of branch, and
  `git checkout -b` in one moves HEAD for the other. Branches cannot
  fix a working-tree race; only a directory-per-session can.

**The hard constraint.** A Claude session is bound to the directory
it was launched in and **cannot relocate itself** into a worktree it
creates. So the parallel path is always launch-time: create the
worktree *first*, then start a session *inside* it. The front door is
**`sage worktree <slug>`** (creates branch + worktree + copies the
gitignored runtime + prints the `cd … && claude` line). Opt in with
`isolation: worktree`; until then, sequential branch-in-place is
unchanged.

## Availability check

Activate only when `git rev-parse --git-dir` exits 0. On failure
(not a git repository): silently inactive — no error, no prompt, no
mention. Every workflow runs exactly as it would without this
capability. Never run any other `git` command before this check
passes.

## Branch naming

| Workflow | Branch |
|----------|--------|
| `/build` | `feat/<slug>` |
| `/fix` | `fix/<slug>` |
| `/architect` | `arch/<slug>` |
| `/build-x` | `feat/<slug>` or `fix/<slug>` — planner proposes from the task shape, user confirms |
| `/autoresearch` | `autoresearch/<slug>` (pre-existing discipline, unchanged by this capability) |

`<slug>` is the initiative's work-dir slug **without** the date
prefix: `.sage/work/20260612-payment-retry/` → `feat/payment-retry`.
The full dated slug remains the work-dir key. On a name collision
(the branch already exists), append `-2`, `-3`, … — and never reuse
an existing branch without the user's explicit choice (see
"Already on a branch" below).

The naming extends the project's conventional-commit convention
(feat, fix, chore, docs) to branch names.

## Worktree bounce (`isolation: worktree` in the main checkout)

Read `isolation:` from `.sage/config.yaml` (default `branch`). When
it is `worktree` AND the workflow is starting in the **main checkout**
(not a linked worktree — the test is `git rev-parse --git-dir` ==
`git rev-parse --git-common-dir`; equal → main checkout), do not
branch in place. Present a **guided menu** (never a hard refusal — a
lone sequential session must still be able to proceed):

- `[1]` **Set up an isolated worktree** (recommended for parallel) —
  run / instruct `sage worktree <slug>`; open a session in the new
  directory and continue there. This session stops here.
- `[2]` **Proceed here in the shared checkout (not isolated)** — fall
  back to the normal in-place branch flow below; record the choice in
  the initiative decision log.
- `[3]` **Sequential, this once** — same as `[2]`, noting
  `isolation: worktree` was overridden for this initiative.

When already running **in a linked worktree** (the user launched via
`sage worktree`), skip the bounce and branch/commit in place as usual
— the session is already isolated. With `isolation: branch` (default),
the bounce never fires.

## Branch creation (propose-confirm)

At the workflow step that consumes this capability, when HEAD is on
the default branch with a clean tree:

1. **Propose** the branch name from the table above.
2. **Let the user confirm or rename.** Never create silently.
3. `git checkout -b <branch>`
4. **Record the actual branch name** in the initiative's manifest
   frontmatter: `branch: feat/payment-retry`. Resume matching reads
   this recorded field — never re-derives from names (see "Branch ↔
   work-dir mapping" below).

**Dirty tree at creation time:** stop and present three options —
stash and proceed, commit current changes first (the user writes or
approves the message), or abort the workflow. Never stash silently.

**Already on a branch** (HEAD on a non-default branch): ask whether
to (a) continue on it — the user may have prepared one — or
(b) create the initiative branch from the default branch. Record the
choice in the initiative decision log.

**Detached HEAD** (tag/SHA checkout; `git worktree add` without
`-b`): surface the state, offer to create the initiative branch from
the default branch or from HEAD (`git checkout -b <branch>` works
from either) — never proceed to implementation commits while
detached.

**User declines branching:** record the decline in the initiative
decision log and proceed exactly as today (commits land on the
current branch). Declining is always available — the discipline is a
default, not a cage. A recorded decline also suppresses the
CLAUDE.md minimum branch gate for this initiative.

## Default-branch resolution

Never hardcode `main`. Resolve via this chain, stopping at the first
success:

1. `git symbolic-ref refs/remotes/origin/HEAD` (strip the
   `refs/remotes/origin/` prefix) — set by clone; absent in
   remote-less repos.
2. `git config init.defaultBranch` — only if a local branch by that
   name exists.
3. An existing local branch named `main`, then `master`.
4. **Ask the user once.**

Persist the answer as `default_branch:` in `.sage/config.yaml` so
every session — and every parallel worktree — resolves identically.
Never silently designate the currently-checked-out branch as the
default.

**Unborn HEAD** (fresh `git init`, no commits): branch creation still
works (`git checkout -b` is valid from unborn HEAD); the merge
protocol requires an existing default branch and otherwise degrades
to "commit on the current branch" with a one-line notice.

## Per-task commits

Implementation commits land on the initiative branch using
conventional-commit subjects. The workflow's existing commit cadence
is unchanged — only the branch it lands on changes.

## Merge protocol (ALWAYS user-gated)

Merging is offered **only** at a completion checkpoint as an explicit
menu option (`[M] Merge to <default>`). No workflow path executes a
merge without the user choosing that option in the same session. This
is a hard line, not a default.

Before offering `[M]`:

- **Run the full test suite and gate on its own exit code.** Capture
  the status, then act — never `suite | tail && merge` (a pipeline's
  exit status is the last command's; a piped suite reads green even
  when red). On a project with no test harness, substitute the
  initiative's documented smoke procedure; if none exists, require an
  explicit user acknowledgment that the merge is unverified.
- **Structural preconditions** — both must hold:
  - `git status --porcelain` is empty (no uncommitted work that a
    checkout would transplant onto the default branch);
  - `git rev-list <default>..<branch>` is non-empty (the branch
    actually has commits to merge).
- Show `git diff <default>...<branch> --stat`.

On user `[M]`:
```
git checkout <default>
git merge --no-ff <branch>
```

On conflict: stop, show the conflicting paths, hand control to the
user. Conflict resolution is out of scope for this capability.

After a successful merge, **offer** (never perform) branch deletion —
**suppressed while the initiative continues** (per-milestone merges):
the deletion offer fires only at initiative completion. Deleting
mid-initiative would strand later milestones on the default branch
with no re-entry into branch creation.

**No remote operations.** This capability never runs `git push`,
never creates PRs, never sets upstreams. Pushing and PRs remain the
user's own actions.

## Branch ↔ work-dir mapping: recorded, not derived

At branch creation the workflow records the **actual** branch name in
the initiative's manifest frontmatter (`branch: feat/payment-retry`).
Resume matching (session-bridge, `/continue`, workflow auto-pickup)
reads the recorded field — never re-derives from names, because the
derivation is non-bijective the moment any sanctioned exception
fires: the collision suffix (`feat/auth-2`), a user rename at the
confirm step, continue-on-existing-branch, or date-stripped slugs
that collide across months (`20260101-auth` and `20260301-auth` both
derive `feat/auth`). The naming-table derivation is only the
**default proposal** at creation time.

## Worktrees (parallel sessions)

**Front door: `sage worktree <slug>`.** When the user wants a second
concurrent initiative — or `isolation: worktree` is set — the launcher
is how a parallel session starts: it creates the branch + worktree,
copies the gitignored runtime, and prints the `cd … && claude` line to
open an isolated session. The user runs one command; the session is
born isolated. (A running session cannot relocate itself — see the
decision rule above — so this is always launch-time.)

The manual recipe below is what the launcher does, kept as
documentation and as the fallback when `sage worktree` is unavailable:

```
git worktree add ../<project>-<slug> <branch>
```

One worktree per initiative, as a sibling directory. A branch can be
checked out in only one worktree at a time; the new worktree shares
`.git` storage. If the target path already exists, offer
`../<project>-<slug>-2` or let the user supply a path — never delete
an existing directory.

**`.sage/` trackedness — two worlds, both handled.** Probe with
`git check-ignore -q .sage` (exit 0 = ignored):

- **Tracked** (`.sage/` committed): state travels with each
  worktree's checkout; the per-initiative state files prevent merge
  conflicts between branches. The offer proceeds as above.
- **Gitignored** (as in sage's own repo): state does NOT travel — a
  fresh worktree contains no `.sage/` at all. The offer still
  proceeds, with a copy step: after `git worktree add`, copy the
  shared runtime (`.sage/config.yaml`, `.sage/constitution.md`,
  `.sage/gates/`; for a `/build-x` initiative also `.sage/scripts/`,
  `.sage/prompts/`, and `.sage/agents.toml` — the multi-agent runtime,
  without which the first dispatcher invocation fails) into the new
  worktree. The seeded set is the `worktree_copy` config list (it
  deliberately does NOT seed `.sage/work/` — a fresh worktree starts a
  fresh initiative); on teardown, `sage worktree remove` harvests the
  `worktree_harvest` list (default `.sage/work/*`) back to the main
  checkout. Both lists are project-configurable in `.sage/config.yaml`.

**The platform runtime needs the same treatment.** The same
`.gitignore` that ignores `.sage/` typically also ignores `.claude/`
and the platform instructions file (`CLAUDE.md` / `AGENTS.md` /
`GEMINI.md`) — sage's own repo ignores all of them. Probe separately:
`git check-ignore -q .claude` (and the instructions file). When
ignored or absent, the worktree offer includes one of two remedies,
user's pick:

- **(a) Copy** `.claude/` and the platform instructions file(s) into
  the worktree alongside the `.sage/` state; or
- **(b) Run `sage update` inside the new worktree** — the platform
  generators regenerate the instructions file and commands; this
  works even when `sage/` itself is absent in the worktree (the CLI
  falls back to the global framework install).

A worktree session without a platform runtime is an inert checkout —
no slash commands, no skills, not even the degraded CLAUDE.md gates.
**The offer must not complete without one of the two remedies.**

**The MCP config and the memory store.** `.mcp.json` is in the default
`worktree_copy` set, so the sage-memory (and other) MCP servers are
configured in the worktree. The memory **database** is different from the
rest of `.sage/`: it is a single shared store, **not** a per-worktree copy.
A SQLite file cannot be merged, so `.sage-memory/` is never seeded into a
worktree and never harvested back. Instead the worktree session points at
the main checkout's store by calling `sage_memory_set_project(<main root>)`
(`dirname "$(git rev-parse --git-common-dir)"`); the session-init hook
surfaces that call automatically when it detects a linked worktree. Result:
one brain, shared by main and every worktree — nothing to reconcile.

**Ownership record.** Record `owner: <worktree-path>` in the **main
checkout's** copy of the initiative manifest (recording in both
copies is acceptable; the main checkout's copy is the one exclusion
reads). Resume surfaces in the original checkout exclude initiatives
owned elsewhere. The comparison probe is
`git rev-parse --show-toplevel` against the recorded `owner:` after
path normalization — trailing slashes and symlinked paths (WSL
mounts alias the same checkout) must not defeat the comparison.

**Ownership return.** When the worktree is removed, always copy back
the work dir **before** the manifest edit that clears `owner:` —
editing first and copying back after re-imports the stale `owner:`
from the worktree copy and permanently locks the initiative out of
every resume surface.

**Cleanup after merge:** `sage worktree remove <slug|dir>` — offered,
user-gated, never automatic. It harvests the gitignored `.sage/work/<slug>/`
back into the main checkout, then removes the worktree (refusing on dirty
*tracked* files unless `--force`). Prefer it over bare `git worktree remove`,
which skips the harvest and silently drops the docs (see Abandonment cleanup).

## Abandonment cleanup

Closing an initiative without merging offers — never performs — the
cleanup pair: `sage worktree remove <slug|dir>` (if a worktree exists)
and branch deletion.

**Ignored-world ordering is mandatory.** When `.sage/` is gitignored,
a bare `git worktree remove` silently deletes the worktree's untracked
`.sage/` state with it — the brief/spec/plan are gone, never merged
(untracked) and never recoverable via git (gitignored files never enter
the object store). `sage worktree remove` exists to prevent exactly this:
it harvests `.sage/work/<slug>/` back into the main checkout **before**
removing the worktree. The abandonment sequence is therefore:

1. `sage worktree remove <slug|dir>` — harvests the work dir back, then
   removes the worktree.
2. In the **main checkout's** harvested manifest, clear `owner:` and write
   `status: abandoned` — after the harvest, never before (see Ownership
   return).

In the tracked world, the harvest is unnecessary (git carries `.sage/`) and
step 2 collapses to a manifest edit + commit on the initiative branch.
Declining the cleanup leaves the branch for later; `status: abandoned` is
recorded either way so resume surfaces stop offering the initiative.

## What this capability never does

- Merge, push, or delete anything without an explicit user menu
  action in the same session.
- Create a branch silently.
- Stash silently.
- Run any `git` command before the availability check passes.
- Touch `/autoresearch`'s pre-existing branch discipline.
