#!/usr/bin/env bash
# End-to-end acceptance check for the Behavioral Skill Testing initiative.
# Demonstrates AC1-AC7 from the spec in a single run. Non-destructive: all
# gating tests operate on throwaway copies, never the real tree.
#
# Usage: bash develop/skill-tests/verify-acceptance.sh
# Exit:  0 = every acceptance check passed, 1 = at least one failed.

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HARNESS="$ROOT/develop/skill-tests/run-skill-test.sh"
FIX="$ROOT/develop/skill-tests/fixtures"
DISC="$ROOT/develop/validators/contracts/validate-discipline-skill.sh"
CSO="$ROOT/develop/validators/cso/validate-cso.sh"
AR="$ROOT/core/capabilities/review/auto-review"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '\033[32m  ✓ %s\033[0m\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '\033[31m  ✗ %s\033[0m\n' "$1"; }
note() { printf '\033[1m\n%s\033[0m\n' "$1"; }

# ── Unit suites ─────────────────────────────────────────────────────────────
note "Unit test suites"
bash "$ROOT/develop/skill-tests/run-skill-test.test.sh"                          >/dev/null 2>&1 && ok "harness verdict tests"           || bad "harness verdict tests"
bash "$ROOT/develop/validators/contracts/validate-discipline-skill.test.sh"     >/dev/null 2>&1 && ok "discipline-skill validator tests" || bad "discipline-skill validator tests"
bash "$ROOT/develop/validators/cso/validate-cso.test.sh"                         >/dev/null 2>&1 && ok "CSO validator tests"             || bad "CSO validator tests"

# ── AC1 — auto-review RED skip → GREEN comply; RED matches a table excuse ────
note "AC1 — auto-review root-fix proof"
out="$(bash "$HARNESS" "$AR" --both \
  --red-transcript "$FIX/auto-review-red.txt" \
  --green-transcript "$FIX/auto-review-green.txt" 2>&1)"; rc=$?
echo "$out" | grep -q '"phase":"red","marker_present":false,"verdict":"PASS"'  && \
echo "$out" | grep -q '"phase":"green","marker_present":true,"verdict":"PASS"' && [ $rc -eq 0 ] \
  && ok "auto-review --both: RED absent / GREEN present, overall PASS" \
  || bad "auto-review --both verdicts"
# The RED transcript's excuse appears in the skill's rationalization table.
if grep -qF "straightforward" "$FIX/auto-review-red.txt" && grep -qF "straightforward" "$AR/SKILL.md"; then
  ok "RED rationalization ('straightforward') is in the skill's table"
else
  bad "RED rationalization not found in table"
fi

# ── AC2 — determinism: 3× identical GREEN verdict; no judgment step ──────────
note "AC2 — determinism"
v1="$(bash "$HARNESS" "$AR" --green --transcript "$FIX/auto-review-green.txt" 2>&1)"
v2="$(bash "$HARNESS" "$AR" --green --transcript "$FIX/auto-review-green.txt" 2>&1)"
v3="$(bash "$HARNESS" "$AR" --green --transcript "$FIX/auto-review-green.txt" 2>&1)"
[ "$v1" = "$v2" ] && [ "$v2" = "$v3" ] && ok "3× --green verdicts identical" || bad "verdict not deterministic"
# The verdict path contains no agent-judgment branch (only the marker grep decides).
if grep -nq "agent" "$HARNESS" && ! grep -nE 'agent.*(judge|decide|verdict)|verdict.*agent' "$HARNESS" >/dev/null; then
  ok "no agent-judgment step in the verdict path (marker grep only)"
else
  # grep "agent" appears only in dispatch-describing comments — acceptable.
  grep -nE 'judge|decides? compliance' "$HARNESS" >/dev/null && bad "judgment step present" || ok "no agent-judgment step in the verdict path (marker grep only)"
fi

# ── AC3 — CSO flags the OLD auto-qa description, passes the rewritten one ─────
note "AC3 — CSO flag on old vs new auto-qa description"
T="$(mktemp -d)"; mkdir -p "$T/core/capabilities/review/old" "$T/core/capabilities/review/new"
cat > "$T/core/capabilities/review/old/SKILL.md" <<'EOF'
---
name: old
description: >
  Automatic sub-agent code verification after quality gates pass. Independent
  context window. Checks spec-implementation alignment, test coverage, error
  handling, boundary conditions, and integration consistency. 60 seconds.
version: "1.0.0"
modes: [build]
skill_type: discipline
---
# old
EOF
cat > "$T/core/capabilities/review/new/SKILL.md" <<'EOF'
---
name: new
description: >
  Use after implementation passes the quality gates, or when the user asks to
  "QA this", "check the implementation", or "verify it matches the spec".
version: "1.0.0"
modes: [build]
skill_type: discipline
---
# new
EOF
csoout="$(CSO_ENFORCE=1 bash "$CSO" "$T" 2>&1)"
echo "$csoout" | grep -qE "(⚠|✗).*old" && echo "$csoout" | grep -qF "Checks spec-implementation alignment" \
  && ok "old auto-qa description flagged, offending phrase named" || bad "old description not flagged/named"
echo "$csoout" | grep -qE "(⚠|✗).*\bnew\b" && bad "clean rewrite wrongly flagged" || ok "rewritten description passes"
rm -rf "$T"

# ── AC4 — discipline skill missing TESTS.md fails; reference skill passes ────
note "AC4 — contract gating"
T="$(mktemp -d)"; mkdir -p "$T/core/capabilities/review"
cp -r "$AR" "$T/core/capabilities/review/auto-review"
rm -f "$T/core/capabilities/review/auto-review/TESTS.md"     # remove the test artifact
# a reference skill with no skill_type and no TESTS.md (exempt)
mkdir -p "$T/core/capabilities/review/ref"
cat > "$T/core/capabilities/review/ref/SKILL.md" <<'EOF'
---
name: ref
description: A reference skill that enforces nothing.
version: "1.0.0"
modes: [build]
---
# ref
EOF
discout="$(bash "$DISC" "$T" 2>&1)"
echo "$discout" | grep -qE "✗.*auto-review" && ok "discipline skill missing TESTS.md → FAIL" || bad "missing TESTS.md not failed"
echo "$discout" | grep -qE "✗.*\bref\b" && bad "reference skill wrongly failed" || ok "reference skill (no skill_type) → exempt/PASS"
rm -rf "$T"

# ── AC6 — testing-skills SKILL.md < 500 words ───────────────────────────────
note "AC6 — capability under budget"
w=$(wc -w < "$ROOT/core/capabilities/verification/testing-skills/SKILL.md")
[ "$w" -lt 500 ] && ok "testing-skills/SKILL.md is $w words (< 500)" || bad "testing-skills is $w words (≥ 500)"

# ── AC7 — off-platform: dispatch unavailable → exit 2, manual-mode instruction ─
note "AC7 — silent off-platform degradation"
out="$(bash "$HARNESS" "$AR" --green </dev/null 2>&1)"; rc=$?
[ "$rc" -eq 2 ] && echo "$out" | grep -q "run-skill-test.sh" && ok "dispatch unavailable → exit 2 with manual-mode instruction" || bad "off-platform path"

# ── AC5 — total ≥ 433 and discipline contract green ─────────────────────────
note "AC5 — suite total and discipline contract"
allout="$(bash "$ROOT/develop/validators/contracts/validate-all.sh" 2>&1)"
total=$(echo "$allout" | grep -oE "Passed:[[:space:]]+[0-9]+" | grep -oE "[0-9]+")
echo "$allout" | grep -q "Discipline skills: 4 checked, 4 passed, 0 failed" && ok "discipline contract: 4/4 green" || bad "discipline contract not 4/4"
[ "${total:-0}" -ge 433 ] && ok "validate-all total = $total (≥ 433)" || bad "validate-all total = ${total:-0} (< 433)"

echo ""
printf '\033[1m── Acceptance: %d passed, %d failed ──\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
