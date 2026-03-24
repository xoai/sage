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
