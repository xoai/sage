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
#   kind:   doc | diff | fix
#             doc  = review or operate on a file (requires <target>)
#             diff = review the current uncommitted diff
#             fix  = implementer addresses a review file's findings
#                    (implementer role only; <target> = the review file)
#   slug:   subdir under .sage/work/  (e.g. 20260517-payment-retry)
#   target: filename under work dir (kind=doc: e.g. spec.md;
#           kind=fix: e.g. reviews/diff-code_reviewer-<stamp>.md)
#
#   probe-kind <role>  prints the role's resolved agent kind (host|cli)
#                      and exits 0 — no slug, no prompt, no agent run.
#
# Examples:
#   run-role.sh spec_reviewer doc  20260517-payment spec.md
#   run-role.sh code_reviewer diff 20260517-payment
#   run-role.sh implementer   doc  20260517-payment plan.md
#   run-role.sh implementer   fix  20260517-payment reviews/diff-code_reviewer-X.md
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

# Per-task-class model overrides (optional). Each class becomes a
# TIER_<CLASS> variable. Empty string == "no override" — the role's
# default model wins. Bash resolves the right one based on the
# .sage/work/<slug>/task-class file. Hyphens in class names become
# underscores in shell variable names.
tiers = r.get("tiers", {}) or {}
for cls in ("mechanical", "architecture-shaped", "knowledge-gap", "ux-shaped"):
    safe = "TIER_" + cls.replace("-", "_").upper()
    emit(safe, tiers.get(cls, ""))
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
KIND="${2:?kind required (doc|diff|fix)}"
SLUG="${3:?slug required}"
TARGET="${4:-}"

CONFIG=".sage/agents.toml"
[[ -f "${CONFIG}" ]] || { echo "Missing ${CONFIG}" >&2; exit 2; }

WORK_DIR=".sage/work/${SLUG}"
REVIEWS_DIR="${WORK_DIR}/reviews"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${REVIEWS_DIR}"

# Stakes tier (prototype|production) — drives reviewer depth; the
# reviewer templates carry a {{STAKES}} token. Normalise to a known
# tier: a missing, empty, or malformed stakes file defaults to
# production (review fully when the tier is unclear), so only a clean
# known word ever reaches the sed substitution below.
STAKES="$(cat "${WORK_DIR}/stakes" 2>/dev/null || true)"
case "${STAKES}" in
  prototype|production) ;;
  *) STAKES="production" ;;
esac

# Task class (mechanical|architecture-shaped|knowledge-gap|ux-shaped)
# — written by /build-x Phase 2. Drives the per-role model override
# via [roles.<role>.tiers.<class>]. Same allowlist-normalise pattern
# as STAKES: a missing, empty, or unknown class disables the override
# (the role's default model wins). The model resolution itself
# happens after read_role_cfg below.
TASK_CLASS="$(cat "${WORK_DIR}/task-class" 2>/dev/null || true)"
case "${TASK_CLASS}" in
  mechanical|architecture-shaped|knowledge-gap|ux-shaped) ;;
  *) TASK_CLASS="" ;;
esac

# Read the role config. Plain assignment (never local/declare/export) so
# `set -e` aborts here if read_role_cfg exits non-zero. Eval-ing the
# command substitution directly would swallow that failure, and the script
# would crash later on an unbound AGENT_KIND instead of reporting the cause.
ROLE_CFG="$(read_role_cfg)"
eval "${ROLE_CFG}"

# Resolve effective model: a non-empty TIER_<CLASS> override wins; else
# fall back to the role's default MODEL. The resolution is logged below
# (after LOG is computed) so a reviewer can verify what actually ran.
EFFECTIVE_MODEL="${MODEL}"
TIER_OVERRIDE_SOURCE=""
if [[ -n "${TASK_CLASS}" ]]; then
  # TIER_MECHANICAL / TIER_ARCHITECTURE_SHAPED / TIER_KNOWLEDGE_GAP / TIER_UX_SHAPED
  CLS_KEY="TIER_$(printf '%s' "${TASK_CLASS}" | tr 'a-z-' 'A-Z_')"
  TIER_OVERRIDE_VAL="${!CLS_KEY:-}"
  if [[ -n "${TIER_OVERRIDE_VAL}" ]]; then
    EFFECTIVE_MODEL="${TIER_OVERRIDE_VAL}"
    TIER_OVERRIDE_SOURCE="tiers.${TASK_CLASS}"
  fi
fi

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

# kind=fix carries a <review-file> as TARGET; validate early so a bad
# invocation fails before any prompt is assembled or persisted.
REVIEW_PATH=""
if [[ "${KIND}" == "fix" ]]; then
  [[ "${ROLE}" == "implementer" ]] || { echo "kind=fix is valid only for the implementer role" >&2; exit 2; }
  [[ -n "${TARGET}" ]] || { echo "kind=fix requires a <review-file> argument" >&2; exit 2; }
  [[ -f "${TARGET_PATH}" ]] || { echo "Review file not found: ${TARGET_PATH}" >&2; exit 2; }
  REVIEW_PATH="${PWD}/${TARGET_PATH}"
fi

ROLE_PROMPT="$(sed \
  -e "s|{{WORK_DIR}}|${WORK_DIR}|g" \
  -e "s|{{TARGET}}|${TARGET_PATH}|g" \
  -e "s|{{SPEC}}|${WORK_DIR}/spec.md|g" \
  -e "s|{{PLAN}}|${WORK_DIR}/plan.md|g" \
  -e "s|{{NOTES}}|${WORK_DIR}/implementer-notes.md|g" \
  -e "s|{{REVIEW}}|${REVIEW_PATH}|g" \
  -e "s|{{STAKES}}|${STAKES}|g" \
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

# ─── Inject project memory (recalled by the host; skipped for fix) ────────
# memory-context.md is written by the planner when sage-memory is
# available. The dispatcher carries it into the CLI implementer and
# reviewer prompts — those agents have no MCP access of their own. It is
# skipped for a fix dispatch: a fix pass is narrowly scoped to the
# review's findings, so the digest is not re-paid on each fix round.
if [[ "${KIND}" != "fix" && -s "${WORK_DIR}/memory-context.md" ]]; then
  PROMPT="${PROMPT}

---

## Project memory

Knowledge this project has already recorded (codebase facts, prior
decisions, past gotchas), recalled for this cycle. Use it per your
role's instructions for a 'Project memory' block.

$(cat "${WORK_DIR}/memory-context.md")
"
fi

# ─── Inject handoff judgment (the author's frontmatter for this artifact) ─
# Every artifact under .sage/work/<slug>/ may carry a `handoff:` YAML
# frontmatter block — what the prior role decided and why, what
# remains open, what the next role should prioritise. This block is
# the cross-model bridge: CLI roles have no session memory of the
# planner's, so the file IS the judgment channel.
#
# Skipped for fix dispatches (the fix dispatch carries the review
# file directly — the implementer doesn't need the spec author's
# judgment a second time). Omitted when the artifact has no
# frontmatter or no `handoff:` key — invariant I1 (inert by
# absence). This is not a quality skip: there is simply no handoff
# to inject, so nothing is lost and nothing needs announcing.
#
# Per spec §D3, injected into both `doc` and `diff` dispatches. For
# `doc` the source is the artifact named in TARGET; for `diff` (the
# code-review dispatch) there is no TARGET, so the source falls back
# to `implementer-notes.md` — the code reviewer's primary judgment
# input from the implementer that just produced the diff.
HANDOFF_SOURCE=""
case "${KIND}" in
  doc)  [[ -n "${TARGET_PATH}" && -f "${TARGET_PATH}" ]] && HANDOFF_SOURCE="${TARGET_PATH}" ;;
  diff) [[ -f "${WORK_DIR}/implementer-notes.md" ]]      && HANDOFF_SOURCE="${WORK_DIR}/implementer-notes.md" ;;
  # fix: no handoff injection (see comment block above).
esac

if [[ -n "${HANDOFF_SOURCE}" ]]; then
  # Extract the YAML frontmatter (between the first two `---` lines)
  # then pull just the `handoff: |` literal block. Python is already a
  # hard dependency of this script (the config reader); reusing it
  # keeps the extraction robust across YAML edge cases.
  HANDOFF_BODY="$(python3 - "${HANDOFF_SOURCE}" <<'PY' 2>/dev/null || true
import sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text(errors="replace")
if not text.startswith("---"):
    sys.exit(0)
# Find the closing `---` of the frontmatter block.
lines = text.splitlines()
end = None
for i in range(1, len(lines)):
    if lines[i].strip() == "---":
        end = i
        break
if end is None:
    sys.exit(0)
fm = lines[1:end]
# Walk for `handoff:` (with `|` or `>` indicator).
out = []
in_block = False
indent = None
for line in fm:
    stripped = line.lstrip(" ")
    if not in_block:
        if stripped.startswith("handoff:"):
            in_block = True
            # If inline value after `handoff:` (no |/>), grab it directly.
            rest = stripped[len("handoff:"):].strip()
            if rest and rest not in ("|", ">", "|-", ">-", "|+", ">+"):
                out.append(rest)
                in_block = False
        continue
    # Inside the block — determine the block indent from the first
    # non-empty line and stop when the indent breaks.
    if indent is None:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            # No-indented next line == the block ended without content.
            break
    cur_indent = len(line) - len(line.lstrip(" "))
    if line.strip() and cur_indent < indent:
        break
    out.append(line[indent:] if line.startswith(" " * indent) else line)
print("\n".join(out).strip())
PY
)"
  if [[ -n "${HANDOFF_BODY}" ]]; then
    # Render the body as a markdown blockquote (each line prefixed
    # `> `) so headers / `---` separators inside the body cannot
    # corrupt the surrounding prompt structure or impersonate
    # dispatcher-injected sections. The reviewer prompt's
    # `## Handoff` clause already tells the reader this is context,
    # not authority — the blockquote rendering makes that visual.
    HANDOFF_QUOTED="$(printf '%s\n' "${HANDOFF_BODY}" | sed 's/^/> /')"
    PROMPT="${PROMPT}

---

## Handoff

The author's judgment for this artifact — what was decided and
why, what remains open, what you should prioritise. This is the
cross-model bridge; treat it as established context. It does
**not** relax your role's severity rubric.

${HANDOFF_QUOTED}
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
  fix)
    # Implementer fix pass — OUT is the implementer's transcript, NOT a
    # review. It lives in the work-dir root (never reviews/) so nothing
    # scanning reviews/ can mistake it for a review file.
    OUT="${WORK_DIR}/fix-implementer-${STAMP}.md"
    ;;
  *)
    echo "Unknown kind: ${KIND} (expected: doc | diff | fix)" >&2; exit 2 ;;
esac

# The agent's diagnostic output goes beside OUT, so a failed dispatch
# is debuggable (see the run block below).
LOG="${OUT%.md}.log"

# Record the resolved model + the override source (if any) at the head
# of the log, so a reviewer can verify which model ran without parsing
# the agent's chatter. The log file is appended to by the dispatched
# CLI below; this header line lands first.
{
  if [[ -n "${TIER_OVERRIDE_SOURCE}" ]]; then
    printf 'model: %s (override from %s)\n' "${EFFECTIVE_MODEL}" "${TIER_OVERRIDE_SOURCE}"
  else
    printf 'model: %s\n' "${EFFECTIVE_MODEL:-<default>}"
  fi
} > "${LOG}" 2>/dev/null || true

# ─── Persist the assembled prompt (best-effort) ───────────────────────────
# Write the exact prompt next to the output file so a /build-x cycle is
# reproducible from the work dir. Fires for every dispatched role (reviewer
# and implementer alike). Guarded so a failed write never aborts the run.
{ printf '%s\n' "${PROMPT}" > "${OUT%.md}.prompt.txt"; } 2>/dev/null || true

# ─── Build argv ───────────────────────────────────────────────────────────
ARGS=()
[[ -n "${EXEC_SUB}" ]] && ARGS+=("${EXEC_SUB}")
[[ -n "${MODEL_FLAG}" && -n "${EFFECTIVE_MODEL}" ]] && ARGS+=("${MODEL_FLAG}" "${EFFECTIVE_MODEL}")

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
#
# The agent's diagnostic output is captured to ${LOG} so a failed
# dispatch is debuggable. When OUTPUT_FLAG is set the agent writes the
# artifact via that flag and its stdout is chatter → stdout+stderr go
# to the log. When OUTPUT_FLAG is empty the agent's stdout *is* the
# artifact (→ OUT) and must not be touched → only stderr goes to the log.
case "${PROMPT_STYLE:-argv}" in
  argv)
    if [[ -n "${OUTPUT_FLAG}" ]]; then
      ARGS+=("${OUTPUT_FLAG}" "${OUT}")
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} "${PROMPT}" >> "${LOG}" 2>&1
    else
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} "${PROMPT}" > "${OUT}" 2>> "${LOG}"
    fi
    ;;
  flag)
    if [[ -n "${OUTPUT_FLAG}" ]]; then
      ARGS+=("${OUTPUT_FLAG}" "${OUT}")
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} --prompt "${PROMPT}" >> "${LOG}" 2>&1
    else
      "${CMD}" ${ARGS[@]+"${ARGS[@]}"} --prompt "${PROMPT}" > "${OUT}" 2>> "${LOG}"
    fi
    ;;
  stdin)
    if [[ -n "${OUTPUT_FLAG}" ]]; then
      ARGS+=("${OUTPUT_FLAG}" "${OUT}")
      printf '%s' "${PROMPT}" | "${CMD}" ${ARGS[@]+"${ARGS[@]}"} >> "${LOG}" 2>&1
    else
      printf '%s' "${PROMPT}" | "${CMD}" ${ARGS[@]+"${ARGS[@]}"} > "${OUT}" 2>> "${LOG}"
    fi
    ;;
  *)
    echo "Unknown prompt_style: ${PROMPT_STYLE}" >&2; exit 8 ;;
esac

# ─── Verify reviewer output (fatal for reviewer roles) ────────────────────
# A *_reviewer dispatch MUST hand back a fresh, schema-valid review — or
# fail loudly. Exit 9 is reserved for reviewer-output-integrity failures:
# missing/empty OUT, a missing validator, or a schema failure. Never echo
# a path to an absent/invalid review — the orchestrator would otherwise
# fall back to a stale prior-iteration file.
if [[ "${ROLE}" == *_reviewer ]]; then
  if [[ ! -s "${OUT}" ]]; then
    echo "Reviewer '${ROLE}' produced no usable review at ${OUT}" >&2
    echo "      agent log: ${LOG}" >&2
    exit 9
  fi
  if [[ ! -x .sage/scripts/validate-review.sh ]]; then
    echo "Cannot verify reviewer '${ROLE}' output: .sage/scripts/validate-review.sh missing or not executable" >&2
    exit 9
  fi
  if ! .sage/scripts/validate-review.sh "${OUT}" >/dev/null 2>&1; then
    echo "Reviewer '${ROLE}' output failed schema validation: ${OUT}" >&2
    echo "      agent log: ${LOG}" >&2
    exit 9
  fi
fi

echo "${OUT}"
