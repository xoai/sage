#!/usr/bin/env bash
# Validate skill DESCRIPTIONS against the CSO standard (Concise, Self-describing
# Operation): a description states triggering conditions ONLY. A description that
# summarizes the workflow becomes a shortcut the agent follows instead of opening
# the skill body — the plausible cause of the original auto-review skip.
# See core/capabilities/verification/testing-skills/references/cso.md.
#
# Usage: bash develop/validators/cso/validate-cso.sh [sage-root]
#
# Heuristic — a description is a CSO violation if it contains any of:
#   H1. Step/check ENUMERATION  — a number (digit or word two…ten) within a few
#       words of an operation noun: checks/steps/dimensions/principles/gates/phases.
#   H2. Process SEQUENCING       — "then", "after that", "followed by", "first…then".
#   H3. WHAT-IT-DOES verb + list — a what-it-does verb (Checks, Verifies, Reviews,
#       Validates, …) followed by a ≥3-item comma list before the next period.
#   H4. "<noun> of A, B, C…"      — review/verification/analysis/check/summary "of"
#       a ≥3-item comma list (artifact enumeration).
#
# Rollout (Q2): WARN by default. Set CSO_ENFORCE=1 to promote violations in
# `skill_type: discipline` skills to hard FAIL. Non-discipline skills are always
# warn-only — this validator runs over ALL skills for signal but gates only
# discipline skills (D2).

set -uo pipefail

SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS="/tmp/sage-test-results-cso"
ENFORCE="${CSO_ENFORCE:-0}"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"

green()  { echo -e "\033[32m$1\033[0m"; }
red()    { echo -e "\033[31m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
pass() { PASS=$((PASS + 1)); echo "  $(green '✓') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(red '✗') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(yellow '⚠') $1"; }

echo ""
echo -e "\033[1m── CSO Description Validation ($([ "$ENFORCE" = 1 ] && echo 'enforce' || echo 'warn') mode) ──\033[0m"

CAP_DIR="$SAGE_ROOT/core/capabilities"
if [ ! -d "$CAP_DIR" ]; then
  echo "  (no core/capabilities under $SAGE_ROOT — nothing to check)"
  echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
  exit 0
fi

# Join the (possibly folded) description: block into a single line.
extract_description() {
  awk '
    NR==1 && $0=="---" { infm=1; next }
    infm && $0=="---" { exit }
    infm && /^description:/ {
      d=$0; sub(/^description:[ \t]*/, "", d)
      if (d==">"||d=="|"||d==">-"||d=="|-"||d==">+"||d=="|+") d=""
      acc=d; collecting=1; next
    }
    infm && collecting {
      if ($0 ~ /^[A-Za-z_][A-Za-z0-9_-]*:/) { collecting=0; next }
      line=$0; sub(/^[ \t]+/, "", line)
      acc = acc (acc==""?"":" ") line
    }
    END { print acc }
  ' "$1"
}

frontmatter_field() {
  awk -v field="$2" '
    NR==1 && $0=="---" { infm=1; next }
    infm && $0=="---" { exit }
    infm && index($0, field":")==1 { sub("^"field":[[:space:]]*", ""); print; exit }
  ' "$1"
}

# Echo the offending phrase if the description violates CSO, else echo nothing.
cso_violation_phrase() {
  local desc="$1" m
  # H1 — numeric/word enumeration of operations (number within 3 words of noun).
  m="$(printf '%s' "$desc" | grep -oiE '\b([0-9]+|two|three|four|five|six|seven|eight|nine|ten)( +[a-z-]+){0,3} +(checks?|steps?|prompts?|dimensions?|principles?|gates?|phases?)\b' | head -1)"
  [ -n "$m" ] && { printf '%s' "$m"; return 0; }
  # H2 — process sequencing words.
  m="$(printf '%s' "$desc" | grep -oiE '\b(then|after that|followed by)\b' | head -1)"
  [ -n "$m" ] && { printf '%s' "$m"; return 0; }
  # H3 — what-it-does verb followed by a ≥3-item comma list before the next period.
  m="$(printf '%s' "$desc" | grep -oE '\b(Checks|Verifies|Validates|Confirms|Reviews|Ensures|Summarizes|Performs|Detects|Scans|Catches|Handles|Inspects|Evaluates|Analyzes|Examines|Tests|Generates|Produces)\b[^.]*,[^.]*,[^.]*' | head -1)"
  [ -n "$m" ] && { printf '%s' "$m" | cut -c1-80; return 0; }
  # H4 — "<noun> of A, B, C…" artifact enumeration.
  m="$(printf '%s' "$desc" | grep -oiE '\b(review|verification|analysis|check|summary) of\b[^.]*,[^.]*,[^.]*' | head -1)"
  [ -n "$m" ] && { printf '%s' "$m" | cut -c1-80; return 0; }
  return 1
}

while IFS= read -r skill_file; do
  [ -z "$skill_file" ] && continue
  name="$(basename "$(dirname "$skill_file")")"
  desc="$(extract_description "$skill_file")"
  [ -z "$desc" ] && continue

  phrase="$(cso_violation_phrase "$desc")" || phrase=""
  if [ -z "$phrase" ]; then
    pass "$name: description is CSO-clean"
    continue
  fi

  stype="$(frontmatter_field "$skill_file" skill_type)"; stype="${stype%$'\r'}"
  msg="$name: workflow-summary in description — \"$phrase\""
  if [ "$ENFORCE" = 1 ] && [ "$stype" = "discipline" ]; then
    fail "$msg"
  else
    warn "$msg"
  fi
done <<EOF
$(find "$CAP_DIR" -name SKILL.md -not -path '*/\{*' 2>/dev/null | sort)
EOF

echo "  CSO: $PASS clean, $WARN warnings, $FAIL failures"
echo "PASS:$PASS" >> "$RESULTS"
echo "FAIL:$FAIL" >> "$RESULTS"
echo "WARN:$WARN" >> "$RESULTS"
