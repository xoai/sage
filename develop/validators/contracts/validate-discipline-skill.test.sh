#!/usr/bin/env bash
# Tests for validate-discipline-skill.sh.
#
# Builds a throwaway core/capabilities tree with one skill per case, runs the
# validator against it, and asserts the per-skill verdict. A skill is subject to
# the discipline contract ONLY when its frontmatter declares
# `skill_type: discipline`; untagged skills are exempt (AC4).
#
# Usage: bash develop/validators/contracts/validate-discipline-skill.test.sh
# Exit:  0 = all pass, 1 = at least one failure.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VALIDATOR="$HERE/validate-discipline-skill.sh"
PASS=0; FAIL=0
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
check() { # check <name> <condition-result(0/1)>
  if [ "$2" -eq 0 ]; then PASS=$((PASS+1)); green "  ✓ $1"; else FAIL=$((FAIL+1)); red "  ✗ $1"; fi
}

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
CAP="$ROOT/core/capabilities/review"
mkdir -p "$CAP"

# Helper: write a skill dir.
mk_skill() { # mk_skill <name> <skill_type|""> <marker|""> <has_tests:0/1> <tests_verdict> <has_table:0/1>
  local name="$1" stype="$2" marker="$3" has_tests="$4" verdict="$5" has_table="$6"
  local d="$CAP/$name"; mkdir -p "$d"
  {
    echo "---"
    echo "name: $name"
    echo "description: fixture skill for the discipline-skill validator tests."
    echo 'version: "1.0.0"'
    echo "modes: [build]"
    [ -n "$stype" ]  && echo "skill_type: $stype"
    [ -n "$marker" ] && echo "compliance_marker: \"$marker\""
    echo "---"
    echo ""
    echo "# $name"
    echo ""
    echo "Body."
    [ "$has_table" -eq 1 ] && { echo ""; echo "## Rationalization table"; echo "| a | b | c |"; echo "|---|---|---|"; }
  } > "$d/SKILL.md"
  if [ "$has_tests" -eq 1 ]; then
    {
      echo "---"
      echo "skill: $name"
      echo "green_verdict: $verdict"
      echo "---"
      echo "## Scenario"
      echo "fixture"
    } > "$d/TESTS.md"
  fi
}

#         name                stype       marker        tests verdict table
mk_skill  disc-complete       discipline  "X MARKER X"  1     PASS    1
mk_skill  disc-no-marker      discipline  ""            1     PASS    1
mk_skill  disc-no-tests       discipline  "X MARKER X"  0     PASS    1
mk_skill  disc-no-table       discipline  "X MARKER X"  1     PASS    0
mk_skill  disc-tests-not-pass discipline  "X MARKER X"  1     FAIL    1
mk_skill  ref-skill           ""          ""            0     PASS    0

# CRLF-endings complete discipline skill: must still be recognized and pass.
# Regression: a CRLF frontmatter delimiter (`---\r`) used to make fm_value return
# empty, so the skill was silently treated as NON-discipline and skipped —
# fail-silent non-enforcement. It must appear as a recognized PASS here.
mk_skill  disc-crlf           discipline  "X MARKER X"  1     PASS    1
sed -i 's/$/\r/' "$CAP/disc-crlf/SKILL.md" "$CAP/disc-crlf/TESTS.md"

OUT="$(bash "$VALIDATOR" "$ROOT" 2>&1)"

echo ""
echo "── validate-discipline-skill.sh tests ──"

printf '%s' "$OUT" | grep -qE "✓.*disc-complete";        check "complete discipline skill → PASS" $?
printf '%s' "$OUT" | grep -qE "✗.*disc-no-marker";       check "missing marker → FAIL" $?
printf '%s' "$OUT" | grep -qE "✗.*disc-no-tests";        check "missing TESTS.md → FAIL" $?
printf '%s' "$OUT" | grep -qE "✗.*disc-no-table";        check "missing rationalization table → FAIL" $?
printf '%s' "$OUT" | grep -qE "✗.*disc-tests-not-pass";  check "green_verdict≠PASS → FAIL" $?

# ref-skill is exempt: it must NOT appear as a failure.
if printf '%s' "$OUT" | grep -qE "✗.*ref-skill"; then ref_rc=1; else ref_rc=0; fi
check "non-discipline skill exempt (no FAIL)" "$ref_rc"

# CRLF discipline skill is recognized and enforced (passes here, not silently skipped).
printf '%s' "$OUT" | grep -qE "✓.*disc-crlf"; check "CRLF discipline skill recognized + enforced (not skipped)" $?

# Tally: exactly 4 FAIL lines were written to the results file.
nfail="$(grep -c "^ERR:" /tmp/sage-test-results-discipline 2>/dev/null || echo 0)"
[ "$nfail" -eq 4 ]; check "exactly 4 discipline failures recorded (got $nfail)" $?

echo ""
echo "  validate-discipline-skill: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
