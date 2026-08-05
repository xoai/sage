#!/usr/bin/env bash
# sage-spec-check.sh — Deterministic checks for Gate 1 (Spec Compliance)
# Verifies that files listed in a task spec actually exist.
# Usage: bash sage/core/gates/scripts/sage-spec-check.sh [--quiet] <plan-file> <task-number>
#
# Exit contract (ADR-1):
#   0 = every declared deliverable exists
#   1 = a declared deliverable is missing, or the task is absent from the plan
#   2 = unverifiable — the task declares no deliverables to check
#
# --quiet (context diet, profile 2026-07-15): drop the section banners on the
# PASS path. The per-deliverable existence lines STAY even when quiet — a spec
# PASS that does not name what it checked is the vacuous pass this gate's
# tests exist to prevent. A FAIL or UNVERIFIABLE is never trimmed.
#
# Task extraction runs in python3. It used to be
#     awk "/Task ${N}[^0-9]/,/^- \[/"
# whose range starts and ends on the task's own line, because Sage's own plan
# template writes each task as `- [ ] **Task 1:** …`. The **Files:** line on
# the following line was never read, so the gate extracted no paths, printed
# "Manual verification required", and passed every plan it was given.

set -uo pipefail

QUIET=false
_pos=()
for _arg in "$@"; do
  case "$_arg" in
    --quiet) QUIET=true ;;
    *) _pos+=("$_arg") ;;
  esac
done
PLAN="${_pos[0]:-}"
TASK_NUM="${_pos[1]:-}"
PASS=true

log()  { echo "$1"; }                        # always printed
vlog() { [ "$QUIET" = true ] || echo "$1"; }  # decorative — dropped when quiet
fail() { log "❌ $1"; PASS=false; }

if [ -z "$PLAN" ] || [ ! -f "$PLAN" ] || [ -z "$TASK_NUM" ]; then
  echo "Usage: sage-spec-check.sh [--quiet] <plan-file> <task-number>"
  echo "  plan-file: path to plan.md"
  echo "  task-number: task number to verify (e.g., 1, 2, 3)"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  log "═══ Gate 1 Result ═══"
  log "⚠️ UNVERIFIABLE — python3 is required to parse the plan"
  exit 2
fi

vlog "═══ Sage Gate 1: Spec Compliance Check ═══"
vlog "Plan: $PLAN"
vlog "Task: $TASK_NUM"
vlog ""

# ── Extract the task's declared deliverables ──
#
# Protocol:
#   FOUND         <0|1>
#   CHECKBOX      <complete|incomplete|unknown>
#   DELIV         <path>  <0|1 exists>  <Files|Output>
#   TEST          <path>  <test-file|->
#   MENTIONS_TEST <0|1>
#
# Temp file, not an inline heredoc inside `$( … )`: bash 3.2 mis-parses that.
PY_EXTRACT=$(mktemp "${TMPDIR:-/tmp}/sage-gate1-XXXXXX") || {
  log "⚠️ UNVERIFIABLE — could not create a temporary file"
  exit 2
}
trap 'rm -f "$PY_EXTRACT"' EXIT

cat > "$PY_EXTRACT" <<'PYEOF'
import glob
import os
import re
import sys

plan_path, task_num = sys.argv[1], sys.argv[2]
out = []


def emit(*fields):
    out.append('\t'.join(str(f) for f in fields))


# `- [ ] **Task 1:** name`, `- [x] Task 1: name`
TASK_START = re.compile(r'^\s*-\s*\[(?P<box>[ xX])\]\s*\*{0,2}Task\s+(?P<num>\d+)\b')
HEADING = re.compile(r'^#{1,6}\s')
FIELD = r'^\s*[-*]?\s*\*{0,2}%s:?\*{0,2}\s*:?\s*(?P<val>.+)$'
FILES_RE = re.compile(FIELD % 'Files', re.I)
OUTPUT_RE = re.compile(FIELD % 'Output', re.I)

KNOWN_EXT = ('.ts', '.tsx', '.js', '.jsx', '.py', '.dart', '.md', '.css',
             '.html', '.go', '.rs', '.java', '.rb', '.sh', '.yaml', '.yml',
             '.json', '.toml')

try:
    with open(plan_path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
except OSError:
    emit('FOUND', 0)
    sys.stdout.write('\n'.join(out) + '\n')
    sys.exit(0)

# ── locate the task block: its own line through the line before the next
#    task (or the next heading, or EOF) ──
start = None
box = None
for i, line in enumerate(lines):
    m = TASK_START.match(line)
    if m and m.group('num') == task_num:
        start = i
        box = m.group('box')
        break

if start is None:
    emit('FOUND', 0)
    sys.stdout.write('\n'.join(out) + '\n')
    sys.exit(0)

end = len(lines)
for j in range(start + 1, len(lines)):
    if TASK_START.match(lines[j]) or HEADING.match(lines[j]):
        end = j
        break

block = lines[start:end]

emit('FOUND', 1)
emit('CHECKBOX', 'complete' if box in ('x', 'X') else 'incomplete')
emit('MENTIONS_TEST', 1 if re.search(r'\btests?\b', '\n'.join(block), re.I) else 0)


def paths_from(value):
    found = []
    for token in value.split(','):
        token = token.strip().strip('`').strip()
        if not token:
            continue
        # `{exact_file_paths}` and friends are unfilled template placeholders.
        if '{' in token or '}' in token:
            continue
        if token.lower() in ('none', 'n/a', '(none)'):
            continue
        found.append(token)
    return found


deliverables = []
for line in block:
    m = FILES_RE.match(line)
    if m:
        deliverables += [(p, 'Files') for p in paths_from(m.group('val'))]
        continue
    m = OUTPUT_RE.match(line)
    if m:
        deliverables += [(p, 'Output') for p in paths_from(m.group('val'))]

if not deliverables:
    # Fall back to any backticked path with a recognizable extension.
    for token in re.findall(r'`([^`]+)`', '\n'.join(block)):
        if token.endswith(KNOWN_EXT) and '{' not in token:
            deliverables.append((token, 'Files'))

seen = set()
for path, kind in deliverables:
    if path in seen:
        continue
    seen.add(path)
    emit('DELIV', path, 1 if os.path.isfile(path) else 0, kind)


def find_test(path):
    stem, _ = os.path.splitext(path)
    base = os.path.basename(stem)
    d = os.path.dirname(path) or '.'
    patterns = [
        '%s.test.*' % stem, '%s.spec.*' % stem,
        os.path.join(d, '__tests__', base + '.*'),
        os.path.join(d, 'test_%s.*' % base),
        os.path.join('test', base + '.*'),
        os.path.join('tests', base + '.*'),
        os.path.join('tests', 'test_%s.*' % base),
    ]
    for pat in patterns:
        for hit in sorted(glob.glob(pat)):
            if hit != path:
                return hit
    return '-'


for path, kind in deliverables:
    if kind == 'Files':
        emit('TEST', path, find_test(path))

sys.stdout.write('\n'.join(out) + '\n')
PYEOF

EXTRACT=$(python3 "$PY_EXTRACT" "$PLAN" "$TASK_NUM")
if [ $? -ne 0 ]; then
  log "═══ Gate 1 Result ═══"
  log "⚠️ UNVERIFIABLE — could not parse $PLAN"
  exit 2
fi

FOUND=0
CHECKBOX="unknown"
MENTIONS_TEST=0
CHECKED=0
MISSING=0
DELIV_LINES=""
TEST_LINES=""

while IFS=$'\t' read -r kind a b c; do
  case "$kind" in
    FOUND)         FOUND="$a" ;;
    CHECKBOX)      CHECKBOX="$a" ;;
    MENTIONS_TEST) MENTIONS_TEST="$a" ;;
    DELIV)         CHECKED=$((CHECKED + 1))
                   [ "$b" = "0" ] && MISSING=$((MISSING + 1))
                   DELIV_LINES="${DELIV_LINES}${a}|${b}|${c}"$'\n' ;;
    TEST)          TEST_LINES="${TEST_LINES}${a}|${b}"$'\n' ;;
  esac
done <<< "$EXTRACT"

# ── Step 1: Task extraction ──
vlog "── Task extraction ──"
if [ "$FOUND" != "1" ]; then
  log "❌ Task $TASK_NUM not found in plan"
  vlog ""
  vlog "═══ Gate 1 Result ═══"
  log "❌ FAIL — Task $TASK_NUM is not in $PLAN"
  exit 1
fi
vlog "  Found task section"

# ── Step 2: Check declared deliverables exist ──
vlog ""
vlog "── File existence check ──"

if [ "$CHECKED" -eq 0 ]; then
  vlog "  Task $TASK_NUM declares no Files: or Output: deliverables"
  vlog ""
  vlog "═══ Gate 1 Result ═══"
  log "⚠️ UNVERIFIABLE — task $TASK_NUM declares no deliverables to check"
  exit 2
fi

# The per-deliverable lines are evidence, not decoration — they print even when
# quiet, so a PASS still names the paths it actually resolved.
while IFS='|' read -r path exists kind; do
  [ -z "$path" ] && continue
  if [ "$exists" = "1" ]; then
    log "  ✅ $path exists ($kind)"
  else
    fail "File not found: $path (listed as $kind in task spec)"
  fi
done <<< "$DELIV_LINES"

vlog ""
vlog "  Checked $CHECKED files, $MISSING missing"

# ── Step 3: Check task checkbox status ──
vlog ""
vlog "── Completion status ──"
case "$CHECKBOX" in
  complete)   vlog "  ✅ Task $TASK_NUM is marked complete in plan" ;;
  incomplete) vlog "  ⚠️  Task $TASK_NUM is NOT yet marked complete" ;;
  *)          vlog "  ⚠️  Could not determine checkbox status" ;;
esac

# ── Step 4: Check for test files ──
vlog ""
vlog "── Test existence ──"
if [ "$MENTIONS_TEST" = "1" ] && [ -n "$TEST_LINES" ]; then
  while IFS='|' read -r path testfile; do
    [ -z "$path" ] && continue
    if [ "$testfile" = "-" ]; then
      vlog "  ⚠️  No test file found for $path"
    else
      vlog "  ✅ Test found: $testfile"
    fi
  done <<< "$TEST_LINES"
else
  vlog "  No test mentioned in task spec"
fi

vlog ""

# ── Result ──
vlog "═══ Gate 1 Result ═══"
if [ "$PASS" = true ]; then
  log "✅ PASS — All $CHECKED spec deliverable(s) verified"
  exit 0
else
  log "❌ FAIL — $MISSING of $CHECKED declared deliverable(s) missing"
  exit 1
fi
