#!/usr/bin/env bash
# generation-smoke.sh — every platform generator produces its files (R62).
#
# Two tiers (12-§20):
#   first-class (claude-code, generic) — generate, then the generated tree is
#     further exercised by the gate/hook/reference CI jobs.
#   community (antigravity, codex, gemini-cli, opencode) — generation-smoke
#     only: the generator runs, emits its instructions file, and keeps a
#     user's own AGENTS.md / GEMINI.md (Sage's text in a marked block).
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
# The operator's own Claude settings must not change what init writes here (a
# globally enabled Sage plugin would) — every run reads an empty config dir.
CLAUDE_CONFIG_DIR="$(mktemp -d)"; export CLAUDE_CONFIG_DIR
trap 'rm -rf "$HOME_DIR" "$CLAUDE_CONFIG_DIR"' EXIT

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

# ── Community instructions files: a user's AGENTS.md / GEMINI.md survives ──
# Codex and Antigravity wrote theirs wholesale (the user's file gone, no
# backup); Opencode and Gemini CLI skipped a user's file and so installed Sage
# with no instructions at all. Same contract as CLAUDE.md (C4): Sage's text in
# a marked block, the user's lines kept, one block however often it runs.
md_check() {  # $1 = platform label, $2 = check label, $3 = "ok" | anything else
  if [ "$3" = ok ]; then
    N_PASS=$((N_PASS + 1)); printf '  [PASS]  %-14s → %s\n' "$1" "$2"
  else
    N_FAIL=$((N_FAIL + 1)); printf '  [FAIL]  %-14s %s\n' "$1" "$2"
  fi
}
md_run() {  # md_run <project> init <platforms> | md_run <project> update
  local d="$1"
  if [ "$2" = init ]; then
    ( cd "$d" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" init --no-memory \
        --platform "$3" </dev/null ) >/dev/null 2>&1
  else
    ( cd "$d" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" update </dev/null ) >/dev/null 2>&1
  fi
}
md_new() {  # a fresh git project; prints its path
  local d; d="$(mktemp -d)/proj"; mkdir -p "$d"
  ( cd "$d" && git init -q . 2>/dev/null || true ); echo "$d"
}
md_blocks() { tr -d '\r' < "$1" | grep -c '^<!-- BEGIN SAGE' || true; }
md_block_has() {  # md_block_has <file> <ERE> — a line inside the Sage block matches
  # awk, not `sed | grep -q`: grep -q quits early and, under pipefail, the
  # writer's SIGPIPE fails the pipeline on a block this size.
  tr -d '\r' < "$1" | awk -v re="$2" '/^<!-- BEGIN SAGE/ { in_b=1 } in_b && $0 ~ re { hit=1 }
    /^<!-- END SAGE/ { in_b=0 } END { exit !hit }'
}
md_kept() {  # md_kept <before> <after> — <after> starts with <before>, byte for byte
  head -c "$(wc -c < "$1" | tr -d ' ')" "$2" | cmp -s - "$1"
}
md_stale() {  # md_stale <file> — change a line inside Sage's block, so an update
  # that silently does nothing cannot pass for an idempotent one
  python3 -c 'import sys;p=sys.argv[1];d=open(p,"rb").read();assert b"## Engineering Principles" in d;open(p,"wb").write(d.replace(b"## Engineering Principles",b"STALE LINE",1))' "$1"
}

# platforms (comma-separated) : the file they write
MD_CASES="
codex:AGENTS.md
opencode:AGENTS.md
codex,opencode:AGENTS.md
antigravity:GEMINI.md
gemini-cli:GEMINI.md
antigravity,gemini-cli:GEMINI.md
"
for entry in $MD_CASES; do
  plats="${entry%%:*}"; f="${entry#*:}"

  # A user's own file: kept line for line, one block appended, update idempotent.
  d="$(md_new)"
  printf '# Team rules\n\nNever edit /build output by hand.\n' > "$d/$f"
  cp "$d/$f" "$d/.before"
  r=ok
  md_run "$d" init "$plats" || r=bad
  md_kept "$d/.before" "$d/$f" || r=bad
  [ "$(md_blocks "$d/$f")" = 1 ] || r=bad
  md_block_has "$d/$f" '^# Sage — Project Instructions' || r=bad
  grep -q '__CONSTITUTION_PLACEHOLDER__' "$d/$f" && r=bad
  md_block_has "$d/$f" '^## Engineering Principles' || r=bad
  cp "$d/$f" "$d/.after-init"
  md_stale "$d/$f"
  md_run "$d" update || r=bad
  cmp -s "$d/$f" "$d/.after-init" || r=bad
  md_run "$d" update || r=bad
  cmp -s "$d/$f" "$d/.after-init" || r=bad
  md_check "$plats" "user $f kept; one Sage block; updates refresh it to the same bytes" "$r"

  # CRLF: the user's Windows file keeps its bytes and gets a CRLF block, once.
  python3 -c 'import sys;p=sys.argv[1];d=open(p,"rb").read().replace(b"\r\n",b"\n");open(p,"wb").write(d.replace(b"\n",b"\r\n"))' "$d/$f"
  printf '# Team rules\r\n\r\nNever edit /build output by hand.\r\n' > "$d/.before"
  md_stale "$d/$f"
  r=ok
  md_run "$d" update || r=bad
  grep -q 'STALE LINE' "$d/$f" && r=bad
  md_kept "$d/.before" "$d/$f" || r=bad
  [ "$(md_blocks "$d/$f")" = 1 ] || r=bad
  [ "$(grep -c $'\r$' "$d/$f")" = "$(wc -l < "$d/$f" | tr -d ' ')" ] || r=bad
  md_check "$plats" "CRLF $f: block refreshed once, still CRLF throughout" "$r"
  rm -rf "$(dirname "$d")"

  # A Sage-written file from before markers: backed up once, then the block alone.
  d="$(md_new)"
  printf '# Sage — Project Instructions\n\nold body\nMY OWN LINE\n' > "$d/$f"
  r=ok
  md_run "$d" init "$plats" || r=bad
  grep -q 'MY OWN LINE' "$d/$f" && r=bad
  [ "$(md_blocks "$d/$f")" = 1 ] || r=bad
  [ "$(ls "$d/.sage/backups/$f".*.bak 2>/dev/null | wc -l | tr -d ' ')" = 1 ] || r=bad
  grep -l 'MY OWN LINE' "$d/.sage/backups/$f".*.bak >/dev/null 2>&1 || r=bad
  md_run "$d" update || r=bad
  [ "$(ls "$d/.sage/backups/$f".*.bak 2>/dev/null | wc -l | tr -d ' ')" = 1 ] || r=bad
  md_check "$plats" "legacy Sage $f moved to a block, old file backed up once" "$r"
  rm -rf "$(dirname "$d")"
done

# Codex: the 32 KiB cap is about what Codex reads — the whole AGENTS.md, the
# user's text included, not just Sage's block. (The warning alone proves
# little: the byte count it names must be the whole file's.)
d="$(md_new)"
python3 -c 'print("# Team rules\n" + "x" * 79 + "\n" + ("y" * 79 + "\n") * 400, end="")' > "$d/AGENTS.md"
out=$( cd "$d" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" init --no-memory \
         --platform codex </dev/null 2>&1 )
r=ok
[ "$(wc -c < "$d/AGENTS.md" | tr -d ' ')" -gt 32768 ] || r=bad
printf '%s' "$out" | grep -q "AGENTS.md is $(wc -c < "$d/AGENTS.md" | tr -d ' ') bytes" || r=bad
md_check "codex" "32 KiB cap counts the whole AGENTS.md and warns" "$r"
rm -rf "$(dirname "$d")"

# Codex: Sage's own text fits under the cap, with room left for the project's.
# Codex reads at most 32 KiB of AGENTS.md and drops the rest without a word, and
# the system skills came last: inlined, a fresh file was ~33.5 KB, so a default
# install lost the tail of Sage's instructions. They are listed now, each by a
# path the agent reads — so each path must exist in the project, or the list
# points at nothing. Opencode fills the same block after Codex, so the shared
# install is held to the same budget.
CODEX_CAP=32768
CODEX_HEADROOM=8192   # left for the project's own AGENTS.md text
for plats in codex codex,opencode; do
  d="$(md_new)"; r=ok; n=0; listed=0
  md_run "$d" init "$plats" || r=bad
  size=$(wc -c < "$d/AGENTS.md" | tr -d ' ')
  [ "$size" -le $((CODEX_CAP - CODEX_HEADROOM)) ] || r=bad
  for sk in "$REPO_ROOT"/core/system-skills/*/SKILL.md; do
    p="sage/core/system-skills/$(basename "$(dirname "$sk")")/SKILL.md"
    n=$((n + 1))
    if md_block_has "$d/AGENTS.md" "\`$p\`" && [ -f "$d/$p" ]; then
      listed=$((listed + 1))
    else
      r=bad
    fi
  done
  [ "$n" -gt 0 ] || r=bad
  md_check "$plats" "fresh AGENTS.md $size B (budget $((CODEX_CAP - CODEX_HEADROOM))); $listed/$n skills listed by a path that exists" "$r"
  rm -rf "$(dirname "$d")"
done

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

# Desktop: .worktreeinclude carries Sage's gitignored runtime into every worktree
# Claude Code makes. The user's own lines survive; update refreshes, never stacks.
r=ok
d="$(cc_new)"; printf '.env\n' > "$d/.worktreeinclude"
cc_run "$d" init
head -1 "$d/.worktreeinclude" | grep -qx '.env' || r=bad
for want in CLAUDE.md sage/ .sage/config.yaml .sage/gates; do
  sed -n '/^# BEGIN SAGE/,/^# END SAGE/p' "$d/.worktreeinclude" | grep -qxF "$want" || r=bad
done
grep -q '^\.claude' "$d/.worktreeinclude" && r=bad
sed -i.bak 's|^worktree_copy: \[|worktree_copy: [.sage/team-notes, |' "$d/.sage/config.yaml" && rm -f "$d/.sage/config.yaml.bak"
cc_run "$d" update
[ "$(grep -c '^# BEGIN SAGE' "$d/.worktreeinclude")" = 1 ] || r=bad
sed -n '/^# BEGIN SAGE/,/^# END SAGE/p' "$d/.worktreeinclude" | grep -qxF '.sage/team-notes' || r=bad
# Read as `sage worktree` reads it: [] copies none of .sage/; block style counts.
sed -i.bak 's|^worktree_copy: .*|worktree_copy: []|' "$d/.sage/config.yaml" && rm -f "$d/.sage/config.yaml.bak"
cc_run "$d" update
sed -n '/^# BEGIN SAGE/,/^# END SAGE/p' "$d/.worktreeinclude" | grep -q '^\.sage/' && r=bad
sed -n '/^# BEGIN SAGE/,/^# END SAGE/p' "$d/.worktreeinclude" | grep -qxF 'CLAUDE.md' || r=bad
sed -i.bak 's|^worktree_copy: .*|worktree_copy:\
  - .sage/config.yaml\
  - ".sage/gates"|' "$d/.sage/config.yaml" && rm -f "$d/.sage/config.yaml.bak"
cc_run "$d" update
for want in .sage/config.yaml .sage/gates; do
  sed -n '/^# BEGIN SAGE/,/^# END SAGE/p' "$d/.worktreeinclude" | grep -qxF "$want" || r=bad
done
# A scalar (malformed) value falls back to the defaults, as `sage worktree` does.
awk '/^worktree_copy:/ { print "worktree_copy: .sage/config.yaml"; skip=1; next }
     skip && /^[[:space:]]+-/ { next } { skip=0; print }' "$d/.sage/config.yaml" > "$d/.cfg" \
  && mv "$d/.cfg" "$d/.sage/config.yaml"
cc_run "$d" update
sed -n '/^# BEGIN SAGE/,/^# END SAGE/p' "$d/.worktreeinclude" | grep -qxF '.sage/constitution.md' || r=bad
cc_check ".worktreeinclude: Sage block from worktree_copy, user lines kept, one block" "$r"

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

# C3: CLAUDE.md carries the Quick reference — routing, tiers, checkpoints.
# (This project's CLAUDE.md went CRLF above; compare without the CRs.)
r=ok
tr -d '\r' < "$target/CLAUDE.md" > "$target/.qr"
grep -q '^## Quick reference$' "$target/.qr" || r=bad
for h in 'Routing — when no keyword matches' 'Tiers — what does not lower one' \
         'Checkpoints — the footers'; do
  grep -qx "### $h" "$target/.qr" || r=bad
done
cc_check "CLAUDE.md carries the Quick reference (routing, tiers, checkpoints)" "$r"

# X6: the vendored CLI refuses to update from itself and leaves sage/ in place.
r=ok
( cd "$target" && HOME="$target/.nohome" SAGE_HOME="" bash sage/bin/sage update </dev/null ) \
  >/dev/null 2>&1 && r=bad
[ -f "$target/sage/bin/sage" ] && [ -d "$target/sage/core" ] || r=bad
cc_check "sage/bin/sage update refuses; sage/ survives" "$r"
rm -rf "$(dirname "$target")"

# C3: with command_prefix on, the Quick reference's commands are prefixed too.
# (A fresh project: the one above ends with CLAUDE.md markers update won't touch.)
target="$(cc_new)"
cc_run "$target" init
r=ok
sed -i.bak 's/^command_prefix: false$/command_prefix: true/' "$target/.sage/config.yaml"
cc_run "$target" update
sed -n '/^## Quick reference$/,$p' "$target/CLAUDE.md" > "$target/.qr"
[ -s "$target/.qr" ] || r=bad
grep -q '`/sage:build`' "$target/.qr" || r=bad
grep -q '`/build`' "$target/.qr" && r=bad
cc_check "command_prefix: the Quick reference says /sage:build" "$r"
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

# C5: the Sage plugin's hooks run instead of ours — decided by who enabled it.
hooks_in() {  # the Sage hook scripts a settings file registers, sorted
  python3 - "$1" <<'PY'
import json, os, re, sys
p = sys.argv[1]
d = json.load(open(p)) if os.path.isfile(p) else {}
names = {re.search(r"(sage-[\w-]+\.sh)", h["command"]).group(1)
         for es in (d.get("hooks") or {}).values() for e in es for h in e["hooks"]
         if re.search(r"sage-[\w-]+\.sh", h.get("command", ""))}
print(" ".join(sorted(names)))
PY
}
# Project level (the team's choice): only what the plugin does not ship.
target="$(cc_new)"
printf '{\n  "enabledPlugins": {"sage@sage": true}\n}\n' > "$target/.claude/settings.json"
cc_run "$target" init
r=ok
[ "$(hooks_in "$target/.claude/settings.json")" = "sage-scope-gate.sh sage-scope-journal.sh" ] || r=bad
[ -z "$(hooks_in "$target/.claude/settings.local.json")" ] || r=bad
grep -q '"sage@sage": true' "$target/.claude/settings.json" || r=bad
cc_check "plugin on (project): only the scope gate + journal registered — no duplicates, none lost" "$r"
# …and enabled later: update trims what an earlier init registered.
target2="$(cc_new)"; cc_run "$target2" init
python3 -c 'import json,sys;p=sys.argv[1];d=json.load(open(p));d["enabledPlugins"]={"sage@sage":True};json.dump(d,open(p,"w"))' "$target2/.claude/settings.json"
cc_run "$target2" update
r=ok
[ "$(hooks_in "$target2/.claude/settings.json")" = "sage-scope-gate.sh sage-scope-journal.sh" ] || r=bad
[ -z "$(hooks_in "$target2/.claude/settings.local.json")" ] || r=bad
cc_check "plugin enabled later (project): update trims the earlier registrations" "$r"
rm -rf "$(dirname "$target")" "$(dirname "$target2")"
# The committed file follows the PROJECT's setting alone — one person's local
# setting, on or off, never reshapes it for the team.
target="$(cc_new)"
printf '{\n  "enabledPlugins": {"sage@sage": true}\n}\n' > "$target/.claude/settings.json"
printf '{"enabledPlugins": {"sage@sage": true}}\n' > "$target/.claude/settings.local.json"
cc_run "$target" init
r=ok
[ "$(hooks_in "$target/.claude/settings.json")" = "sage-scope-gate.sh sage-scope-journal.sh" ] || r=bad
cc_check "plugin on (project + local): the committed file still keeps only the scope gate + journal" "$r"
target2="$(cc_new)"
printf '{\n  "enabledPlugins": {"sage@sage": true}\n}\n' > "$target2/.claude/settings.json"
printf '{"enabledPlugins": {"sage@sage": false}}\n' > "$target2/.claude/settings.local.json"
out=$( cd "$target2" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" init --no-memory --platform claude-code 2>&1 )
r=ok
[ "$(hooks_in "$target2/.claude/settings.json")" = "sage-scope-gate.sh sage-scope-journal.sh" ] || r=bad
hooks_in "$target2/.claude/settings.local.json" | grep -q "sage-session-init.sh" || r=bad
printf '%s' "$out" | grep -q "your own settings turn it off" || r=bad
cc_check "plugin on (project) but off locally: team file unchanged, session hook here, the gap said" "$r"
rm -rf "$(dirname "$target")" "$(dirname "$target2")"

# User level only (one person's choice): the committed file stays whole.
target="$(cc_new)"
printf '{"enabledPlugins": {"sage@sage": true}}\n' > "$CLAUDE_CONFIG_DIR/settings.json"
out=$( cd "$target" && SAGE_HOME="$HOME_DIR" bash "$REPO_ROOT/bin/sage" init --no-memory --platform claude-code 2>&1 )
r=ok
hooks_in "$target/.claude/settings.json" | grep -q "sage-spec-gate.sh" || r=bad
[ -z "$(hooks_in "$target/.claude/settings.local.json")" ] || r=bad
printf '%s' "$out" | grep -q "enabled in your user settings only" || r=bad
cc_check "plugin on (user only): committed hooks kept for the team, the overlap said out loud" "$r"
# Precedence: the project's local settings turn it off → everything registers.
target3="$(cc_new)"
printf '{"enabledPlugins": {"sage@sage": false}}\n' > "$target3/.claude/settings.local.json"
cc_run "$target3" init
r=ok
hooks_in "$target3/.claude/settings.json" | grep -q "sage-spec-gate.sh" || r=bad
hooks_in "$target3/.claude/settings.local.json" | grep -q "sage-session-init.sh" || r=bad
cc_check "local false beats user true: the plugin is off here, so Sage registers everything" "$r"
rm -f "$CLAUDE_CONFIG_DIR/settings.json"
rm -rf "$(dirname "$target")" "$(dirname "$target3")"

echo ""
printf '  pass %d · fail %d\n' "$N_PASS" "$N_FAIL"
[ "$N_FAIL" -eq 0 ] || exit 1
exit 0
