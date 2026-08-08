#!/usr/bin/env bash
# generation-smoke.sh — every platform generator produces its files (R62).
#
# Two tiers (12-§20):
#   first-class (claude-code, generic) — generate, then the generated tree is
#     further exercised by the gate/hook/reference CI jobs.
#   community (antigravity, codex, gemini-cli, opencode, hermes) — generation-smoke
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
hermes:SOUL.md
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
         HERMES_HOME="$HOME_DIR/hermes" \
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

# ── Opencode content pin: reviewer-binding note ──
# The task tool routes by agent name, and only a named agent carries a
# model binding. Without this note in the instructions AND the
# review-bearing commands, independent reviews dispatch as `general` and
# silently run on the primary model (observed live 2026-08-04).
target="$(mktemp -d)/proj"
mkdir -p "$target"
( cd "$target" && git init -q . 2>/dev/null || true )
( cd "$target" && SAGE_HOME="$HOME_DIR" \
  bash "$REPO_ROOT/bin/sage" init --no-memory --platform opencode ) \
  >/dev/null 2>&1
bind_ok=true
grep -q "Sub-agent dispatch on Opencode" "$target/AGENTS.md" 2>/dev/null || bind_ok=false
for c in build fix architect review; do
  grep -q "Sub-agent dispatch on Opencode" \
    "$target/.opencode/commands/$c.md" 2>/dev/null || bind_ok=false
done
grep -q "code quality" "$target/.opencode/agents/sage-reviewer.md" 2>/dev/null || bind_ok=false
# A6: the subagent role-binding resolver line must reach the commands too —
# and the generator must NOT emit the role agents themselves (a generated
# modelless agent is the inherit trap; a generated model is guessed spend).
grep -q "agent_binding.py sage-implementer" \
  "$target/.opencode/commands/build.md" 2>/dev/null || bind_ok=false
for a in sage-implementer sage-task-reviewer sage-branch-reviewer; do
  [ -f "$target/.opencode/agents/$a.md" ] && bind_ok=false
done
if [ "$bind_ok" = true ]; then
  N_PASS=$((N_PASS + 1))
  printf '  [PASS]  %-14s → reviewer binding in AGENTS.md + 4 commands + agent\n' "opencode"
else
  N_FAIL=$((N_FAIL + 1))
  printf '  [FAIL]  %-14s reviewer-binding note missing from generated tree\n' "opencode"
fi

# ── Update stamp pin: `sage update` must refresh sage-version ──
# Field report 2026-08-04: a project updated to vendored 1.3.12 still
# stamped "1.3.10" — update replaced sage/ wholesale but never touched
# the config record, so it lied a little more with every release.
# Non-semver placeholder on purpose: release.py's hardcoded-version scan
# rightly flags numeric literals, and the stamp rewrite never parses the
# old value anyway.
sed -i.bak 's/^sage-version:.*/sage-version: "stale-for-test"/' "$target/.sage/config.yaml"
rm -f "$target/.sage/config.yaml.bak"
( cd "$target" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" update ) \
  >/dev/null 2>&1
want_v="$(tr -d ' \t\n\r' < "$REPO_ROOT/VERSION")"
if grep -q "^sage-version: \"$want_v\"" "$target/.sage/config.yaml"; then
  N_PASS=$((N_PASS + 1))
  printf '  [PASS]  %-14s → update refreshes the config stamp (%s)\n' "opencode" "$want_v"
else
  N_FAIL=$((N_FAIL + 1))
  printf '  [FAIL]  %-14s update left a stale sage-version stamp: %s\n' "opencode" \
    "$(grep '^sage-version:' "$target/.sage/config.yaml" 2>/dev/null || echo missing)"
fi
rm -rf "$(dirname "$target")"

echo ""
printf '  pass %d · fail %d\n' "$N_PASS" "$N_FAIL"
[ "$N_FAIL" -eq 0 ] || exit 1
exit 0
