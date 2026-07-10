#!/usr/bin/env bash
# Sage Contract Validation — validate all modules meet their contracts
# Usage: bash develop/validators/contracts/validate-all.sh [sage-root]
# Exit code: 0 = all pass, 1 = failures found

set -euo pipefail

# Resolve the Sage root. An explicit first arg wins. Otherwise walk up from the
# script dir to the nearest ancestor that contains core/capabilities — this keeps
# the documented no-arg invocation working regardless of how deeply the validators
# are nested (they live at develop/validators/contracts/ after the repo reorg).
resolve_root() {
  if [ -n "${1:-}" ]; then printf '%s' "$1"; return; fi
  local d; d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    [ -d "$d/core/capabilities" ] && { printf '%s' "$d"; return; }
    d="$(dirname "$d")"
  done
  (cd "$(dirname "$0")/../../.." && pwd)   # fallback: repo root from this script
}
SAGE_ROOT="$(resolve_root "${1:-}")"
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

# Result files are aggregated by glob below. Clear any stragglers from a prior
# run (or a standalone validator/.test.sh invocation) BEFORE we start, so an
# orphaned file can never inflate this run's totals. A trap guarantees cleanup
# on every exit path — the previous inline `rm` could be skipped when `set -e`
# aborted the error-print loop, leaving stale files that poisoned the next run.
rm -f /tmp/sage-test-results-* 2>/dev/null || true
trap 'rm -f /tmp/sage-test-results-* 2>/dev/null || true' EXIT

# Run each validator
bash "$TESTS_DIR/validate-skills.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-gates.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-workflows.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-constitution.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-personas.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-templates.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-cross-refs.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-structure.sh" "$SAGE_ROOT"
bash "$TESTS_DIR/validate-discipline-skill.sh" "$SAGE_ROOT"
# CSO description check. CSO_ENFORCE=1 promotes a workflow-summary in a
# `skill_type: discipline` description to a hard FAIL; non-discipline skills stay
# warn-only. The first batch is CSO-clean, so this stays green. Override by
# exporting CSO_ENFORCE=0 to drop back to warn-everywhere.
CSO_ENFORCE="${CSO_ENFORCE:-1}" bash "$TESTS_DIR/../cso/validate-cso.sh" "$SAGE_ROOT"
# Token-budget check — advisory only. Emits WARN lines (folded into Warnings:);
# never PASS/FAIL, so the contract total is untouched.
bash "$TESTS_DIR/validate-token-budget.sh" "$SAGE_ROOT"
# Deterministic runtime smoke — catalogs, route authority, replay, and strict facts.
PYTHON_BIN="${PYTHON_BIN:-python3}" bash "$TESTS_DIR/../router-state-smoke.sh" "$SAGE_ROOT"
PYTHON_BIN="${PYTHON_BIN:-python3}" bash "$TESTS_DIR/../composition-smoke.sh" "$SAGE_ROOT"

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
  # Print collected errors. `|| true` so a file with no ERR line never trips
  # set -e and aborts the loop (the EXIT trap handles cleanup either way).
  for f in /tmp/sage-test-results-*; do
    [ -f "$f" ] || continue
    grep "^ERR:" "$f" 2>/dev/null | sed 's/^ERR:/  ✗ /' || true
  done
  exit 1
else
  green "RESULT: PASS — all modules satisfy their contracts"
  exit 0
fi
