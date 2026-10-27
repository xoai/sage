#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Sage Session Init Hook for Claude Code
# Fires on: startup, resume, clear, compact
# ONE source: the plugin ships this file byte-identical (build_plugin.py
# FILE_MAP). It used to keep a hand-edited copy that lost the collision
# guard and the worktree notices.
# Reads .sage/ artifacts and outputs structured context
# Zero dependencies — bash only
# ═══════════════════════════════════════════════════════════════

SAGE_DIR=".sage"

# ── Linked worktree? (a Claude Desktop session, `claude --worktree`, `sage
# worktree`). Computed once; the notices below use it.
GD=""; GCD=""; MAIN_ROOT=""
if git rev-parse --git-dir >/dev/null 2>&1; then
  GD=$(cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd)
  GCD=$(cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd)
  if [ -n "$GD" ] && [ -n "$GCD" ] && [ "$GD" != "$GCD" ]; then
    # Main checkout root = the first worktree git lists (canonical; matches what
    # `sage worktree` uses). Fall back to the parent of the common git dir.
    MAIN_ROOT=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')
    [ -n "$MAIN_ROOT" ] || MAIN_ROOT=$(dirname "$GCD")
  fi
fi

# A worktree of a Sage project that has no Sage config of its own: the
# project gitignores .sage/ and nothing copied it in. The gates fall back to
# the main checkout's .sage/ — its config and cycles — and never see this
# worktree's branch, HEAD or cycles. Say so instead of staying silent.
MAIN_PROJECT=""
[ -n "$MAIN_ROOT" ] && MAIN_PROJECT="$MAIN_ROOT/$(git rev-parse --show-prefix 2>/dev/null)"
MAIN_PROJECT="${MAIN_PROJECT%/}"
# The gates fall back to the SESSION's project (CLAUDE_PROJECT_DIR): the main
# checkout in a Desktop worktree session, but the worktree itself when the
# session was started inside it (`cd <worktree> && claude`).
real_dir() { (cd "$1" 2>/dev/null && pwd -P); }
FROM_MAIN=""
if [ -n "$MAIN_PROJECT" ] && [ "$(real_dir "${CLAUDE_PROJECT_DIR:-$PWD}")" = "$(real_dir "$MAIN_PROJECT")" ]; then
  FROM_MAIN=1
fi
if [ ! -f "$SAGE_DIR/config.yaml" ] && [ -n "$MAIN_PROJECT" ] && [ -d "$MAIN_PROJECT/.sage" ] \
    && [ -z "$FROM_MAIN" ]; then
  echo "Sage: this worktree has no .sage/config.yaml, and the session was started in it,"
  echo "so Sage's gates treat it as no Sage project at all. Tell the user: start the"
  echo "session from the main checkout ($MAIN_PROJECT), or run \`sage update\` there"
  echo "and make a new worktree — it will carry Sage's files (.worktreeinclude)."
  exit 0
fi
if [ ! -f "$SAGE_DIR/config.yaml" ] && [ -n "$MAIN_PROJECT" ] && [ -d "$MAIN_PROJECT/.sage" ]; then
  echo "Sage: this worktree has no .sage/config.yaml of its own (the project gitignores"
  echo ".sage/ and it was not copied in). Sage's gates judge work here from the main"
  echo "checkout ($MAIN_PROJECT): its config and cycles apply, but this worktree's branch,"
  echo "commits and cycles are not seen. Tell the user: run \`sage update\` in the main"
  echo "checkout — it writes .worktreeinclude, so worktrees made after that carry Sage."
  exit 0
fi

# ── Not initialized? Say so — do not exit silently. ──
#
# The plugin ships the commands, the skills and the hooks. It does NOT ship the
# framework's capabilities: /build reads sage/core/capabilities/orchestration/
# build-loop/SKILL.md, /architect reads deep-elicit, /sage reads the navigator —
# and that tree is created by `sage init`, not by installing the plugin.
#
# Installing the plugin alone therefore produces a workflow that references files
# which are not there. Found by smoking the marketplace install: the agent read
# /sage, went looking for the navigator, could not find it, and said so mid-answer.
# It coped — but a user who has just installed a plugin should be told what to do,
# not watch the agent discover the gap.
#
# This output is context for the model, not a banner for the user: it only surfaces
# if they actually reach for a Sage workflow.
if [ ! -d "$SAGE_DIR" ] && [ ! -d "sage" ]; then
  echo "Sage: the plugin is installed, but this project is NOT initialized."
  echo "The plugin provides the commands and the hooks. The workflows read the"
  echo "framework's capabilities from the project's vendored sage/ tree, which does"
  echo "not exist here — so /sage, /build, /fix and /architect will reference files"
  echo "that are missing."
  echo ""
  echo "If the user reaches for a Sage workflow, tell them to run \`sage init\` first."
  echo "The plugin bundles the CLI at scripts/sage; install.sh puts it on PATH."
  exit 0
fi

# Initialized state directory exists but the framework does not — a half-installed
# project (someone removed sage/, or an init that did not finish).
if [ -d "$SAGE_DIR" ] && [ ! -d "sage" ]; then
  echo "Sage: .sage/ exists but the vendored sage/ framework is missing."
  echo "Workflows will reference capabilities that are not on disk. Run \`sage update\`."
  echo ""
fi

# Exit silently if no Sage project
[ -d "$SAGE_DIR" ] || exit 0

# ── Parallel-session collision guard ─────────────────────────────
# Warns (never blocks) when a second Sage session is active in the
# SAME checkout — two sessions in one working tree clobber each other.
# Liveness is grounded on $PPID (the hook's parent = the Claude
# session process), checked with `kill -0`; no undocumented stdin
# contract. Git-gated: skipped entirely in a non-git project so a
# missing `git rev-parse --show-toplevel` never yields a false
# collision. A dead/stale lock only suppresses a warning, never blocks.
COLLISION_WARNING=""
if git rev-parse --git-dir >/dev/null 2>&1; then
  LOCK="$SAGE_DIR/.session-lock"
  TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null)
  STALE_SECONDS=21600   # 6h backstop for a recycled pid

  # Keep the lock out of git: if .sage/ is not wholesale-ignored,
  # ensure .sage/.gitignore covers .session-lock.
  if ! git check-ignore -q "$LOCK" 2>/dev/null; then
    GI="$SAGE_DIR/.gitignore"
    if [ ! -f "$GI" ] || ! grep -qx ".session-lock" "$GI" 2>/dev/null; then
      # Add a trailing newline first if the file ends without one, so
      # the append never concatenates onto the user's last rule.
      if [ -s "$GI" ] && [ -n "$(tail -c1 "$GI" 2>/dev/null)" ]; then echo "" >> "$GI"; fi
      echo ".session-lock" >> "$GI"
    fi
  fi

  if [ -f "$LOCK" ]; then
    L_PID=$(sed -n 's/^pid=//p' "$LOCK" 2>/dev/null)
    L_TOP=$(sed -n 's/^toplevel=//p' "$LOCK" 2>/dev/null)
    L_UPD=$(sed -n 's/^updated_at=//p' "$LOCK" 2>/dev/null)
    NOW=$(date +%s 2>/dev/null)
    # Liveness: alive if `kill -0` exits 0 (running) OR fails with
    # EPERM (running, owned by another user). Only ESRCH = dead.
    alive=0
    if [ -n "$L_PID" ]; then
      if kill -0 "$L_PID" 2>/dev/null; then
        alive=1
      else
        # Distinguish EPERM (alive, foreign user) from ESRCH (dead).
        # Force C locale so the EPERM string is stable across locales.
        if LC_ALL=C kill -0 "$L_PID" 2>&1 | grep -qi "permitted"; then alive=1; fi
      fi
    fi
    # Staleness backstop: a too-old lock is treated as dead.
    if [ -n "$L_UPD" ] && [ -n "$NOW" ] && [ $((NOW - L_UPD)) -gt "$STALE_SECONDS" ]; then alive=0; fi

    if [ "$alive" = "1" ] && [ "$L_PID" != "$PPID" ] && [ "$L_TOP" = "$TOPLEVEL" ]; then
      COLLISION_WARNING="⚠ Another Sage session appears active in this checkout. Parallel sessions in one directory clobber each other. For an isolated session: sage worktree <name>"
    fi
  fi

  # Claim/refresh the lock for this session.
  {
    echo "pid=$PPID"
    echo "toplevel=$TOPLEVEL"
    echo "updated_at=$(date +%s 2>/dev/null)"
  } > "$LOCK" 2>/dev/null || true
fi

# ── Worktree memory directive ─────────────────────────────────────
# In a linked worktree, sage-memory defaults its project database to the
# session's working directory — an empty store separate from the main
# checkout. The DB is a single shared store, not a per-worktree copy (a
# SQLite file cannot be merged, so it is never copied in or harvested
# back). Point this session at the main checkout's store with
# set_project so reads and writes land in the one shared brain.
WORKTREE_MEMORY=""
WORKTREE_RECORDS=""
WORKTREE_CONFIG=""
# The policy lines of a Sage config — the gates' resolver (sage_worktree_root)
# compares exactly these: no blank lines, comments or sage-version.
sage_policy() {
  grep -v '^[[:space:]]*#' "$1" 2>/dev/null | grep -v '^[[:space:]]*$' \
    | grep -v '^sage-version:' | sed 's/[[:space:]]*$//'
}
if [ -n "$FROM_MAIN" ] && [ -f "$SAGE_DIR/config.yaml" ] && [ -f "$MAIN_PROJECT/.sage/config.yaml" ] \
    && [ "$(sage_policy "$SAGE_DIR/config.yaml")" != "$(sage_policy "$MAIN_PROJECT/.sage/config.yaml")" ]; then
  WORKTREE_CONFIG="Config (worktree): this worktree's .sage/config.yaml says something different from the main checkout's (${MAIN_PROJECT}), so Sage's gates judge work here from the main checkout — its config and cycles — and do not see this worktree's branch, commits or cycles. Tell the user if that matters; a worktree made after the configs agree is judged on its own."
fi
if [ -n "$MAIN_ROOT" ]; then
  # Emit the bare path (the agent quotes it) — never a pre-quoted literal, which
  # would break on a path containing an apostrophe.
  WORKTREE_MEMORY="Memory (worktree): before any other sage_memory tool, call sage_memory_set_project with this MAIN checkout root as the path: ${MAIN_ROOT} — so reads and writes share the main checkout's store. This worktree's own .sage-memory is empty and disposable; never copy or harvest it."
  # Cycle records in a gitignored .sage/work die with the worktree; close-out
  # mirrors them to the main checkout (manifest.py mirror_to_main).
  if git check-ignore -q "$SAGE_DIR/work/x/manifest.md" 2>/dev/null; then
    WT_TOP=$(git rev-parse --show-toplevel 2>/dev/null)
    WT_PREFIX=$(git rev-parse --show-prefix 2>/dev/null)
    WORKTREE_RECORDS="Records (worktree): .sage/work/ is gitignored here, so it is not carried by git and is deleted with this worktree. Every manifest.py close-out copies the cycle to ${MAIN_ROOT}/${WT_PREFIX}.sage/worktree-records/$(basename "$WT_TOP")/ — record state through close-out, not by hand."
  fi
fi

# ── Desktop mode ──────────────────────────────────────────────────
# Claude Desktop's Code tab has question buttons, a live task list and its
# own worktree and pull-request flow; Sage's text conventions (footers,
# per-task progress lines, [M] merge, a typed branch proposal) map onto them.
# desktop_mode in .sage/config.yaml: auto (default — on when the app is the
# host: CLAUDE_CODE_ENTRYPOINT=claude-desktop, which Claude Code sets but does
# not document, hence the knob), on, or off.
DESKTOP_MODE=""
DM=$(sed -n 's/^desktop_mode:[[:space:]]*//p' "$SAGE_DIR/config.yaml" 2>/dev/null | head -1 \
       | tr -d '\r' | sed "s/[[:space:]]*#.*//; s/[\"']//g; s/[[:space:]]*\$//" | tr 'A-Z' 'a-z')
case "$DM" in
  on|true|yes) DESKTOP_MODE=1 ;;
  off|false|no) ;;
  *) [ "${CLAUDE_CODE_ENTRYPOINT:-}" = "claude-desktop" ] && DESKTOP_MODE=1 ;;
esac
# A worktree session on its own (non-default) branch keeps it; the default
# branch is resolved as the branch gate resolves it.
DESKTOP_BRANCH=""
if [ -n "$DESKTOP_MODE" ] && [ -n "$MAIN_ROOT" ]; then
  DESKTOP_BRANCH=$(git symbolic-ref --quiet --short HEAD 2>/dev/null)
  DEFAULT_BRANCH=$(sed -n 's/^default_branch:[[:space:]]*"\{0,1\}\([^"#[:space:]]*\).*/\1/p' "$SAGE_DIR/config.yaml" 2>/dev/null | head -1)
  if [ -z "$DEFAULT_BRANCH" ]; then
    for cand in "$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/origin/||')" \
                "$(git config --get init.defaultBranch 2>/dev/null)" main master; do
      if [ -n "$cand" ] && git show-ref --verify --quiet "refs/heads/$cand" 2>/dev/null; then
        DEFAULT_BRANCH="$cand"; break
      fi
    done
  fi
  [ -n "$DEFAULT_BRANCH" ] && [ "$DESKTOP_BRANCH" = "$DEFAULT_BRANCH" ] && DESKTOP_BRANCH=""
fi

# ── Scan active work via frontmatter ──
ACTIVE_WORK=""
WORK_COUNT=0
IN_PROGRESS=""
for dir in "$SAGE_DIR"/work/*/; do
  [ -d "$dir" ] || continue
  for artifact in "plan.md" "spec.md" "brief.md"; do
    f="$dir$artifact"
    [ -f "$f" ] || continue

    title=$(sed -n '/^---$/,/^---$/{ /^title:/s/^title: *"*\([^"]*\)"*/\1/p; }' "$f" 2>/dev/null)
    status=$(sed -n '/^---$/,/^---$/{ /^status:/s/^status: *//p; }' "$f" 2>/dev/null)
    phase=$(sed -n '/^---$/,/^---$/{ /^phase:/s/^phase: *//p; }' "$f" 2>/dev/null)

    [ -z "$title" ] && title=$(basename "$dir" | sed 's|/$||')
    [ -z "$status" ] && status="unknown"

    ACTIVE_WORK="$ACTIVE_WORK  - $title [$status, $phase] — $f\n"
    WORK_COUNT=$((WORK_COUNT + 1))
    [ "$status" = "in-progress" ] && IN_PROGRESS="$title"
    break
  done
done

# ── Scan docs ──
DOC_COUNT=0
for doc in "$SAGE_DIR"/docs/*.md; do
  [ -f "$doc" ] || continue
  DOC_COUNT=$((DOC_COUNT + 1))
done

# ── Read recent decisions ──
RECENT_DECISIONS=""
if [ -f "$SAGE_DIR/decisions.md" ]; then
  RECENT_DECISIONS=$(grep "^### " "$SAGE_DIR/decisions.md" 2>/dev/null | tail -3)
fi

# ── Output structured context ──
echo ""
echo "## Sage Context (auto-injected)"
echo ""

if [ -n "$COLLISION_WARNING" ]; then
  echo "$COLLISION_WARNING"
  echo ""
fi

if [ -n "$WORKTREE_MEMORY" ]; then
  echo "$WORKTREE_MEMORY"
  echo ""
fi

if [ -n "$WORKTREE_RECORDS" ]; then
  echo "$WORKTREE_RECORDS"
  echo ""
fi

if [ -n "$WORKTREE_CONFIG" ]; then
  echo "$WORKTREE_CONFIG"
  echo ""
fi

if [ "$WORK_COUNT" -gt 0 ]; then
  if [ -n "$IN_PROGRESS" ]; then
    echo "Sage: $IN_PROGRESS is in progress."
  fi
  echo ""
  echo "Active work ($WORK_COUNT):"
  printf "$ACTIVE_WORK"
else
  echo "Sage: No active work. Ready for a new task."
fi

if [ "$DOC_COUNT" -gt 0 ]; then
  echo "Project docs: $DOC_COUNT files in .sage/docs/"
fi

if [ -n "$RECENT_DECISIONS" ]; then
  echo ""
  echo "Recent decisions:"
  echo "$RECENT_DECISIONS"
fi

if [ -n "$DESKTOP_MODE" ]; then
  echo ""
  echo "Desktop mode (Claude Desktop's Code tab; desktop_mode in .sage/config.yaml):"
  echo "- Checkpoints: show the work, then ask with the AskUserQuestion tool — the"
  echo "  zone's options as buttons — instead of printing the footer; that question"
  echo "  is the turn's question. Still a hard wait. Zone by zone, and menus of more"
  echo "  than four options: sage/core/system-skills/sage-checkpoints/references/desktop-mode.md"
  echo "- Progress: keep the plan's tasks in your task list as you work; plan.md"
  echo "  checkboxes stay the record. No per-task progress lines in chat."
  if [ -n "$DESKTOP_BRANCH" ]; then
    echo "- Branch: this session's worktree is on $DESKTOP_BRANCH. Use it for the"
    echo "  initiative — propose no other (/autoresearch keeps its own branch rules) —"
    echo "  and record it: python3 sage/runtime/tools/manifest.py close-out <manifest>"
    echo "  --branch $DESKTOP_BRANCH (git-discipline: \"Worktree sessions\"). At completion"
    echo "  offer no [M] merge: the branch is merged from the main checkout or through"
    echo "  a pull request — the user's call."
  else
    echo "- Branch: when git-discipline asks a branch question — create, rename,"
    echo "  continue, or decline — ask it as buttons."
  fi
fi

echo ""
echo "Use /sage, /build, /fix, /architect, /status, /review, or /learn."
echo ""
