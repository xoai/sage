#!/usr/bin/env bash
# sage-verify.sh — Deterministic verification for Gate 5
# Runs tests, checks results, collects evidence.
# Usage: bash sage/core/gates/scripts/sage-verify.sh [project-root]
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

set -uo pipefail

ROOT="${1:-.}"
PASS=true

log() { echo "$1"; }

unverifiable() {
  log ""
  log "═══ Gate 5 Result ═══"
  log "⚠️ UNVERIFIABLE — $1"
  exit 2
}

log "═══ Sage Gate 5: Verification ═══"
log "Root: $ROOT"
log "Time: $(date -Iseconds 2>/dev/null || date)"
log ""

if ! ROOT=$(cd "$ROOT" 2>/dev/null && pwd); then
  unverifiable "project root does not exist: ${1:-.}"
fi

if ! command -v python3 >/dev/null 2>&1; then
  unverifiable "python3 is required to detect the test runner"
fi

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
trap 'rm -f "$PY_DETECT"' EXIT

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
        ('mocha', ['--recursive']),
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
    for a in (interpreter, '-m', 'pytest', '-v'):
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
    for a in ('go', 'test', './...', '-v'):
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

while IFS=$'\t' read -r kind value; do
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

log "Test runner: $TEST_RUNNER"
log "Command: ${TEST_ARGV[*]+"${TEST_ARGV[*]}"}"
log ""

# ── Step 2: Run tests ──
#
# argv is executed directly. The old script built a string and ran `eval` on
# it, which is needless indirection for an internally-constructed command and
# a hazard the moment detection reads anything from project config.
log "── Running tests ──"

TEST_OUTPUT=$(cd "$ROOT" && ${TEST_ARGV[@]+"${TEST_ARGV[@]}"} 2>&1)
TEST_RC=$?

if [ "$TEST_RC" -ne 0 ]; then
  log "❌ TESTS FAILED (exit code: $TEST_RC)"
  log ""
  log "── Test output (last 40 lines) ──"
  printf '%s\n' "$TEST_OUTPUT" | tail -40
  PASS=false
else
  log "✅ ALL TESTS PASSED"
  SUMMARY=$(printf '%s\n' "$TEST_OUTPUT" | tail -5 | grep -e "passed" -e "PASS" -e "ok" | tail -1)
  [ -n "$SUMMARY" ] && log "    $SUMMARY"
fi

log ""

# ── Step 3: Check build compiles ──
log "── Build check ──"
if [ ${#BUILD_ARGV[@]} -gt 0 ]; then
  BUILD_OUTPUT=$(cd "$ROOT" && ${BUILD_ARGV[@]+"${BUILD_ARGV[@]}"} 2>&1)
  if [ $? -ne 0 ]; then
    log "❌ BUILD FAILED (${BUILD_ARGV[*]+"${BUILD_ARGV[*]}"})"
    printf '%s\n' "$BUILD_OUTPUT" | tail -20
    PASS=false
  else
    log "✅ Build succeeds"
  fi
else
  log "⚠️  No build step detected"
fi

log ""

# ── Step 4: Check for leftover markers ──
log "── Clean code check ──"
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
  log "⚠️  Found $TODO_COUNT TODO/FIXME/HACK/XXX markers in source"
  for d in src app lib; do
    [ -d "$ROOT/$d" ] || continue
    grep -rn -e TODO -e FIXME -e HACK -e XXX \
      --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
      --include="*.py" --include="*.dart" \
      "$ROOT/$d" 2>/dev/null | head -5
  done
else
  log "✅ No TODO/FIXME/HACK markers"
fi

log ""

# ── Result ──
log "═══ Gate 5 Result ═══"
if [ "$PASS" = true ]; then
  log "✅ PASS — All verifications passed"
  exit 0
else
  log "❌ FAIL — See evidence above"
  exit 1
fi
