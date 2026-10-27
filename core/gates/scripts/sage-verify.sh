#!/usr/bin/env bash
# sage-verify.sh — Deterministic verification for Gate 5
# Runs tests, checks results, collects evidence.
# Usage: bash sage/core/gates/scripts/sage-verify.sh [--quiet] [project-root]
#
# This script replaces language-based "verify tests pass" instructions
# with deterministic execution. Code is deterministic; language isn't.
#
# Exit contract (ADR-1):
#   0 = tests ran and passed
#   1 = tests ran and failed (or the build failed)
#   2 = unverifiable — no runner detected, or the runner is not installed
#
# Exit 2 exists because "the suite is green" and "there is no suite" are not
# the same claim. They used to share exit 0, so a project with zero tests
# passed the verification gate.
#
# Baseline (review 2026-10-26, L2): failures that were already there when the
# cycle started are not the cycle's to fix, and must not block it forever.
#   --record-baseline FILE  run the suite and record which tests fail — once,
#                           at the start of a cycle: refused if FILE exists,
#                           and refused while source files are modified (a
#                           baseline over the cycle's own edits would excuse
#                           them; --force skips only that check)
#   --baseline FILE         judge against FILE. Without the flag, the ONE
#                           in-progress cycle's .sage/work/<slug>/
#                           verify-baseline.json is used (never a paused or
#                           another checkout's cycle's).
#   --no-baseline           judge every failure, as before
# A red run passes only when the gate can PROVE every failure is a baseline
# one: each runner's output is parsed into fully qualified test ids
# (pytest node ids, go package::test, jest/vitest file › describe path, mocha
# full title, node file:line:col title from its spec or TAP reporter), the
# runner's own failure count must match the ids named, at least as many tests
# must have RUN as at the baseline (a fail-fast setting — pytest -x, bail,
# -failfast — hides every later failure; Sage's own argv also overrides
# it), and the baseline must come
# from this branch's history. Anything less is never excused: an interrupted
# run (collection error, unhandled or async error, panic, failing hook), a
# count mismatch, an output format it does not parse (flutter), a timeout, a
# broken build. A file that failed to LOAD is
# excused only while that file is unchanged — tests added to it never ran.
#
# --gate marks the run as Gate 5 itself: it is then recorded in the
# in-progress cycle's review ledger (review.py gate), so retries are counted
# by the tool, not reported by the agent (L1).
#
# --quiet (context diet, profile 2026-07-15): on the PASS path, print one
# summary line instead of a dozen section banners — that output is re-paid in
# every later call's context. It NEVER trims a FAIL or an UNVERIFIABLE: the
# evidence a failure carries is the whole point of the gate, and a quiet
# failure would be a lie the same shape as a skipped one.

set -uo pipefail

QUIET=false
TAB=$(printf '\t')
ROOT="."
_root_set=false
RECORD_BASELINE=""
BASELINE=""
BASELINE_MODE=auto        # auto | file | off
FORCE=false
GATE_RUN=false            # --gate: this run IS Gate 5 — count it in the ledger
while [ $# -gt 0 ]; do
  case "$1" in
    --quiet) QUIET=true ;;
    --record-baseline|--baseline)
      if [ -z "${2:-}" ] || [ "${2#--}" != "$2" ]; then
        echo "⚠️ UNVERIFIABLE — $1 needs a file path" ; exit 2
      fi
      if [ "$1" = --record-baseline ]; then RECORD_BASELINE="$2"
      else BASELINE="$2"; BASELINE_MODE=file; fi
      shift ;;
    --no-baseline) BASELINE_MODE=off ;;
    --gate) GATE_RUN=true ;;
    --force) FORCE=true ;;
    *) if [ "$_root_set" = false ]; then ROOT="$1"; _root_set=true; fi ;;
  esac
  shift
done
ROOT_ARG="$ROOT"
PASS=true

log()  { echo "$1"; }                       # always printed
vlog() { [ "$QUIET" = true ] || echo "$1"; } # decorative — dropped when quiet

unverifiable() {
  vlog ""
  vlog "═══ Gate 5 Result ═══"
  log "⚠️ UNVERIFIABLE — $1"
  exit 2
}

vlog "═══ Sage Gate 5: Verification ═══"
vlog "Root: $ROOT"
vlog "Time: $(date -Iseconds 2>/dev/null || date)"
vlog ""

if ! ROOT=$(cd "$ROOT" 2>/dev/null && pwd); then
  unverifiable "project root does not exist: $ROOT_ARG"
fi

if ! command -v python3 >/dev/null 2>&1; then
  unverifiable "python3 is required to detect the test runner"
fi

# Bounded execution: runner and build run under a watchdog so a hanging
# suite becomes a FAIL with evidence instead of an hours-long grind
# (mechanics + portability constraints documented in sage-bounded.sh).
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sage-bounded.sh"
VERIFY_TIMEOUT=$(sage_bounded_timeout "$ROOT")

# ── Step 1: Detect test runner ──
#
# Detection reads package.json as JSON. It used to grep for the substring
# '"vitest"', which matches a keywords array, a description, or any unrelated
# field — and then invoked a runner the project does not have.
#
# The heredoc is written to a temp file rather than inlined into `$( … )`:
# bash 3.2 mis-parses a heredoc nested inside a command substitution.
PY_DETECT=$(mktemp "${TMPDIR:-/tmp}/sage-gate5-XXXXXX") || \
  unverifiable "could not create a temporary file"
trap 'rm -f "$PY_DETECT" "$PY_DETECT".base "$PY_DETECT".out-* "$PY_DETECT".sentinel-*' EXIT

cat > "$PY_DETECT" <<'PYEOF'
import json
import os
import sys

root = sys.argv[1]
CHECKED = "vitest, jest, mocha, npm test, pytest, flutter, go"
out = []


def emit(*fields):
    out.append('\t'.join(str(f) for f in fields))


def load_json(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def ancestors(start):
    cur = os.path.abspath(start)
    while True:
        yield cur
        if os.path.isdir(os.path.join(cur, '.git')):
            return
        parent = os.path.dirname(cur)
        if parent == cur:
            return
        cur = parent


def node_bin(name):
    """Runners are hoisted to the workspace root in monorepos."""
    for d in ancestors(root):
        p = os.path.join(d, 'node_modules', '.bin', name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def none(reason):
    emit('RUNNER', '-')
    emit('REASON', reason)


def finish():
    sys.stdout.write('\n'.join(out) + ('\n' if out else ''))
    sys.exit(0)


pkg_json = os.path.join(root, 'package.json')

if os.path.isfile(pkg_json):
    data = load_json(pkg_json)
    if data is None:
        none('package.json is not valid JSON')
        finish()
    deps = {}
    for field in ('dependencies', 'devDependencies'):
        deps.update(data.get(field) or {})
    scripts = data.get('scripts') or {}

    JS_RUNNERS = (
        ('vitest', ['run', '--reporter=verbose']),
        ('jest', ['--verbose', '--no-coverage']),
        # --no-bail: a fail-fast run hides every failure after the first.
        ('mocha', ['--recursive', '--no-bail']),
    )
    for name, args in JS_RUNNERS:
        if name not in deps:
            continue
        binary = node_bin(name)
        if binary is None:
            none('%s is declared in package.json but not installed '
                 '(run: npm install)' % name)
            finish()
        emit('RUNNER', name)
        emit('ARG', binary)
        for a in args:
            emit('ARG', a)
        break
    else:
        # npm init writes a placeholder "test" script that always exits 1.
        script = (scripts.get('test') or '').strip()
        if script and 'no test specified' not in script:
            emit('RUNNER', 'npm-test')
            emit('ARG', 'npm')
            emit('ARG', 'test')
            emit('PRECHECK', 'npm')
            emit('PRECHECK', '--version')
            emit('PRECHECK_MSG', 'npm is required to run the "test" script')
        else:
            none('no test runner detected (checked: %s)' % CHECKED)

    if (scripts.get('build') or '').strip():
        emit('BUILD', 'npm')
        emit('BUILD', 'run')
        emit('BUILD', 'build')

elif any(os.path.isfile(os.path.join(root, f))
         for f in ('pyproject.toml', 'setup.py', 'setup.cfg',
                   # pytest's own config files. A project configured the way
                   # pytest documents — pytest.ini and a tests/ dir, no packaging
                   # metadata — was reported "no test runner detected" and went
                   # unverified, though `pytest` ran fine in it.
                   'pytest.ini', 'tox.ini')):
    venv_python = os.path.join(root, '.venv', 'bin', 'python')
    # `python` is absent on systems that ship only `python3`; the old script
    # hard-coded it and reported a green suite as a failure.
    interpreter = venv_python if os.path.isfile(venv_python) else 'python3'
    emit('RUNNER', 'pytest')
    # --maxfail=0 overrides an addopts -x: a run that stops at the first
    # failure hides every failure after it.
    for a in (interpreter, '-m', 'pytest', '-v', '--maxfail=0'):
        emit('ARG', a)
    emit('PRECHECK', interpreter)
    emit('PRECHECK', '-c')
    emit('PRECHECK', 'import pytest')
    emit('PRECHECK_MSG', 'pytest is not importable by %s' % interpreter)

elif os.path.isfile(os.path.join(root, 'pubspec.yaml')):
    emit('RUNNER', 'flutter-test')
    for a in ('flutter', 'test'):
        emit('ARG', a)
    emit('PRECHECK', 'flutter')
    emit('PRECHECK', '--version')
    emit('PRECHECK_MSG', 'the flutter SDK is not on PATH')
    for a in ('flutter', 'analyze'):
        emit('BUILD', a)

elif os.path.isfile(os.path.join(root, 'go.mod')):
    emit('RUNNER', 'go-test')
    # -failfast=false: GOFLAGS=-failfast would hide every later failure.
    go_args = ['go', 'test', './...', '-v', '-failfast=false']
    # Go's default lets a hung test binary run 10 minutes PER PACKAGE.
    # Inject a per-binary limit — additive, never overriding: a project
    # that sets -timeout in GOFLAGS wins (command line beats GOFLAGS in
    # go, so injecting here would silently override it).
    if '-timeout' not in os.environ.get('GOFLAGS', ''):
        go_args.append('-timeout=120s')
    for a in go_args:
        emit('ARG', a)
    emit('PRECHECK', 'go')
    emit('PRECHECK', 'version')
    emit('PRECHECK_MSG', 'the go toolchain is not on PATH')

else:
    none('no test runner detected (checked: %s)' % CHECKED)

finish()
PYEOF

DETECTED=$(python3 "$PY_DETECT" "$ROOT")
if [ $? -ne 0 ]; then
  unverifiable "test-runner detection failed"
fi

TEST_RUNNER="-"
REASON=""
PRECHECK_MSG=""
TEST_ARGV=()
BUILD_ARGV=()
PRECHECK_ARGV=()

while IFS="$TAB" read -r kind value; do
  case "$kind" in
    RUNNER)       TEST_RUNNER="$value" ;;
    REASON)       REASON="$value" ;;
    ARG)          TEST_ARGV+=("$value") ;;
    BUILD)        BUILD_ARGV+=("$value") ;;
    PRECHECK)     PRECHECK_ARGV+=("$value") ;;
    PRECHECK_MSG) PRECHECK_MSG="$value" ;;
  esac
done <<< "$DETECTED"

if [ "$TEST_RUNNER" = "-" ]; then
  unverifiable "$REASON"
fi

# A declared runner that cannot actually run is unverifiable, not a failure.
if [ ${#PRECHECK_ARGV[@]} -gt 0 ]; then
  if ! (cd "$ROOT" && ${PRECHECK_ARGV[@]+"${PRECHECK_ARGV[@]}"}) >/dev/null 2>&1; then
    unverifiable "$PRECHECK_MSG"
  fi
fi

# ── Baseline helper (L2) ──
# One embedded script, several verbs. Embedded rather than shipped beside the
# gate: .sage/gates/scripts/ receives only the *.sh files.
PY_BASE="$PY_DETECT.base"
cat > "$PY_BASE" <<'PYEOF'
import datetime
import json
import os
import re
import subprocess
import sys

# ── Naming failures — strictly ─────────────────────────────────────────────
# A baseline may only ever EXCUSE a failure it can prove was already there, so
# every parser below returns either the COMPLETE set of failures, each named
# as precisely as the runner allows, or None ("cannot tell"). None is never
# excused. Completeness is checked against the runner's own failure count
# wherever it prints one; a run that was interrupted, crashed, or raised an
# unhandled error is never attributable, because tests that did not run
# cannot be judged. A failure that is a whole FILE (failed to load) is
# returned in `files` and is excused only while that file is unchanged.
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# Each runner's own "this run cannot be trusted" banners — matched only where
# the runner prints them (a line start, its banner shape), never anywhere in
# the output: a passing test TITLED "logs unhandled errors" is not one.
NEVER = {
    "pytest": re.compile(r"^!+ (?:Interrupted: |stopping after \d+ failures)", re.M),
    "go-test": re.compile(r"^panic: |^FAIL\s+\S+\s+\[(?:build|setup) failed\]", re.M),
    "vitest": re.compile(r"^⎯+ Unhandled Errors? ⎯|^\s*Vitest caught \d+ unhandled error", re.M),
    "jest": None,
    "mocha": re.compile(r"^\s*Exception during run:", re.M),
    "node": re.compile(r"^ℹ cancelled [1-9]|^ℹ Error\b", re.M),
    # The same banners in node's TAP ("# Error:" — a child's stderr echoed as
    # "# Error [ERR_…]" is a file failing to load, which names its file).
    "node-tap": re.compile(r"^# cancelled [1-9]|^# Error:", re.M),
}
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
            ".java", ".rb", ".dart", ".c", ".cc", ".cpp", ".h", ".swift", ".kt")


def _pytest(text):
    ids = []
    for line in text.splitlines():
        # Greedy: the LAST " FAILED"/" ERROR" before the progress column, so
        # parametrize ids holding spaces or " - " stay whole.
        m = re.match(r"^(\S.*::.*) (FAILED|ERROR)(?: +\[ *\d+%\])?\s*$", line)
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    tail = [l for l in text.splitlines() if re.match(r"^=+ .* in [\d.]+s", l)]
    if not tail:
        return None, None, "no pytest summary line"
    want = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b", tail[-1]))
    if want != len(ids):
        return None, None, "pytest reported %d failure(s), %d named" % (want, len(ids))
    return ids, {}, ""


def _go(text):
    """Every `=== RUN X` must close with `--- PASS/FAIL/SKIP: X` before its
    package line: a test that kills the binary (log.Fatal, os.Exit) closes
    nothing, and the tests after it never ran."""
    ids, pending, open_runs = [], [], set()
    for line in text.splitlines():
        m = re.match(r"^\s*=== RUN\s+(\S+)", line)
        if m:
            open_runs.add(m.group(1))
            continue
        m = re.match(r"^\s*--- (PASS|FAIL|SKIP): (\S+)", line)
        if m:
            open_runs.discard(m.group(2))
            if m.group(1) == "FAIL":
                pending.append(m.group(2))
            continue
        m = re.match(r"^(FAIL|ok)\s+(\S+)\s", line)
        if m:
            if open_runs:
                return None, None, "go test %s never finished in %s (the binary exited)" % (
                    sorted(open_runs)[0], m.group(2))
            if m.group(1) == "FAIL" and not pending:
                return None, None, "package %s failed with no failing test named" % m.group(2)
            ids += ["%s::%s" % (m.group(2), t) for t in pending]
            pending = []
    if pending or open_runs:
        return None, None, "go output ended mid-package"
    return ids, {}, ""


def _vitest(text):
    """Failed Tests entries are tests; EVERY Failed Suites entry is a whole
    file or describe block whose tests did not run (a failing beforeAll, an
    import error) — excusable only while its file is unchanged."""
    ids, files, section = [], {}, None
    for line in text.splitlines():
        if re.search(r"⎯ Failed Tests \d+ ⎯", line):
            section = "tests"
        elif re.search(r"⎯ Failed Suites \d+ ⎯", line):
            section = "suites"
        m = re.match(r"^\s*FAIL\s+(\S.*?)\s*$", line)
        if not m or section is None:
            continue
        name = m.group(1)
        if section == "suites":
            path = re.split(r" \[ | > ", name)[0]
            files["%s <suite did not run>" % name] = path
        elif name not in ids:
            ids.append(name)
    m = re.search(r"^\s*Tests\s+(\d+) failed", text, re.M)
    want = int(m.group(1)) if m else 0
    if want != len(ids):
        return None, None, "vitest reported %d failed test(s), %d named" % (want, len(ids))
    m = re.search(r"^\s*Test Files\s+(\d+) failed", text, re.M)
    named_files = {i.split(" > ")[0] for i in ids} | set(files.values())
    if (int(m.group(1)) if m else 0) != len(named_files):
        return None, None, "vitest reported failed files the output did not name"
    return ids + list(files), files, ""


def _jest(text):
    ids, files, current = [], {}, None
    for line in text.splitlines():
        m = re.match(r"^FAIL\s+(\S+)", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r"^  ● (.+?)\s*$", line)
        if m and current and not m.group(1).startswith("Console"):
            if m.group(1) == "Test suite failed to run":
                files["%s <failed to load>" % current] = current
            else:
                ident = "%s › %s" % (current, m.group(1))
                if ident not in ids:
                    ids.append(ident)
    m = re.search(r"^Tests:\s+(\d+) failed", text, re.M)
    want = int(m.group(1)) if m else 0
    if want != len(ids):
        return None, None, "jest reported %d failed test(s), %d named" % (want, len(ids))
    return ids + list(files), files, ""


def _mocha(text):
    """Titles come from the live tree, where indentation IS the structure:
    the summary below it cannot separate a title that ends in ':' from the
    error message that follows. A failing hook skips the tests it guards, so
    a run with one is never attributable."""
    lines = text.splitlines()
    want = next((int(m.group(1)) for m in
                 (re.match(r"^\s+(\d+) failing\s*$", l) for l in lines) if m), None)
    if want is None:
        return None, None, "no mocha failure summary"
    ids, stack = [], []
    for line in lines:
        if re.match(r"^\s+\d+ (passing|failing|pending)\b", line):
            break
        if not line.strip():
            continue
        ind = len(line) - len(line.lstrip(" "))
        body = line.strip()
        while stack and stack[-1][0] >= ind:
            stack.pop()
        m = re.match(r"^(\d+)\) (.*)$", body)
        if m:
            title = m.group(2)
            if re.match(r'^"(before|after) (all|each)" hook', title):
                return None, None, "a mocha hook failed — the tests it guards never ran"
            ident = " › ".join([t for _, t in stack] + [title])
            if ident not in ids:
                ids.append(ident)
        elif not re.match(r"^(✔|✓|-) ", body):
            stack.append((ind, body))
    if want != len(ids):
        return None, None, "mocha reported %d failing, %d named" % (want, len(ids))
    return ids, {}, ""


def _node(text):
    lines = text.splitlines()
    # Leaf failures in the live tree: a "✖ title" that does not close a
    # "▶ title" opened at the same indent (a parent failing because a child
    # did is not a failure of its own).
    leaves, stack = 0, []
    cut = next((i for i, l in enumerate(lines) if l.startswith("✖ failing tests:")),
               len(lines))
    for line in lines[:cut]:
        m = re.match(r"^(\s*)([▶✖✔﹣])\s(.+?)(?:\s+\([\d.]+m?s\))?\s*$", line)
        if not m:
            continue
        ind, mark, title = len(m.group(1)), m.group(2), m.group(3)
        while stack and stack[-1][0] > ind:
            stack.pop()
        if mark == "▶":
            stack.append((ind, title))
        elif mark == "✖":
            if stack and stack[-1] == (ind, title):
                stack.pop()
            else:
                leaves += 1
    ids, files, loc = [], {}, None
    for line in lines[cut:]:
        m = re.match(r"^test at (\S+?):(\d+):(\d+)$", line)
        if m:
            loc = m
            continue
        m = re.match(r"^✖ (.+?)(?:\s+\([\d.]+m?s\))?\s*$", line)
        if m and loc:
            if m.group(1) == loc.group(1):
                files["%s <failed to load>" % loc.group(1)] = loc.group(1)
            else:
                # file:line:col — exact; judge() maps lines through the diff
                # since the baseline, so a test that only MOVED stays itself.
                ident = "%s:%s:%s %s" % (loc.group(1), loc.group(2), loc.group(3),
                                         m.group(1))
                if ident not in ids:
                    ids.append(ident)
            loc = None
    if leaves != len(ids) + len(files):
        return None, None, "node reported %d failing test(s), %d named" % (
            leaves, len(ids) + len(files))
    return ids + list(files), files, ""


def _node_tap(text, root=None):
    """node --test's TAP — its default reporter off a terminal before node 23,
    which is how Sage runs it. Ids match _node's: "path:line:col title", the
    path relative to the project (TAP prints it absolute)."""
    base = os.path.realpath(root) if root else None
    lines = text.splitlines()
    ids, files = [], {}
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)not ok \d+ - (.*?)(\s+# (?:TODO|SKIP)\b.*)?$", line)
        if not m or m.group(3):
            continue
        ind = m.group(1) + "  "
        loc = kind = None
        if i + 1 < len(lines) and lines[i + 1] == ind + "---":
            for yl in lines[i + 2:]:
                if yl == ind + "...":
                    break
                lm = re.match(r"^%slocation: '(.+):(\d+):(\d+)'$" % re.escape(ind), yl)
                if lm:
                    loc = lm
                fm = re.match(r"^%sfailureType: '(\w+)'$" % re.escape(ind), yl)
                if fm:
                    kind = fm.group(1)
        if kind == "subtestsFailed":
            continue        # a parent failing because a child did
        if not loc:
            return None, None, "node reported a failing test (%s) without its location" % (
                m.group(2))
        path = loc.group(1)
        if base and os.path.isabs(path):
            real = os.path.realpath(path)
            if real == base or real.startswith(base + os.sep):
                path = os.path.relpath(real, base)
        title = re.sub(r"\\(.)", lambda e: {"n": "\n"}.get(e.group(1), e.group(1)),
                       m.group(2))
        if title == path:
            files["%s <failed to load>" % path] = path
        else:
            ident = "%s:%s:%s %s" % (path, loc.group(2), loc.group(3), title)
            if ident not in ids:
                ids.append(ident)
    return ids + list(files), files, ""


def _fmt(runner, text):
    if runner != "npm-test":
        return {"pytest": "pytest", "go-test": "go-test", "vitest": "vitest",
                "jest": "jest", "mocha": "mocha"}.get(runner)
    if re.search(r"^\s*Test Files\s", text, re.M):
        return "vitest"
    if re.search(r"^Test Suites:", text, re.M):
        return "jest"
    if re.search(r"^\s+\d+ failing\s*$", text, re.M):
        return "mocha"
    if re.search(r"^ℹ fail \d+", text, re.M):
        return "node"
    if re.search(r"^TAP version", text, re.M) and re.search(r"^# suites \d+", text, re.M):
        return "node-tap"
    return None


def tests_ran(runner, path):
    """How many tests this run executed, or None. A run that executed FEWER
    than the baseline's stopped early — a fail-fast setting (-x, bail,
    -failfast) or a crash — and the tests it skipped can hide anything."""
    try:
        text = ANSI.sub("", open(path, encoding="utf-8", errors="replace").read())
    except OSError:
        return None
    fmt = _fmt(runner, text)
    if fmt == "pytest":
        tail = [l for l in text.splitlines() if re.match(r"^=+ .* in [\d.]+s", l)]
        if not tail:
            return None
        return sum(int(n) for n in re.findall(
            r"(\d+) (?:passed|failed|errors?|skipped|xfailed|xpassed)\b", tail[-1]))
    if fmt == "go-test":
        return len(re.findall(r"^\s*=== RUN\s", text, re.M))
    if fmt in ("vitest", "jest"):
        # The outcomes listed, not the "(N)" / "N total" — a bailed run still
        # counts the tests it never reached in its total.
        m = re.search(r"^\s*Tests:?\s+(.*)$", text, re.M)
        if not m:
            return None
        n = sum(int(x) for x in re.findall(r"(\d+) (?:failed|passed|skipped|todo)\b",
                                           m.group(1)))
        # A bailed run lists fewer outcomes than it collected: vitest's "(N)",
        # jest's "Test Suites: … N total" / "1 of N total".
        total = re.search(r"\((\d+)\)\s*$", m.group(1)) if fmt == "vitest" else None
        if total and n < int(total.group(1)):
            return None
        suites = re.search(r"^Test Suites:\s+(.*)$", text, re.M) if fmt == "jest" else None
        if suites:
            listed = sum(int(x) for x in re.findall(r"(\d+) (?:failed|passed|skipped)\b",
                                                    suites.group(1)))
            st = re.search(r"(\d+) total", suites.group(1))
            if " of " in suites.group(1) or (st and listed < int(st.group(1))):
                return None
        return n or None
    elif fmt in ("node", "node-tap"):
        m = re.search(r"^(?:ℹ|#) tests (\d+)", text, re.M)
        return int(m.group(1)) if m else None
    elif fmt == "mocha":
        n = [int(x) for x in re.findall(r"^\s+(\d+) (?:passing|failing|pending)\b", text, re.M)]
        return sum(n) if n else None
    return None


def parse(runner, path, root=None):
    try:
        text = ANSI.sub("", open(path, encoding="utf-8", errors="replace").read())
    except OSError as exc:
        return None, None, "test output unreadable: %s" % exc
    fmt = _fmt(runner, text)
    parser = {"pytest": _pytest, "go-test": _go, "vitest": _vitest,
              "jest": _jest, "mocha": _mocha, "node": _node,
              "node-tap": lambda t: _node_tap(t, root)}.get(fmt)
    if parser is None:
        return None, None, "this runner's output cannot be attributed to named tests"
    bad = NEVER.get(fmt) and NEVER[fmt].search(text)
    if bad:
        return None, None, "the run was interrupted or raised outside a test (%s)" % bad.group(0).strip()
    return parser(text)


def git(root, *args):
    try:
        p = subprocess.run(["git", "-C", root, *args], capture_output=True,
                           text=True, timeout=15)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def dirty_sources(root):
    out = git(root, "status", "--porcelain", "--untracked-files=all")
    if out is None:
        return []
    dirty = []
    for line in out.splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        parts = path.split("/")
        if parts[0] in (".sage", "sage", ".claude", "node_modules"):
            continue
        if path.endswith(CODE_EXT):
            dirty.append(path)
    return dirty


def manifest_field(text, name):
    m = re.search(r"(?m)^%s\s*:\s*\"?([^\"\n#]*)" % re.escape(name), text)
    return m.group(1).strip() if m else ""


def active_cycle(root):
    """The cycle dir of the ONE in-progress manifest owned by this checkout,
    or "" — paused/blocked cycles, another checkout's, or two at once are
    never guessed between."""
    work = os.path.join(root, ".sage", "work")
    found = []
    try:
        cycles = sorted(os.listdir(work))
    except OSError:
        return ""
    for slug in cycles:
        manifest = os.path.join(work, slug, "manifest.md")
        try:
            text = open(manifest, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if manifest_field(text, "status").lower() != "in-progress":
            continue
        owner = manifest_field(text, "owner")
        if owner and os.path.realpath(os.path.expanduser(owner)) != os.path.realpath(root):
            continue
        found.append(os.path.join(work, slug))
    return found[0] if len(found) == 1 else ""


def started(root, cycle_dir):
    """Why recording a baseline now would be too late, or "": the cycle is
    past planning, or source changed since the commit that added its
    manifest. (Uncommitted edits are the `dirty` check's.)"""
    if not cycle_dir:
        return ""
    manifest = os.path.join(cycle_dir, "manifest.md")
    try:
        text = open(manifest, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""
    state = manifest_field(text, "gate_state").lower()
    if state in ("building", "gates-passed", "complete"):
        return "the cycle is already %s" % state
    # Review rounds or gate runs on record mean the cycle's work is under way
    # (the backstop where .sage/ is gitignored and the manifest has no commit).
    try:
        led = json.load(open(os.path.join(cycle_dir, "review-ledger.json"),
                             encoding="utf-8"))
        if led.get("gates") or any("instance" not in h for h in led.get("history", [])):
            return "the cycle's ledger already records review rounds or gate runs"
    except (OSError, ValueError):
        pass
    rel = os.path.relpath(manifest, root)
    born = (git(root, "log", "--diff-filter=A", "--format=%H", "--", rel) or "").split()
    if born:
        changed = (git(root, "diff", "--name-only", born[-1], "HEAD") or "").split()
        src = [c for c in changed if c.endswith(CODE_EXT)
               and c.split("/")[0] not in (".sage", "sage", ".claude", "node_modules")]
        if src:
            return "source changed since the cycle began (%s)" % ", ".join(src[:3])
    return ""


def cmd_record(out_path, dest, rc, timed_out, runner, root):
    if int(rc) == 0:
        ids, attributable, why = [], True, ""
    elif timed_out == "1":
        ids, attributable, why = [], False, "the suite timed out"
    else:
        ids, _, why = parse(runner, out_path, root)
        attributable = ids is not None
        ids = ids or []
    record = {
        "version": 3,
        "recorded_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "head": (git(root, "rev-parse", "HEAD") or "").strip() or None,
        "runner": runner,
        "exit": int(rc),
        "timed_out": timed_out == "1",
        "attributable": attributable,
        "unattributable_reason": why or None,
        "failing": ids,
        "tests_ran": tests_ran(runner, out_path),
    }
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "x", encoding="utf-8") as fh:      # never over an existing one
        json.dump(record, fh, indent=2)
        fh.write("\n")
    print("%d\t%s\t%s" % (len(ids), "yes" if attributable else "no", why))


_NODE_ID = re.compile(r"^(\S+?):(\d+):(\d+) (.*)$")


def _at_baseline(ident, head, root):
    """A node id names file:line:col. Edits above a test move its line, so map
    the line back through the diff since the baseline — but only through
    UNCHANGED lines: a test whose own line was edited is a different test and
    keeps its new coordinates (so it reads as new)."""
    m = _NODE_ID.match(ident)
    if not m:
        return ident
    path, line = m.group(1), int(m.group(2))
    old = git(root, "show", "%s:%s" % (head, path))
    try:
        new = open(os.path.join(root, path), encoding="utf-8", errors="replace").read()
    except OSError:
        return ident
    if old is None or old == new:
        return ident
    import difflib
    sm = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" and j1 < line <= j2:
            return "%s:%d:%s %s" % (path, i1 + (line - j1), m.group(3), m.group(4))
    return ident


def cmd_judge(out_path, base_path, runner, root):
    """EXCUSED <ids> | NEW <ids> | UNATTRIBUTABLE <why>, tab-separated."""
    try:
        base = json.load(open(base_path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("UNATTRIBUTABLE\tbaseline unreadable: %s" % exc)
        return
    if not base.get("attributable") or base.get("version") != 3:
        print("UNATTRIBUTABLE\tthe baseline names no failures it can vouch for")
        return
    head = base.get("head")
    if not head or git(root, "merge-base", "--is-ancestor", head, "HEAD") is None:
        print("UNATTRIBUTABLE\tthe baseline was not recorded in this branch's history")
        return
    ids, files, why = parse(runner, out_path, root)
    if ids is None:
        print("UNATTRIBUTABLE\t" + why)
        return
    ran, before = tests_ran(runner, out_path), base.get("tests_ran")
    if ran is None or not before or ran < before:
        print("UNATTRIBUTABLE\tfewer tests ran (%s) than at the baseline (%s) — a "
              "fail-fast setting or a crash stopped the run, and what it skipped "
              "could hide anything" % (ran, before))
        return
    if not ids:
        print("UNATTRIBUTABLE\tno failing test could be named in this run's output")
        return
    known = set(base.get("failing") or [])
    ids = [_at_baseline(i, head, root) for i in ids]
    new = [i for i in ids if i not in known]
    # A file that failed to load hides every test inside it: excused only
    # while the file is exactly as it was when the baseline was recorded.
    changed = git(root, "diff", "--name-only", head, "--") or ""
    changed = set(changed.split()) | set(dirty_sources(root))
    new += ["%s (changed since the baseline; its tests cannot run)" % f
            for i, f in files.items() if i in known and f in changed]
    if new:
        print("NEW\t" + "\t".join(new))
    else:
        print("EXCUSED\t" + "\t".join(ids))


verb = sys.argv[1]
if verb == "dirty":
    for p in dirty_sources(sys.argv[2]):
        print(p)
elif verb == "cycle":
    print(active_cycle(sys.argv[2]))
elif verb == "started":
    print(started(sys.argv[2], sys.argv[3]))
elif verb == "record":
    cmd_record(*sys.argv[2:8])
elif verb == "judge":
    cmd_judge(*sys.argv[2:6])
PYEOF

# Recording happens once per cycle, before its first edit, or not at all: a
# baseline taken over the cycle's own edits — or re-taken after it committed
# them — would excuse the cycle's own failures. To re-record, a human deletes
# the file. --force skips only the uncommitted-edits check (for edits that
# predate the cycle).
if [ -n "$RECORD_BASELINE" ]; then
  if [ -e "$RECORD_BASELINE" ]; then
    unverifiable "a baseline already exists at $RECORD_BASELINE — it is recorded once, at cycle start, and only the user may replace it."
  fi
  if [ "$FORCE" = false ]; then
    DIRTY=$(python3 "$PY_BASE" dirty "$ROOT")
    if [ -n "$DIRTY" ]; then
      unverifiable "cannot record a baseline over uncommitted source changes ($(printf '%s' "$DIRTY" | head -3 | tr '\n' ' ')) — a baseline describes the tree BEFORE the cycle's first edit. Record it then, or pass --force if these changes predate the cycle."
    fi
  fi
fi

# The cycle this run belongs to: the ONE in-progress cycle of this checkout.
# Its own baseline judges the run (never another cycle's), and its ledger
# counts the attempt.
CYCLE_DIR=$(python3 "$PY_BASE" cycle "$ROOT")
if [ -n "$RECORD_BASELINE" ]; then
  TOO_LATE=$(python3 "$PY_BASE" started "$ROOT" "$CYCLE_DIR")
  if [ -n "$TOO_LATE" ]; then
    unverifiable "too late to record a baseline: $TOO_LATE. A baseline describes the tree before the cycle's work; it is recorded when the cycle's manifest is created, or not at all — Gate 5 then judges every failure."
  fi
fi
BASELINE_NOTE=""
if [ -z "$RECORD_BASELINE" ] && [ "$BASELINE_MODE" = auto ]; then
  BASELINE=""
  if [ -n "$CYCLE_DIR" ] && [ -f "$CYCLE_DIR/verify-baseline.json" ]; then
    BASELINE="$CYCLE_DIR/verify-baseline.json"
  fi
fi
if [ "$BASELINE_MODE" = file ] && [ ! -f "$BASELINE" ]; then
  unverifiable "baseline file not found: $BASELINE"
fi

vlog "Test runner: $TEST_RUNNER"
vlog "Command: ${TEST_ARGV[*]+"${TEST_ARGV[*]}"}"
vlog ""

# ── Step 2: Run tests ──
#
# argv is executed directly. The old script built a string and ran `eval` on
# it, which is needless indirection for an internally-constructed command and
# a hazard the moment detection reads anything from project config.
vlog "── Running tests ──"

# JS runners default to watch mode in a TTY-adjacent world; CI=true is
# the additive, runner-native "run once and exit" switch.
RUN_PREFIX=()
case "$TEST_RUNNER" in
  vitest|jest|mocha|npm-test) RUN_PREFIX=(env CI=true) ;;
esac

TEST_SENTINEL="$PY_DETECT.sentinel-test"
sage_bounded_run "$PY_DETECT.out-test" "$TEST_SENTINEL" \
  "$VERIFY_TIMEOUT" "$ROOT" \
  ${RUN_PREFIX[@]+"${RUN_PREFIX[@]}"} ${TEST_ARGV[@]+"${TEST_ARGV[@]}"}
TEST_RC=$?
TEST_OUTPUT=$(cat "$PY_DETECT.out-test" 2>/dev/null)

TIMED_OUT=0
if [ -f "$TEST_SENTINEL" ] && [ "$TEST_RC" -ne 0 ]; then TIMED_OUT=1; fi

# ── Record mode: write the baseline and stop (no build, no verdict) ──
if [ -n "$RECORD_BASELINE" ]; then
  if ! REC=$(python3 "$PY_BASE" record "$PY_DETECT.out-test" "$RECORD_BASELINE" \
        "$TEST_RC" "$TIMED_OUT" "$TEST_RUNNER" "$ROOT"); then
    unverifiable "could not write the baseline to $RECORD_BASELINE"
  fi
  REC_N="${REC%%"$TAB"*}"
  REC_ATTR="${REC#*"$TAB"}"; REC_WHY="${REC_ATTR#*"$TAB"}"; REC_ATTR="${REC_ATTR%%"$TAB"*}"
  if [ "$TEST_RC" -eq 0 ]; then
    log "📌 Baseline recorded: the suite is green at cycle start → $RECORD_BASELINE"
  elif [ "$REC_ATTR" = yes ]; then
    log "📌 Baseline recorded: $REC_N failing test(s)/file(s) named at cycle start → $RECORD_BASELINE"
    python3 -c 'import json,sys;[print("   - "+i) for i in json.load(open(sys.argv[1]))["failing"]]' "$RECORD_BASELINE"
    log "   Gate 5 will not hold the cycle to these; any OTHER failure still fails it."
  else
    log "📌 Baseline recorded, but its failures could not be named: ${REC_WHY:-unknown output}"
    log "   → $RECORD_BASELINE excuses nothing: Gate 5 will judge every failure this cycle."
  fi
  exit 0
fi

# ── Judge a red run against the baseline (never a timeout) ──
BASE_VERDICT=""
if [ "$TEST_RC" -ne 0 ] && [ "$TIMED_OUT" = 0 ] && [ "$BASELINE_MODE" != off ] \
   && [ -n "$BASELINE" ]; then
  BASE_VERDICT=$(python3 "$PY_BASE" judge "$PY_DETECT.out-test" "$BASELINE" \
                 "$TEST_RUNNER" "$ROOT")
fi

if [ "${BASE_VERDICT%%"$TAB"*}" = EXCUSED ]; then
  _ids="${BASE_VERDICT#*"$TAB"}"
  _n=$(printf '%s\n' "$_ids" | tr '\t' '\n' | grep -c .)
  # Printed even when quiet: an excused failure is evidence, not decoration.
  log "✅ NO NEW TEST FAILURES — all $_n named failure(s) were already failing at cycle start (baseline ${BASELINE#"$ROOT"/}):"
  printf '%s\n' "$_ids" | tr '\t' '\n' | sed 's/^/   - /'
  TESTS_NOTE="no new test failures; $_n pre-existing (baseline)"
elif [ -f "$TEST_SENTINEL" ] && [ "$TEST_RC" -ne 0 ]; then
  log "❌ TESTS TIMED OUT — suite exceeded ${VERIFY_TIMEOUT}s; the watchdog killed it"
  log "   A hanging test is a defect surfaced, not hidden. If the suite is"
  log "   legitimately slower, raise verify_timeout in .sage/config.yaml."
  log ""
  log "── Test output (last 40 lines) ──"
  printf '%s\n' "$TEST_OUTPUT" | tail -40
  PASS=false
elif [ "$TEST_RC" -ne 0 ]; then
  log "❌ TESTS FAILED (exit code: $TEST_RC)"
  case "${BASE_VERDICT%%"$TAB"*}" in
    NEW)
      log "   Not in the cycle's baseline (introduced by this cycle):"
      printf '%s\n' "${BASE_VERDICT#*"$TAB"}" | tr '\t' '\n' | sed 's/^/   - /' ;;
    UNATTRIBUTABLE)
      log "   Baseline not applied — ${BASE_VERDICT#*"$TAB"}." ;;
  esac
  [ -n "$BASELINE_NOTE" ] && log "   ($BASELINE_NOTE)"
  log ""
  log "── Test output (last 40 lines) ──"
  printf '%s\n' "$TEST_OUTPUT" | tail -40
  PASS=false
else
  vlog "✅ ALL TESTS PASSED"
  SUMMARY=$(printf '%s\n' "$TEST_OUTPUT" | tail -5 | grep -e "passed" -e "PASS" -e "ok" | tail -1)
  [ -n "$SUMMARY" ] && vlog "    $SUMMARY"
  TESTS_NOTE="tests passed"
fi

vlog ""

# ── Step 3: Check build compiles ──
vlog "── Build check ──"
BUILD_NOTE="no build step"
if [ ${#BUILD_ARGV[@]} -gt 0 ]; then
  BUILD_SENTINEL="$PY_DETECT.sentinel-build"
  sage_bounded_run "$PY_DETECT.out-build" "$BUILD_SENTINEL" \
    "$VERIFY_TIMEOUT" "$ROOT" ${BUILD_ARGV[@]+"${BUILD_ARGV[@]}"}
  BUILD_RC=$?
  BUILD_OUTPUT=$(cat "$PY_DETECT.out-build" 2>/dev/null)
  if [ -f "$BUILD_SENTINEL" ] && [ "$BUILD_RC" -ne 0 ]; then
    log "❌ BUILD TIMED OUT — exceeded ${VERIFY_TIMEOUT}s (${BUILD_ARGV[*]+"${BUILD_ARGV[*]}"})"
    printf '%s\n' "$BUILD_OUTPUT" | tail -20
    PASS=false
  elif [ "$BUILD_RC" -ne 0 ]; then
    log "❌ BUILD FAILED (${BUILD_ARGV[*]+"${BUILD_ARGV[*]}"})"
    printf '%s\n' "$BUILD_OUTPUT" | tail -20
    PASS=false
  else
    vlog "✅ Build succeeds"
    BUILD_NOTE="build ok"
  fi
else
  vlog "⚠️  No build step detected"
fi

vlog ""

# ── Step 4: Check for leftover markers ──
vlog "── Clean code check ──"
TODO_COUNT=0
for d in src app lib; do
  [ -d "$ROOT/$d" ] || continue
  n=$(grep -rn -e TODO -e FIXME -e HACK -e XXX \
        --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
        --include="*.py" --include="*.dart" \
        "$ROOT/$d" 2>/dev/null | wc -l | tr -d ' ')
  TODO_COUNT=$((TODO_COUNT + n))
done

if [ "$TODO_COUNT" -gt 0 ]; then
  # Markers never fail the gate (they are advisory) — but they are evidence, so
  # they print even when quiet.
  log "⚠️  Found $TODO_COUNT TODO/FIXME/HACK/XXX markers in source"
  MARKER_NOTE="$TODO_COUNT marker(s)"
  if [ "$QUIET" = false ]; then
    for d in src app lib; do
      [ -d "$ROOT/$d" ] || continue
      grep -rn -e TODO -e FIXME -e HACK -e XXX \
        --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
        --include="*.py" --include="*.dart" \
        "$ROOT/$d" 2>/dev/null | head -5
    done
  fi
else
  vlog "✅ No TODO/FIXME/HACK markers"
  MARKER_NOTE="no markers"
fi

vlog ""

# ── Count the attempt (review 2026-10-26, L1) ──
# A run made AS Gate 5 (--gate, which the quality-gates workflow passes) lands
# in the in-progress cycle's ledger by itself — re-running the gate on each
# "continue" is exactly the loop the budget exists to end, so the count is not
# left to the agent. TDD runs and the commit gate's evidence runs do not pass
# --gate and are not gate attempts. The
# verdict (RETRY / ESCALATE / STOP_BUDGET) is printed; the exit code is not
# changed by it. SAGE_VERIFY_NO_LEDGER=1 skips it (graders on a finished tree).
record_attempt() {
  [ "$GATE_RUN" = true ] && [ -n "$CYCLE_DIR" ] && [ -z "${SAGE_VERIFY_NO_LEDGER:-}" ] || return 0
  local here review_py=""
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  for cand in "$ROOT/sage/runtime/tools/review.py" "$here/../../../runtime/tools/review.py"; do
    if [ -f "$cand" ]; then review_py="$cand"; break; fi
  done
  [ -n "$review_py" ] || return 0
  local out verdict
  out=$(python3 "$review_py" gate "$CYCLE_DIR/review-ledger.json" --gate 5 \
        --exit "$1" --evidence "$2" 2>&1) || {
    log "⚠️  could not record this run in the cycle ledger: $out"; return 0; }
  verdict=$(printf '%s' "$out" | python3 -c 'import json,sys;d=json.load(sys.stdin);b=d["budget"];print("%s (gate 5: %d consecutive failure(s); cycle budget %d/%s)"%(d["verdict"],d["consecutive_failures"],b["spent"],b["limit"] or "off"))' 2>/dev/null)
  case "$verdict" in
    ESCALATE*)    log "🛑 Gate ledger: $verdict — stop retrying; present the failures to the user." ;;
    STOP_BUDGET*) log "🛑 Gate ledger: $verdict — the cycle's budget is spent; run review.py summary and stop." ;;
    "")           ;;
    *)            vlog "Gate ledger: $verdict" ;;
  esac
}

# ── Result ──
vlog "═══ Gate 5 Result ═══"
if [ "$PASS" = true ]; then
  # Quiet PASS collapses to one line that still carries the word the gate
  # harness asserts on (PASS) plus the summary facts. Verbose keeps the banner.
  log "✅ Gate 5 PASS — ${TESTS_NOTE:-tests passed}; ${BUILD_NOTE}; ${MARKER_NOTE:-no markers}"
  record_attempt 0 "${TESTS_NOTE:-tests passed}"
  exit 0
else
  log "❌ FAIL — See evidence above"
  record_attempt 1 "tests or build failed (exit ${TEST_RC:-?})"
  exit 1
fi
