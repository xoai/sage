#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Sage Session Init Hook for Claude Code
# Fires on: startup, resume, clear, compact
# Reads .sage/ artifacts and outputs structured context
# Zero dependencies — bash only
# ═══════════════════════════════════════════════════════════════

SAGE_DIR=".sage"

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
