#!/usr/bin/env bash
# Integration tests for `sage worktree remove` (harvest-then-remove).
#
# Drives the real bin/sage against throwaway git repos + worktrees. Verifies the
# gitignored .sage/work docs are harvested back into the main checkout BEFORE the
# worktree is removed — the data-loss this command exists to prevent.
#
# Usage: bash develop/validators/worktree-remove.test.sh
# Exit:  0 = all pass, 1 = at least one failure.

set -uo pipefail

BIN="$(cd "$(dirname "$0")/../.." && pwd)/bin/sage"
PASS=0; FAIL=0
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
check() { if [ "$2" -eq 0 ]; then PASS=$((PASS+1)); green "  ✓ $1"; else FAIL=$((FAIL+1)); red "  ✗ $1"; fi; }

# new_repo <dir> — a minimal git repo with .sage/ gitignored and one commit.
new_repo() {
  local d="$1"
  mkdir -p "$d" && git -C "$d" init -q -b main
  git -C "$d" config user.email t@t; git -C "$d" config user.name t
  printf '.sage/\nnode_modules/\n' > "$d/.gitignore"
  echo "code" > "$d/app.txt"
  git -C "$d" add -A && git -C "$d" commit -qm init
}
# add_wt <repo> <slug> — raw worktree at <parent>/<base>-<slug> with build docs.
add_wt() {
  local repo="$1" slug="$2" wt; wt="$(dirname "$repo")/$(basename "$repo")-$slug"
  git -C "$repo" worktree add -q -b "feat/$slug" "$wt" main
  mkdir -p "$wt/.sage/work/$slug"
  echo "the spec for $slug" > "$wt/.sage/work/$slug/spec.md"
  echo "the plan for $slug" > "$wt/.sage/work/$slug/plan.md"
  printf '%s' "$wt"
}

echo ""
echo "── sage worktree remove tests ──"

# 1) Clean harvest by DIR: docs land in main, worktree dir gone.
T="$(mktemp -d)"; new_repo "$T/main"
WT="$(add_wt "$T/main" alpha)"
( cd "$T/main" && bash "$BIN" worktree remove "$WT" ) >/dev/null 2>&1
[ -f "$T/main/.sage/work/alpha/spec.md" ] && [ -f "$T/main/.sage/work/alpha/plan.md" ] \
  && check "harvest by dir: docs copied into main checkout" 0 || check "harvest by dir: docs copied into main checkout" 1
[ ! -d "$WT" ] && check "harvest by dir: worktree directory removed" 0 || check "harvest by dir: worktree directory removed" 1
rm -rf "$T"

# 2) Resolve by SLUG (not full path).
T="$(mktemp -d)"; new_repo "$T/main"
WT="$(add_wt "$T/main" beta)"
( cd "$T/main" && bash "$BIN" worktree remove beta ) >/dev/null 2>&1
{ [ -f "$T/main/.sage/work/beta/spec.md" ] && [ ! -d "$WT" ]; } \
  && check "slug resolution: harvested and removed" 0 || check "slug resolution: harvested and removed" 1
rm -rf "$T"

# 3) Collision: main already has .sage/work/<slug> → kept separate, original intact.
T="$(mktemp -d)"; new_repo "$T/main"
mkdir -p "$T/main/.sage/work/gamma"; echo "MAIN ORIGINAL" > "$T/main/.sage/work/gamma/spec.md"
WT="$(add_wt "$T/main" gamma)"
( cd "$T/main" && bash "$BIN" worktree remove "$WT" ) >/dev/null 2>&1
orig_intact=1; grep -q "MAIN ORIGINAL" "$T/main/.sage/work/gamma/spec.md" 2>/dev/null && orig_intact=0
harvested_sep=1; [ -f "$T/main/.sage/work/gamma--harvested/spec.md" ] && harvested_sep=0
check "collision: main's original .sage/work/gamma untouched" "$orig_intact"
check "collision: worktree copy harvested to gamma--harvested/" "$harvested_sep"
rm -rf "$T"

# 4) Guard: refuse to remove the main checkout.
T="$(mktemp -d)"; new_repo "$T/main"
( cd "$T/main" && bash "$BIN" worktree remove "$T/main" ) >/dev/null 2>&1
[ $? -ne 0 ] && check "guard: refuses to remove the main checkout (exit≠0)" 0 || check "guard: refuses to remove the main checkout (exit≠0)" 1
[ -f "$T/main/app.txt" ] && check "guard: main checkout still intact" 0 || check "guard: main checkout still intact" 1
rm -rf "$T"

# 5) Tracked-dirty safety: a modified tracked file blocks removal (no --force),
#    but the docs are still harvested first.
T="$(mktemp -d)"; new_repo "$T/main"
WT="$(add_wt "$T/main" delta)"
echo "uncommitted change" >> "$WT/app.txt"   # dirty a TRACKED file
( cd "$T/main" && bash "$BIN" worktree remove "$WT" ) >/dev/null 2>&1
rc=$?
[ "$rc" -eq 3 ] && check "dirty tracked file: removal refused (exit 3)" 0 || check "dirty tracked file: removal refused (exit 3)" 1
[ -d "$WT" ] && check "dirty tracked file: worktree preserved" 0 || check "dirty tracked file: worktree preserved" 1
[ -f "$T/main/.sage/work/delta/spec.md" ] && check "dirty tracked file: docs still harvested first" 0 || check "dirty tracked file: docs still harvested first" 1
# --force removes it
( cd "$T/main" && bash "$BIN" worktree remove "$WT" --force ) >/dev/null 2>&1
[ ! -d "$WT" ] && check "dirty tracked file: --force removes it" 0 || check "dirty tracked file: --force removes it" 1
rm -rf "$T"

# 6) Configurable harvest: worktree_harvest controls which paths come back.
#    A whole-path entry (.sage/notes) and a per-child entry (.sage/work/*).
T="$(mktemp -d)"; new_repo "$T/main"
mkdir -p "$T/main/.sage"
printf 'worktree_harvest: [.sage/notes, .sage/work/*]\n' > "$T/main/.sage/config.yaml"
WT="$(add_wt "$T/main" zeta)"   # creates .sage/work/zeta/{spec,plan}.md
mkdir -p "$WT/.sage/notes"; echo "NOTE" > "$WT/.sage/notes/n.md"
( cd "$T/main" && bash "$BIN" worktree remove zeta ) >/dev/null 2>&1
[ -f "$T/main/.sage/notes/n.md" ] && check "configurable harvest: custom whole-path (.sage/notes) brought back" 0 || check "configurable harvest: custom whole-path (.sage/notes) brought back" 1
[ -f "$T/main/.sage/work/zeta/spec.md" ] && check "configurable harvest: per-child (.sage/work/*) still works" 0 || check "configurable harvest: per-child (.sage/work/*) still works" 1
rm -rf "$T"

# 7) Configurable copy: worktree_copy controls what `sage worktree` seeds.
T="$(mktemp -d)"; new_repo "$T/main"
mkdir -p "$T/main/.sage"
printf 'platforms: [claude-code]\nworktree_copy: [.sage/custom.txt]\n' > "$T/main/.sage/config.yaml"
echo "CUSTOM" > "$T/main/.sage/custom.txt"
echo "CONSTITUTION" > "$T/main/.sage/constitution.md"   # a default-set path NOT in the custom list
( cd "$T/main" && bash "$BIN" worktree eta ) >/dev/null 2>&1
WT="$T/main-eta"
[ -f "$WT/.sage/custom.txt" ] && check "configurable copy: listed path seeded into worktree" 0 || check "configurable copy: listed path seeded into worktree" 1
[ ! -f "$WT/.sage/constitution.md" ] && check "configurable copy: unlisted default path NOT seeded" 0 || check "configurable copy: unlisted default path NOT seeded" 1
( cd "$T/main" && bash "$BIN" worktree remove eta --force ) >/dev/null 2>&1
rm -rf "$T"

# 8) BLOCK-STYLE YAML harvest config is honored (regression: it used to yield a
#    garbage token and silently harvest nothing → total data loss).
T="$(mktemp -d)"; new_repo "$T/main"; mkdir -p "$T/main/.sage"
printf 'worktree_harvest:\n  - .sage/work/*\n' > "$T/main/.sage/config.yaml"
WT="$(add_wt "$T/main" blk)"
( cd "$T/main" && bash "$BIN" worktree remove blk ) >/dev/null 2>&1
[ -f "$T/main/.sage/work/blk/spec.md" ] && check "block-style YAML harvest honored (no silent loss)" 0 || check "block-style YAML harvest honored (no silent loss)" 1
rm -rf "$T"

# 9) Untracked-but-not-ignored configured path is harvested (gate = not-tracked).
T="$(mktemp -d)"; new_repo "$T/main"; mkdir -p "$T/main/.sage"
printf 'worktree_harvest: [scratch.txt, .sage/work/*]\n' > "$T/main/.sage/config.yaml"
WT="$(add_wt "$T/main" theta)"
echo "SCRATCH" > "$WT/scratch.txt"   # untracked, NOT gitignored
( cd "$T/main" && bash "$BIN" worktree remove theta --force ) >/dev/null 2>&1
[ -f "$T/main/scratch.txt" ] && check "untracked-not-ignored path harvested (not dropped)" 0 || check "untracked-not-ignored path harvested (not dropped)" 1
rm -rf "$T"

# 10) Re-collision does NOT clobber a prior un-reconciled --harvested copy.
T="$(mktemp -d)"; new_repo "$T/main"; mkdir -p "$T/main/.sage/work/rc" "$T/main/.sage/work/rc--harvested"
echo "ORIG" > "$T/main/.sage/work/rc/spec.md"
echo "PRIOR-UNRECONCILED" > "$T/main/.sage/work/rc--harvested/spec.md"
WT="$(add_wt "$T/main" rc)"   # worktree also has .sage/work/rc
( cd "$T/main" && bash "$BIN" worktree remove rc ) >/dev/null 2>&1
grep -q PRIOR-UNRECONCILED "$T/main/.sage/work/rc--harvested/spec.md" 2>/dev/null && check "re-collision: prior --harvested preserved" 0 || check "re-collision: prior --harvested preserved" 1
[ -f "$T/main/.sage/work/rc--harvested-2/spec.md" ] && check "re-collision: new copy lands at --harvested-2" 0 || check "re-collision: new copy lands at --harvested-2" 1
rm -rf "$T"

# 11) Slug resolves exact match even when an -N sibling exists.
T="$(mktemp -d)"; new_repo "$T/main"
WT1="$(add_wt "$T/main" iota)"      # main-iota   (branch feat/iota)
WT2="$(add_wt "$T/main" iota-2)"    # main-iota-2 (branch feat/iota-2)
( cd "$T/main" && bash "$BIN" worktree remove iota ) >/dev/null 2>&1
{ [ ! -d "$WT1" ] && [ -d "$WT2" ]; } && check "slug 'iota' resolves exact main-iota, not the -2 sibling" 0 || check "slug 'iota' resolves exact main-iota, not the -2 sibling" 1
( cd "$T/main" && bash "$BIN" worktree remove "$WT2" --force ) >/dev/null 2>&1
rm -rf "$T"

# 12) An explicit empty harvest list disables harvest (intentional, not defaults).
T="$(mktemp -d)"; new_repo "$T/main"; mkdir -p "$T/main/.sage"
printf 'worktree_harvest: []\n' > "$T/main/.sage/config.yaml"
WT="$(add_wt "$T/main" kappa)"
( cd "$T/main" && bash "$BIN" worktree remove kappa --force ) >/dev/null 2>&1
{ [ ! -e "$T/main/.sage/work/kappa" ] && [ ! -d "$WT" ]; } && check "empty harvest list [] harvests nothing (intentional)" 0 || check "empty harvest list [] harvests nothing (intentional)" 1
rm -rf "$T"

# 14) Identical content already in main → skipped silently (no --harvested noise).
T="$(mktemp -d)"; new_repo "$T/main"; mkdir -p "$T/main/.sage/work/dup"
echo "SAME" > "$T/main/.sage/work/dup/spec.md"
WT="$(add_wt "$T/main" lam)"
mkdir -p "$WT/.sage/work/dup"; echo "SAME" > "$WT/.sage/work/dup/spec.md"   # byte-identical to main
out="$( cd "$T/main" && bash "$BIN" worktree remove lam 2>&1 )"
[ ! -e "$T/main/.sage/work/dup--harvested" ] && check "identical content: no pointless --harvested copy" 0 || check "identical content: no pointless --harvested copy" 1
printf '%s' "$out" | grep -q "already current" && check "identical content: reported as 'already current'" 0 || check "identical content: reported as 'already current'" 1
rm -rf "$T"

# 15) DIFFERING content already in main → kept as --harvested (real divergence).
T="$(mktemp -d)"; new_repo "$T/main"; mkdir -p "$T/main/.sage/work/div"
echo "MAIN-VERSION" > "$T/main/.sage/work/div/spec.md"
WT="$(add_wt "$T/main" mu)"
mkdir -p "$WT/.sage/work/div"; echo "WORKTREE-VERSION" > "$WT/.sage/work/div/spec.md"
( cd "$T/main" && bash "$BIN" worktree remove mu ) >/dev/null 2>&1
{ grep -q MAIN-VERSION "$T/main/.sage/work/div/spec.md" && grep -q WORKTREE-VERSION "$T/main/.sage/work/div--harvested/spec.md"; } \
  && check "differing content: main intact + worktree copy kept as --harvested" 0 || check "differing content: main intact + worktree copy kept as --harvested" 1
rm -rf "$T"

# 16) THE REGRESSION: main already has initiatives AND the worktree has a
#     genuinely-new one. The new dir MUST be harvested; the existing identical
#     ones must NOT be expanded against main (the `for entry in $entries` glob bug).
T="$(mktemp -d)"; new_repo "$T/main"
mkdir -p "$T/main/.sage/work/keep-1" "$T/main/.sage/work/keep-2"
echo same > "$T/main/.sage/work/keep-1/spec.md"; echo same > "$T/main/.sage/work/keep-2/spec.md"
WT="$(add_wt "$T/main" nu)"            # add_wt also creates .sage/work/nu in the worktree
mkdir -p "$WT/.sage/work/keep-1" "$WT/.sage/work/keep-2"  # identical copies of main's
echo same > "$WT/.sage/work/keep-1/spec.md"; echo same > "$WT/.sage/work/keep-2/spec.md"
mkdir -p "$WT/.sage/work/brand-new"; echo fresh > "$WT/.sage/work/brand-new/spec.md"  # only in worktree
out="$( cd "$T/main" && bash "$BIN" worktree remove nu 2>&1 )"
[ -f "$T/main/.sage/work/brand-new/spec.md" ] && check "new worktree initiative IS harvested (the reported bug)" 0 || check "new worktree initiative IS harvested (the reported bug)" 1
[ -f "$T/main/.sage/work/nu/spec.md" ] && check "the worktree's own initiative dir is harvested too" 0 || check "the worktree's own initiative dir is harvested too" 1
{ [ ! -e "$T/main/.sage/work/keep-1--harvested" ] && [ ! -e "$T/main/.sage/work/keep-2--harvested" ]; } \
  && check "identical existing dirs make no --harvested noise" 0 || check "identical existing dirs make no --harvested noise" 1
rm -rf "$T"

# 17) Main-checkout guard exits with the specific code 2 (not just any non-zero).
T="$(mktemp -d)"; new_repo "$T/main"
( cd "$T/main" && bash "$BIN" worktree remove "$T/main" ) >/dev/null 2>&1; rc=$?
[ "$rc" -eq 2 ] && check "main-checkout guard exits 2 (specific)" 0 || check "main-checkout guard exits 2 (got $rc)" 1
rm -rf "$T"

echo ""
echo "  worktree-remove: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
