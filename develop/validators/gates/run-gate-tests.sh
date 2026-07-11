#!/usr/bin/env bash
# run-gate-tests.sh — regression tests for Sage's deterministic gate scripts.
#
# Usage:
#   bash develop/validators/gates/run-gate-tests.sh [--only ID] [--verbose]
#
# Exit: 0 = every case behaved as declared   |   1 = a case regressed
#       2 = bad invocation
#
# A case declares the exit code and output substrings a gate script MUST
# produce for a fixture. Cases marked --xfail document behavior that is
# currently WRONG and is scheduled to be fixed; when such a case starts
# passing, the harness reports XPASS and fails, forcing the marker's removal.
# That keeps this file honest in both directions.
#
# Gate exit contract (ADR-1 / brief C7):
#   0 = verified pass   1 = verified fail   2 = unverifiable (nothing to check)
#
# Convention: every gate bug gets a numbered fixture here BEFORE it is fixed.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
GATES_DIR="${SAGE_GATES_DIR:-$REPO_ROOT/core/gates/scripts}"
FIX="$SCRIPT_DIR/fixtures"

ONLY=""
VERBOSE=false
while [ $# -gt 0 ]; do
  case "$1" in
    --only)    ONLY="$2"; shift 2 ;;
    --verbose|-v) VERBOSE=true; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

N_PASS=0; N_FAIL=0; N_XFAIL=0; N_XPASS=0; N_SKIP=0
FAILED_IDS=""

# ── tool availability ────────────────────────────────────────────────────
have_tool() {
  case "$1" in
    pytest) python3 -c 'import pytest' >/dev/null 2>&1 ;;
    tsc)    command -v tsc >/dev/null 2>&1 || npx --no-install tsc --version >/dev/null 2>&1 ;;
    node)   command -v node >/dev/null 2>&1 ;;
    playwright) node -e "require.resolve('playwright')" >/dev/null 2>&1 ;;
    *)      command -v "$1" >/dev/null 2>&1 ;;
  esac
}

report() {
  # report <status> <id> <label> [detail...]
  local status="$1" id="$2" label="$3"; shift 3
  printf '  %-7s %-4s %s\n' "[$status]" "$id" "$label"
  while [ $# -gt 0 ]; do printf '            %s\n' "$1"; shift; done
}

# ── run_case ─────────────────────────────────────────────────────────────
# run_case <id> <label> --script X --exit N [--contains S]... [--not-contains S]...
#          [--requires T]... [--skip-if-tool T] [--cwd D] [--env K=V]...
#          [--xfail REASON] [--timeout SECS] -- <script args...>
run_case() {
  local id="$1" label="$2"; shift 2
  [ -n "$ONLY" ] && [ "$ONLY" != "$id" ] && return 0

  local script="" expect_exit="" xfail="" cwd="$REPO_ROOT" tmo=120
  local contains=() not_contains=() requires=() envs=() args=() skip_if=()

  while [ $# -gt 0 ]; do
    case "$1" in
      --script)       script="$2"; shift 2 ;;
      --exit)         expect_exit="$2"; shift 2 ;;
      --contains)     contains+=("$2"); shift 2 ;;
      --not-contains) not_contains+=("$2"); shift 2 ;;
      --requires)     requires+=("$2"); shift 2 ;;
      --skip-if-tool) skip_if+=("$2"); shift 2 ;;
      --cwd)          cwd="$2"; shift 2 ;;
      --env)          envs+=("$2"); shift 2 ;;
      --xfail)        xfail="$2"; shift 2 ;;
      --timeout)      tmo="$2"; shift 2 ;;
      --)             shift; args=("$@"); break ;;
      *) echo "run_case $id: unknown option $1" >&2; exit 2 ;;
    esac
  done

  if [ -z "$script" ] || [ -z "$expect_exit" ]; then
    echo "run_case $id: --script and --exit are required" >&2; exit 2
  fi

  # Skip when a required tool is missing (keeps the harness usable offline).
  local t
  for t in ${requires[@]+"${requires[@]}"}; do
    if ! have_tool "$t"; then
      N_SKIP=$((N_SKIP + 1))
      report SKIP "$id" "$label" "missing tool: $t"
      return 0
    fi
  done
  for t in ${skip_if[@]+"${skip_if[@]}"}; do
    if have_tool "$t"; then
      N_SKIP=$((N_SKIP + 1))
      report SKIP "$id" "$label" "tool present, case only valid without it: $t"
      return 0
    fi
  done

  local runner=()
  if command -v timeout >/dev/null 2>&1; then runner=(timeout "$tmo"); fi

  local out rc
  out=$(cd "$cwd" && env ${envs[@]+"${envs[@]}"} \
        ${runner[@]+"${runner[@]}"} bash "$GATES_DIR/$script" \
        ${args[@]+"${args[@]}"} 2>&1)
  rc=$?

  # ── evaluate declared expectations ──
  local ok=true problems=()
  if [ "$rc" -ne "$expect_exit" ]; then
    ok=false; problems+=("expected exit $expect_exit, got $rc")
  fi
  local s
  for s in ${contains[@]+"${contains[@]}"}; do
    if ! printf '%s' "$out" | grep -Fq -- "$s"; then
      ok=false; problems+=("output missing substring: '$s'")
    fi
  done
  for s in ${not_contains[@]+"${not_contains[@]}"}; do
    if printf '%s' "$out" | grep -Fq -- "$s"; then
      ok=false; problems+=("output contains forbidden substring: '$s'")
    fi
  done

  # ── classify ──
  if [ -n "$xfail" ]; then
    if [ "$ok" = true ]; then
      N_XPASS=$((N_XPASS + 1)); FAILED_IDS="$FAILED_IDS $id"
      report XPASS "$id" "$label" \
        "case now behaves correctly — remove the --xfail marker" "was: $xfail"
    else
      N_XFAIL=$((N_XFAIL + 1))
      report XFAIL "$id" "$label" "known-broken: $xfail"
    fi
  elif [ "$ok" = true ]; then
    N_PASS=$((N_PASS + 1))
    report PASS "$id" "$label"
  else
    N_FAIL=$((N_FAIL + 1)); FAILED_IDS="$FAILED_IDS $id"
    report FAIL "$id" "$label" ${problems[@]+"${problems[@]}"}
  fi

  if [ "$VERBOSE" = true ] || { [ "$ok" = false ] && [ -z "$xfail" ]; }; then
    printf '            ── captured output (exit %s) ──\n' "$rc"
    printf '%s\n' "$out" | sed 's/^/            | /'
  fi
}

# ═════════════════════════════════════════════════════════════════════════
echo "═══ Sage gate regression tests ═══"
echo "Gates: $GATES_DIR"
echo ""

# ── Gate 4: hallucination check ──────────────────────────────────────────
echo "Gate 4 — sage-hallucination-check.sh"
H=sage-hallucination-check.sh

run_case G1 "missing relative import fails closed (01-analysis §2.1 repro)" \
  --script "$H" --exit 1 \
  --contains "FAIL" --contains "does-not-exist" \
  -- "$FIX/hallucination/missing-relative-import/src/app.ts" \
     "$FIX/hallucination/missing-relative-import"

# The 'Checked 1 imports' assertion stops this case from passing vacuously —
# the pre-P1-T2 gate reached PASS having examined nothing.
run_case G2 "clean TypeScript passes, having actually resolved the import" \
  --script "$H" --exit 0 --contains "PASS" \
  --contains "Checked 1 imports, 0 missing" \
  -- "$FIX/hallucination/clean-ts/src/app.ts" "$FIX/hallucination/clean-ts"

run_case G3 "phantom package fails closed" \
  --script "$H" --exit 1 \
  --contains "FAIL" --contains "totally-not-a-real-package" \
  -- "$FIX/hallucination/phantom-package/src/app.ts" \
     "$FIX/hallucination/phantom-package"

run_case G4 "nothing to check is UNVERIFIABLE, not pass" \
  --script "$H" --exit 2 --contains "UNVERIFIABLE" \
  -- "$FIX/hallucination/nothing-to-check" "$FIX/hallucination/nothing-to-check"

# Gate 4 has no import analysis for Python. Without a type-checker it has
# examined nothing, and must say so rather than report a clean bill of health.
run_case G4b "Python file with no type-checker is UNVERIFIABLE, not pass" \
  --script "$H" --exit 2 --contains "UNVERIFIABLE" \
  --skip-if-tool pyright --skip-if-tool mypy \
  -- "$FIX/hallucination/python-only" "$FIX/hallucination/python-only"

run_case G5 "type error fails closed via toolchain" \
  --script "$H" --exit 1 --contains "FAIL" \
  --requires tsc \
  -- "$FIX/hallucination/tsc-error/src/app.ts" "$FIX/hallucination/tsc-error"

run_case G12 "counters are truthful (no contradictory 'no imports' line)" \
  --script "$H" --exit 1 \
  --contains "Checked 1 imports, 1 missing" \
  --not-contains "No relative imports to check" \
  -- "$FIX/hallucination/missing-relative-import/src/app.ts" \
     "$FIX/hallucination/missing-relative-import"

echo ""

# ── Gate 5: verification ─────────────────────────────────────────────────
echo "Gate 5 — sage-verify.sh"
V=sage-verify.sh

run_case G6 "no test runner is UNVERIFIABLE, not pass" \
  --script "$V" --exit 2 --contains "UNVERIFIABLE" \
  -- "$FIX/verify/no-runner"

run_case G7 "passing pytest suite passes" \
  --script "$V" --exit 0 --contains "PASS" \
  --requires pytest \
  -- "$FIX/verify/passing-pytest"

# Asserting on the test's name proves the gate failed because the SUITE failed,
# not because the runner itself blew up.
run_case G8 "failing pytest suite fails, with captured evidence" \
  --script "$V" --exit 1 --contains "FAIL" --contains "test_arithmetic_is_broken" \
  --requires pytest \
  -- "$FIX/verify/failing-pytest"

# pytest.ini + tests/ is how pytest documents its own setup. The gate only looked
# for packaging metadata, so such a project was "no test runner detected" — the
# suite ran fine, and Sage declined to look at it.
run_case G9b "a pytest.ini project is detected, not UNVERIFIABLE" \
  --script "$V" --exit 0 --contains "PASS" \
  --requires pytest \
  -- "$FIX/verify/pytest-ini-only"

run_case G9 "'vitest' in package.json metadata is not a runner" \
  --script "$V" --exit 2 --contains "UNVERIFIABLE" \
  --not-contains "npx vitest" \
  --env npm_config_offline=true --env npm_config_yes=false \
  --timeout 60 \
  -- "$FIX/verify/misleading-package-json"

echo ""

# ── Gate 1: spec compliance ──────────────────────────────────────────────
echo "Gate 1 — sage-spec-check.sh"
S=sage-spec-check.sh

# Asserting the filename proves the path was actually extracted and checked.
# Without it the pre-P1-T5 gate passed vacuously — which is how the bug hid.
run_case G10a "declared file that exists passes, having actually been checked" \
  --script "$S" --exit 0 --contains "PASS" --contains "src/greeter.ts" \
  --cwd "$FIX/spec-check/pass" \
  -- plan.md 1

run_case G10b "declared file that is missing fails closed" \
  --script "$S" --exit 1 --contains "FAIL" --contains "src/missing.ts" \
  --cwd "$FIX/spec-check/fail" \
  -- plan.md 1

run_case G10c "task declaring no deliverables is UNVERIFIABLE, not pass" \
  --script "$S" --exit 2 --contains "UNVERIFIABLE" \
  --cwd "$FIX/spec-check/unverifiable" \
  -- plan.md 1

run_case G10d "[DOC] task's Output: path is checked like Files:" \
  --script "$S" --exit 1 --contains "FAIL" --contains "docs/absent.md" \
  --cwd "$FIX/spec-check/doc-task" \
  -- plan.md 1

echo ""

# ── Gate 6: visual verification ──────────────────────────────────────────
echo "Gate 6 — sage-visual-gate.sh"
W=sage-visual-gate.sh

run_case G11a "missing URL argument is a usage error" \
  --script "$W" --exit 1 --contains "Usage:" \
  --

run_case G11b "no browser toolchain is UNVERIFIABLE, not fail" \
  --script "$W" --exit 2 --contains "UNVERIFIABLE" \
  --skip-if-tool playwright \
  --timeout 60 \
  -- "file://$FIX/visual/page.html" "$(mktemp -d)/shots"

run_case G11c "clean page passes" \
  --script "$W" --exit 0 --contains "PASS" \
  --requires playwright --timeout 180 \
  -- "file://$FIX/visual/page.html" "$(mktemp -d)/shots"

# ═════════════════════════════════════════════════════════════════════════
echo ""
echo "═══ Summary ═══"
printf '  pass %d · fail %d · xfail %d · xpass %d · skip %d\n' \
  "$N_PASS" "$N_FAIL" "$N_XFAIL" "$N_XPASS" "$N_SKIP"

if [ "$N_FAIL" -gt 0 ] || [ "$N_XPASS" -gt 0 ]; then
  echo ""
  echo "  Problem cases:$FAILED_IDS"
  [ "$N_XPASS" -gt 0 ] && echo "  XPASS means a fix landed — delete the --xfail marker for those IDs."
  exit 1
fi

if [ "$N_XFAIL" -gt 0 ]; then
  echo ""
  echo "  $N_XFAIL case(s) document known-broken gate behavior (see --xfail reasons)."
  echo "  These are expected to flip to PASS during Phase 1."
fi
exit 0
