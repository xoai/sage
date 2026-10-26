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

# ── Claude Code install pins (review 2026-10-26: C1, C2, C4, X3, X5, X6) ──
# What `sage init` GENERATES, checked directly — the evals measure model
# behaviour and caught none of these.
cc_check() {  # $1 = label, $2 = "ok" | anything else
  if [ "$2" = ok ]; then
    N_PASS=$((N_PASS + 1)); printf '  [PASS]  %-14s → %s\n' "claude-code" "$1"
  else
    N_FAIL=$((N_FAIL + 1)); printf '  [FAIL]  %-14s %s\n' "claude-code" "$1"
  fi
}
cc_new() {  # a fresh git project; prints its path
  local d; d="$(mktemp -d)/proj"; mkdir -p "$d/.claude"
  ( cd "$d" && git init -q . 2>/dev/null || true ); echo "$d"
}
cc_run() {  # cc_run <project> init|update [args...]
  local d="$1"; shift
  if [ "$1" = init ]; then
    ( cd "$d" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" init --no-memory \
        --platform claude-code ) >/dev/null 2>&1
  else
    ( cd "$d" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" update </dev/null ) >/dev/null 2>&1
  fi
}
mode_of() { python3 -c 'import os,sys;print(oct(os.stat(sys.argv[1]).st_mode & 0o777))' "$1"; }

target="$(cc_new)"
printf '# Team rules\n\nNever edit /build output by hand.\n' > "$target/CLAUDE.md"
printf '{\n  "permissions": {"allow": ["Bash(npm test)"]}\n}\n' > "$target/.claude/settings.local.json"
( cd "$target" && SAGE_HOME="$HOME_DIR" \
  bash "$REPO_ROOT/bin/sage" init --no-memory --platform claude-code ) >/dev/null 2>&1

# C4: the user's CLAUDE.md survives, with Sage's instructions in a marked block,
# and an update replaces the block rather than stacking a second one.
r=ok
head -1 "$target/CLAUDE.md" | grep -qx '# Team rules' || r=bad
grep -q 'Never edit /build output by hand.' "$target/CLAUDE.md" || r=bad
grep -q '^# Sage — Project Instructions' "$target/CLAUDE.md" || r=bad
cp "$target/CLAUDE.md" "$target/.claude-md-before"
( cd "$target" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" update </dev/null ) >/dev/null 2>&1
cmp -s "$target/CLAUDE.md" "$target/.claude-md-before" || r=bad
[ "$(grep -c '^<!-- BEGIN SAGE' "$target/CLAUDE.md")" = 1 ] || r=bad
rm -f "$target/.claude-md-before"
cc_check "user CLAUDE.md kept; Sage block merged once across init + update" "$r"

# C4: saved permissions survive init + update; the session hook is registered once.
r=ok
python3 - "$target/.claude/settings.local.json" <<'PY' || r=bad
import json, sys
d = json.load(open(sys.argv[1]))
assert d["permissions"]["allow"] == ["Bash(npm test)"], d
cmds = [h["command"] for e in d["hooks"]["SessionStart"] for h in e["hooks"]]
assert len([c for c in cmds if "sage-session-init.sh" in c]) == 1, cmds
assert all("$CLAUDE_PROJECT_DIR" in c for c in cmds), cmds
PY
cc_check "settings.local.json permissions kept; one session hook" "$r"

# C4: CRLF — a Windows checkout gets its block refreshed, not a second one.
r=ok
python3 -c 'import sys;p=sys.argv[1];d=open(p,"rb").read().replace(b"\r\n",b"\n");open(p,"wb").write(d.replace(b"\n",b"\r\n"))' "$target/CLAUDE.md"
cc_run "$target" update
[ "$(tr -d '\r' < "$target/CLAUDE.md" | grep -c '^<!-- BEGIN SAGE')" = 1 ] || r=bad
[ "$(grep -c $'\r$' "$target/CLAUDE.md")" = "$(wc -l < "$target/CLAUDE.md" | tr -d ' ')" ] || r=bad
cc_check "CRLF CLAUDE.md: one block, still CRLF throughout" "$r"

# C4: malformed markers (END deleted) → the file is left exactly as it is.
r=ok
grep -v '^<!-- END SAGE' "$target/CLAUDE.md" > "$target/.cm" && cat "$target/.cm" > "$target/CLAUDE.md"
cp "$target/CLAUDE.md" "$target/.cm"
cc_run "$target" update
cmp -s "$target/CLAUDE.md" "$target/.cm" || r=bad
rm -f "$target/.cm"
cc_check "malformed SAGE markers: CLAUDE.md left untouched" "$r"

# C1/C2: every generated skill registers; no Hermes port; nothing shadows /sage;
# the folded-description skills the old loop dropped are present.
r=ok
python3 "$target/sage/runtime/tools/skill_frontmatter.py" check-claude \
  "$target/.claude/skills" >/dev/null 2>&1 || r=bad
for s in sage-memory sage-self-learning sage-ontology api web baas autoresearch; do
  [ -f "$target/.claude/skills/$s/SKILL.md" ] || r=bad
done
[ -e "$target/.claude/skills/sage" ] && r=bad
[ -f "$target/.claude/commands/sage.md" ] || r=bad
cc_check "every .claude/skills entry registers; /sage reaches its command" "$r"

# X3: nothing vendored under sage/ is a file `node --test` would pick up.
r=ok
found=$(cd "$target" && find sage -type f \( -name '*.test.*' -o -name '*-test.*' \
  -o -name '*_test.*' -o -name 'test-*.*' -o -name 'test.*' -o -path '*/test/*' \) \
  \( -name '*.js' -o -name '*.mjs' -o -name '*.cjs' \) 2>/dev/null)
[ -z "$found" ] || r=bad
cc_check "vendored sage/ has no test files for npm test to discover${found:+: $found}" "$r"

# X5: config.yaml comments arrive whole — no backtick span executed away.
r=ok
grep -q 'Escape with `tier: tier1` on a manifest' "$target/.sage/config.yaml" || r=bad
grep -q '`manifest.py scope derive`' "$target/.sage/config.yaml" || r=bad
grep -q '^command_prefix: false$' "$target/.sage/config.yaml" || r=bad
cc_check "config.yaml comments intact; values interpolated" "$r"

# X6: the vendored CLI refuses to update from itself and leaves sage/ in place.
r=ok
( cd "$target" && HOME="$target/.nohome" SAGE_HOME="" bash sage/bin/sage update </dev/null ) \
  >/dev/null 2>&1 && r=bad
[ -f "$target/sage/bin/sage" ] && [ -d "$target/sage/core" ] || r=bad
cc_check "sage/bin/sage update refuses; sage/ survives" "$r"
rm -rf "$(dirname "$target")"

# C4: a fresh install is marked too, so a user's own addition survives update;
# and the file gets an ordinary mode (not mktemp's 0600).
target="$(cc_new)"; rm -rf "$target/.claude"
cc_run "$target" init
r=ok
head -1 "$target/CLAUDE.md" | grep -q '^<!-- BEGIN SAGE.*Sage' || r=bad
printf '\n## Team rules\nAlways use pnpm.\n' >> "$target/CLAUDE.md"
cc_run "$target" update
grep -q 'Always use pnpm.' "$target/CLAUDE.md" || r=bad
: > "$target/.probe-mode"
[ "$(mode_of "$target/CLAUDE.md")" = "$(mode_of "$target/.probe-mode")" ] || r=bad
cc_check "fresh CLAUDE.md is marked; an addition after it survives update" "$r"

# C4: settings.json that does not parse is left alone; an EMPTY
# settings.local.json is just empty — the session hook still lands.
r=ok
printf '{\n  "permissions": {"allow": ["Bash(npm test)"],}\n}\n' > "$target/.claude/settings.json"
cp "$target/.claude/settings.json" "$target/.sj"
: > "$target/.claude/settings.local.json"
cc_run "$target" update
cmp -s "$target/.claude/settings.json" "$target/.sj" || r=bad
grep -q 'sage-session-init.sh' "$target/.claude/settings.local.json" || r=bad
rm -f "$target/.sj" "$target/.probe-mode"
cc_check "invalid settings.json untouched; empty settings.local.json merged" "$r"
rm -rf "$(dirname "$target")"

# C4: a Sage-written CLAUDE.md from before markers moves into a block once,
# with the old file (and anything the user added to it) backed up.
target="$(cc_new)"
printf '# Sage — Project Instructions\n\nold body\nMY OWN LINE\n' > "$target/CLAUDE.md"
cc_run "$target" init
r=ok
grep -q 'MY OWN LINE' "$target/CLAUDE.md" && r=bad
grep -l 'MY OWN LINE' "$target"/.sage/backups/CLAUDE.md.*.bak >/dev/null 2>&1 || r=bad
[ "$(grep -c '^<!-- BEGIN SAGE' "$target/CLAUDE.md")" = 1 ] || r=bad
cc_check "legacy Sage CLAUDE.md converted to a block, old file backed up" "$r"
rm -rf "$(dirname "$target")"

# C4: CLAUDE.md as a symlink (`ln -s AGENTS.md CLAUDE.md`) stays a symlink, and
# the block lands in the file it points at.
target="$(cc_new)"
printf '# Shared agent rules\n' > "$target/AGENTS.md"
ln -s AGENTS.md "$target/CLAUDE.md"
cc_run "$target" init
r=ok
[ -L "$target/CLAUDE.md" ] || r=bad
grep -q '^# Shared agent rules' "$target/AGENTS.md" || r=bad
grep -q '^<!-- BEGIN SAGE' "$target/AGENTS.md" || r=bad
cc_check "symlinked CLAUDE.md stays a symlink; its target gets the block" "$r"

# X6: a sage/ that is a SYMLINK to the framework is not the vendored CLI —
# the global update proceeds (only the link is replaced).
rm -rf "$target/sage"; ln -s "$REPO_ROOT" "$target/sage"
r=ok
cc_run "$target" update || r=bad
[ -d "$target/sage/core" ] && [ ! -L "$target/sage" ] || r=bad
[ -d "$REPO_ROOT/core" ] || r=bad
cc_check "global update over a symlinked sage/ proceeds" "$r"
rm -rf "$(dirname "$target")"

echo ""
printf '  pass %d · fail %d\n' "$N_PASS" "$N_FAIL"
[ "$N_FAIL" -eq 0 ] || exit 1
exit 0
