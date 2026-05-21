#!/usr/bin/env bash
# .sage/scripts/run-role.sh
#
# Dispatch a role from .sage/agents.toml to its configured CLI agent.
#
# Usage:
#   run-role.sh <role> <kind> <slug> [target]
#   run-role.sh probe-kind <role>
#
#   role:   key under [roles.*] in .sage/agents.toml
#           (planner | implementer | spec_reviewer | code_reviewer | …)
#   kind:   doc | diff
#             doc  = review or operate on a file (requires <target>)
#             diff = review the current uncommitted diff
#   slug:   subdir under .sage/work/  (e.g. 20260517-payment-retry)
#   target: filename under work dir   (only when kind=doc, e.g. spec.md)
#
#   probe-kind <role>  prints the role's resolved agent kind (host|cli)
#                      and exits 0 — no slug, no prompt, no agent run.
#
# Examples:
#   run-role.sh spec_reviewer doc  20260517-payment spec.md
#   run-role.sh code_reviewer diff 20260517-payment
#   run-role.sh implementer   doc  20260517-payment plan.md
#   run-role.sh probe-kind    implementer
#
# Output: prints the path to the produced artifact on stdout.

set -euo pipefail

# bash 3.2 compatibility (macOS /bin/bash): under `set -u`, expanding an
# empty array via "${arr[@]}" aborts. Any array that can be empty MUST
# use the empty-safe form  ${arr[@]+"${arr[@]}"}. See sage CONTRIBUTING.md.

# ─── Config reader ────────────────────────────────────────────────────────
# One python call returns all settings as shell-safe KEY=VALUE lines.
# Defined before argument parsing so the `probe-kind` sub-command can reuse
# it. Reads the role from the global ROLE; callers set ROLE before invoking.
read_role_cfg() {
  python3 - "$ROLE" <<'PY'
import sys, pathlib, shlex
try:
    import tomllib
except ImportError:
    sys.stderr.write("Python 3.11+ is required (for tomllib). "
                     "Run 'sage setup multi-agent', which checks this.\n")
    sys.exit(5)

role = sys.argv[1]
cfg = tomllib.loads(pathlib.Path(".sage/agents.toml").read_text())

if role not in cfg.get("roles", {}):
    sys.stderr.write(f"Unknown role: {role}\n"); sys.exit(6)
r = cfg["roles"][role]
agent_name = r["agent"]
model = r.get("model", "")
mode = r.get("mode", "")

if agent_name not in cfg.get("agents", {}):
    sys.stderr.write(f"Unknown agent: {agent_name}\n"); sys.exit(6)
a = cfg["agents"][agent_name]

def emit(k, v):
    print(f"{k}={shlex.quote(str(v))}")

emit("AGENT",        agent_name)
emit("MODEL",        model)
emit("MODE",         mode)
emit("AGENT_KIND",   a.get("kind", "cli"))
emit("CMD",          a.get("command", ""))
emit("EXEC_SUB",     a.get("exec_subcommand", ""))
emit("MODEL_FLAG",   a.get("model_flag", ""))
emit("OUTPUT_FLAG",  a.get("output_flag", ""))
emit("PROMPT_STYLE", a.get("prompt_style", "argv"))

# Flags as a single shell-quoted string — eval back into an array.
emit("BASE_FLAGS",   shlex.join(a.get("flags", [])))
emit("MODE_FLAGS",   shlex.join(a.get("modes", {}).get(mode, [])))
PY
}

# ─── probe-kind sub-command ───────────────────────────────────────────────
# `run-role.sh probe-kind <role>` prints the resolved agent kind (host|cli)
# for <role> and exits 0 — no slug, no prompt, no agent invocation. Used by
# /implement and /build-x Phase 6 to decide whether to delegate to a CLI
# sub-agent or run the implementer in the host session. Handled here, before
# the positional-argument checks below, because a probe call has no slug.
if [[ "${1:-}" == "probe-kind" ]]; then
  ROLE="${2:?role required for probe-kind}"
  CONFIG=".sage/agents.toml"
  [[ -f "${CONFIG}" ]] || { echo "Missing ${CONFIG}" >&2; exit 2; }
  # Plain assignment (never local/declare/export) so `set -e` aborts the
  # script if read_role_cfg exits non-zero (Python <3.11, or unknown role).
  ROLE_CFG="$(read_role_cfg)"
  eval "${ROLE_CFG}"
  echo "${AGENT_KIND}"
  exit 0
fi

ROLE="${1:?role required}"
KIND="${2:?kind required (doc|diff)}"
SLUG="${3:?slug required}"
TARGET="${4:-}"

CONFIG=".sage/agents.toml"
[[ -f "${CONFIG}" ]] || { echo "Missing ${CONFIG}" >&2; exit 2; }

WORK_DIR=".sage/work/${SLUG}"
REVIEWS_DIR="${WORK_DIR}/reviews"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${REVIEWS_DIR}"

# Read the role config. Plain assignment (never local/declare/export) so
# `set -e` aborts here if read_role_cfg exits non-zero. Eval-ing the
# command substitution directly would swallow that failure, and the script
# would crash later on an unbound AGENT_KIND instead of reporting the cause.
ROLE_CFG="$(read_role_cfg)"
eval "${ROLE_CFG}"

if [[ "${AGENT_KIND}" == "host" ]]; then
  echo "Role '${ROLE}' uses the host agent ('${AGENT}'); invoke it from the host session, not via this script." >&2
  exit 3
fi

# ─── Prompt assembly ──────────────────────────────────────────────────────
SHARED=""
[[ -f .sage/prompts/_shared.md ]] && SHARED="$(cat .sage/prompts/_shared.md)"

PROMPT_FILE=".sage/prompts/${ROLE}.md"
[[ -f "${PROMPT_FILE}" ]] || { echo "Missing prompt template: ${PROMPT_FILE}" >&2; exit 4; }

TARGET_PATH=""
[[ -n "${TARGET}" ]] && TARGET_PATH="${WORK_DIR}/${TARGET}"

ROLE_PROMPT="$(sed \
  -e "s|{{WORK_DIR}}|${WORK_DIR}|g" \
  -e "s|{{TARGET}}|${TARGET_PATH}|g" \
  -e "s|{{SPEC}}|${WORK_DIR}/spec.md|g" \
  -e "s|{{PLAN}}|${WORK_DIR}/plan.md|g" \
  -e "s|{{NOTES}}|${WORK_DIR}/implementer-notes.md|g" \
  "${PROMPT_FILE}")"

PROMPT="${SHARED}

---

${ROLE_PROMPT}"

# ─── Inject previous-review context (for reviewer roles only) ─────────────
if [[ "${ROLE}" == *_reviewer && -n "${TARGET}" ]]; then
  BASE="$(basename "${TARGET}" .md)"
  PREV="$(ls -1t "${REVIEWS_DIR}/${BASE}-${ROLE}-"*.md 2>/dev/null | head -1 || true)"
  if [[ -n "${PREV}" ]]; then
    PROMPT="${PROMPT}

---

## Previous review pass

The author may have addressed prior findings. For each previous BLOCKER and
MAJOR, confirm it is resolved; if not, re-raise it. Look for new issues
introduced by the fix. Do not soften standards on round 2 — a regressing
review is worse than no review.

Equally, do not escalate trivia to keep the loop alive: if a hard-lens
re-read finds only MINOR issues, say so and APPROVE. Convergence to
only-MINOR findings is a success, not a failure to look harder.

Previous review:
$(cat "${PREV}")
"
  fi
fi

# ─── Output path ──────────────────────────────────────────────────────────
case "${KIND}" in
  doc)
    [[ -n "${TARGET}" ]] || { echo "target required for kind=doc" >&2; exit 2; }
    OUT="${REVIEWS_DIR}/$(basename "${TARGET}" .md)-${ROLE}-${STAMP}.md"
    ;;
  diff)
    OUT="${REVIEWS_DIR}/diff-${ROLE}-${STAMP}.md"
    ;;
  *)
    echo "Unknown kind: ${KIND} (expected: doc | diff)" >&2; exit 2 ;;
esac

# ─── Persist the assembled prompt (best-effort) ───────────────────────────
# Write the exact prompt next to the output file so a /build-x cycle is
# reproducible from the work dir. Fires for every dispatched role (reviewer
# and implementer alike). Guarded so a failed write never aborts the run.
{ printf '%s\n' "${PROMPT}" > "${OUT%.md}.prompt.txt"; } 2>/dev/null || true

# ─── Build argv ───────────────────────────────────────────────────────────
ARGS=()
[[ -n "${EXEC_SUB}" ]] && ARGS+=("${EXEC_SUB}")
[[ -n "${MODEL_FLAG}" && -n "${MODEL}" ]] && ARGS+=("${MODEL_FLAG}" "${MODEL}")

if [[ -n "${BASE_FLAGS}" ]]; then
  eval "BASE_ARR=(${BASE_FLAGS})"
  ARGS+=(${BASE_ARR[@]+"${BASE_ARR[@]}"})
fi
if [[ -n "${MODE_FLAGS}" ]]; then
  eval "MODE_ARR=(${MODE_FLAGS})"
  ARGS+=(${MODE_ARR[@]+"${MODE_ARR[@]}"})
fi

# ─── Run ──────────────────────────────────────────────────────────────────
command -v "${CMD}" >/dev/null 2>&1 || {
  echo "Agent CLI not on PATH: ${CMD}" >&2; exit 7;
}

# ARGS may be empty (an agent configured with no exec_subcommand,
# no model_flag, no flags, and no modes). macOS /bin/bash 3.2 aborts
# on "${ARGS[@]}" when ARGS is empty under `set -u`, so every
# expansion below uses the empty-safe form ${ARGS[@]+"${ARGS[@]}"}.
case "${PROMPT_STYLE:-argv}" in
  argv)
    if [[ -n "${OUTPUT_FLAG}" ]]; then
      ARGS+=("${OUTPUT_FLAG}" "${OUT}")
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} "${PROMPT}" > /dev/null
    else
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} "${PROMPT}" > "${OUT}"
    fi
    ;;
  flag)
    if [[ -n "${OUTPUT_FLAG}" ]]; then
      ARGS+=("${OUTPUT_FLAG}" "${OUT}")
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} --prompt "${PROMPT}" > /dev/null
    else
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} --prompt "${PROMPT}" > "${OUT}"
    fi
    ;;
  stdin)
    if [[ -n "${OUTPUT_FLAG}" ]]; then
      ARGS+=("${OUTPUT_FLAG}" "${OUT}")
      printf '%s' "${PROMPT}" | "${CMD}" ${ARGS[@]+"${ARGS[@]}"} > /dev/null
    else
      printf '%s' "${PROMPT}" | "${CMD}" ${ARGS[@]+"${ARGS[@]}"} > "${OUT}"
    fi
    ;;
  *)
    echo "Unknown prompt_style: ${PROMPT_STYLE}" >&2; exit 8 ;;
esac

# ─── Validate reviewer output (non-fatal, warns only) ─────────────────────
if [[ "${ROLE}" == *_reviewer ]] && [[ -x .sage/scripts/validate-review.sh ]]; then
  if ! .sage/scripts/validate-review.sh "${OUT}" >/dev/null 2>&1; then
    echo "WARN: review output failed schema validation: ${OUT}" >&2
    echo "      The orchestrator should surface the malformed output to the user." >&2
  fi
fi

echo "${OUT}"
