#!/usr/bin/env bash
# Tests for validate-token-budget.sh — the advisory word-count budget.
#
# Builds a throwaway core/capabilities tree of skills with controlled body sizes
# and asserts which exceed their per-skill_type budget. The count is BODY ONLY:
# YAML frontmatter and fenced ``` blocks are excluded. It is advisory — it MUST
# never emit a hard failure (AC5).
#
# Usage: bash develop/validators/contracts/validate-token-budget.test.sh
# Exit:  0 = all pass, 1 = at least one failure.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VALIDATOR="$HERE/validate-token-budget.sh"
PASS=0; FAIL=0
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
check() { if [ "$2" -eq 0 ]; then PASS=$((PASS+1)); green "  ✓ $1"; else FAIL=$((FAIL+1)); red "  ✗ $1"; fi; }

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
CAP="$ROOT/core/capabilities/review"
mkdir -p "$CAP"

words() { awk -v n="$1" 'BEGIN{for(i=0;i<n;i++) printf "lorem "; print ""}'; }

# mk_skill <name> <skill_type|""> <prose_words> <fence_words> <fm_filler_words>
mk_skill() {
  local name="$1" stype="$2" pw="$3" fw="$4" fmw="${5:-0}"
  local d="$CAP/$name"; mkdir -p "$d"
  {
    echo "---"
    echo "name: $name"
    printf 'description: >\n  fixture %s\n' "$(words "$fmw")"
    echo 'version: "1.0.0"'
    echo "modes: [build]"
    [ -n "$stype" ] && echo "skill_type: $stype"
    echo "---"
    echo ""
    echo "# $name"
    echo ""
    words "$pw"
    if [ "$fw" -gt 0 ]; then
      echo '```text'
      words "$fw"
      echo '```'
    fi
  } > "$d/SKILL.md"
}

#         name             type         prose fence fmfiller
mk_skill  disc-600         discipline   600   0     0     # > 500 → WARN
mk_skill  disc-400         discipline   400   0     0     # < 500 → silent
mk_skill  fenced-heavy     discipline   100   800   0     # prose 100, fence excluded → silent
mk_skill  big-frontmatter  discipline   100   0     600   # body 100, fm excluded → silent
mk_skill  methodology-650  methodology  650   0     0     # < 700 → silent
mk_skill  methodology-800  methodology  800   0     0     # > 700 → WARN
mk_skill  other-1000       ""           1000  0     0     # untyped > 900 → WARN (and worst)

OUT="$(bash "$VALIDATOR" "$ROOT" 2>&1)"
RESULTS="/tmp/sage-test-results-token-budget"

echo ""
echo "── validate-token-budget.sh tests ──"

flagged() { printf '%s' "$OUT" | grep -qE "(⚠|WARN).*\b$1\b"; }

flagged disc-600        && check "600-word discipline skill → WARN" 0       || check "600-word discipline skill → WARN" 1
flagged disc-400        && check "400-word discipline skill → silent" 1     || check "400-word discipline skill → silent" 0
flagged fenced-heavy    && check "fence-heavy skill → silent (fences excluded, AC3)" 1 || check "fence-heavy skill → silent (fences excluded, AC3)" 0
flagged big-frontmatter && check "big-frontmatter skill → silent (frontmatter excluded)" 1 || check "big-frontmatter skill → silent (frontmatter excluded)" 0
flagged methodology-650 && check "650-word methodology → silent (< 700)" 1  || check "650-word methodology → silent (< 700)" 0
flagged methodology-800 && check "800-word methodology → WARN (> 700)" 0    || check "800-word methodology → WARN (> 700)" 1
flagged other-1000      && check "1000-word untyped → WARN (> 900)" 0       || check "1000-word untyped → WARN (> 900)" 1

# Worst-first ordering: other-1000 (1000) must appear before disc-600 (600) in the output.
n_other="$(printf '%s' "$OUT" | grep -nE "\bother-1000\b" | head -1 | cut -d: -f1)"
n_disc="$(printf '%s'  "$OUT" | grep -nE "\bdisc-600\b"   | head -1 | cut -d: -f1)"
{ [ -n "$n_other" ] && [ -n "$n_disc" ] && [ "$n_other" -lt "$n_disc" ]; } \
  && check "worst-first ordering (other-1000 before disc-600)" 0 \
  || check "worst-first ordering (other-1000 before disc-600)" 1

# AC5 — never a hard failure: zero ERR lines, and the FAIL tally is 0.
nerr="$(grep -c "^ERR:" "$RESULTS" 2>/dev/null || true)"; nerr="${nerr:-0}"
[ "$nerr" -eq 0 ] && check "no ERR lines emitted (advisory only, AC5)" 0 || check "no ERR lines emitted (advisory only, AC5)" 1
grep -q "^FAIL:0" "$RESULTS" && check "FAIL tally is 0 (AC2/AC5)" 0 || check "FAIL tally is 0 (AC2/AC5)" 1
# AC2 — contributes 0 passes (must not inflate the PASS total).
grep -q "^PASS:0" "$RESULTS" && check "PASS tally is 0 (warnings only, AC2)" 0 || check "PASS tally is 0 (warnings only, AC2)" 1

echo ""
echo "  validate-token-budget: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
