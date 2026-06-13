#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Sage Session Init Hook for Claude Code
# Fires on: startup, resume, clear, compact
# Reads .sage/ artifacts and outputs structured context
# Zero dependencies — bash only
# ═══════════════════════════════════════════════════════════════

SAGE_DIR=".sage"

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

echo ""
echo "Use /sage, /build, /fix, /architect, /status, /review, or /learn."
echo ""
