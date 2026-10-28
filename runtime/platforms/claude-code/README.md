# Sage on Claude Code

Setup guide for using Sage with Claude Code.

## Quick Setup

```bash
sage init
# Select Claude Code when prompted (or auto-detected)
```

Or run the Claude Code generator directly:

```bash
bash sage/runtime/platforms/claude-code/setup/generate-claude-code.sh .
```

## What Gets Generated

```
your-project/
├── CLAUDE.md                    # Always-on project instructions
├── .worktreeinclude             # Sage's gitignored files, copied into new worktrees
├── .claude/
│   └── commands/                # Slash commands
│       ├── sage.md              # /sage — intelligent entry point
│       ├── build.md             # /build — feature development
│       ├── fix.md               # /fix — debug and patch
│       ├── architect.md         # /architect — system design
│       └── status.md            # /status — project state
├── .sage/                       # Project state (platform-agnostic)
│   ├── decisions.md          # Shared decision log
│   ├── docs/
│   └── work/
└── sage/                        # Framework source
```

## How It Works

### CLAUDE.md = Process Constitution + Navigator

CLAUDE.md is always-on — Claude Code reads it at the start of every
session. It contains:

- The five non-negotiable process rules (state first, skills before
  assumptions, use Sage's planning, checkpoints are sacred, save state)
- Instructions to activate the sage-navigator for substantial tasks
- The build loop with checkpoint markers
- Available commands reference
- Interaction patterns (numbered options, `[A]/[R]`, `[C]`)

### Commands = Slash Shortcuts

Type `/` in Claude Code to see available commands:

| Command | What Happens |
|---------|-------------|
| `/sage` | **Start here.** Navigator reads state, assesses intent, guides process |
| `/build` | Feature development with scope assessment and checkpoints |
| `/fix` | Debug → test → fix → verify |
| `/architect` | Deep elicitation → architecture → milestone plan |
| `/status` | Show current project state |

Commands are markdown files in `.claude/commands/`. They provide the
prompt context for each workflow.

### Skills = On-Demand Knowledge

Sage skills live in `sage/skills/`. When the navigator or a
command references a skill, the agent reads its SKILL.md and follows
the methodology. Skills aren't auto-loaded — they're read on demand
when referenced. This keeps context clean.

### Project State

All Sage state lives in `.sage/` — platform-agnostic:

- `.sage/decisions.md` — shared decision log (agent + human)
- `.sage/docs/` — analyses, voice & tone guides, decision records
- `.sage/work/` — specs, plans, briefs per initiative

## Switching Between Platforms

Sage supports both Claude Code and Antigravity from the same project:

```bash
sage init
# Choose "Both" when prompted
```

This creates CLAUDE.md + `.claude/` (for Claude Code) and GEMINI.md +
`.agent/` (for Antigravity) side by side. The `.sage/` state is shared.

## Updating

```bash
sage update
```

Regenerates CLAUDE.md and `.claude/commands/` without touching `.sage/`.

### Your own files are kept

- **CLAUDE.md** — Sage's instructions live in one block between
  `<!-- BEGIN SAGE … -->` and `<!-- END SAGE -->`; `sage update` rewrites only
  that block. Anything outside it is yours and is kept — a CLAUDE.md you had
  before `sage init` stays line for line, with the block added at the end. A
  CLAUDE.md written by an older Sage (no markers) is backed up once to
  `.sage/backups/` when it moves into the block. If the markers get damaged,
  the file is left alone and the update says how to fix it. A symlinked
  CLAUDE.md stays a symlink.
- **`.claude/settings.local.json`** and **`.claude/settings.json`** — merged,
  never replaced: Sage adds or refreshes its own hook entries and leaves your
  permissions and other settings alone. A file that is not valid JSON is left
  untouched (the update reports it).
- **`.claude/skills/`** — one loader per Sage skill. Skills written for another
  platform (the Hermes port) are not deployed here, and no skill is named
  `sage`, so `/sage` always reaches the command. Your own skills in this folder
  are never touched.

### How a gate says no

From Claude Code, a gate that blocks returns Claude Code's structured deny:
the model gets the gate's reason alone, not the hook's command line that made
a correct block read like a script failing. (Claude Code itself still labels
any hook block "PreToolUse:<Tool> hook error" — see
`docs/attestations/claude-code-structured-deny-2026-10-27.md`.)

A shell command that writes a source file (`>`, `tee`, an in-place `sed`,
`cp`/`mv`, `git checkout -- <file>`, …) is judged by the same gates as the
edit it is (`sage-bash-write-gate.sh`). It reads the command, not what a
script or interpreter does at run time — `python3 gen.py` writing a file is
not seen. While a Standard+ cycle is in progress, source edits on the default
branch are blocked until the initiative branch exists — proposed to the user
and created once they confirm it (`sage-branch-gate.sh`; `branch_gate: false` opts out, and a user's decline
recorded with `manifest.py close-out --branch declined` exempts that cycle).

### Plugin and `sage init` together

`sage init` / `sage update` ask two questions about the Sage plugin
(`sage@sage`). The committed `.claude/settings.json` follows the project's
own setting alone — one person's settings never reshape the team's file:

- **Enabled in the project's `.claude/settings.json`** — every teammate gets
  the plugin, so Sage registers only the hooks the plugin does not ship
  (today, the scope gate and its journal) and removes the rest it registered
  before. No gate fires twice. If your own settings turn the plugin off,
  Sage says so: most gates would not run for you.
- **Enabled only for you** (`.claude/settings.local.json` or your user
  settings) — teammates without the plugin still need the committed hooks,
  so Sage keeps them and says that, for you, gates run twice. Enable the
  plugin at the project level to avoid it.
- **Not enabled** — Sage registers everything, as before.

Session hooks in your `settings.local.json` are dropped whenever the plugin
is on (the plugin starts the session). The vendored `sage/` is still written:
the plugin's skills read it. The check runs at `sage init` / `sage update`
only — after turning the plugin on or off, run `sage update` again.

### Worktree sessions (Claude Desktop, `claude --worktree`)

Claude Desktop runs each Code session in its own git worktree, under
`.claude/worktrees/`, on a branch the app names; `claude --worktree` does the
same from the CLI. Sage's gates judge the worktree being edited — its branch,
its cycles, its HEAD — not the main checkout, where `CLAUDE_PROJECT_DIR`
points. They do that for a registered worktree whose `.sage/config.yaml`
says what the main checkout's says (comments, blank lines and `sage-version`
aside); any other worktree is judged from the main checkout — its config and
cycles — and the session says so at start. A worktree is a separate
initiative: its own cycles apply there, not the main checkout's.

- **Tracked `.sage/`** travels with git; nothing to do.
- **Gitignored `.sage/`** — `sage init` / `sage update` write a marked Sage
  block into `.worktreeinclude`, which Claude Code reads to copy gitignored
  files into each new worktree: `CLAUDE.md`, a vendored `sage/`, and the
  `worktree_copy` paths from `.sage/config.yaml`. A worktree made before that
  is judged from the main checkout's `.sage/` — its config and cycles — and
  its own branch and commits are not seen; the session says so at start.
- **The switch stays protected across worktrees.** While enforcement is on in
  any checkout, the agent cannot loosen any checkout's `.sage/config.yaml`,
  and cannot create one: a worktree's config comes from `.worktreeinclude` or
  `sage worktree`, never from the agent. While a cycle is in progress, the
  agent cannot `git worktree add` either — a new worktree would start outside
  that cycle; Desktop's own session worktrees and `sage worktree` are not
  affected.
- **Cycle records** in a gitignored `.sage/work/` would die with the worktree
  (the app removes it, not `sage worktree remove`). Every `manifest.py
  close-out` there copies the cycle to the main checkout's
  `.sage/worktree-records/<worktree>/` — an archive no gate reads, so a
  worktree's open cycle never governs the main checkout.

### Desktop mode

Inside Claude Desktop's Code tab, Sage's text conventions map onto the
app: each checkpoint is asked with question buttons instead of an
`[A] [R] [N]` footer (the work is still shown first, and it is still a hard
wait); progress goes to the session's task list instead of per-task lines
in chat; branch questions are buttons too, and a worktree session keeps
the branch it runs on. The session hook switches this on when Claude Code
reports the Desktop app as its host; `desktop_mode: on|off|auto` in
`.sage/config.yaml` overrides it (`docs/configuration.md`). Verified live in
a Desktop worktree session:
`docs/attestations/claude-code-desktop-worktree-session-2026-10-27.md`.

Independently of Desktop mode, a session working in a worktree never
offers `[M]` merge — `git checkout <default>` fails there; the branch is
merged from the main checkout or through a pull request, the user's call.
