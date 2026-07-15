#!/usr/bin/env bash
# fastcheck.sh — the inner-loop gate for cutting ceremony.
#
# Runs every SECOND-SCALE deterministic check in one shot. This is the guard you
# run after each prose/ceremony deletion — it exercises the layer that actually
# carries the value (hooks, gate scripts, generated state) and it finishes in
# under a minute, so you are not paying the agentic-eval tax to learn you broke
# a hook.
#
# It deliberately does NOT run: the agentic sage-vs-bare evals (minutes to hours
# — use `develop/evals/confirm.sh` for a batched confirmation) or the docker
# bash-3.2 smoke (needs docker; check-bash-arrays + check-portability are its
# static stand-ins and ARE included here).
#
# Usage:
#   bash develop/fastcheck.sh          # run all, summarize, exit 1 on any failure
#   bash develop/fastcheck.sh --stop   # stop at the first failure (fastest signal)
#   bash develop/fastcheck.sh -v       # stream each check's output, not just failures
#
# Exit: 0 = everything green | 1 = a check failed | 2 = bad invocation

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2

STOP=false; VERBOSE=false
for a in "$@"; do
  case "$a" in
    --stop) STOP=true ;;
    -v|--verbose) VERBOSE=true ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

# Each row: "label :: command". Keep them ordered cheapest-first so --stop bails fast.
CHECKS=(
  "version drift          :: python3 runtime/tools/release.py --check"
  "context budget         :: python3 runtime/tools/context_budget.py --check"
  "platform contract      :: python3 runtime/tools/contract.py --check"
  "truth table            :: python3 runtime/tools/gen_truth_table.py --check"
  "plugin builds          :: python3 runtime/tools/build_plugin.py --check"
  "bash-array safety       :: python3 develop/validators/check-bash-arrays.py"
  "shell portability      :: python3 develop/validators/check-portability.py"
  "eval coverage registry :: python3 develop/validators/check-eval-coverage.py --check"
  "eval scenarios offline :: python3 develop/evals/run_evals.py --offline-check"
  "manifest tests         :: python3 develop/validators/tools/test_manifest.py"
  "driver tests           :: python3 develop/evals/test_driver.py"
  "grader tests           :: python3 develop/evals/test_graders.py"
  "gate regression tests  :: bash develop/validators/gates/run-gate-tests.sh"
  "spec-gate hook tests   :: bash develop/validators/hooks/run-hook-tests.sh"
)

echo "═══ fastcheck — deterministic inner-loop gate (${#CHECKS[@]} checks) ═══"
START=$(date +%s 2>/dev/null || echo 0)
PASS=0; FAIL=0; FAILED_LABELS=""

for row in ${CHECKS[@]+"${CHECKS[@]}"}; do
  label="${row%% :: *}"; cmd="${row##* :: }"
  out=$(eval "$cmd" 2>&1); rc=$?
  if [ "$rc" -eq 0 ]; then
    printf '  \033[32m✓\033[0m %s\n' "$label"
    PASS=$((PASS + 1))
    [ "$VERBOSE" = true ] && printf '%s\n' "$out" | sed 's/^/       | /'
  else
    printf '  \033[31m✗\033[0m %s  (exit %d)\n' "$label" "$rc"
    printf '%s\n' "$out" | tail -20 | sed 's/^/       | /'
    FAIL=$((FAIL + 1)); FAILED_LABELS="$FAILED_LABELS\n    - $label"
    [ "$STOP" = true ] && break
  fi
done

END=$(date +%s 2>/dev/null || echo 0)
echo "───────────────────────────────────────────────"
printf 'pass %d · fail %d · %ss\n' "$PASS" "$FAIL" "$((END - START))"
if [ "$FAIL" -gt 0 ]; then
  printf 'FAILED:%b\n' "$FAILED_LABELS"
  exit 1
fi
echo "all green — safe to keep cutting."
