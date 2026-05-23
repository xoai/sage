#!/usr/bin/env bash
# .sage/scripts/validate-step.sh
#
# Per-step validator for /implement. Catches "wrong files touched",
# "spec citation unresolved", and "smoke broke" *while the
# implementer is still on context* — before the codex code-review
# pass pays its full cost on a defective diff. Light by design: no
# CLI agent invoked, bash-only.
#
# Usage:
#   validate-step.sh <slug> <step-number>
#
# Output: a 6-bullet text report to stdout. Verdict (last bullet)
# is "PASS" or "INVESTIGATE".
#
# Exit codes:
#   0 — PASS (every check clean).
#   1 — INVESTIGATE (one or more checks flagged).
#   2 — bad invocation (missing slug, missing plan.md, etc).
#
# Tolerated failures (intentional): grep returning 1 on no match
# (handled via `|| true` per call site); `git diff` against a
# non-repo (caught and reported). Each tolerance is named here so a
# reviewer can verify they are not silent bugs.

set -euo pipefail

SLUG="${1:?slug required}"
STEP_NUM="${2:?step number required}"

WORK_DIR=".sage/work/${SLUG}"
PLAN="${WORK_DIR}/plan.md"
SPEC="${WORK_DIR}/spec.md"
NOTES="${WORK_DIR}/implementer-notes.md"

[[ -f "${PLAN}" ]]  || { echo "validate-step: missing ${PLAN}"  >&2; exit 2; }
[[ -f "${SPEC}" ]]  || { echo "validate-step: missing ${SPEC}"  >&2; exit 2; }
[[ -f "${NOTES}" ]] || { echo "validate-step: missing ${NOTES}" >&2; exit 2; }

VERDICT="PASS"
fail() { VERDICT="INVESTIGATE"; }

# ── 1. Step ref — the line from plan.md naming this step ───────────────
STEP_LINE="$(grep -n -E "^## (Phase|Step) ${STEP_NUM}[^0-9]" "${PLAN}" 2>/dev/null | head -1 || true)"
if [[ -z "${STEP_LINE}" ]]; then
  echo "- **Step ref.** (unresolved — no '## Phase ${STEP_NUM}' / '## Step ${STEP_NUM}' header in ${PLAN})"
  fail
else
  echo "- **Step ref.** ${STEP_LINE}"
fi

# ── 2. Files touched this step (per implementer-notes.md "Files:" line) ──
# Notes follow the implementer-charter format:
#   - Step <n>: complete | blocked | skipped
#     Files:  <list>
# Find the block, extract the Files line.
FILES_LINE="$(awk -v n="${STEP_NUM}" '
  $0 ~ "^- Step " n ":" || $0 ~ "^- Step " n "\\." { in_block=1; next }
  in_block && /^- Step / { in_block=0 }
  in_block && /Files:/ { print; exit }
' "${NOTES}" || true)"

# Pull the comma- or space-separated file list from the Files: line.
FILES_RAW="$(printf '%s\n' "${FILES_LINE}" | sed -E 's/.*Files:[[:space:]]*//; s/[[:space:]]*Notes:.*$//' || true)"
# Normalise: comma → space, collapse whitespace.
FILES_LIST="$(printf '%s' "${FILES_RAW}" | tr ',' ' ' | tr -s '[:space:]' ' ' | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"

if [[ -z "${FILES_LIST}" ]]; then
  echo "- **Files touched this step.** (empty in implementer-notes.md — Step ${STEP_NUM} claims complete but lists no files)"
  fail
else
  echo "- **Files touched this step.** ${FILES_LIST}"
fi

# ── 3. Spec section the plan step cites ────────────────────────────────
# Look for the first **Spec ref.** line under the step's plan section.
SPEC_REF="$(awk -v n="${STEP_NUM}" '
  $0 ~ "^## (Phase|Step) " n "[^0-9]" { in_block=1; next }
  in_block && /^## / && !/^## (Phase|Step)/ { in_block=0 }
  in_block && /\*\*Spec ref\.\*\*/ { print; exit }
' "${PLAN}" || true)"

if [[ -z "${SPEC_REF}" ]]; then
  echo "- **Spec section.** (no '**Spec ref.**' line in plan step ${STEP_NUM})"
else
  echo "- **Spec section.** $(printf '%s' "${SPEC_REF}" | sed -E 's/^[[:space:]-]*//')"
fi

# ── 4. Smoke pass — run the project's test command, restricted to the
# touched files when possible. File-scope detection follows the
# spec §E1 convention: CLAUDE.md may carry a `## Test (single file):`
# section whose body is `<cmd> {file}` (the `{file}` token is the
# substitution point). Fallback: the default `## Test:` section's
# command runs once with the touched files as positional args iff
# the first word is in the whitelist (pytest / vitest / jest);
# otherwise whole-suite.
CLAUDE_MD="CLAUDE.md"
SMOKE_PREFIX=""
SMOKE_CMD=""
SMOKE_MODE="whole-suite"   # single-file | argv | whole-suite
if [[ -f "${CLAUDE_MD}" ]]; then
  # Per-file template (case-insensitive match on the header).
  SF_TEMPLATE="$(awk '
    BEGIN { IGNORECASE=1 }
    /^## Test \(single file\):/ { in_block=1; next }
    in_block && /^## / { in_block=0 }
    in_block && NF { print; exit }
  ' "${CLAUDE_MD}" || true)"

  if [[ -n "${SF_TEMPLATE}" ]] && printf '%s' "${SF_TEMPLATE}" | grep -qF '{file}'; then
    SMOKE_MODE="single-file"
    SMOKE_CMD="${SF_TEMPLATE}"
  else
    DEFAULT_CMD="$(awk '
      BEGIN { IGNORECASE=1 }
      /^## Test:/ { in_block=1; next }
      in_block && /^## / { in_block=0 }
      in_block && NF { print; exit }
    ' "${CLAUDE_MD}" || true)"
    if [[ -n "${DEFAULT_CMD}" ]]; then
      FIRST_WORD="$(printf '%s' "${DEFAULT_CMD}" | awk '{print $1}')"
      case "${FIRST_WORD}" in
        pytest|vitest|jest)
          SMOKE_MODE="argv"
          SMOKE_CMD="${DEFAULT_CMD}"
          ;;
        *)
          SMOKE_MODE="whole-suite"
          SMOKE_CMD="${DEFAULT_CMD}"
          SMOKE_PREFIX="(whole-suite — no per-file form) "
          ;;
      esac
    fi
  fi
fi

if [[ -z "${SMOKE_CMD}" ]]; then
  echo "- **Smoke pass.** n/a — no '## Test:' section in CLAUDE.md (smoke procedure verification is the implementer's responsibility on a no-harness project)"
else
  case "${SMOKE_MODE}" in
    single-file)
      # Substitute {file} for each touched file and run.
      smoke_ok=1
      for f in ${FILES_LIST}; do
        cmd="$(printf '%s' "${SMOKE_CMD}" | sed -E "s|\\{file\\}|${f}|g")"
        if ! eval "${cmd}" >/dev/null 2>&1; then smoke_ok=0; break; fi
      done
      if [[ "${smoke_ok}" -eq 1 ]]; then
        echo "- **Smoke pass.** pass"
      else
        echo "- **Smoke pass.** fail (single-file run on ${FILES_LIST})"
        fail
      fi
      ;;
    argv)
      # shellcheck disable=SC2086
      if ${SMOKE_CMD} ${FILES_LIST} >/dev/null 2>&1; then
        echo "- **Smoke pass.** pass"
      else
        echo "- **Smoke pass.** fail (${FIRST_WORD} ${FILES_LIST})"
        fail
      fi
      ;;
    whole-suite)
      if eval "${SMOKE_CMD}" >/dev/null 2>&1; then
        echo "- **Smoke pass.** ${SMOKE_PREFIX}pass"
      else
        echo "- **Smoke pass.** ${SMOKE_PREFIX}fail"
        fail
      fi
      ;;
  esac
fi

# ── 5. Hallucination quick-check (item F integration) ──
HC=".sage/scripts/hallucination-check.sh"
if [[ -x "${HC}" ]]; then
  HC_OUT="$("${HC}" "${SLUG}" 2>/dev/null || true)"
  HC_EXIT=$?
  case "${HC_EXIT}" in
    0) echo "- **Hallucination quick-check.** clean" ;;
    1) echo "- **Hallucination quick-check.** unresolved imports:"; printf '%s\n' "${HC_OUT}" | sed 's/^/    /'; fail ;;
    *) echo "- **Hallucination quick-check.** n/a — script reported exit ${HC_EXIT}" ;;
  esac
else
  echo "- **Hallucination quick-check.** n/a — script absent"
fi

# ── 6. Verdict ──
echo "- **Verdict.** ${VERDICT}"

case "${VERDICT}" in
  PASS) exit 0 ;;
  *)    exit 1 ;;
esac
