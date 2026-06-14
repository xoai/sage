#!/usr/bin/env bash
# Advisory token-budget check for skills. A discipline skill loads into context
# where every token competes with the instruction that must not be missed; a long
# skill is easy to skim past. This surfaces the worst offenders as WARNINGS so a
# separate hygiene pass can tighten them. It NEVER emits a failure — budget is
# advisory, not a gate.
#
# Usage: bash develop/validators/contracts/validate-token-budget.sh [sage-root]
#
# Count is BODY ONLY: YAML frontmatter (the first --- … --- block) and fenced
# ``` blocks (sub-agent prompts, reference tables) are excluded — a skill that is
# long only because of a fenced reference block is not falsely flagged.
#
# Thresholds (warn above), by skill_type:
#   discipline                 500   loaded under pressure; the rule must be findable
#   methodology                700   conceptual, but heavy detail belongs in references/
#   eager | fragment           250   eager-layer fragments are always in context
#   other / untyped            900   soft ceiling; encourages a references/ split
#
# Results append to /tmp/sage-test-results-token-budget as PASS:0 FAIL:0 WARN:N so
# validate-all.sh folds the warnings into its Warnings: tally and leaves the
# PASS/FAIL total untouched.

set -uo pipefail

SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS="/tmp/sage-test-results-token-budget"
WARN=0
> "$RESULTS"

yellow() { echo -e "\033[33m$1\033[0m"; }
warn() { WARN=$((WARN + 1)); echo "  $(yellow '⚠') $1"; }

echo ""
echo -e "\033[1m── Token-Budget (advisory) ──\033[0m"

CAP_DIR="$SAGE_ROOT/core/capabilities"
if [ ! -d "$CAP_DIR" ]; then
  echo "  (no core/capabilities under $SAGE_ROOT — nothing to check)"
  echo "PASS:0" >> "$RESULTS"; echo "FAIL:0" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
  exit 0
fi

# Body word count: drop the first frontmatter block and every fenced ``` block.
count_body_words() {
  awk '
    NR==1 && $0=="---" { fm=1; next }
    fm && $0=="---"    { fm=0; next }
    fm                 { next }
    /^[[:space:]]*```/ { fence=!fence; next }
    fence              { next }
    { print }
  ' "$1" | wc -w | tr -d ' '
}

skill_type_of() {
  local t
  t="$(awk '
    NR==1 && $0=="---" { fm=1; next }
    fm && $0=="---" { exit }
    fm && /^skill_type:/ { sub(/^skill_type:[[:space:]]*/, ""); print; exit }
  ' "$1")"
  t="${t%$'\r'}"
  case "$t" in \"*\") t="${t#\"}"; t="${t%\"}" ;; \'*\') t="${t#\'}"; t="${t%\'}" ;; esac
  printf '%s' "$t"
}

threshold_for() {
  case "$1" in
    discipline)        echo 500 ;;
    methodology)       echo 700 ;;
    eager|fragment|eager-layer) echo 250 ;;
    *)                 echo 900 ;;
  esac
}

# Collect over-budget skills as "words|name|threshold|type" for a worst-first sort.
overs=""
checked=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  checked=$((checked + 1))
  name="$(basename "$(dirname "$f")")"
  stype="$(skill_type_of "$f")"
  [ -n "$stype" ] || stype="other"
  limit="$(threshold_for "$stype")"
  words="$(count_body_words "$f")"
  if [ "${words:-0}" -gt "$limit" ]; then
    overs+="${words}|${name}|${limit}|${stype}"$'\n'
  fi
done <<EOF
$(find "$CAP_DIR" -name SKILL.md -not -path '*/\{*' 2>/dev/null | sort)
EOF

if [ -z "$overs" ]; then
  echo "  All $checked skills are within their token budget."
else
  n_over=$(printf '%s' "$overs" | grep -c . )
  echo "  $n_over of $checked skills over budget (worst first):"
  # Worst-first: numeric descending by word count.
  while IFS='|' read -r words name limit stype; do
    [ -z "$name" ] && continue
    warn "$name: ${words}w > ${limit}w (skill_type:${stype}) — consider moving detail to references/"
  done <<EOF
$(printf '%s' "$overs" | sort -t'|' -k1,1nr)
EOF
fi

echo "PASS:0" >> "$RESULTS"
echo "FAIL:0" >> "$RESULTS"
echo "WARN:$WARN" >> "$RESULTS"
