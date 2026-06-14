#!/usr/bin/env bash
# Tests for run-skill-test.sh — the deterministic marker-grep verdict.
#
# These tests exercise ONLY the verdict path, feeding known transcripts via
# --transcript so no sub-agent dispatch is involved. The verdict must be a
# pure function of (declared marker, transcript, phase): marker present/absent
# grepped against the transcript, compared to what the phase expects.
#
# Usage: bash develop/skill-tests/run-skill-test.test.sh
# Exit:  0 = all pass, 1 = at least one failure.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$HERE/run-skill-test.sh"
FIX="$HERE/fixtures"
PRESENT="$FIX/transcripts/marker-present.txt"
ABSENT="$FIX/transcripts/marker-absent.txt"

PASS=0
FAIL=0

green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }

# assert_case <name> <expected-exit> <expected-substring-in-output> <args...>
assert_case() {
  local name="$1" want_exit="$2" want_sub="$3"; shift 3
  local out rc
  out="$(bash "$HARNESS" "$@" 2>&1)"; rc=$?
  local ok=1
  if [ "$rc" -ne "$want_exit" ]; then ok=0; fi
  if [ -n "$want_sub" ] && ! printf '%s' "$out" | grep -qF "$want_sub"; then ok=0; fi
  if [ "$ok" -eq 1 ]; then
    PASS=$((PASS + 1)); green "  ✓ $name"
  else
    FAIL=$((FAIL + 1))
    red "  ✗ $name"
    red "      expected exit=$want_exit substring='$want_sub'"
    red "      got      exit=$rc"
    printf '      output: %s\n' "$out"
  fi
}

echo ""
echo "── run-skill-test.sh verdict tests ──"

# 1. GREEN, marker present in transcript → PASS, exit 0.
assert_case "GREEN marker-present → PASS" 0 '"verdict":"PASS"' \
  "$FIX/skill-ok" --green --transcript "$PRESENT"

# 2. GREEN, marker absent in transcript → FAIL, exit 1 (the agent skipped).
assert_case "GREEN marker-absent → FAIL" 1 '"verdict":"FAIL"' \
  "$FIX/skill-ok" --green --transcript "$ABSENT"

# 3. RED, marker absent in transcript → PASS, exit 0 (baseline confirmed).
assert_case "RED marker-absent → PASS" 0 '"verdict":"PASS"' \
  "$FIX/skill-ok" --red --transcript "$ABSENT"

# 4. RED, marker present in transcript → FAIL, exit 1 (baseline contaminated).
assert_case "RED marker-present → FAIL" 1 '"verdict":"FAIL"' \
  "$FIX/skill-ok" --red --transcript "$PRESENT"

# 5. Missing TESTS.md → setup error, exit 2.
assert_case "missing TESTS.md → exit 2" 2 '' \
  "$FIX/skill-no-tests" --green --transcript "$PRESENT"

# 6. Missing compliance_marker → setup error, exit 2.
assert_case "missing compliance_marker → exit 2" 2 '' \
  "$FIX/skill-no-marker" --green --transcript "$PRESENT"

# 7. marker_present boolean reflects the grep (true on present, false on absent).
assert_case "marker_present:true on present" 0 '"marker_present":true' \
  "$FIX/skill-ok" --green --transcript "$PRESENT"
assert_case "marker_present:false on absent" 0 '"marker_present":false' \
  "$FIX/skill-ok" --red --transcript "$ABSENT"

# 8. Dispatch unavailable (no --transcript, non-interactive stdin) → exit 2,
#    with a manual-mode instruction (AC7 / C2). stdin is closed via </dev/null.
assert_case "dispatch unavailable → exit 2 (manual mode)" 2 'run-skill-test.sh' \
  "$FIX/skill-ok" --green </dev/null

echo ""
echo "  run-skill-test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
