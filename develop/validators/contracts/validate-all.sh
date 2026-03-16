#!/usr/bin/env bash
# Sage Contract Validation — validate all modules meet their contracts
# Usage: bash develop/validators/contracts/validate-all.sh [sage-root]
# Exit code: 0 = all pass, 1 = failures found

set -euo pipefail

SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0
WARN=0
ERRORS=""

# ─── Helpers ────────────────────────────────────────────────────────────────

green()  { echo -e "\033[32m$1\033[0m"; }
red()    { echo -e "\033[31m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
bold()   { echo -e "\033[1m$1\033[0m"; }

pass() {
  PASS=$((PASS + 1))
  echo "  $(green '✓') $1"
}

fail() {
  FAIL=$((FAIL + 1))
  ERRORS+="  FAIL: $1"$'\n'
  echo "  $(red '✗') $1"
}

warn() {
  WARN=$((WARN + 1))
  echo "  $(yellow '⚠') $1"
}

section() {
  echo ""
  bold "── $1 ──"
}

# ─── Run All Validators ────────────────────────────────────────────────────

echo ""
bold "╔═══════════════════════════════════════╗"
bold "║   Sage Contract Validation Suite     ║"
bold "╚═══════════════════════════════════════╝"
echo ""
echo "Root: $SAGE_ROOT"

# Run each validator
bash "$TESTS_DIR/validate-skills.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-gates.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-workflows.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-constitution.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-personas.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-templates.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-cross-refs.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-structure.sh" "$SAGE_ROOT"

echo ""
bold "═══ Summary ═══"
echo ""

# Collect results from all sub-validators
TOTAL_PASS=$(grep -rh "^PASS:" /tmp/sage-test-results-* 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
TOTAL_FAIL=$(grep -rh "^FAIL:" /tmp/sage-test-results-* 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
TOTAL_WARN=$(grep -rh "^WARN:" /tmp/sage-test-results-* 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')

echo "  $(green "Passed:   $TOTAL_PASS")"
[ "$TOTAL_WARN" -gt 0 ] && echo "  $(yellow "Warnings: $TOTAL_WARN")"
[ "$TOTAL_FAIL" -gt 0 ] && echo "  $(red "Failed:   $TOTAL_FAIL")"
echo ""

if [ "$TOTAL_FAIL" -gt 0 ]; then
  red "RESULT: FAIL — $TOTAL_FAIL contract violations found"
  echo ""
  # Print collected errors
  for f in /tmp/sage-test-results-*; do
    [ -f "$f" ] && grep "^ERR:" "$f" 2>/dev/null | sed 's/^ERR:/  ✗ /'
  done
  rm -f /tmp/sage-test-results-*
  exit 1
else
  green "RESULT: PASS — all modules satisfy their contracts"
  rm -f /tmp/sage-test-results-*
  exit 0
fi
