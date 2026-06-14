#!/usr/bin/env bash
# develop/skill-tests/run-skill-test.sh
#
# Behavioral test harness for DISCIPLINE skills. Dispatches a skill's scenario
# to a sub-agent twice — once with the skill withheld (RED) and once present
# (GREEN) — captures each transcript, and returns a DETERMINISTIC verdict by
# grepping the transcript for the skill's declared compliance_marker.
#
# The verdict is a pure marker grep. There is NO judgment step — no model is
# asked "did it comply?" The marker's presence/absence IS the verdict. This is
# the same compute-don't-ask pattern as runtime/multi-agent/scripts/review-stop.sh.
#
# Usage:
#   run-skill-test.sh <skill-path> [--red | --green | --both]
#                     [--transcript <path>]        # single-phase replay
#                     [--red-transcript <path>]    # --both replay (RED side)
#                     [--green-transcript <path>]  # --both replay (GREEN side)
#
#   <skill-path>  directory containing SKILL.md and TESTS.md.
#   --both        (default) run RED then GREEN; overall PASS only if both expected.
#   --transcript  feed a recorded transcript instead of dispatching (replay mode).
#                 When omitted, the scenario is dispatched via dispatch.sh.
#
# Output (stdout, one JSON line per phase, mirroring review-stop.sh's style):
#   {"skill":"auto-review","phase":"red","marker_present":false,"verdict":"PASS"}
#
# Exit codes:
#   0  expected result    (RED → marker ABSENT, GREEN → marker PRESENT)
#   1  unexpected result  (RED → marker PRESENT, or GREEN → marker ABSENT) = FAIL
#   2  setup error        (no TESTS.md, no compliance_marker, dispatch unavailable)
#
# A RED run PASSES when the marker is ABSENT (baseline skip confirmed).
# A GREEN run PASSES when the marker is PRESENT (enforcement held).

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# ─── Args ───────────────────────────────────────────────────────────────────
SKILL_PATH=""
PHASE="both"
TRANSCRIPT=""
RED_TRANSCRIPT=""
GREEN_TRANSCRIPT=""

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --red)             PHASE="red" ;;
    --green)           PHASE="green" ;;
    --both)            PHASE="both" ;;
    --transcript)      TRANSCRIPT="${2:?--transcript needs a path}"; shift ;;
    --red-transcript)  RED_TRANSCRIPT="${2:?--red-transcript needs a path}"; shift ;;
    --green-transcript) GREEN_TRANSCRIPT="${2:?--green-transcript needs a path}"; shift ;;
    -h|--help)         usage ;;
    -*)                echo "run-skill-test.sh: unknown flag: $1" >&2; exit 2 ;;
    *)                 SKILL_PATH="$1" ;;
  esac
  shift
done

[ -n "$SKILL_PATH" ] || { echo "run-skill-test.sh: <skill-path> required" >&2; exit 2; }
SKILL_PATH="${SKILL_PATH%/}"
SKILL_MD="$SKILL_PATH/SKILL.md"
TESTS_MD="$SKILL_PATH/TESTS.md"
SKILL_NAME="$(basename "$SKILL_PATH")"

# ─── Setup checks (exit 2) ──────────────────────────────────────────────────
[ -f "$SKILL_MD" ]  || { echo "run-skill-test.sh: no SKILL.md at $SKILL_MD" >&2; exit 2; }
[ -f "$TESTS_MD" ]  || { echo "run-skill-test.sh: no TESTS.md at $TESTS_MD (setup error)" >&2; exit 2; }

# Read compliance_marker from the SKILL.md frontmatter (first --- … --- block).
extract_marker() {
  awk '
    NR==1 && $0=="---" { infm=1; next }
    infm && $0=="---" { exit }
    infm && /^compliance_marker:/ {
      sub(/^compliance_marker:[[:space:]]*/, "")
      print
      exit
    }
  ' "$SKILL_MD"
}

MARKER="$(extract_marker)"
MARKER="${MARKER%$'\r'}"
# strip one layer of surrounding single or double quotes
case "$MARKER" in
  \"*\") MARKER="${MARKER#\"}"; MARKER="${MARKER%\"}" ;;
  \'*\') MARKER="${MARKER#\'}"; MARKER="${MARKER%\'}" ;;
esac

if [ -z "$MARKER" ]; then
  echo "run-skill-test.sh: $SKILL_NAME declares no compliance_marker (setup error)" >&2
  exit 2
fi

# ─── Transcript acquisition ─────────────────────────────────────────────────
# Replay mode: a transcript path was supplied → use it verbatim (no dispatch).
# Dispatch mode: ask dispatch.sh to produce one. dispatch.sh is the SINGLE
# platform-dependent seam; if it is absent or cannot dispatch it exits 2 with
# a manual-mode instruction, which we propagate.
DISPATCH="$HERE/dispatch.sh"

obtain_transcript() {
  local phase="$1" supplied="$2"
  if [ -n "$supplied" ]; then
    [ -f "$supplied" ] || { echo "run-skill-test.sh: transcript not found: $supplied" >&2; exit 2; }
    printf '%s' "$supplied"
    return 0
  fi
  if [ ! -x "$DISPATCH" ] && [ ! -f "$DISPATCH" ]; then
    echo "run-skill-test.sh: no transcript supplied and dispatch.sh is unavailable." >&2
    echo "  Manual mode: run the scenario in $TESTS_MD, save the transcript, then re-run" >&2
    echo "  with --transcript <path>. (dispatch unavailable — setup error)" >&2
    exit 2
  fi
  local out
  out="$(mktemp 2>/dev/null || echo "/tmp/skill-test-$$-$phase.txt")"
  if ! bash "$DISPATCH" dispatch_scenario "$SKILL_PATH" "$phase" "$out"; then
    # dispatch.sh prints its own manual-mode instruction and exits non-zero.
    exit 2
  fi
  printf '%s' "$out"
}

# ─── Verdict: the marker grep ALONE decides. No judgment step (AC2). ─────────
# present := grep -F <marker> over the transcript.
#   GREEN expects present;  RED expects absent.
emit_verdict() {
  local phase="$1" transcript="$2"
  local present verdict
  if grep -qF -- "$MARKER" "$transcript"; then present=true; else present=false; fi
  case "$phase" in
    green) [ "$present" = true ]  && verdict=PASS || verdict=FAIL ;;
    red)   [ "$present" = false ] && verdict=PASS || verdict=FAIL ;;
  esac
  printf '{"skill":"%s","phase":"%s","marker_present":%s,"verdict":"%s"}\n' \
    "$SKILL_NAME" "$phase" "$present" "$verdict"
  [ "$verdict" = PASS ]
}

run_phase() {
  local phase="$1" supplied="$2"
  local transcript
  # obtain_transcript runs in a command substitution; its internal `exit 2`
  # only kills the subshell, surfacing here as a non-zero substitution status.
  # Propagate it as a real setup-error exit (2) rather than verdict-grepping an
  # empty transcript.
  if ! transcript="$(obtain_transcript "$phase" "$supplied")"; then
    exit 2
  fi
  emit_verdict "$phase" "$transcript"
}

case "$PHASE" in
  red)
    run_phase red "$TRANSCRIPT"; exit $?
    ;;
  green)
    run_phase green "$TRANSCRIPT"; exit $?
    ;;
  both)
    rc=0
    run_phase red   "$RED_TRANSCRIPT"   || rc=1
    run_phase green "$GREEN_TRANSCRIPT" || rc=1
    exit $rc
    ;;
esac
