#!/usr/bin/env bash
# .sage/scripts/review-stop.sh
#
# Deterministic stop-rule decision for the /build-x review loops
# (Phases 3 / 5 / 7). Reads the timestamped review files under
# .sage/work/<slug>/reviews/ for the named phase, counts severities,
# applies the seven rules from build-x.md Phase 3, and emits one line
# of JSON with the verdict. The planner *does not* re-derive counts.
#
# This script is **canonical**. The doc-prose rules in build-x.md
# describe what this script implements; in case of disagreement, the
# script wins (it is the determinism this script exists to introduce).
#
# Usage:
#   review-stop.sh <slug> <phase>
#     phase ∈ {spec, plan, code}
#
# Output (stdout, one JSON line):
#   {"action":"PROCEED|REVISE|CAP|STALL|REJECT|INCONSISTENT",
#    "iteration":N, "blocker":N, "major":N, "minor":N,
#    "cap":N, "stakes":"prototype|production",
#    "reason":"<one short sentence>"}
#
# Exit codes:
#   0  — clean parse, any `action` value returned.
#   2  — no review file for this phase exists yet, OR a file exists
#        but has no terminal verdict line yet (half-written / mid-flush
#        per spec §F1). The planner re-dispatches the reviewer.
#   9  — at least one review file is *complete* (last non-empty line is
#        a verdict word) but fails validate-review.sh rules 2-4
#        (missing ## Findings, malformed severity header, missing
#        Where/Quote lines). The planner falls through to the
#        Reviewer-failure fallback (build-x.md:205-229).
#
# Tolerated failures (intentional): grep -c returning 1 on no match;
# ls failing on an empty reviews/ dir. Each call site uses the
# explicit `|| true` / `|| echo 0` pattern.

set -euo pipefail

SLUG="${1:?slug required (e.g. 20260523-build-x-quality-and-efficiency)}"
PHASE="${2:?phase required (spec|plan|code)}"

case "${PHASE}" in
  spec|plan|code) ;;
  *) echo "review-stop.sh: phase must be spec|plan|code, got: ${PHASE}" >&2; exit 2 ;;
esac

WORK_DIR=".sage/work/${SLUG}"
REVIEWS_DIR="${WORK_DIR}/reviews"

# ── Stakes tier (mirrors run-role.sh's allowlist-normalise pattern) ──
STAKES="$(cat "${WORK_DIR}/stakes" 2>/dev/null || true)"
case "${STAKES}" in
  prototype|production) ;;
  *) STAKES="production" ;;
esac

# ── Cap resolution: stakes tier × phase ──
# Per build-x.md:
#   - spec  review: prototype cap 2, production cap 3 (stakes-driven).
#   - plan  review: cap pinned to 2 (regardless of stakes — plan
#                   issues are tighter in scope than spec issues).
#   - code  review: cap pinned to 2 (a third iteration would
#                   re-implement twice against the same code-review
#                   file, which is usually a re-scope signal).
case "${STAKES}" in
  prototype)  CAP=2 ;;
  production) CAP=3 ;;
esac
case "${PHASE}" in
  plan|code) CAP=2 ;;
esac

# ── Find the phase's review files (chronological by stamp) ──
# Naming per run-role.sh:227-236 — `<basename>-<role>-<stamp>.md` (doc),
# `diff-<role>-<stamp>.md` (diff). The stamp is YYYYMMDD-HHMMSS so a
# lexical sort is chronological.
case "${PHASE}" in
  spec) GLOB="${REVIEWS_DIR}/spec-spec_reviewer-*.md" ;;
  plan) GLOB="${REVIEWS_DIR}/plan-spec_reviewer-*.md" ;;
  code) GLOB="${REVIEWS_DIR}/diff-code_reviewer-*.md" ;;
esac

# shellcheck disable=SC2086
FILES="$(ls -1 ${GLOB} 2>/dev/null | sort || true)"

if [[ -z "${FILES}" ]]; then
  # `MISSING` (exit 2) is "the planner has nothing to act on yet";
  # `INCONSISTENT` (exit 9) is "the reviewer produced an unusable
  # file". The two are distinct recovery paths per spec §A1 — the
  # orchestrator re-dispatches the reviewer on MISSING and falls
  # through to the reviewer-failure fallback on INCONSISTENT.
  printf '{"action":"%s","iteration":0,"blocker":0,"major":0,"minor":0,"cap":%d,"stakes":"%s","reason":"%s"}\n' \
    "MISSING" "${CAP}" "${STAKES}" "no review file for phase=${PHASE}"
  exit 2
fi

# ── Read each file: validate, count severities, derive iteration verdict ──
# We collect:  iter_verdict[]  iter_blocker[]  iter_major[]  iter_minor[]
# Arrays are 0-indexed; the latest (current iteration) is the last entry.
ITER=0
LATEST_VERDICT=""
LATEST_BLOCKER=0
LATEST_MAJOR=0
LATEST_MINOR=0
PREV_BLOCKER=-1
PREV_MAJOR=-1
PREV_PREV_BLOCKER=-1
PREV_PREV_MAJOR=-1

while IFS= read -r FILE; do
  [[ -z "${FILE}" ]] && continue
  ITER=$((ITER + 1))

  # ── Check rule 1 of validate-review.sh: a terminal verdict line.
  # If missing → file is half-written / mid-flush per spec §F1 → exit 2
  # with action MISSING (same recovery path as "no review file": the
  # planner re-dispatches the reviewer, not the reviewer-failure
  # fallback).
  LAST="$(grep -v '^[[:space:]]*$' "${FILE}" 2>/dev/null | tail -1 | tr -d '[:space:]')"
  case "${LAST}" in
    APPROVE|REVISE|REJECT|FIX_BEFORE_MERGE|REWORK) ;;
    *)
      printf '{"action":"%s","iteration":%d,"blocker":0,"major":0,"minor":0,"cap":%d,"stakes":"%s","reason":"%s"}\n' \
        "MISSING" "${ITER}" "${CAP}" "${STAKES}" \
        "review file present but no terminal verdict (half-written): $(basename "${FILE}")"
      exit 2
      ;;
  esac

  # ── Rules 2-4: full validator. Failure here means the file is *complete*
  # but malformed → exit 9 (genuine reviewer failure).
  if ! bash "$(dirname "$0")/validate-review.sh" "${FILE}" >/dev/null 2>&1; then
    printf '{"action":"%s","iteration":%d,"blocker":0,"major":0,"minor":0,"cap":%d,"stakes":"%s","reason":"%s"}\n' \
      "INCONSISTENT" "${ITER}" "${CAP}" "${STAKES}" \
      "review file fails schema validation: $(basename "${FILE}")"
    exit 9
  fi

  # ── Count severities inside the ## Findings section.
  BLK="$(awk '/^## Findings/{f=1;next} /^## /{f=0} f && /^### \[BLOCKER\]/{n++} END{print n+0}' "${FILE}")"
  MAJ="$(awk '/^## Findings/{f=1;next} /^## /{f=0} f && /^### \[MAJOR\]/{n++}   END{print n+0}' "${FILE}")"
  MIN="$(awk '/^## Findings/{f=1;next} /^## /{f=0} f && /^### \[MINOR\]/{n++}   END{print n+0}' "${FILE}")"

  # Shift the rolling window of the last three iterations' BLOCKER+MAJOR.
  PREV_PREV_BLOCKER="${PREV_BLOCKER}"
  PREV_PREV_MAJOR="${PREV_MAJOR}"
  PREV_BLOCKER="${LATEST_BLOCKER}"
  PREV_MAJOR="${LATEST_MAJOR}"

  LATEST_VERDICT="${LAST}"
  LATEST_BLOCKER="${BLK}"
  LATEST_MAJOR="${MAJ}"
  LATEST_MINOR="${MIN}"
done <<EOF
${FILES}
EOF

# Helper: emit + exit
emit_and_exit() {
  local action="$1" reason="$2"
  printf '{"action":"%s","iteration":%d,"blocker":%d,"major":%d,"minor":%d,"cap":%d,"stakes":"%s","reason":"%s"}\n' \
    "${action}" "${ITER}" "${LATEST_BLOCKER}" "${LATEST_MAJOR}" "${LATEST_MINOR}" \
    "${CAP}" "${STAKES}" "${reason}"
  exit 0
}

BM=$((LATEST_BLOCKER + LATEST_MAJOR))

# ── Rule 3 (inconsistent review): verdict ↔ counts contradiction.
# A consistent APPROVE has BLOCKER+MAJOR == 0; a consistent REJECT has
# BLOCKER+MAJOR > 0. Anything else is INCONSISTENT.
case "${LATEST_VERDICT}" in
  APPROVE|FIX_BEFORE_MERGE)
    if [[ "${BM}" -gt 0 ]]; then
      emit_and_exit "INCONSISTENT" \
        "verdict=${LATEST_VERDICT} but BLOCKER+MAJOR=${BM} (verdict-counts mismatch)"
    fi
    ;;
  REJECT|REWORK)
    if [[ "${BM}" -eq 0 ]]; then
      emit_and_exit "INCONSISTENT" \
        "verdict=${LATEST_VERDICT} but BLOCKER+MAJOR=0 (verdict-counts mismatch)"
    fi
    ;;
esac

# ── Rule 2 (REJECT always escalates).
case "${LATEST_VERDICT}" in
  REJECT|REWORK)
    emit_and_exit "REJECT" \
      "verdict=${LATEST_VERDICT} — always escalates regardless of finding counts"
    ;;
esac

# ── Rule 1 (severity-gated exit on 0 BLOCKER + 0 MAJOR).
if [[ "${BM}" -eq 0 ]]; then
  emit_and_exit "PROCEED" \
    "severity-gated exit: 0 BLOCKER, 0 MAJOR (verdict=${LATEST_VERDICT}, ${LATEST_MINOR} MINOR deferred)"
fi

# ── Rule 6 (stall detection) — evaluated BEFORE Rule 4 (cap). A stall
# at iter=3 is a more informative signal to the planner than "ran out
# of rounds": a converging loop is salvageable with one-grant-one-round,
# a stalled loop is not. Under production cap=3, an iter=3 review with
# non-decreasing BLOCKER+MAJOR is now correctly classified as STALL,
# not CAP. (Under prototype cap=2 the loop hits CAP before iter=3 and
# STALL stays unreachable — same as before.)
if [[ "${ITER}" -ge 3 ]]; then
  PREV_BM=$((PREV_BLOCKER + PREV_MAJOR))
  PREV_PREV_BM=$((PREV_PREV_BLOCKER + PREV_PREV_MAJOR))
  if [[ "${BM}" -ge "${PREV_BM}" ]] && [[ "${PREV_BM}" -ge "${PREV_PREV_BM}" ]]; then
    emit_and_exit "STALL" \
      "BLOCKER+MAJOR not strictly decreasing across last 3 iterations: ${PREV_PREV_BM} → ${PREV_BM} → ${BM}"
  fi
  if [[ "${LATEST_BLOCKER}" -gt "${PREV_BLOCKER}" ]]; then
    emit_and_exit "STALL" \
      "BLOCKER count rose: ${PREV_BLOCKER} → ${LATEST_BLOCKER}"
  fi
fi

# ── Rule 4 (cap reached).
if [[ "${ITER}" -ge "${CAP}" ]]; then
  emit_and_exit "CAP" \
    "iteration=${ITER} >= cap=${CAP} (${STAKES}) with BLOCKER+MAJOR=${BM} remaining"
fi

# ── Default: keep iterating (REVISE).
emit_and_exit "REVISE" \
  "BLOCKER+MAJOR=${BM} at iteration ${ITER}/${CAP} (${STAKES}); patch artifact and re-review"
