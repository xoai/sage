#!/usr/bin/env bash
# sage-tdd-gate.sh — Claude Code PreToolUse hook. Rule 1 (tests before code),
# made mechanical.
#
# The base constitution's first principle is "Tests before code. Every behavior has
# a test written before the implementation." Phase 4 measured it. Asked to change
# one constant under pressure — "it's literally changing one number, just do it
# quickly" — the agent wrote no test in 3 runs of 3, with the `tdd` skill loaded and
# the constitution in context. It edited the source, ran the existing suite, watched
# it pass, and committed. Nothing had ever stopped it, because nothing could: the
# rule was a sentence, and sentences are read by the model that is deciding whether
# they apply to this case.
#
# Worse, the rationalization never even reached the spec-gate. The agent classified
# the change as trivial, created no cycle at all, and so completed the whole task
# outside the process — every gate Sage owns fires on a CYCLE, and there was none.
# A rule that can be escaped by declaring the work small is not a rule.
#
# So this fires on the EDIT, not on the cycle. If a source file is about to change
# and no test has been written for it, the edit does not happen.
#
#   ALLOW when: a test file is already dirty or untracked in the working tree
#               (you wrote the test — proceed), or the most recent commit touched
#               a test (you committed the test first, now write the code).
#   BLOCK when: neither. Write the failing test first.
#
# Deliberately NOT clever. It does not try to decide whether the test is a GOOD
# test, or whether it covers this particular change — that is undecidable and the
# attempt would produce a gate that is wrong in both directions. It asserts the one
# thing that is mechanically true or false: a test was written, or it was not.
#
# Escapes, because an inescapable gate gets disabled wholesale:
#   - `tdd_enforcement: false` in .sage/config.yaml
#   - `tier: tier1` on an active manifest (genuinely trivial work)
#   - editing a test file (obviously)
#   - a project with no test suite at all (nothing to be test-first about yet)
#
# Exit: 0 allow | 2 block (reason on stderr, fed back to the model). Fails OPEN on
# any internal error — a broken hook must never brick the editor.

set -uo pipefail

command -v python3 >/dev/null 2>&1 || {
  echo "sage-tdd-gate: python3 not found; allowing edit" >&2
  exit 0
}

PY=$(mktemp "${TMPDIR:-/tmp}/sage-tdd-gate-XXXXXX" 2>/dev/null) || exit 0
trap 'rm -f "$PY"' EXIT

cat > "$PY" <<'PYEOF'
import json
import os
import re
import subprocess
import sys

def allow():
    sys.exit(0)

def block(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(2)

try:
    payload = json.load(sys.stdin)
except (ValueError, OSError):
    allow()

tool = payload.get("tool_name") or ""
if tool not in ("Edit", "Write", "MultiEdit"):
    allow()

tool_input = payload.get("tool_input") or {}
file_path = tool_input.get("file_path") or tool_input.get("path") or ""
if not file_path:
    allow()

project_root = os.path.abspath(
    os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
)
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    allow()                                   # not a Sage project

# ── opt-in, exactly like hard_enforcement ──
enforce = None
config = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config):
    try:
        with open(config, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*tdd_enforcement\s*:\s*(true|false)\b", line, re.I)
                if m:
                    enforce = m.group(1).lower() == "true"
                    break
    except OSError:
        pass
if enforce is not True:
    allow()

abspath = file_path if os.path.isabs(file_path) else os.path.join(project_root, file_path)
abspath = os.path.normpath(abspath)
try:
    rel = os.path.relpath(abspath, project_root)
except ValueError:
    allow()
if rel.startswith(".."):
    allow()                                   # outside the project

rel_posix = rel.replace(os.sep, "/")

# ── never gate Sage's own state, the vendored framework, or dependencies ──
SKIP_PREFIX = (".sage/", "sage/", ".claude/", "node_modules/", "vendor/", ".git/")
if any(rel_posix.startswith(p) for p in SKIP_PREFIX):
    allow()

SOURCE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".rb", ".php", ".swift", ".kt", ".kts", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".cs", ".scala", ".ex", ".exs", ".dart",
}
ext = os.path.splitext(rel_posix)[1].lower()
if ext not in SOURCE_EXT:
    allow()                                   # docs, config, JSON, lockfiles…

TEST_RE = re.compile(
    r"(^|/)tests?/|(^|/)__tests__/|(^|/)spec/"           # a test directory
    r"|(^|/)test_[^/]+$|[^/]*_test\.[a-z]+$"             # test_x.py / x_test.go
    r"|[^/]*\.(test|spec)\.[a-z]+$",                     # x.test.ts / x.spec.js
    re.I,
)

def is_test(path):
    """A test file belonging to the PROJECT.

    The `sage/` directory is Sage's own vendored framework and it is full of test
    files — fixtures, TESTS.md, gate suites. Counting those is not a subtle bug: it
    means `sage init` itself, whose commit touches the whole vendored tree, looks
    exactly like "the developer just wrote a test", and the gate waves through the
    next source edit. It did, and this is what let the first version pass a change
    with no test at all.
    """
    path = path.replace(os.sep, "/")
    if any(path.startswith(p) for p in SKIP_PREFIX):
        return False
    return bool(TEST_RE.search(path))

if is_test(rel_posix):
    allow()                                   # writing the test IS the point

# ── a tier1 cycle is exempt: genuinely trivial work opts out of the process ──
import glob
for mpath in glob.glob(os.path.join(sage_dir, "work", "*", "manifest.md")):
    try:
        with open(mpath, encoding="utf-8", errors="replace") as fh:
            head = fh.read(2048)
    except OSError:
        continue
    m = re.match(r"^\s*---\s*\n(.*?)\n---", head.lstrip("﻿"), re.S)
    if not m:
        continue
    fm = m.group(1)
    state = re.search(r"^\s*gate_state\s*:\s*\"?([\w-]+)\"?", fm, re.M)
    if state and state.group(1).lower() == "complete":
        continue                              # a finished cycle exempts nothing
    tier = re.search(r"^\s*tier\s*:\s*\"?([\w-]+)\"?", fm, re.M)
    if tier and tier.group(1).lower() == "tier1":
        allow()

def git(*args):
    try:
        p = subprocess.run(["git", "-C", project_root, *args],
                           capture_output=True, text=True, timeout=5)
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""

# Not a git repo → nothing to compare against. Fail open.
if not git("rev-parse", "--git-dir").strip():
    allow()

# ── does this project even have a test suite? ──
tracked = git("ls-files")
has_suite = any(is_test(p) for p in tracked.splitlines() if p.strip())
if not has_suite:
    allow()   # nothing to be test-first about yet; documented hole, see the header

# ── ALLOW 1: a test is already written but not committed ──
# `git status --porcelain` lines are "XY path"; renames carry "old -> new".
for line in git("status", "--porcelain").splitlines():
    if len(line) < 4:
        continue
    path = line[3:].split(" -> ")[-1].strip().strip('"')
    if path and is_test(path):
        allow()

# ── ALLOW 2: the previous commit was the RED commit — a test, and only a test ──
#
# "The last commit touched a test" is not good enough, and the difference is the
# whole gate. Almost every repo's initial import contains src/ and tests/ together,
# so that rule hands out a free pass on the very next source edit — which is exactly
# the edit this gate exists to stop. It did: against the real fixture, the gate
# allowed the untested change and measured as working while enforcing nothing.
#
# A commit that adds a failing test AND NOTHING ELSE is the red step of TDD, and it
# is the only commit shape that earns the right to write the implementation next.
head_files = [p.strip() for p in
              git("show", "--name-only", "--format=", "HEAD").splitlines() if p.strip()]


def is_source(path):
    path = path.replace(os.sep, "/")
    if any(path.startswith(p) for p in SKIP_PREFIX):
        return False
    if is_test(path):
        return False
    return os.path.splitext(path)[1].lower() in SOURCE_EXT


if head_files:
    tests_in_head = [p for p in head_files if is_test(p)]
    source_in_head = [p for p in head_files if is_source(p)]
    if tests_in_head and not source_in_head:
        allow()                               # the red commit

block(
    'Sage TDD gate: tests before code — no test has been written for this change.\n'
    'Constitution principle 1: every behavior has a test written BEFORE the\n'
    'implementation. Write a test that FAILS without this change, then make it pass.\n'
    '"It is only one number", "it is just config" and "the tests already cover it"\n'
    'are the excuses this rule exists to refuse — measured, they were used in 3 runs\n'
    'out of 3.\n'
    '\n'
    'Blocked edit: %s\n'
    '\n'
    'To proceed, do ONE of:\n'
    '  - write or update a test (that is the intended path)\n'
    '  - set `tier: tier1` on the active manifest, if this is genuinely trivial\n'
    '  - set `tdd_enforcement: false` in .sage/config.yaml to disable this gate'
    % rel_posix
)
PYEOF

python3 "$PY"
rc=$?
exit $rc
