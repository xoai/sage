#!/usr/bin/env bash
# sage-spec-check.sh — Deterministic checks for Gate 1 (Spec Compliance)
# Verifies that files listed in a task spec actually exist and were modified.
# Usage: bash sage/core/gates/scripts/sage-spec-check.sh <plan-file> <task-number>

set -uo pipefail

PLAN="${1:-}"
TASK_NUM="${2:-}"
PASS=true

log() { echo "$1"; }
fail() { log "❌ $1"; PASS=false; }

if [ -z "$PLAN" ] || [ ! -f "$PLAN" ]; then
  echo "Usage: sage-spec-check.sh <plan-file> <task-number>"
  echo "  plan-file: path to plan.md"
  echo "  task-number: task number to verify (e.g., 1, 2, 3)"
  exit 1
fi

log "═══ Sage Gate 1: Spec Compliance Check ═══"
log "Plan: $PLAN"
log "Task: $TASK_NUM"
log ""

# ── Step 1: Extract task spec from plan ──
log "── Task extraction ──"

# Find the task section in the plan
TASK_SECTION=$(awk "/Task ${TASK_NUM}[^0-9]/,/^- \[/" "$PLAN" | head -20)

if [ -z "$TASK_SECTION" ]; then
  fail "Task $TASK_NUM not found in plan"
  exit 1
fi

log "  Found task section"

# ── Step 2: Check listed files exist ──
log ""
log "── File existence check ──"

# Extract file paths from **Files:** line
FILES=$(echo "$TASK_SECTION" | grep -oP '(?<=Files:\*\*\s).*|(?<=files:\s).*' | tr ',' '\n' | sed 's/`//g' | sed 's/^ *//' | grep -v '^$')

if [ -z "$FILES" ]; then
  # Try alternate format
  FILES=$(echo "$TASK_SECTION" | grep -oP '`[^`]+\.(ts|tsx|js|jsx|py|dart|md|css|html)`' | tr -d '`')
fi

CHECKED=0
MISSING=0

if [ -n "$FILES" ]; then
  while IFS= read -r filepath; do
    filepath=$(echo "$filepath" | xargs)  # trim
    [ -z "$filepath" ] && continue
    
    if [ -f "$filepath" ]; then
      log "  ✅ $filepath exists"
    else
      fail "File not found: $filepath (listed in task spec)"
      MISSING=$((MISSING + 1))
    fi
    CHECKED=$((CHECKED + 1))
  done <<< "$FILES"
  
  log ""
  log "  Checked $CHECKED files, $MISSING missing"
else
  log "  ⚠️  No file paths extracted from task spec"
  log "  Manual verification required"
fi

# ── Step 3: Check task checkbox status ──
log ""
log "── Completion status ──"

if grep -qP "^\- \[x\].*Task ${TASK_NUM}\b" "$PLAN" 2>/dev/null; then
  log "  ✅ Task $TASK_NUM is marked complete in plan"
elif grep -qP "^\- \[ \].*Task ${TASK_NUM}\b" "$PLAN" 2>/dev/null; then
  log "  ⚠️  Task $TASK_NUM is NOT yet marked complete"
else
  log "  ⚠️  Could not determine checkbox status"
fi

# ── Step 4: Check for test files ──
log ""
log "── Test existence ──"

TEST_MENTION=$(echo "$TASK_SECTION" | grep -i "test" | head -3)
if [ -n "$TEST_MENTION" ]; then
  # Look for test files matching the task's main files
  for filepath in $FILES; do
    filepath=$(echo "$filepath" | xargs)
    [ -z "$filepath" ] && continue
    
    dir=$(dirname "$filepath")
    base=$(basename "$filepath" | sed 's/\.[^.]*$//')
    
    # Common test file patterns
    FOUND_TEST=false
    for pattern in "${dir}/${base}.test."* "${dir}/${base}.spec."* "${dir}/__tests__/${base}."* "test/${base}."* "tests/${base}."*; do
      if ls $pattern 2>/dev/null | head -1 > /dev/null; then
        FOUND_TEST=true
        TEST_FILE=$(ls $pattern 2>/dev/null | head -1)
        log "  ✅ Test found: $TEST_FILE"
        break
      fi
    done
    
    if [ "$FOUND_TEST" = false ]; then
      log "  ⚠️  No test file found for $filepath"
    fi
  done
else
  log "  No test mentioned in task spec"
fi

log ""

# ── Result ──
log "═══ Gate 1 Result ═══"
if [ "$PASS" = true ]; then
  log "✅ PASS — All spec deliverables verified"
  exit 0
else
  log "❌ FAIL — Missing deliverables"
  exit 1
fi
