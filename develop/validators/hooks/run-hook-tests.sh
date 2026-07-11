#!/usr/bin/env bash
# run-hook-tests.sh — tests for the Claude Code spec-gate hook (30-§3).
#
# Simulates Claude Code's PreToolUse I/O by piping tool-input JSON to
# sage-spec-gate.sh inside fixture projects built in a temp dir. Covers the
# §11 acceptance matrix H1-H9.
#
# Usage:  bash develop/validators/hooks/run-hook-tests.sh [--only ID] [--verbose]
# Exit:   0 = every case behaved as declared | 1 = a case regressed | 2 = bad args
#
# Like the gate harness, a case marked --xfail documents behavior not yet
# implemented; when it starts passing the harness reports XPASS and fails,
# forcing the marker's removal.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
HOOK="${SAGE_SPEC_GATE:-$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-spec-gate.sh}"
DEG_LOG="${SAGE_DEG_LOG:-$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-degradation-log.sh}"
TDD_GATE="${SAGE_TDD_GATE:-$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-tdd-gate.sh}"

ONLY=""
VERBOSE=false
while [ $# -gt 0 ]; do
  case "$1" in
    --only)       ONLY="$2"; shift 2 ;;
    --verbose|-v) VERBOSE=true; shift ;;
    -h|--help)    sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

N_PASS=0; N_FAIL=0; N_XFAIL=0; N_XPASS=0
FAILED_IDS=""

# ── fixture builders ──────────────────────────────────────────────────────
new_project() {
  local d; d="$(mktemp -d "${TMPDIR:-/tmp}/sage-hooktest-XXXXXX")/proj"
  mkdir -p "$d/.sage/work" "$d/src"
  echo "$d"
}

set_config() {  # set_config <proj> <yaml-line>
  printf 'sage-version: "1.1.11"\n%s\n' "$2" > "$1/.sage/config.yaml"
}

add_manifest() {  # add_manifest <proj> <slug> <gate_state> [status] [qa]
  local status="${4:-in-progress}"
  local qa="${5:-}"
  mkdir -p "$1/.sage/work/$2"
  printf -- '---\ncycle_id: "%s"\nworkflow: build\nphase: spec\nstatus: %s\ntier: standard\ngate_state: %s\n' \
    "$2" "$status" "$3" > "$1/.sage/work/$2/manifest.md"
  # Omitted entirely when empty — that is the pre-upgrade manifest, which must
  # never be surprise-blocked by a field it has never heard of.
  [ -n "$qa" ] && printf -- 'qa: %s\n' "$qa" >> "$1/.sage/work/$2/manifest.md"
  printf -- '---\n\n# Cycle: %s\n' "$2" >> "$1/.sage/work/$2/manifest.md"
}


# ── TDD-gate fixtures (the gate reads git, so these are real repos) ──────────
tdd_project() {  # tdd_project [--no-tests] → prints project dir; has a committed suite
  local d; d="$(mktemp -d "${TMPDIR:-/tmp}/sage-tddtest-XXXXXX")/proj"
  mkdir -p "$d/src" "$d/tests" "$d/.sage"
  printf 'sage-version: "1.2.0"\ntdd_enforcement: true\n' > "$d/.sage/config.yaml"
  printf 'TIMEOUT = 30\n' > "$d/src/config.py"
  [ "${1:-}" = "--no-tests" ] || printf 'def test_x():\n    assert True\n' > "$d/tests/test_x.py"
  ( cd "$d" && git init -q \
      && git -c user.email=t@t -c user.name=t add -A \
      && git -c user.email=t@t -c user.name=t commit -qm seed ) >/dev/null 2>&1
  echo "$d"
}

report() {  # report <status> <id> <label> [detail...]
  local st="$1" id="$2" label="$3"; shift 3
  printf '  %-7s %-4s %s\n' "[$st]" "$id" "$label"
  while [ $# -gt 0 ]; do printf '            %s\n' "$1"; shift; done
}

# ── assert ────────────────────────────────────────────────────────────────
# assert <id> <label> <proj> <json> --exit N [--stderr S]... [--no-stderr S]...
#        [--env K=V]... [--xfail REASON]
assert() {
  local id="$1" label="$2" proj="$3" json="$4"; shift 4
  [ -n "$ONLY" ] && [ "$ONLY" != "$id" ] && return 0

  local want_exit="" xfail="" hook="$HOOK"
  local want=() nowant=() envs=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --exit)      want_exit="$2"; shift 2 ;;
      --stderr)    want+=("$2"); shift 2 ;;
      --no-stderr) nowant+=("$2"); shift 2 ;;
      --env)       envs+=("$2"); shift 2 ;;
      --hook)      hook="$2"; shift 2 ;;
      --xfail)     xfail="$2"; shift 2 ;;
      *) echo "assert $id: unknown option $1" >&2; exit 2 ;;
    esac
  done

  local errfile rc stderr
  errfile="$(mktemp)"
  ( cd "$proj" && printf '%s' "$json" \
      | env ${envs[@]+"${envs[@]}"} bash "$hook" >/dev/null 2>"$errfile" )
  rc=$?
  stderr="$(cat "$errfile")"; rm -f "$errfile"

  local ok=true problems=()
  if [ "$rc" -ne "$want_exit" ]; then
    ok=false; problems+=("expected exit $want_exit, got $rc")
  fi
  local s
  for s in ${want[@]+"${want[@]}"}; do
    if ! printf '%s' "$stderr" | grep -Fq -- "$s"; then
      ok=false; problems+=("stderr missing: '$s'")
    fi
  done
  for s in ${nowant[@]+"${nowant[@]}"}; do
    if printf '%s' "$stderr" | grep -Fq -- "$s"; then
      ok=false; problems+=("stderr contains forbidden: '$s'")
    fi
  done

  if [ -n "$xfail" ]; then
    if [ "$ok" = true ]; then
      N_XPASS=$((N_XPASS + 1)); FAILED_IDS="$FAILED_IDS $id"
      report XPASS "$id" "$label" "now passes — remove --xfail" "was: $xfail"
    else
      N_XFAIL=$((N_XFAIL + 1)); report XFAIL "$id" "$label" "known-pending: $xfail"
    fi
  elif [ "$ok" = true ]; then
    N_PASS=$((N_PASS + 1)); report PASS "$id" "$label"
  else
    N_FAIL=$((N_FAIL + 1)); FAILED_IDS="$FAILED_IDS $id"
    report FAIL "$id" "$label" ${problems[@]+"${problems[@]}"}
  fi

  if [ "$VERBOSE" = true ] || { [ "$ok" = false ] && [ -z "$xfail" ]; }; then
    printf '            ── exit %s, stderr ──\n' "$rc"
    printf '%s\n' "$stderr" | sed 's/^/            | /'
  fi
}

echo "═══ Sage spec-gate hook tests ═══"
echo "Hook: $HOOK"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "  python3 required; skipping" ; exit 0
fi

SRC='{"tool_name":"Edit","tool_input":{"file_path":"src/app.ts"}}'

# H1 — pre-spec + source file → blocked
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo pre-spec
assert H1 "pre-spec source edit is blocked" "$P" "$SRC" \
  --exit 2 --stderr "pre-spec" --stderr "demo"

# H2 — spec-approved → allow
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo spec-approved
assert H2 "spec-approved source edit is allowed" "$P" "$SRC" --exit 0

# H3 — writing the spec itself is never blocked
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo pre-spec
assert H3 "writing spec.md while pre-spec is allowed" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".sage/work/demo/spec.md"}}' --exit 0

# H4 — hard_enforcement: false → allow
P=$(new_project); set_config "$P" "hard_enforcement: false"; add_manifest "$P" demo pre-spec
assert H4 "hard_enforcement false allows edits" "$P" "$SRC" --exit 0

# H5 — no .sage/ dir → allow
P="$(mktemp -d "${TMPDIR:-/tmp}/sage-hooktest-XXXXXX")/plain"; mkdir -p "$P/src"
assert H5 "non-Sage project is allowed" "$P" "$SRC" --exit 0

# H6 — corrupt manifest → allow + one warning (fail-open, R24)
P=$(new_project); set_config "$P" "hard_enforcement: true"
mkdir -p "$P/.sage/work/demo"
printf -- '---\ngate_state: pre-spec\ncycle_id: demo\n(no closing delimiter\n' > "$P/.sage/work/demo/manifest.md"
assert H6 "corrupt manifest fails open with a warning" "$P" "$SRC" \
  --exit 0 --stderr "could not be parsed"

# H7 — two manifests, one pre-spec → blocked (R26)
P=$(new_project); set_config "$P" "hard_enforcement: true"
add_manifest "$P" alpha building
add_manifest "$P" beta pre-spec
assert H7 "any pre-spec cycle blocks source edits" "$P" "$SRC" \
  --exit 2 --stderr "pre-spec" --stderr "beta"

# H8 — completion guard: manifest Write to complete while building → block (R25)
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo building
assert H8 "closing a cycle before gates pass is blocked" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".sage/work/demo/manifest.md","content":"---\ngate_state: complete\nstatus: complete\n---\n"}}' \
  --exit 2 --stderr "Rule 5" --stderr "gates-passed"

# H8b — completion guard via Edit new_string → block
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo building
assert H8b "Edit that sets complete before gates pass is blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/demo/manifest.md","old_string":"gate_state: building","new_string":"gate_state: complete"}}' \
  --exit 2 --stderr "Rule 5"

# H8c — completing after gates-passed is allowed
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo gates-passed
assert H8c "closing a cycle after gates pass is allowed" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".sage/work/demo/manifest.md","content":"---\ngate_state: complete\nstatus: complete\n---\n"}}' \
  --exit 0

# H8d — an ordinary manifest advance (building, no complete) is not touched
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo spec-approved
assert H8d "advancing gate_state (not to complete) is allowed" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/demo/manifest.md","old_string":"gate_state: spec-approved","new_string":"gate_state: plan-approved"}}' \
  --exit 0

# ─── R29: a completion may not be silent about independent QA ───────────────
# Phase 4 measured the old prose version: the decisions.md line was written in 1
# run of 3. These cases pin the mechanism that replaced it.

# H12 — gates passed, but qa is still `pending` → BLOCK. This is the whole point:
# silence about a skipped review is the failure mode, and it is now impossible.
P=$(new_project); set_config "$P" "hard_enforcement: true"
add_manifest "$P" demo gates-passed in-progress pending
assert H12 "completing while qa is 'pending' is blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/demo/manifest.md","old_string":"status: in-progress","new_string":"status: complete"}}' \
  --exit 2 --stderr "R29" --stderr "skipped-no-subagent"

# H13 — the skip is DECLARED → allowed. Sage does not forbid degrading; it forbids
# degrading quietly.
P=$(new_project); set_config "$P" "hard_enforcement: true"
add_manifest "$P" demo gates-passed in-progress skipped-no-subagent
assert H13 "completing with a declared skip is allowed" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/demo/manifest.md","old_string":"status: in-progress","new_string":"status: complete"}}' \
  --exit 0

# H14 — QA actually ran → allowed.
P=$(new_project); set_config "$P" "hard_enforcement: true"
add_manifest "$P" demo gates-passed in-progress passed
assert H14 "completing with qa: passed is allowed" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/demo/manifest.md","old_string":"status: in-progress","new_string":"status: complete"}}' \
  --exit 0

# H15 — declaring the disposition IN the same edit that completes is allowed. The
# agent should not have to make two round-trips to satisfy the gate.
P=$(new_project); set_config "$P" "hard_enforcement: true"
add_manifest "$P" demo gates-passed in-progress pending
assert H15 "declaring qa in the same edit that completes is allowed" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".sage/work/demo/manifest.md","content":"---\ngate_state: complete\nstatus: complete\nqa: waived\n---\n"}}' \
  --exit 0

# H16 — a manifest written before the field existed → allowed. An upgrade must not
# freeze a cycle that was mid-flight when it landed.
P=$(new_project); set_config "$P" "hard_enforcement: true"
add_manifest "$P" demo gates-passed
assert H16 "a pre-upgrade manifest with no qa field still completes" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/demo/manifest.md","old_string":"status: in-progress","new_string":"status: complete"}}' \
  --exit 0 --no-stderr "R29"

# ─── R29: the audit line is written by CODE, not asked for ──────────────────
# H17 — a declared skip lands in decisions.md without the model touching it.
P=$(new_project); add_manifest "$P" demo gates-passed in-progress skipped-no-subagent
: > "$P/.sage/decisions.md"
assert H17 "the degradation hook records a declared skip" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"'"$P"'/.sage/work/demo/manifest.md"}}' \
  --hook "$DEG_LOG" --exit 0 --stderr "recorded a degraded completion"
if [ -z "$ONLY" ] || [ "$ONLY" = "H17b" ]; then
  if grep -Fq "auto-logged by sage-degradation-log" "$P/.sage/decisions.md" 2>/dev/null; then
    report PASS H17b "the line is actually in decisions.md"
  else
    report FAIL H17b "the line is actually in decisions.md" "decisions.md has no audit line"
  fi
fi

# H18 — idempotent. A manifest is edited many times per cycle; the record is one line.
P=$(new_project); add_manifest "$P" demo gates-passed in-progress skipped-no-subagent
: > "$P/.sage/decisions.md"
if [ -z "$ONLY" ] || [ "$ONLY" = "H18" ]; then
  for _ in 1 2 3; do
    ( cd "$P" && printf '%s' '{"tool_name":"Edit","tool_input":{"file_path":"'"$P"'/.sage/work/demo/manifest.md"}}' \
        | bash "$DEG_LOG" >/dev/null 2>&1 )
  done
  n=$(grep -c "auto-logged by sage-degradation-log" "$P/.sage/decisions.md" 2>/dev/null || echo 0)
  if [ "$n" = "1" ]; then
    report PASS H18 "the audit line is written once, not once per edit"
  else
    report FAIL H18 "the audit line is written once, not once per edit" "found $n lines"
  fi
fi

# H19 — qa: passed is not a degradation and must NOT be logged as one.
P=$(new_project); add_manifest "$P" demo gates-passed in-progress passed
: > "$P/.sage/decisions.md"
assert H19 "qa: passed writes no degradation line" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"'"$P"'/.sage/work/demo/manifest.md"}}' \
  --hook "$DEG_LOG" --exit 0 --no-stderr "recorded a degraded completion"

# H20 — the logger never fails a tool call, whatever it is handed.
P=$(new_project)
assert H20 "the degradation hook never blocks, even on garbage" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"/nonexistent/manifest.md"}}' \
  --hook "$DEG_LOG" --exit 0


# ─── Rule 1: tests before code, made mechanical ─────────────────────────────
# Measured at v1.2.0: asked to change one constant under pressure, the agent wrote
# no test in 3 runs of 3, with the tdd skill loaded and the constitution in context.
# It also created no cycle, so every gate Sage owns — all of which fire on a cycle —
# was bypassed by declaring the work small. This gate fires on the EDIT instead.

SRCEDIT='{"tool_name":"Edit","tool_input":{"file_path":"src/config.py"}}'

# H21 — the exact move E1 measured: edit source, no test written → BLOCK
P=$(tdd_project)
assert H21 "a source edit with no test written is blocked" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 2 --stderr "tests before code" --stderr "src/config.py"

# H22 — write the test first (dirty tree) → ALLOW. This is the intended path.
P=$(tdd_project); printf 'def test_new():\n    assert True\n' > "$P/tests/test_new.py"
assert H22 "a source edit is allowed once a test is written" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 0

# H23 — the test was COMMITTED first, tree now clean → ALLOW. Committing the failing
# test before the implementation is textbook TDD; a gate that blocked it would be
# punishing the very thing it exists to demand.
P=$(tdd_project)
printf 'def test_new():\n    assert True\n' > "$P/tests/test_new.py"
( cd "$P" && git -c user.email=t@t -c user.name=t add -A \
    && git -c user.email=t@t -c user.name=t commit -qm "test: first" ) >/dev/null 2>&1
assert H23 "a source edit is allowed when the last commit was a test" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 0

# H23b — a commit containing a test AND source is NOT a red commit, and grants
# nothing. This is the distinction the whole gate turns on: nearly every repo's
# initial import commits src/ and tests/ together, so "the last commit touched a
# test" would hand out a free pass on the very next source edit — the exact edit
# this gate exists to stop. Only a test-ONLY commit is the red step.
P=$(tdd_project)
printf 'def test_new():\n    assert True\n' > "$P/tests/test_new.py"
printf 'TIMEOUT = 31\n' > "$P/src/config.py"
( cd "$P" && git -c user.email=t@t -c user.name=t add -A \
    && git -c user.email=t@t -c user.name=t commit -qm "test + impl together" ) >/dev/null 2>&1
assert H23b "a test+source commit is not a red commit and grants nothing" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 2 --stderr "tests before code"

# H24 — editing a test is never blocked (writing the test IS the point)
P=$(tdd_project)
assert H24 "editing a test file is never blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"tests/test_x.py"}}' \
  --hook "$TDD_GATE" --exit 0

# H25 — non-source files are not gated. A README is not a behavior.
P=$(tdd_project)
assert H25 "editing a non-source file is not gated" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"README.md"}}' \
  --hook "$TDD_GATE" --exit 0

# H26 — a project with no test suite at all → ALLOW. Blocking every edit in a repo
# that has no tests yet would make it impossible to bootstrap one. Documented hole.
P=$(tdd_project --no-tests)
assert H26 "a project with no test suite is not gated" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 0

# H27 — tdd_enforcement: false → ALLOW. An inescapable gate gets disabled wholesale.
P=$(tdd_project); printf 'sage-version: "1.2.0"\ntdd_enforcement: false\n' > "$P/.sage/config.yaml"
assert H27 "tdd_enforcement: false disables the gate" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 0

# H28 — the key absent entirely → ALLOW. Never surprise-block an upgraded project.
P=$(tdd_project); printf 'sage-version: "1.2.0"\n' > "$P/.sage/config.yaml"
assert H28 "an absent tdd_enforcement key allows (no surprise block)" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 0

# H29 — tier: tier1 exempts genuinely trivial work
P=$(tdd_project); mkdir -p "$P/.sage/work/t"
printf -- '---\ncycle_id: "t"\nstatus: in-progress\ntier: tier1\ngate_state: building\n---\n' \
  > "$P/.sage/work/t/manifest.md"
assert H29 "a tier1 cycle exempts the source edit" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 0

# H30 — SAGE'S OWN VENDORED TESTS MUST NOT COUNT. sage/ is full of test files, and
# `sage init` commits the whole tree — so the first version of this gate saw that
# commit, thought "the developer just wrote a test", and waved the next source edit
# straight through. It passed a change with no test at all. This is that regression.
P=$(tdd_project)
mkdir -p "$P/sage/develop/validators/gates/fixtures/verify/passing-pytest/tests"
printf 'def test_framework():\n    assert True\n' \
  > "$P/sage/develop/validators/gates/fixtures/verify/passing-pytest/tests/test_ok.py"
( cd "$P" && git -c user.email=t@t -c user.name=t add -A \
    && git -c user.email=t@t -c user.name=t commit -qm "sage init" ) >/dev/null 2>&1
assert H30 "the vendored framework's own tests do not satisfy the gate" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 2 --stderr "tests before code"

# H31 — not a git repo → fail open. A broken hook must never brick the editor.
P="$(mktemp -d "${TMPDIR:-/tmp}/sage-tddtest-XXXXXX")/nogit"
mkdir -p "$P/.sage" "$P/src"
printf 'tdd_enforcement: true\n' > "$P/.sage/config.yaml"
assert H31 "a non-git project fails open" "$P" "$SRCEDIT" \
  --hook "$TDD_GATE" --exit 0

# H9 — hard_enforcement not set at all (key absent) → allow (never surprise-block)
P=$(new_project); printf 'sage-version: "1.1.11"\n' > "$P/.sage/config.yaml"; add_manifest "$P" demo pre-spec
assert H9 "absent hard_enforcement key allows (no surprise block)" "$P" "$SRC" --exit 0

# H10 — CLAUDE_PROJECT_DIR resolves the project root when CWD differs
P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo pre-spec
OTHER="$(mktemp -d)"
# run from an unrelated CWD, pointing CLAUDE_PROJECT_DIR at the project
assert H10 "CLAUDE_PROJECT_DIR anchors the project root" "$OTHER" \
  '{"tool_name":"Edit","tool_input":{"file_path":"'"$P"'/src/app.ts"}}' \
  --env "CLAUDE_PROJECT_DIR=$P" --exit 2 --stderr "pre-spec"

# H11 — timing budget (loose CI threshold 200 ms)
if [ -z "$ONLY" ] || [ "$ONLY" = "H11" ]; then
  P=$(new_project); set_config "$P" "hard_enforcement: true"; add_manifest "$P" demo pre-spec
  t0=$(python3 -c 'import time;print(int(time.time()*1000))')
  (cd "$P" && printf '%s' "$SRC" | bash "$HOOK" >/dev/null 2>&1)
  t1=$(python3 -c 'import time;print(int(time.time()*1000))')
  ms=$((t1 - t0))
  if [ "$ms" -lt 200 ]; then
    N_PASS=$((N_PASS + 1)); report PASS H11 "decides in ${ms}ms (< 200ms budget)"
  else
    N_FAIL=$((N_FAIL + 1)); FAILED_IDS="$FAILED_IDS H11"
    report FAIL H11 "timing" "took ${ms}ms, budget is 200ms"
  fi
fi

echo ""
echo "═══ Summary ═══"
printf '  pass %d · fail %d · xfail %d · xpass %d\n' "$N_PASS" "$N_FAIL" "$N_XFAIL" "$N_XPASS"
if [ "$N_FAIL" -gt 0 ] || [ "$N_XPASS" -gt 0 ]; then
  echo ""
  echo "  Problem cases:$FAILED_IDS"
  [ "$N_XPASS" -gt 0 ] && echo "  XPASS: a fix landed — delete the --xfail marker."
  exit 1
fi
exit 0
