#!/usr/bin/env bash
# sage-verify.sh — Deterministic verification for Gate 5
# Runs tests, checks results, collects evidence. Returns exit code 0 on pass.
# Usage: bash sage/core/gates/scripts/sage-verify.sh [project-root]
#
# This script replaces language-based "verify tests pass" instructions
# with deterministic execution. Code is deterministic; language isn't.

set -euo pipefail

ROOT="${1:-.}"
PASS=true
EVIDENCE=""

log() { EVIDENCE="$EVIDENCE\n$1"; echo "$1"; }

log "═══ Sage Gate 5: Verification ═══"
log "Root: $ROOT"
log "Time: $(date -Iseconds)"
log ""

# ── Step 1: Detect test runner ──
TEST_CMD=""
TEST_RUNNER="unknown"

if [ -f "$ROOT/package.json" ]; then
  if grep -q '"vitest"' "$ROOT/package.json" 2>/dev/null; then
    TEST_CMD="npx vitest run --reporter=verbose"
    TEST_RUNNER="vitest"
  elif grep -q '"jest"' "$ROOT/package.json" 2>/dev/null; then
    TEST_CMD="npx jest --verbose --no-coverage"
    TEST_RUNNER="jest"
  elif grep -q '"mocha"' "$ROOT/package.json" 2>/dev/null; then
    TEST_CMD="npx mocha --recursive"
    TEST_RUNNER="mocha"
  elif grep -q '"test"' "$ROOT/package.json" 2>/dev/null; then
    TEST_CMD="npm test"
    TEST_RUNNER="npm-test"
  fi
elif [ -f "$ROOT/pyproject.toml" ] || [ -f "$ROOT/setup.py" ]; then
  if [ -d "$ROOT/.venv" ]; then
    TEST_CMD="$ROOT/.venv/bin/python -m pytest -v"
  else
    TEST_CMD="python -m pytest -v"
  fi
  TEST_RUNNER="pytest"
elif [ -f "$ROOT/pubspec.yaml" ]; then
  TEST_CMD="flutter test --verbose"
  TEST_RUNNER="flutter-test"
elif [ -f "$ROOT/go.mod" ]; then
  TEST_CMD="go test ./... -v"
  TEST_RUNNER="go-test"
fi

if [ -z "$TEST_CMD" ]; then
  log "⚠️  No test runner detected. Skipping automated test verification."
  log "    Checked: vitest, jest, mocha, npm test, pytest, flutter test, go test"
  log "    Manual verification required."
  exit 0
fi

log "Test runner: $TEST_RUNNER"
log "Command: $TEST_CMD"
log ""

# ── Step 2: Run tests ──
log "── Running tests ──"
cd "$ROOT"

TEST_OUTPUT=$(eval "$TEST_CMD" 2>&1) || {
  EXIT_CODE=$?
  log "❌ TESTS FAILED (exit code: $EXIT_CODE)"
  log ""
  log "── Test Output ──"
  log "$TEST_OUTPUT"
  PASS=false
}

if [ "$PASS" = true ]; then
  log "✅ ALL TESTS PASSED"
  # Count tests if possible
  case "$TEST_RUNNER" in
    vitest|jest)
      SUITE_COUNT=$(echo "$TEST_OUTPUT" | grep -c "✓\|PASS" 2>/dev/null || echo "?")
      log "    Suites: ~$SUITE_COUNT passing"
      ;;
    pytest)
      SUMMARY=$(echo "$TEST_OUTPUT" | grep -E "^\d+ passed" 2>/dev/null || echo "")
      [ -n "$SUMMARY" ] && log "    $SUMMARY"
      ;;
  esac
fi

log ""

# ── Step 3: Check build compiles ──
log "── Build check ──"
if [ -f "$ROOT/package.json" ]; then
  if grep -q '"build"' "$ROOT/package.json" 2>/dev/null; then
    BUILD_OUT=$(npm run build 2>&1) || {
      log "❌ BUILD FAILED"
      log "$BUILD_OUT" | tail -20
      PASS=false
    }
    [ "$PASS" = true ] && log "✅ Build succeeds"
  else
    log "⚠️  No build script in package.json"
  fi
elif [ -f "$ROOT/pubspec.yaml" ]; then
  BUILD_OUT=$(flutter analyze 2>&1) || {
    log "❌ Flutter analyze failed"
    PASS=false
  }
  [ "$PASS" = true ] && log "✅ Flutter analyze passes"
else
  log "⚠️  No build step detected"
fi

log ""

# ── Step 4: Check for leftover markers ──
log "── Clean code check ──"
TODO_COUNT=$(grep -rn "TODO\|FIXME\|HACK\|XXX" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.py" --include="*.dart" "$ROOT/src" "$ROOT/app" "$ROOT/lib" 2>/dev/null | wc -l || echo "0")
if [ "$TODO_COUNT" -gt 0 ]; then
  log "⚠️  Found $TODO_COUNT TODO/FIXME/HACK markers in source"
  grep -rn "TODO\|FIXME\|HACK" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.py" --include="*.dart" "$ROOT/src" "$ROOT/app" "$ROOT/lib" 2>/dev/null | head -5
else
  log "✅ No TODO/FIXME/HACK markers"
fi

log ""

# ── Result ──
log "═══ Gate 5 Result ═══"
if [ "$PASS" = true ]; then
  log "✅ PASS — All verifications passed"
  exit 0
else
  log "❌ FAIL — See evidence above"
  exit 1
fi
