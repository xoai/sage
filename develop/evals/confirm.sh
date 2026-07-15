#!/usr/bin/env bash
# confirm.sh — the once-per-batch agentic confirmation.
#
# fastcheck.sh (deterministic, seconds) is the inner loop. THIS is the outer
# loop: after a BATCH of ceremony cuts — not after each one — run it once to
# confirm the agentic behaviour actually held. It bakes in the cheap-iteration
# defaults so you are not paying for a full frontier sage-vs-bare comparison
# every time:
#
#   • sage arm ONLY        — bare is unaffected by your changes; skip it
#   • runs=2               — a regression is usually binary and shows at low N
#                            (a hook stops firing, a gate stops blocking).
#                            Use the full N=3+ sage-vs-bare run for a PUBLISHED
#                            number, not for "did I break it".
#   • whatever model the CLI defaults to, unless you pass --model
#
# For an even faster/cheaper screen that only catches gross breakage, add
#   --model haiku      (misses frontier-only regressions — screen, not verdict)
#
# Background it so wall-clock is not YOUR time:
#   bash develop/evals/confirm.sh E1 E4 E5 E8 > /tmp/confirm.log 2>&1 &
#
# Usage:
#   confirm.sh [SCENARIO...] [--runs N] [--model M] [--both] [--budget-usd B] [-- <extra run_evals args>]
# Defaults: scenarios = E1 E4 E5 E8 (the surfaces prose cuts touch most); sage only; runs 2.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 2

SCENARIOS=(); RUNS=2; MODEL=""; COND="sage"; BUDGET=""; EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --runs)       RUNS="$2"; shift 2 ;;
    --model)      MODEL="$2"; shift 2 ;;
    --both)       COND="both"; shift ;;
    --budget-usd) BUDGET="$2"; shift 2 ;;
    --)           shift; EXTRA=("$@"); break ;;
    -h|--help)    sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)           echo "unknown option: $1" >&2; exit 2 ;;
    *)            SCENARIOS+=("$1"); shift ;;
  esac
done
[ ${#SCENARIOS[@]} -eq 0 ] && SCENARIOS=(E1 E4 E5 E8)

CMD=(python3 develop/evals/run_evals.py --report --runs "$RUNS")
for s in ${SCENARIOS[@]+"${SCENARIOS[@]}"}; do CMD+=(--scenario "$s"); done
[ "$COND" = "both" ] || CMD+=(--condition sage)
[ -n "$MODEL" ]  && CMD+=(--model "$MODEL")
[ -n "$BUDGET" ] && CMD+=(--budget-usd "$BUDGET")
CMD+=(${EXTRA[@]+"${EXTRA[@]}"})

echo "═══ confirm — batched agentic check ═══"
echo "  scenarios: ${SCENARIOS[*]+"${SCENARIOS[*]}"}"
echo "  condition: $COND   runs: $RUNS   model: ${MODEL:-<cli default>}"
echo "  → ${CMD[*]+"${CMD[*]}"}"
echo "  (this makes real model calls; background it if you don't want to wait)"
echo
exec ${CMD[@]+"${CMD[@]}"}
