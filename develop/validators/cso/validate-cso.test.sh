#!/usr/bin/env bash
# Tests for validate-cso.sh — the CSO description heuristic.
#
# Builds a throwaway core/capabilities tree of skills with specific descriptions
# and asserts which get flagged as workflow-summarizing (CSO violations). The
# headline case (AC3): the ACTUAL current auto-qa description, which enumerates
# its five checks, MUST be flagged and the offending phrase MUST be named; the
# rewritten triggering-conditions-only description MUST pass.
#
# Usage: bash develop/validators/cso/validate-cso.test.sh
# Exit:  0 = all pass, 1 = at least one failure.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VALIDATOR="$HERE/validate-cso.sh"
PASS=0; FAIL=0
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
check() { if [ "$2" -eq 0 ]; then PASS=$((PASS+1)); green "  ✓ $1"; else FAIL=$((FAIL+1)); red "  ✗ $1"; fi; }

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
CAP="$ROOT/core/capabilities/review"
mkdir -p "$CAP"

mk_skill() { # mk_skill <name> <skill_type|""> <description-block...>
  local name="$1" stype="$2"; shift 2
  local d="$CAP/$name"; mkdir -p "$d"
  {
    echo "---"
    echo "name: $name"
    echo "description: >"
    local line
    for line in "$@"; do echo "  $line"; done
    echo 'version: "1.0.0"'
    echo "modes: [build]"
    [ -n "$stype" ] && echo "skill_type: $stype"
    echo "---"
    echo ""
    echo "# $name"
    echo "Body."
  } > "$d/SKILL.md"
}

# Offender: the ACTUAL current auto-qa description (enumerates five checks).
mk_skill auto-qa-old discipline \
  "Automatic sub-agent code verification after quality gates pass." \
  "Independent context window. Checks spec-implementation alignment," \
  "test coverage, error handling, boundary conditions, and integration" \
  "consistency. 60 seconds, code-only, advisory."

# Clean rewrite: triggering conditions only.
mk_skill auto-qa-new discipline \
  "Use after implementation passes the quality gates, when a change needs an" \
  "independent pass over the code before it ships, or when the user asks to" \
  '"QA this", "check the implementation", or "verify it matches the spec".'

# Numeric enumeration offender (coding-principles style).
mk_skill principles-old "" \
  "Seven universal coding principles applied during implementation."

# Process-sequencing offender.
mk_skill sequencing-old "" \
  "Reads the plan, then dispatches each task, then validates the result."

OUT="$(bash "$VALIDATOR" "$ROOT" 2>&1)"

echo ""
echo "── validate-cso.sh tests ──"

# A flag is a ⚠ (warn) or ✗ (fail) line naming the skill; a ✓ line is NOT a flag.
flagged() { printf '%s' "$1" | grep -qE "(⚠|✗).*$2"; }

# auto-qa-old flagged, and the offending phrase is named (AC3).
flagged "$OUT" "auto-qa-old"; check "auto-qa-old is flagged" $?
printf '%s' "$OUT" | grep -qF "Checks spec-implementation alignment"; check "offending phrase named in output (AC3)" $?

# auto-qa-new passes (not flagged).
if flagged "$OUT" "auto-qa-new"; then nrc=1; else nrc=0; fi
check "auto-qa-new (clean rewrite) not flagged" "$nrc"

# numeric + sequencing offenders flagged.
flagged "$OUT" "principles-old"; check "numeric enumeration flagged (Seven … principles)" $?
flagged "$OUT" "sequencing-old"; check "process-sequencing flagged (then …)" $?

# Warn mode (default): violations are WARNINGS, not failures — 0 ERR lines.
nerr_warn="$(grep -c "^ERR:" /tmp/sage-test-results-cso 2>/dev/null || true)"; nerr_warn="${nerr_warn:-0}"
[ "$nerr_warn" -eq 0 ]; check "warn mode: no hard failures (got $nerr_warn ERR)" $?

# Enforce mode: a DISCIPLINE skill violation becomes a hard FAIL.
OUT2="$(CSO_ENFORCE=1 bash "$VALIDATOR" "$ROOT" 2>&1)"
nerr_enforce="$(grep -c "^ERR:" /tmp/sage-test-results-cso 2>/dev/null || true)"; nerr_enforce="${nerr_enforce:-0}"
[ "$nerr_enforce" -ge 1 ]; check "enforce mode: discipline violation hard-fails (got $nerr_enforce ERR)" $?
# Non-discipline offenders stay warnings even under enforce.
printf '%s' "$OUT2" | grep -qE "✗.*principles-old" && irc=1 || irc=0
check "enforce mode: non-discipline offender stays a warning" "$irc"

echo ""
echo "  validate-cso: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
