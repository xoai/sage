#!/usr/bin/env bash
# generation-smoke.sh — every platform generator produces its files (R62).
#
# Two tiers (12-§20):
#   first-class (claude-code, generic) — generate, then the generated tree is
#     further exercised by the gate/hook/reference CI jobs.
#   community (antigravity, codex, gemini-cli, opencode) — generation-smoke
#     only: the generator runs and emits its instructions file.
#
# This job proves each generator at least runs and writes output. It does NOT
# exercise the community quality chain (there isn't one — see each STATUS.md).
#
# Usage: bash develop/validators/platforms/generation-smoke.sh
# Exit:  0 = every generator produced output | 1 = one failed

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
N_PASS=0
N_FAIL=0

# platform : expected-output-file (relative to the target project).
# Only platforms with a generator are smoked. `generic` ships a static
# AGENTS.md baseline, not a generator, so it is not listed here.
CASES="
claude-code:CLAUDE.md
antigravity:GEMINI.md
codex:AGENTS.md
gemini-cli:GEMINI.md
opencode:AGENTS.md
"

HOME_DIR="$(mktemp -d)"
ln -s "$REPO_ROOT" "$HOME_DIR/framework"
trap 'rm -rf "$HOME_DIR"' EXIT

echo "═══ Platform generation smoke ═══"
echo ""

for entry in $CASES; do
  [ -z "$entry" ] && continue
  platform="${entry%%:*}"
  expected="${entry#*:}"
  target="$(mktemp -d)/proj"
  mkdir -p "$target"
  ( cd "$target" && git init -q . 2>/dev/null || true )

  out=$( cd "$target" && SAGE_HOME="$HOME_DIR" \
         bash "$REPO_ROOT/bin/sage" init --no-memory --platform "$platform" 2>&1 )
  rc=$?

  if [ "$rc" -eq 0 ] && [ -f "$target/$expected" ]; then
    N_PASS=$((N_PASS + 1))
    printf '  [PASS]  %-14s → %s\n' "$platform" "$expected"
  else
    N_FAIL=$((N_FAIL + 1))
    printf '  [FAIL]  %-14s (exit %s, %s %s)\n' "$platform" "$rc" "$expected" \
      "$([ -f "$target/$expected" ] && echo present || echo MISSING)"
    printf '%s\n' "$out" | tail -8 | sed 's/^/          | /'
  fi
  rm -rf "$(dirname "$target")"
done

echo ""
printf '  pass %d · fail %d\n' "$N_PASS" "$N_FAIL"
[ "$N_FAIL" -eq 0 ] || exit 1
exit 0
