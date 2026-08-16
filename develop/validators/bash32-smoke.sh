#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# bash32-smoke.sh
#
# Behavioral smoke test for bash 3.2 compatibility. Designed to run
# INSIDE a real bash 3.2 (the macOS system shell, or the `bash:3.2`
# Docker image used by CI) — it proves:
#
#   1. The bash 3.2 empty-array quirk is actually present on this
#      shell (otherwise the rest of the test proves nothing).
#   2. The empty-safe idiom  ${arr[@]+"${arr[@]}"}  works — both the
#      [@] and [*] forms, empty and non-empty.
#   3. Every shell script Sage ships parses under bash 3.2 (`bash -n`).
#
# This is the runtime counterpart to check-bash-arrays.py (which is
# static). CI runs it via:
#   docker run --rm -v "$PWD":/sage -w /sage bash:3.2 \
#     bash develop/validators/bash32-smoke.sh
#
# Exit: 0 = all good   |   1 = a check failed
# ═══════════════════════════════════════════════════════════════
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../.." && pwd)"
cd "$REPO_ROOT"

fail=0

echo "── bash version ──"
bash --version | head -1
echo ""

# ── 1. The quirk must be present, else this test is meaningless ───────
echo "── Check 1: empty-array quirk is present on this shell ──"
# The "${a[@]}" below is the DELIBERATE unsafe payload under test — it
# is supposed to abort on bash 3.2, so the lint marker exempts the line.
if bash -c 'set -u; a=(); echo "${a[@]}"' >/dev/null 2>&1; then  # bash-array-ok
  echo "  ✗ This bash does NOT abort on empty \"\${a[@]}\" under set -u."
  echo "    It is bash >= 4.4 — run this test under bash 3.2 to be meaningful."
  fail=1
else
  echo "  ✓ empty \"\${a[@]}\" aborts under set -u (bash 3.2 quirk confirmed)"
fi
echo ""

# ── 2. The empty-safe idiom must work ─────────────────────────────────
echo "── Check 2: empty-safe idiom \${arr[@]+\"\${arr[@]}\"} works ──"
idiom_ok=1

# [@] empty → expands to nothing, no abort
if ! bash -c 'set -euo pipefail; a=(); printf "%s" ${a[@]+"${a[@]}"}; echo "ok"' \
     >/dev/null 2>&1; then
  echo "  ✗ [@] empty form aborted"
  idiom_ok=0
fi
# [@] non-empty → element integrity (spaces preserved)
out="$(bash -c 'set -euo pipefail; a=("x" "y z"); printf "[%s]" ${a[@]+"${a[@]}"}')"
if [ "$out" != "[x][y z]" ]; then
  echo "  ✗ [@] non-empty form mangled elements: got '$out', want '[x][y z]'"
  idiom_ok=0
fi
# [*] empty → expands to nothing, no abort
if ! bash -c 'set -euo pipefail; a=(); s="${a[*]+"${a[*]}"}"; echo "[$s]"' \
     >/dev/null 2>&1; then
  echo "  ✗ [*] empty form aborted"
  idiom_ok=0
fi
# [*] non-empty → space-joined
out="$(bash -c 'set -euo pipefail; a=("a b" "c"); echo "${a[*]+"${a[*]}"}"')"
if [ "$out" != "a b c" ]; then
  echo "  ✗ [*] non-empty form wrong: got '$out', want 'a b c'"
  idiom_ok=0
fi

if [ "$idiom_ok" -eq 1 ]; then
  echo "  ✓ [@] and [*], empty and non-empty — all correct"
else
  fail=1
fi
echo ""

# ── 3. Every shell script parses under bash 3.2 ───────────────────────
echo "── Check 3: bash -n syntax check on all shell scripts ──"
# ── Bounded-execution helper: EXERCISED, not just parsed ──
# The watchdog is the one gate mechanism whose failure mode is a hang;
# parsing proves nothing about kill/wait semantics under bash 3.2.
echo "── sage-bounded.sh under this bash ──"
if . core/gates/scripts/sage-bounded.sh 2>/dev/null; then
  SB_TMP=$(mktemp -d "${TMPDIR:-/tmp}/sb32-XXXXXX" 2>/dev/null) || SB_TMP=""
  if [ -n "$SB_TMP" ]; then
    sb_start=$(date +%s)
    sage_bounded_run "$SB_TMP/out" "$SB_TMP/sentinel" 1 "$SB_TMP" sleep 30
    sb_rc=$?
    sb_elapsed=$(( $(date +%s) - sb_start ))
    if [ -f "$SB_TMP/sentinel" ] && [ "$sb_rc" -ne 0 ] && [ "$sb_elapsed" -lt 20 ]; then
      echo "  ✓ watchdog kills a hung command (rc=$sb_rc, ${sb_elapsed}s) and writes the sentinel"
    else
      echo "  ✗ watchdog failed (rc=$sb_rc, elapsed=${sb_elapsed}s, sentinel=$([ -f "$SB_TMP/sentinel" ] && echo yes || echo no))"
      fail=1
    fi
    sage_bounded_run "$SB_TMP/out2" "$SB_TMP/sentinel2" 30 "$SB_TMP" true
    if [ $? -eq 0 ] && [ ! -f "$SB_TMP/sentinel2" ]; then
      echo "  ✓ fast command unaffected"
    else
      echo "  ✗ fast path broken"
      fail=1
    fi
    rm -rf "$SB_TMP"
  else
    echo "  ✗ could not create a temp dir for the exercise"
    fail=1
  fi
else
  echo "  ✗ sage-bounded.sh failed to source"
  fail=1
fi
echo ""

syntax_ok=1
# bin/sage has no .sh extension — check it explicitly.
for f in bin/sage $(find . -name '*.sh' \
                      -not -path './.git/*' \
                      -not -path './node_modules/*' \
                      | sort); do
  [ -f "$f" ] || continue
  if ! bash -n "$f" 2>/dev/null; then
    echo "  ✗ syntax error: $f"
    syntax_ok=0
  fi
done
if [ "$syntax_ok" -eq 1 ]; then
  echo "  ✓ all shell scripts parse under bash 3.2"
else
  fail=1
fi
echo ""

if [ "$fail" -ne 0 ]; then
  echo "FAIL — bash 3.2 compatibility check failed."
  exit 1
fi
echo "OK — bash 3.2 compatibility verified."
exit 0
