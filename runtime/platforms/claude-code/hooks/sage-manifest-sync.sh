#!/usr/bin/env bash
# sage-manifest-sync.sh — Claude Code PostToolUse hook (R120, mechanical).
#
# L1 measured resume fidelity for the first time and found the manifest lying.
# Three runs of the identical cycle, all three completing and committing all three
# tasks:
#
#     run 1    gate_state: gates-passed
#     run 2    gate_state: plan-approved     <-- "plan approved, no tasks started"
#     run 3    gate_state: complete
#
# Run 2 is the bug. A session resuming from that manifest reads "no tasks started"
# and does the work again. The artifact whose whole job is to carry work across a
# context boundary had drifted from the tree beside it.
#
# cycle-protocol.md said "Advance it at every checkpoint", in prose — and prose is
# read by the same model that is deciding whether to bother. So the manifest is not
# asked to advance any more. It ADVANCES, because the agent wrote source code, and
# the hook firing IS the evidence that it did.
#
# Third time for this exact bug, and the third fix of the same shape:
#
#     R29     degradation record   prose -> logged 1 of 3 runs   -> now a hook
#     ADR-10  task ledger          prose -> written 2 of 3 runs  -> now a script
#     R120    manifest gate_state  prose -> correct 1 of 3 runs  -> now this
#
# WHAT IT WILL NOT DO: advance a cycle to `gates-passed` or `complete`. Those are
# APPROVAL states — a human grants them, or the quality-locked loop does after the
# gates actually run. A hook that advanced a cycle to `gates-passed` because the
# files looked finished would forge the signature the gate exists to collect. It
# reports that work HAS BEGUN. It never reports that work has been APPROVED.
#
# I/O: PostToolUse JSON on stdin. Exit 0 ALWAYS — a bookkeeping hook that can fail
# a user's tool call is a worse bug than the one it fixes.

set -uo pipefail

command -v python3 >/dev/null 2>&1 || exit 0

# The logic lives in ONE place (runtime/tools/manifest.py) and this hook delegates
# to it. Inlining it here would make a second copy of a state machine, and a second
# copy of a thing with a canonical source is what ADR-5 exists to forbid — the
# navigator was exactly that, and it drifted for two releases.
project="${CLAUDE_PROJECT_DIR:-$PWD}"
tool=""
for candidate in \
  "$project/sage/runtime/tools/manifest.py" \
  "${CLAUDE_PLUGIN_ROOT:-}/tools/manifest.py"
do
  if [ -f "$candidate" ]; then tool="$candidate"; break; fi
done
[ -n "$tool" ] || exit 0

payload=$(cat) || exit 0

# The path that was just written, out of the PostToolUse payload, and the
# checkout it landed in (a Desktop or --worktree session writes in a linked
# worktree while CLAUDE_PROJECT_DIR stays at the main checkout).
PY=$(mktemp "${TMPDIR:-/tmp}/sage-manifest-sync-XXXXXX" 2>/dev/null) || exit 0
trap 'rm -f "$PY"' EXIT
cat > "$PY" <<'PYEOF'
import json, os, sys
try:
    p = json.load(sys.stdin)
except (ValueError, OSError):
    sys.exit(0)
if not isinstance(p, dict):
    sys.exit(0)
ti = p.get("tool_input") or {}

# ── sage-root: identical in every hook (pinned by hook test WT0) ──
# A Desktop or `--worktree` session edits in a linked worktree while
# CLAUDE_PROJECT_DIR stays at the main checkout. Judge the checkout the
# edit lands in: when `probe` is in ANOTHER registered worktree of the same
# repository whose Sage config (at the project subdirectory, if the project
# lives in one) says what the main checkout config says, that worktree is
# the root — its branch, HEAD and cycles. Anything else keeps `base`, as
# before: the same checkout, a nested repo, a hand-made .git file, a
# worktree without Sage, or one whose config differs (an empty, laxer or
# older one would otherwise be the judge — review 2026-10-27).
def sage_worktree_root(base, probe):
    import subprocess as _sp

    def _git(d, *a):
        try:
            p = _sp.run(["git", "-C", d] + list(a), capture_output=True,
                        text=True, timeout=5)
            return p.stdout if p.returncode == 0 else ""
        except (OSError, _sp.SubprocessError):
            return ""

    if not base or not probe or not os.path.isfile(os.path.join(base, ".sage", "config.yaml")):
        return base                      # no Sage policy to match: nothing to switch to
    d = os.path.abspath(probe)
    while not os.path.isdir(d):
        up = os.path.dirname(d)
        if up == d:
            return base
        d = up
    a = d                                # no .sage/ above the probe: no git calls
    while not os.path.isdir(os.path.join(a, ".sage")):
        up = os.path.dirname(a)
        if up == a:
            return base
        a = up
    # One line per value; --show-prefix prints an EMPTY line at the top.
    out = _git(d, "rev-parse", "--show-toplevel", "--git-dir", "--git-common-dir").split("\n")[:-1]
    ref = _git(base, "rev-parse", "--git-dir", "--git-common-dir", "--show-prefix").split("\n")[:-1]
    if len(out) != 3 or len(ref) != 3 or not all(out) or not all(ref[:2]):
        return base
    top, git_dir, common = out

    def real(p, at):
        return os.path.realpath(os.path.join(at, p))

    if real(common, d) != real(ref[1], base) or real(git_dir, d) == real(ref[0], base):
        return base                      # another repository, or the base checkout itself
    root = os.path.join(os.path.realpath(top), ref[2]).rstrip(os.sep)
    # NUL-separated: a path holding a newline cannot forge an entry.
    listing = _git(base, "worktree", "list", "--porcelain", "-z")
    listed = [os.path.realpath(f[9:]) for f in listing.split("\0") if f.startswith("worktree ")]
    if os.path.realpath(top) not in listed:
        return base

    def policy(r):
        try:
            with open(os.path.join(r, ".sage", "config.yaml"), encoding="utf-8",
                      errors="replace") as fh:
                return [x.rstrip() for x in fh.read().split("\n")
                        if x.strip() and not x.lstrip().startswith("#")
                        and not x.startswith("sage-version:")]
        except OSError:
            return None

    mine = policy(root)
    if mine is None or mine != policy(base):
        return base
    # Hand the root back spelled like the probe (macOS /var is /private/var;
    # a symlinked directory), or every relpath against it reads "../". No
    # lexical ancestor that IS the root: keep base rather than guess.
    a = d
    while os.path.realpath(a) != root:
        up = os.path.dirname(a)
        if up == a:
            return base
        a = up
    return a


def sage_probe(data):
    """Where the call acts: the edited file, else the shell cwd."""
    cwd = (data.get("cwd") or "").strip()
    fp = str((data.get("tool_input") or {}).get("file_path") or "").strip()
    return os.path.join(cwd or os.getcwd(), fp) if fp else cwd
# ── end sage-root ──

print(ti.get("file_path") or ti.get("path") or "")
print(sage_worktree_root(os.environ["SAGE_PROJECT"], sage_probe(p)))
PYEOF
out=$(printf '%s' "$payload" | SAGE_PROJECT="$project" python3 "$PY" 2>/dev/null) || exit 0

wrote=$(printf '%s\n' "$out" | sed -n 1p)
root=$(printf '%s\n' "$out" | sed -n 2p)
[ -n "$wrote" ] || exit 0
[ -n "$root" ] || root="$project"

# Every ACTIVE cycle. The hook does not attribute an edit to a specific cycle (the
# spec-gate has the same limitation, R26) — but the failure being fixed is a cycle
# claiming no work has started while work plainly has, and that is true of any
# active cycle in a repo where source is being written.
for manifest in "$root"/.sage/work/*/manifest.md; do
  [ -f "$manifest" ] || continue
  python3 "$tool" advance "$manifest" --wrote "$wrote" >/dev/null 2>&1 || true
done

exit 0
