#!/usr/bin/env bash
# develop/skill-tests/dispatch.sh
#
# The SINGLE platform-dependent seam of the skill-test harness. run-skill-test.sh
# calls `dispatch.sh dispatch_scenario <skill-path> <red|green> <out-path>` and
# expects the sub-agent transcript to be written to <out-path>.
#
# Resolution order:
#   1. Programmatic dispatch — if $SAGE_SKILL_DISPATCH names an executable, call
#      it as `$SAGE_SKILL_DISPATCH <skill-path> <phase> <out-path>`. That hook is
#      where a platform with real sub-agent dispatch (e.g. a wrapper around the
#      Claude Code Task tool) plugs in. It MUST write the transcript to <out-path>.
#   2. Manual mode — print the scenario + the exact marker to verify, then read a
#      pasted transcript path from stdin and copy it to <out-path>.
#   3. Degraded — no programmatic dispatch AND no interactive stdin → exit 2 with
#      a manual-mode instruction (C2 / AC7). The harness is a dev tool; it never
#      becomes a runtime dependency and never blocks where dispatch is absent.
#
# Exit codes: 0 = transcript written to <out-path>; 2 = dispatch unavailable.

set -uo pipefail

[ "${1:-}" = "dispatch_scenario" ] || {
  echo "dispatch.sh: usage: dispatch.sh dispatch_scenario <skill-path> <red|green> <out-path>" >&2
  exit 2
}
shift

SKILL_PATH="${1:?skill-path required}"; SKILL_PATH="${SKILL_PATH%/}"
PHASE="${2:?phase (red|green) required}"
OUT="${3:?out-path required}"
TESTS_MD="$SKILL_PATH/TESTS.md"
SKILL_MD="$SKILL_PATH/SKILL.md"
SKILL_NAME="$(basename "$SKILL_PATH")"

case "$PHASE" in red|green) ;; *) echo "dispatch.sh: phase must be red|green" >&2; exit 2 ;; esac

# ─── 1. Programmatic seam ───────────────────────────────────────────────────
if [ -n "${SAGE_SKILL_DISPATCH:-}" ] && [ -x "${SAGE_SKILL_DISPATCH}" ]; then
  "${SAGE_SKILL_DISPATCH}" "$SKILL_PATH" "$PHASE" "$OUT"
  exit $?
fi

# ─── Gather scenario + marker for the human ─────────────────────────────────
marker="$(awk '
  { sub(/\r$/, "") }
  NR==1 && $0=="---" { infm=1; next }
  infm && $0=="---" { exit }
  infm && /^compliance_marker:/ { sub(/^compliance_marker:[[:space:]]*/, ""); print; exit }
' "$SKILL_MD" 2>/dev/null)"

section() {  # print a "## <name>" section body from TESTS.md
  awk -v want="## $1" '
    $0==want { grab=1; next }
    /^## / && grab { exit }
    grab { print }
  ' "$TESTS_MD" 2>/dev/null
}

if [ "$PHASE" = red ]; then
  expectation="ABSENT (a compliant baseline would NOT emit it)"
else
  expectation="PRESENT (the skill, when followed, emits it)"
fi

{
  echo "──────────────────────────────────────────────────────────────"
  echo "Skill: $SKILL_NAME   Phase: $PHASE"
  echo "Compliance marker to verify — expected $expectation:"
  echo "    $marker"
  echo ""
  echo "## Scenario"
  section Scenario
  if [ "$PHASE" = red ]; then
    echo ""
    echo "## red_setup (withhold the skill as described)"
    section red_setup
  fi
  echo "──────────────────────────────────────────────────────────────"
} >&2

# ─── 2/3. Manual mode or degraded ───────────────────────────────────────────
if [ ! -t 0 ]; then
  {
    echo "dispatch.sh: no programmatic sub-agent dispatch on this platform, and"
    echo "  stdin is not interactive — cannot paste a transcript. Run the scenario"
    echo "  above as a sub-agent, save the transcript, then re-run:"
    echo "    run-skill-test.sh $SKILL_PATH --$PHASE --transcript <path>"
  } >&2
  exit 2
fi

printf 'Paste path to the saved transcript (Enter to abort): ' >&2
read -r path
if [ -n "${path:-}" ] && [ -f "$path" ]; then
  cp "$path" "$OUT"
  exit 0
fi
echo "dispatch.sh: no transcript provided — aborting (manual mode)." >&2
exit 2
