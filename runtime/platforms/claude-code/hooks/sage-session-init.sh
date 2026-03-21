#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Sage Session Init Hook for Claude Code
# Fires on: startup, resume, clear, compact
# Reads .sage/ state and outputs structured context for the agent
# Zero dependencies — bash only
# ═══════════════════════════════════════════════════════════════

SAGE_DIR=".sage"

# Exit silently if no Sage project
[ -d "$SAGE_DIR" ] || exit 0

# ── Read progress ──
STATUS="idle"
FEATURE="none"
PHASE="ready"
NEXT=""
if [ -f "$SAGE_DIR/progress.md" ]; then
  STATUS=$(grep "^Mode:" "$SAGE_DIR/progress.md" 2>/dev/null | head -1 | sed 's/^Mode: *//')
  FEATURE=$(grep "^Feature:" "$SAGE_DIR/progress.md" 2>/dev/null | head -1 | sed 's/^Feature: *//')
  PHASE=$(grep "^Phase:" "$SAGE_DIR/progress.md" 2>/dev/null | head -1 | sed 's/^Phase: *//')
  NEXT=$(grep "^Next:" "$SAGE_DIR/progress.md" 2>/dev/null | head -1 | sed 's/^Next: *//')
fi

# ── Scan active work via frontmatter ──
ACTIVE_WORK=""
WORK_COUNT=0
for dir in "$SAGE_DIR"/work/*/; do
  [ -d "$dir" ] || continue
  # Find the most relevant artifact file
  for artifact in "plan.md" "spec.md" "brief.md"; do
    f="$dir$artifact"
    [ -f "$f" ] || continue

    # Read frontmatter fields
    title=$(sed -n '/^---$/,/^---$/{ /^title:/s/^title: *"*\([^"]*\)"*/\1/p; }' "$f" 2>/dev/null)
    status=$(sed -n '/^---$/,/^---$/{ /^status:/s/^status: *//p; }' "$f" 2>/dev/null)
    phase=$(sed -n '/^---$/,/^---$/{ /^phase:/s/^phase: *//p; }' "$f" 2>/dev/null)
    tasks_total=$(sed -n '/^---$/,/^---$/{ /^tasks-total:/s/^tasks-total: *//p; }' "$f" 2>/dev/null)
    tasks_done=$(sed -n '/^---$/,/^---$/{ /^tasks-done:/s/^tasks-done: *//p; }' "$f" 2>/dev/null)

    [ -z "$title" ] && title=$(basename "$dir" | sed 's|/$||')
    [ -z "$status" ] && status="unknown"

    progress=""
    if [ -n "$tasks_total" ] && [ "$tasks_total" != "0" ]; then
      progress=" ($tasks_done/$tasks_total tasks)"
    fi

    ACTIVE_WORK="$ACTIVE_WORK  - $title [$status, $phase]$progress — $f\n"
    WORK_COUNT=$((WORK_COUNT + 1))
    break  # One artifact per initiative is enough
  done
done

# ── Scan recent docs ──
RECENT_DOCS=""
DOC_COUNT=0
for doc in "$SAGE_DIR"/docs/*.md; do
  [ -f "$doc" ] || continue
  DOC_COUNT=$((DOC_COUNT + 1))
  name=$(basename "$doc" .md)
  RECENT_DOCS="$RECENT_DOCS  - $name — $doc\n"
done

# ── Output structured context ──
echo ""
echo "## Sage Context (auto-injected)"
echo ""
echo "Sage: Project status — $STATUS | Feature: $FEATURE | Phase: $PHASE"

if [ -n "$NEXT" ] && [ "$NEXT" != "Describe what you want to build — Sage will guide you" ]; then
  echo "Next: $NEXT"
fi

if [ "$WORK_COUNT" -gt 0 ]; then
  echo ""
  echo "Active work ($WORK_COUNT):"
  printf "$ACTIVE_WORK"
fi

if [ "$DOC_COUNT" -gt 0 ]; then
  echo "Project docs: $DOC_COUNT files in .sage/docs/"
fi

echo ""
echo "Sage navigator: sage/core/capabilities/orchestration/sage-navigator/SKILL.md"
echo "Run Pre-Flight memory recall before assessing intent."
echo ""
