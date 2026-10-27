#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-branch-gate.sh — Claude Code PreToolUse hook (Edit/Write/MultiEdit)
#
# "Implementation does not start on the default branch" was a sentence in the
# eager layer with no hook behind it, and 4 of 4 small /build runs implemented
# straight onto master (review 2026-10-26, X4). Now it is code: while a
# Standard+ cycle is in progress in this checkout, a source edit on the
# default branch is blocked, and the block names the one command that fixes
# it. Merging stays the user's [M]; this only keeps the work off the default
# branch until then.
#
# Allowed unconditionally:
#   - not a Sage project; python3 or git missing; not a git repo; detached HEAD
#   - hard_enforcement not explicitly true; branch_gate: false (opt-out)
#   - no in-progress cycle in this checkout, or only tier1 cycles
#   - the user declined branching for this initiative — recorded as
#     `branch: declined` in its manifest (git-discipline: "declining is always
#     available"; manifest.py close-out --branch declined writes it)
#   - not a source file (docs, config, Sage's own state); a test file
#   - the current branch is not the default branch
#
# Default branch: git-discipline's chain, as bin/sage's _wt_default_branch
# resolves it — `default_branch:` in .sage/config.yaml (the user's persisted
# answer), then origin/HEAD, then init.defaultBranch (each only if that branch
# exists locally), then main, then master. Nothing resolves → allow: the gate
# never guesses which branch is "default".
#
# Contract: exit 0 allow · a block is exit 2 (stderr) — or Claude Code's
# structured deny when the input names hook_event_name (C6). Fails open.
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-branch-gate-XXXXXX" 2>/dev/null) || exit 0
trap 'rm -f "$PY_GATE"' EXIT

cat > "$PY_GATE" <<'PYEOF'
import glob
import json
import os
import re
import subprocess
import sys


def emit(decision, message=""):
    # Structured deny for Claude Code (C6); exit 2 for other callers.
    payload = globals().get("data")
    if (decision == "BLOCK" and isinstance(payload, dict)
            and payload.get("hook_event_name") == "PreToolUse"):
        decision = "DENY"
    sys.stdout.write(decision + "\n")
    if message:
        sys.stdout.write(message)
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    emit("ALLOW")
if not isinstance(data, dict) or data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
    emit("ALLOW")

project_root = os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR")
                               or (data.get("cwd") or "").strip() or os.getcwd())

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

project_root = sage_worktree_root(project_root, sage_probe(data))
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    emit("ALLOW")

# Same master switch as the other gates (first occurrence wins), plus the opt-out.
# First occurrence wins, at column 0 — the other gates' reader convention.
enforce, gate_on, configured_default = None, None, ""
try:
    with open(os.path.join(sage_dir, "config.yaml"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.match(r"hard_enforcement\s*:\s*(true|false)\b", line, re.I)
            if m and enforce is None:
                enforce = m.group(1).lower() == "true"
            m = re.match(r"branch_gate\s*:\s*(true|false)\b", line, re.I)
            if m and gate_on is None:
                gate_on = m.group(1).lower() == "true"
            m = re.match(r"default_branch\s*:\s*\"?([^\s\"#]+)", line)
            if m and not configured_default:
                configured_default = m.group(1)
except OSError:
    pass
if enforce is not True or gate_on is False:
    emit("ALLOW")

file_path = str((data.get("tool_input") or {}).get("file_path") or "")
if not file_path:
    emit("ALLOW")
abspath = os.path.normpath(file_path if os.path.isabs(file_path)
                           else os.path.join(project_root, file_path))
rel = os.path.relpath(abspath, project_root).replace(os.sep, "/")
SKIP_PREFIX = (".sage/", "sage/", ".claude/", ".opencode/", "node_modules/",
               "vendor/", ".git/")
SOURCE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".rb", ".php", ".swift", ".kt", ".kts", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".cs", ".scala", ".ex", ".exs", ".dart",
}
TEST_RE = re.compile(r"(^|/)tests?/|(^|/)__tests__/|(^|/)spec/|(^|/)test_[^/]+$"
                     r"|[^/]*_test\.[a-z]+$|[^/]*\.(test|spec)\.[a-z]+$", re.I)
if (rel.startswith("..") or any(rel.startswith(p) for p in SKIP_PREFIX)
        or os.path.splitext(rel)[1].lower() not in SOURCE_EXT or TEST_RE.search(rel)):
    emit("ALLOW")


def field(text, name):
    m = re.search(r"(?m)^%s\s*:\s*\"?([^\"\n#]*)" % re.escape(name), text)
    return m.group(1).strip() if m else ""


# The in-progress, non-tier1 cycle of THIS checkout.
cycle = None
for manifest in sorted(glob.glob(os.path.join(sage_dir, "work", "*", "manifest.md"))):
    try:
        text = open(manifest, encoding="utf-8", errors="replace").read(4096)
    except OSError:
        continue
    fm = re.match(r"^\s*---\s*\n(.*?)\n---", text.lstrip("﻿"), re.S)
    if not fm:
        continue
    fm = fm.group(1)
    if field(fm, "status").lower() != "in-progress":
        continue
    if field(fm, "tier").lower() in ("tier1", "1", "tier-1"):
        continue
    if field(fm, "branch").lower() == "declined":
        continue                                # the user's recorded decline
    owner = field(fm, "owner")
    if owner and os.path.realpath(os.path.expanduser(owner)) != os.path.realpath(project_root):
        continue
    cycle = (os.path.basename(os.path.dirname(manifest)), field(fm, "branch"))
    break
if cycle is None:
    emit("ALLOW")


def git(*args):
    try:
        p = subprocess.run(["git", "-C", project_root, *args], capture_output=True,
                           text=True, timeout=5)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


current = git("symbolic-ref", "--quiet", "--short", "HEAD")
if not current:
    emit("ALLOW")                               # not a repo, or detached HEAD


def local_branch(name):
    return bool(name) and subprocess.run(
        ["git", "-C", project_root, "show-ref", "--verify", "--quiet",
         "refs/heads/" + name], capture_output=True).returncode == 0


default = configured_default
if not default:
    origin = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    for name in (origin.replace("refs/remotes/origin/", "", 1),
                 git("config", "--get", "init.defaultBranch"), "main", "master"):
        if local_branch(name):
            default = name
            break
if not default or current != default:
    emit("ALLOW")

slug, branch = cycle
if not branch or branch == default:
    branch = "feat/" + re.sub(r"^\d+-", "", slug)
emit("BLOCK", (
    "Sage: implementation does not start on the default branch (%s), and cycle "
    "\"%s\" is in progress.\n\nPropose the initiative branch to the user and create "
    "it once they confirm or rename it\n(git-discipline: never create one silently):\n"
    "    git switch -c %s\n"
    "Record the name they chose, then make this edit:\n"
    "    python3 sage/runtime/tools/manifest.py close-out .sage/work/%s/manifest.md "
    "--branch <name>\n\nMerging back stays your [M]. To turn this off: "
    "branch_gate: false in .sage/config.yaml (a human edit). If the USER\n"
    "declines branching for this initiative, record their decision:\n"
    "    python3 sage/runtime/tools/manifest.py close-out .sage/work/%s/manifest.md \\\n"
    "      --branch declined --decision \"branching declined by the user: <reason>\"\n"
    % (current, slug, branch, slug, slug)))
PYEOF

GATE_OUT=$(python3 "$PY_GATE")
[ $? -eq 0 ] || exit 0
DECISION=$(printf '%s\n' "$GATE_OUT" | sed -n '1p')
MESSAGE=$(printf '%s\n' "$GATE_OUT" | sed -n '2,$p')

case "$DECISION" in
  DENY)
    SAGE_DENY_REASON="$MESSAGE" python3 -c 'import json, os; print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": os.environ["SAGE_DENY_REASON"]}}))'
    exit 0
    ;;
  BLOCK)
    printf '%s\n' "$MESSAGE" >&2
    exit 2
    ;;
  *)
    exit 0
    ;;
esac
