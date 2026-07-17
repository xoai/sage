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
SESSION_INIT="${SAGE_SESSION_INIT:-$REPO_ROOT/runtime/plugin-overlay/hooks/scripts/sage-session-init.sh}"

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


add_ledger_manifest() {  # <proj> <slug> <gate_state> <ledger-yaml>
  mkdir -p "$1/.sage/work/$2"
  {
    printf -- '---\ncycle_id: "%s"\nworkflow: build\nphase: implement\n' "$2"
    printf -- 'status: in-progress\ntier: standard\ngate_state: %s\n' "$3"
    printf -- 'execution_mode: subagent\n'
    printf -- '%s' "$4"
    printf -- '---\n\n# Cycle: %s\n' "$2"
  } > "$1/.sage/work/$2/manifest.md"
}

LEDGER_ALL_DONE='tasks:
  - id: 1
    status: done
    review: approved
    commits: aaa1111..bbb2222
  - id: 2
    status: done
    review: approved
    commits: bbb2222..ccc3333
'

LEDGER_ONE_UNREVIEWED='tasks:
  - id: 1
    status: done
    review: approved
    commits: aaa1111..bbb2222
  - id: 2
    status: done
    review: pending
    commits: bbb2222..ccc3333
'

LEDGER_ONE_UNFINISHED='tasks:
  - id: 1
    status: done
    review: approved
    commits: aaa1111..bbb2222
  - id: 2
    status: in-progress
    review: pending
    commits: ""
'

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


# ─── The plugin is step 1 of 2, and must say so ─────────────────────────────
# Found by smoking the marketplace install. The plugin ships commands, skills and
# hooks — but the workflows read capabilities from the project's vendored sage/
# tree, which only `sage init` creates. Installed alone, /build references files
# that are not on disk. The session hook used to `exit 0` silently in that state, so
# the agent discovered the gap mid-answer and improvised. It now says so up front.

if [ -z "$ONLY" ] || [ "$ONLY" = "H32" ]; then
  P="$(mktemp -d "${TMPDIR:-/tmp}/sage-inittest-XXXXXX")/proj"; mkdir -p "$P/src"
  out="$( cd "$P" && bash "$SESSION_INIT" 2>/dev/null )"
  if printf '%s' "$out" | grep -Fq "NOT initialized" \
     && printf '%s' "$out" | grep -Fq "sage init"; then
    report PASS H32 "an uninitialized project is told to run sage init (not silence)"
    N_PASS=$((N_PASS + 1))
  else
    report FAIL H32 "an uninitialized project is told to run sage init (not silence)" \
      "session hook said: ${out:-<nothing>}"
    N_FAIL=$((N_FAIL + 1)); FAILED_IDS="$FAILED_IDS H32"
  fi
fi

if [ -z "$ONLY" ] || [ "$ONLY" = "H33" ]; then
  P="$(mktemp -d "${TMPDIR:-/tmp}/sage-inittest-XXXXXX")/proj"
  mkdir -p "$P/.sage/work" "$P/sage/core"
  out="$( cd "$P" && bash "$SESSION_INIT" 2>/dev/null )"
  if printf '%s' "$out" | grep -Fq "NOT initialized"; then
    report FAIL H33 "a properly initialized project is not nagged" "false alarm: $out"
    N_FAIL=$((N_FAIL + 1)); FAILED_IDS="$FAILED_IDS H33"
  else
    report PASS H33 "a properly initialized project is not nagged"
    N_PASS=$((N_PASS + 1))
  fi
fi

if [ -z "$ONLY" ] || [ "$ONLY" = "H34" ]; then
  # Half-installed: .sage/ present, the framework removed.
  P="$(mktemp -d "${TMPDIR:-/tmp}/sage-inittest-XXXXXX")/proj"; mkdir -p "$P/.sage/work"
  out="$( cd "$P" && bash "$SESSION_INIT" 2>/dev/null )"
  if printf '%s' "$out" | grep -Fq "sage update"; then
    report PASS H34 "a half-installed project is told to run sage update"
    N_PASS=$((N_PASS + 1))
  else
    report FAIL H34 "a half-installed project is told to run sage update" "said: ${out:-<nothing>}"
    N_FAIL=$((N_FAIL + 1)); FAILED_IDS="$FAILED_IDS H34"
  fi
fi

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


# ═══════════════════════════════════════════════════════════════════════════
# H35-H40 — the subagent task ledger (R101)
#
# The claim: in subagent execution, a task is finished when an INDEPENDENT
# reviewer approved it — not when the implementer said it was done. The ledger
# records both, and gates-passed is blocked while they disagree.
#
# gates-passed is the trigger, not complete. gates-passed is the state that
# ASSERTS the quality chain ran; a cycle reaching it with an unreviewed task has
# already made a false claim, and blocking only at completion would let that
# claim sit in the manifest where /continue and the next session read it as true.
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "── Ledger guard (R101, subagent execution) ──"

P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_ledger_manifest "$P" "led-a" "building" "$LEDGER_ALL_DONE"
assert H35 "every ledger task done+approved → gates-passed allowed" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/led-a/manifest.md","new_string":"gate_state: gates-passed"}}' \
  --exit 0

P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_ledger_manifest "$P" "led-b" "building" "$LEDGER_ONE_UNREVIEWED"
assert H36 "a task the implementer called done but NO REVIEWER approved → blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/led-b/manifest.md","new_string":"gate_state: gates-passed"}}' \
  --exit 2 --stderr "R101" --stderr "task 2"

P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_ledger_manifest "$P" "led-c" "building" "$LEDGER_ONE_UNFINISHED"
assert H37 "an unfinished task → blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/led-c/manifest.md","new_string":"gate_state: gates-passed"}}' \
  --exit 2 --stderr "R101"

# BACKWARD COMPATIBILITY — the case that matters most.
#
# Every manifest written before v1.3.0, and every inline-mode cycle, has no
# `tasks:` block. parse_ledger() returns None for those, and None disables the
# guard entirely. A project mid-flight when Sage upgraded must never be
# surprise-blocked by a field it has never heard of. This is the same promise
# H16 makes for `qa:`, and it is the promise that makes upgrades safe.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_manifest "$P" "no-ledger" "building"
assert H38 "a manifest with NO ledger is unaffected (pre-1.3.0 / inline mode)" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/no-ledger/manifest.md","new_string":"gate_state: gates-passed"}}' \
  --exit 0 --no-stderr "R101"

# A Write carries the WHOLE manifest, so the ledger it declares is in the payload
# rather than on disk. If the guard only ever read the file, an agent could write
# a fresh manifest declaring gates-passed AND an unreviewed ledger in one call,
# and the guard would read the old file and wave it through.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_ledger_manifest "$P" "led-d" "building" "$LEDGER_ALL_DONE"
assert H39 "a Write declaring gates-passed with an unreviewed ledger in the SAME payload → blocked" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".sage/work/led-d/manifest.md","content":"---\ncycle_id: \"led-d\"\ngate_state: gates-passed\nexecution_mode: subagent\ntasks:\n  - id: 1\n    status: done\n    review: pending\n---\n"}}' \
  --exit 2 --stderr "R101"

# H41 — the hole E9 found. A cycle in subagent mode that never wrote a ledger
# would sail through the guard: parse_ledger() returns None, the guard disables
# itself for backward compatibility, and the cycle claims gates-passed with no
# evidence any task was ever reviewed. The check was opt-in by the agent it polices.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"
mkdir -p "$P/.sage/work/no-led"
printf -- '---\ncycle_id: "no-led"\nworkflow: build\nphase: implement\nstatus: in-progress\ntier: standard\ngate_state: building\nexecution_mode: subagent\n---\n\n# Cycle\n' \
  > "$P/.sage/work/no-led/manifest.md"
assert H41 "subagent mode with NO ledger cannot reach gates-passed" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/no-led/manifest.md","new_string":"gate_state: gates-passed"}}' \
  --exit 2 --stderr "NO task ledger"

# H42 — and the backward-compatibility promise still holds: an INLINE cycle with
# no ledger is untouched. Only `execution_mode: subagent` arms the requirement.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"
mkdir -p "$P/.sage/work/inline-c"
printf -- '---\ncycle_id: "inline-c"\nworkflow: build\nphase: implement\nstatus: in-progress\ntier: standard\ngate_state: building\nexecution_mode: inline\n---\n\n# Cycle\n' \
  > "$P/.sage/work/inline-c/manifest.md"
assert H42 "inline mode with no ledger is unaffected" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/inline-c/manifest.md","new_string":"gate_state: gates-passed"}}' \
  --exit 0 --no-stderr "ledger"

# The guard must not fire on ordinary ledger updates mid-cycle — only on the
# claim that the chain has run. A hook that blocks every manifest write is a hook
# people disable.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_ledger_manifest "$P" "led-e" "building" "$LEDGER_ONE_UNFINISHED"
assert H40 "updating the ledger mid-cycle (no gates-passed claim) → allowed" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/led-e/manifest.md","new_string":"    status: done"}}' \
  --exit 0

# ── sage-bookkeeping-gate: hand-edits of cycle bookkeeping redirect to close-out ──
# The 2026-07-16 kept profile: the close-out command shipped with instructions in
# four documents and got ZERO calls, because the session read none of them. The
# tool call is the only channel that provably reaches every session.
echo ""
echo "sage-bookkeeping-gate — the close-out redirect"
BKG="$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-bookkeeping-gate.sh"

P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_manifest "$P" bk "building"
assert B1 "hand-edit of an active cycle's manifest is redirected to close-out" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/bk/manifest.md","new_string":"## Context summary\nnew prose"}}' \
  --exit 2 --stderr "close-out" --stderr "ONE pass" --hook "$BKG"

printf -- '# Decisions\n' > "$P/.sage/work/bk/decisions.md"
assert B2 "hand-edit of the cycle decisions.md is redirected too" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/bk/decisions.md","new_string":"### new decision"}}' \
  --exit 2 --stderr "close-out" --hook "$BKG"

assert B3 "CREATION is authoring, not bookkeeping — a new manifest may be written" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".sage/work/brand-new/manifest.md","content":"---\n---"}}' \
  --exit 0 --hook "$BKG"

assert B4 "a gate_state transition YIELDS to the spec-gate's completion guard" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/bk/manifest.md","new_string":"gate_state: gates-passed"}}' \
  --exit 0 --hook "$BKG"

assert B5 "plan.md stays free (authored and revised as an artifact)" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/bk/plan.md","new_string":"- [x] Task 1"}}' \
  --exit 0 --hook "$BKG"

assert B6 "the global .sage/decisions.md stays free (cross-initiative log)" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/decisions.md","new_string":"### x"}}' \
  --exit 0 --hook "$BKG"

assert B7 "source edits are none of this hook's business" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"src/app.ts","new_string":"x"}}' \
  --exit 0 --hook "$BKG"

P="$(new_project)"; set_config "$P" "hard_enforcement: true"
add_manifest "$P" done-c "complete" "complete"
assert B8 "a dead cycle's manifest may be edited (post-mortems are fine)" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/done-c/manifest.md","new_string":"note"}}' \
  --exit 0 --hook "$BKG"

P="$(new_project)"; set_config "$P" "hard_enforcement: false"
add_manifest "$P" bk2 "building"
assert B9 "hard_enforcement false → the gate never fires" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/bk2/manifest.md","new_string":"x"}}' \
  --exit 0 --hook "$BKG"

P="$(new_project)"
printf 'sage-version: "1.1.11"\nhard_enforcement: true\nbookkeeping_gate: false\n' > "$P/.sage/config.yaml"
add_manifest "$P" bk3 "building"
assert B10 "bookkeeping_gate: false is a dedicated opt-out" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/work/bk3/manifest.md","new_string":"x"}}' \
  --exit 0 --hook "$BKG"

# ── sage-secrets-gate: credentials never go into source ────────────────────
# The weak-model campaign measured why: handed a live key, haiku-bare hardcodes
# it 3/3 and haiku with the CONSTITUTION PARAGRAPH still hardcoded it 2/3.
# Opus refused on judgment alone — a hook is how the refusal transfers down-model.
echo ""
echo "sage-secrets-gate — no hardcoded credentials"
SG="$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-secrets-gate.sh"

P="$(new_project)"; set_config "$P" "hard_enforcement: true"
assert S1 "an sk- key written into source is blocked, with the env-var recovery path" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"src/client.py","content":"API_KEY = \"sk-proj-Abc123Def456Ghi789Jkl\""}}' \
  --exit 2 --stderr "environment" --hook "$SG"

assert S2 "an AWS access key id in an Edit is blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"src/deploy.py","new_string":"key = \"AKIAIOSFODNN7EXAMPLE\""}}' \
  --exit 2 --stderr "AWS" --hook "$SG"

assert S3 "an obvious placeholder is NOT a credential" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"src/client.py","content":"API_KEY = os.environ[\"OPENAI_API_KEY\"]  # or YOUR_API_KEY"}}' \
  --exit 0 --hook "$SG"

assert S4 ".env files are where secrets BELONG — allowed" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".env.local","content":"OPENAI_API_KEY=sk-proj-Abc123Def456Ghi789Jkl"}}' \
  --exit 0 --hook "$SG"

assert S5 "test fixtures may carry fake tokens — allowed" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"tests/test_auth.py","content":"FAKE = \"sk-proj-Abc123Def456Ghi789Jkl\""}}' \
  --exit 0 --hook "$SG"

assert S6 "a GitHub token is blocked" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"src/publish.py","content":"tok = \"ghp_AbCdEfGhIjKlMnOpQrStUvWx\""}}' \
  --exit 2 --stderr "GitHub" --hook "$SG"

# Class 1: live-marked keys are blocked EVERYWHERE except .env — the E2 proof
# run caught a fictional-vendor live key (pfk_live_…) parked in tests/, which
# the provider-list class structurally cannot catch and the tests/ exemption
# structurally cannot block. `live` means live; it is never a fixture.
assert S9 "a live-marked key of an UNKNOWN vendor is blocked even in tests/" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"tests/test_pay.py","content":"KEY = \"pfk_live_9Fq2XvR7tLpZ4NcW8HbY3sKd\""}}' \
  --exit 2 --stderr "live-marked" --hook "$SG"

# (The fake key is deliberately NOT a real vendor's format — GitHub push
# protection rejects Stripe-shaped sk_live_ strings even in test fixtures,
# which is this gate's own lesson enforced on this gate's own tests.)
assert S10 "a live-marked key in source is blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"src/pay.py","new_string":"payments.api_key = \"payco_live_4eC39HqLyjWDarjtT\""}}' \
  --exit 2 --stderr "live-marked" --hook "$SG"

assert S11 "a live-marked key in .env is where it BELONGS — allowed" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".env","content":"PAY_KEY=pfk_live_9Fq2XvR7tLpZ4NcW8HbY3sKd"}}' \
  --exit 0 --hook "$SG"

assert S12 "a vendor TEST key in tests/ stays allowed (vendors design those for CI)" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"tests/test_pay.py","content":"KEY = \"payco_test_4eC39HqLyjWDarjtT\""}}' \
  --exit 0 --hook "$SG"

P="$(new_project)"; set_config "$P" "hard_enforcement: false"
assert S7 "hard_enforcement false → the gate never fires" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"src/client.py","content":"k=\"sk-proj-Abc123Def456Ghi789Jkl\""}}' \
  --exit 0 --hook "$SG"

P="$(new_project)"
printf 'sage-version: "1.1.11"\nhard_enforcement: true\nsecrets_gate: false\n' > "$P/.sage/config.yaml"
assert S8 "secrets_gate: false is a dedicated opt-out" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":"src/client.py","content":"k=\"sk-proj-Abc123Def456Ghi789Jkl\""}}' \
  --exit 0 --hook "$SG"

# ── sage-verify-gate + tracker: verify before claiming, mechanically ────────
# Measured why (weak-model campaign): told "the tests passed" by a wrong user,
# haiku-bare trusts it 0/3 and haiku with the PARAGRAPH still failed 2/3. The
# commit is where "done" becomes durable, so the commit demands the evidence.
echo ""
echo "sage-verify-gate — no commit without evidence"
VG="$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-verify-gate.sh"
VT="$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-verify-tracker.sh"
COMMIT_JSON='{"tool_name":"Bash","tool_input":{"command":"git commit -m \"done\""}}'

# V1 — the live chain: tracker records a source edit; the gate then blocks.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"
( cd "$P" && printf '{"tool_name":"Edit","tool_input":{"file_path":"src/app.py","new_string":"x=1"}}' | bash "$VT" ) >/dev/null 2>&1
assert V1 "source edited, no test run → commit is blocked with the run-the-tests path" "$P" \
  "$COMMIT_JSON" --exit 2 --stderr "run the tests" --hook "$VG"

# V2 — tests ran after the edit → allowed. Explicit state: deterministic.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"; mkdir -p "$P/.sage/tmp"
printf 'last_source_edit=1000\nlast_test_run=2000\n' > "$P/.sage/tmp/verify-state"
assert V2 "tests ran AFTER the last edit → commit allowed" "$P" \
  "$COMMIT_JSON" --exit 0 --hook "$VG"

# V3 — edited again after the tests → stale evidence, blocked.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"; mkdir -p "$P/.sage/tmp"
printf 'last_source_edit=3000\nlast_test_run=2000\n' > "$P/.sage/tmp/verify-state"
assert V3 "source edited AFTER the tests → evidence stale, blocked" "$P" \
  "$COMMIT_JSON" --exit 2 --stderr "since the last test run" --hook "$VG"

# V4 — verify-then-commit in one chained command IS the discipline.
assert V4 "'pytest && git commit' chains are the discipline, not a violation" "$P" \
  '{"tool_name":"Bash","tool_input":{"command":"python3 -m pytest -q && git commit -m ok"}}' \
  --exit 0 --hook "$VG"

# V5 — docs-only commit: staged changes touch no code file → allowed.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"; mkdir -p "$P/.sage/tmp"
printf 'last_source_edit=3000\nlast_test_run=2000\n' > "$P/.sage/tmp/verify-state"
( cd "$P" && git init -q && git -c user.email=t@t -c user.name=t add -A \
    && git -c user.email=t@t -c user.name=t commit -qm seed \
    && printf 'notes\n' > README.md && git add README.md ) >/dev/null 2>&1
assert V5 "docs-only staged commit passes even with stale evidence" "$P" \
  "$COMMIT_JSON" --exit 0 --hook "$VG"

# V6 — no tracker state at all → an older install or a fresh session; fail open.
P="$(new_project)"; set_config "$P" "hard_enforcement: true"
assert V6 "no recorded evidence at all → fail open" "$P" \
  "$COMMIT_JSON" --exit 0 --hook "$VG"

P="$(new_project)"; set_config "$P" "hard_enforcement: false"; mkdir -p "$P/.sage/tmp"
printf 'last_source_edit=3000\n' > "$P/.sage/tmp/verify-state"
assert V7 "hard_enforcement false → the gate never fires" "$P" \
  "$COMMIT_JSON" --exit 0 --hook "$VG"

P="$(new_project)"
printf 'sage-version: "1.1.11"\nhard_enforcement: true\nverify_gate: false\n' > "$P/.sage/config.yaml"
mkdir -p "$P/.sage/tmp"; printf 'last_source_edit=3000\n' > "$P/.sage/tmp/verify-state"
assert V8 "verify_gate: false is a dedicated opt-out" "$P" \
  "$COMMIT_JSON" --exit 0 --hook "$VG"

assert V9 "a non-commit command is none of this gate's business" "$P" \
  '{"tool_name":"Bash","tool_input":{"command":"git status"}}' --exit 0 --hook "$VG"

# v2 (after the E3 shape): the unverified work may be SOMEONE ELSE'S — a user
# hands over a 'fixed and tested' tree and asks for the commit. The agent edited
# nothing, so the v1 edit-anchor fails open. v2: a code-bearing commit demands
# THIS-session test evidence, whoever wrote the code.
mk_dirty_repo() {  # a repo with a staged CODE change and no tracker state
  local d; d="$(new_project)"; set_config "$d" "hard_enforcement: true"
  ( cd "$d" && git init -q && printf 'x = 1\n' > src/app.py \
      && git -c user.email=t@t -c user.name=t add -A \
      && git -c user.email=t@t -c user.name=t commit -qm seed \
      && printf 'x = 2  # their fix\n' > src/app.py && git add src/app.py ) >/dev/null 2>&1
  echo "$d"
}
P="$(mk_dirty_repo)"
assert V10 "committing SOMEONE ELSE'S staged code with no test evidence → blocked" "$P" \
  '{"tool_name":"Bash","session_id":"s-1","tool_input":{"command":"git commit -m \"apply their fix\""}}' \
  --exit 2 --stderr "run the tests" --hook "$VG"

P="$(mk_dirty_repo)"; mkdir -p "$P/.sage/tmp"
printf 'last_source_edit=1000\nlast_test_run=2000\nlast_test_session=s-1\n' > "$P/.sage/tmp/verify-state"
assert V11 "same-session test evidence → the commit is allowed" "$P" \
  '{"tool_name":"Bash","session_id":"s-1","tool_input":{"command":"git commit -m ok"}}' \
  --exit 0 --hook "$VG"

P="$(mk_dirty_repo)"; mkdir -p "$P/.sage/tmp"
printf 'last_test_run=2000\nlast_test_session=s-OLD\n' > "$P/.sage/tmp/verify-state"
assert V12 "test evidence from ANOTHER session is stale — yesterday's green suite says nothing about today's tree" "$P" \
  '{"tool_name":"Bash","session_id":"s-1","tool_input":{"command":"git commit -m ok"}}' \
  --exit 2 --stderr "run the tests" --hook "$VG"

# ── sage-config-gate: an agent cannot disable its own enforcement ───────────
# The 2026-07-17 opencode probe found the hole: blocked from editing source, the
# agent edited .sage/config.yaml → hard_enforcement:false → every gate off. This
# is the regression test, because a hole without one comes back.
echo ""
echo "sage-config-gate — the meta-gate"
CG="$REPO_ROOT/runtime/platforms/claude-code/hooks/sage-config-gate.sh"

mk_enforced() {  # a project with hard_enforcement: true and given extra lines
  local d; d="$(new_project)"
  { printf 'sage-version: "1.3.8"\nhard_enforcement: true\n'; [ -n "${1:-}" ] && printf '%s\n' "$1"; } > "$d/.sage/config.yaml"
  echo "$d"
}

P="$(mk_enforced)"
assert C1 "THE HOLE: Edit flipping hard_enforcement true→false is blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/config.yaml","old_string":"hard_enforcement: true","new_string":"hard_enforcement: false"}}' \
  --exit 2 --stderr "disable its own" --hook "$CG"

P="$(mk_enforced)"
assert C2 "a Write that rewrites the whole config with enforcement off is blocked" "$P" \
  '{"tool_name":"Write","tool_input":{"file_path":".sage/config.yaml","content":"sage-version: \"1.3.8\"\nhard_enforcement: false\n"}}' \
  --exit 2 --stderr "enforcement" --hook "$CG"

P="$(mk_enforced)"
assert C3 "DELETING the hard_enforcement line (→ default off) is blocked" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/config.yaml","old_string":"hard_enforcement: true\n","new_string":""}}' \
  --exit 2 --stderr "enforcement" --hook "$CG"

P="$(mk_enforced)"
assert C4 "adding a secrets_gate: false opt-out is blocked (sub-gate off while master on)" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/config.yaml","old_string":"hard_enforcement: true","new_string":"hard_enforcement: true\nsecrets_gate: false"}}' \
  --exit 2 --stderr "enforcement" --hook "$CG"

P="$(mk_enforced)"
assert C5 "a NON-reducing config edit (adding an unrelated setting) is allowed" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/config.yaml","old_string":"hard_enforcement: true","new_string":"hard_enforcement: true\nlog_level: debug"}}' \
  --exit 0 --hook "$CG"

# Turning enforcement ON (or a project that never had it) is never our business.
P="$(new_project)"; set_config "$P" "hard_enforcement: false"
assert C6 "enforcement already OFF → the guard is dormant (off→on must stay possible)" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":".sage/config.yaml","old_string":"hard_enforcement: false","new_string":"hard_enforcement: true"}}' \
  --exit 0 --hook "$CG"

P="$(mk_enforced)"
assert C7 "editing a NORMAL source file is none of this gate's business" "$P" \
  '{"tool_name":"Edit","tool_input":{"file_path":"src/app.py","new_string":"x=1"}}' \
  --exit 0 --hook "$CG"

# A redirect that writes the switch off — the Bash evasion path.
P="$(mk_enforced)"
assert C8 "the Bash evasion (a redirect writing the switch off) is blocked" "$P" \
  '{"tool_name":"Bash","tool_input":{"command":"echo \"hard_enforcement: false\" > .sage/config.yaml"}}' \
  --exit 2 --stderr "enforcement" --hook "$CG"

P="$(mk_enforced)"
assert C9 "READING the config in Bash (grep) is not a write — allowed" "$P" \
  '{"tool_name":"Bash","tool_input":{"command":"grep hard_enforcement .sage/config.yaml"}}' \
  --exit 0 --hook "$CG"

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
