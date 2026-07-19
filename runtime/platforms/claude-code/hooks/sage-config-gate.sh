#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-config-gate.sh — Claude Code PreToolUse hook (the meta-gate)
#
# Blocks a gated agent from turning OFF its own enforcement. While
# `hard_enforcement: true`, an agent Edit/Write to .sage/config.yaml that would
# reduce any gate's effective-enabled state (flip hard_enforcement true→false,
# add a *_gate: false opt-out, remove tdd_enforcement: true; with the v2
# review loop active, flip review_loop mode v2→v1 or witness_capping
# true→false — an agent must not soften its own review floor) exits 2. Also
# catches the obvious Bash evasions (a redirect/sed/tee that writes the switch
# off). Exit 2; the reason says humans disable enforcement out-of-band.
#
# WHY, MEASURED. The 2026-07-17 opencode veto probe: the agent, blocked from
# editing source in a pre-spec cycle, edited .sage/config.yaml and set
# hard_enforcement:false, then made the edit freely. Reproduced against the real
# spec-gate (exit 2 on source, exit 0 on the config edit, exit 0 after the flip).
# Every gate in every release reads hard_enforcement from a file the gated agent
# could rewrite — a prisoner holding the keys. This closes that.
#
# There is NO opt-out flag: the guard IS part of hard enforcement, inseparable.
# A human who wants enforcement off sets hard_enforcement:false in their OWN
# editor (which never goes through PreToolUse). The agent under enforcement
# cannot switch it off. Fires only while hard_enforcement is currently true, so
# a project that never enabled it is never touched.
#
# HOOKS ARE GUARDS, NOT GATES — any internal error fails OPEN (exit 0).
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "sage-config-gate: python3 not found; allowing" >&2
  exit 0
fi

PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-config-gate-XXXXXX" 2>/dev/null) || {
  echo "sage-config-gate: could not create a temp file; allowing" >&2
  exit 0
}
trap 'rm -f "$PY_GATE"' EXIT

cat > "$PY_GATE" <<'PYEOF'
import json
import os
import re
import sys


def emit(decision, message=""):
    sys.stdout.write(decision + "\n")
    if message:
        sys.stdout.write(message)
    sys.exit(0)


BLOCK_MSG = (
    "sage-config-gate: this would turn OFF enforcement that is currently on — "
    "an agent under enforcement cannot disable its own gates.\n"
    "\n"
    "If enforcement genuinely needs to change, a human edits .sage/config.yaml "
    "directly (outside the agent). If a gate is blocking legitimate work, fix "
    "the work it is pointing at — that is what it is for.")

# The enforcement keys and how each reads when ABSENT.
#   master  hard_enforcement — default OFF; ON only when explicitly true.
#   opt_out secrets_gate / verify_gate — default ON; OFF only when explicitly false.
#   opt_in  tdd_enforcement — default OFF; ON only when explicitly true.
MASTER = "hard_enforcement"
OPT_OUT = ("secrets_gate", "verify_gate")
OPT_IN = ("tdd_enforcement",)


def read_flag(text, key):
    """None if the key is absent, else True/False."""
    m = re.search(r"(?mi)^\s*%s\s*:\s*(true|false)\b" % re.escape(key), text or "")
    return None if not m else (m.group(1).lower() == "true")


def enabled(text, key):
    v = read_flag(text, key)
    if key == MASTER or key in OPT_IN:
        return v is True                       # default off
    return v is not False                      # opt-out: default on


def review_mode(text):
    """The review_loop: block's mode — v1 when absent (RR-8). The LAST
    block wins, matching review.py's duplicate-key convention."""
    blocks = re.findall(r"(?m)^review_loop:[ \t]*$((?:\n[ \t]+.*)*)", text or "")
    for block in reversed(blocks):
        mm = re.search(r"(?mi)^[ \t]+mode[ \t]*:[ \t]*(\S+)", block)
        if mm:
            return mm.group(1).lower()
    return "v1"


def witness_capping(text):
    return read_flag(text, "witness_capping") is not False   # default on


def weaker(before, after):
    """after reduces enforcement vs before, for any key."""
    for key in (MASTER,) + OPT_OUT + OPT_IN:
        if enabled(before, key) and not enabled(after, key):
            return True
    # The review floor (RR-8): while the v2 review loop is active, its mode
    # and witness capping are enforcement — mode v2→v1 or capping true→false
    # is an agent softening its own review floor.
    if review_mode(before) == "v2":
        if review_mode(after) != "v2":
            return True
        if witness_capping(before) and not witness_capping(after):
            return True
    return False


try:
    data = json.load(sys.stdin)
except Exception:
    emit("WARN", "could not parse hook input JSON")
if not isinstance(data, dict):
    emit("WARN", "hook input was not a JSON object")

tool = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}

project_root = (os.environ.get("CLAUDE_PROJECT_DIR")
                or (data.get("cwd") or "").strip() or os.getcwd())
project_root = os.path.abspath(project_root)
config_path = os.path.join(project_root, ".sage", "config.yaml")
if not os.path.isfile(config_path):
    emit("ALLOW")

try:
    with open(config_path, encoding="utf-8", errors="replace") as fh:
        current = fh.read()
except OSError:
    emit("ALLOW")

# Only active while enforcement is currently ON — nothing to protect otherwise,
# and this is what makes turning enforcement ON (off→on) always allowed.
if not enabled(current, MASTER):
    emit("ALLOW")


def rel_is_config(path):
    if not path:
        return False
    p = path if os.path.isabs(path) else os.path.join(project_root, path)
    try:
        return os.path.abspath(p) == config_path
    except Exception:
        return False


# ── Edit/Write/MultiEdit: reconstruct the resulting file and compare ──
if tool in ("Edit", "Write", "MultiEdit"):
    if not rel_is_config(str(tool_input.get("file_path") or "")):
        emit("ALLOW")
    after = None
    if tool == "Write":
        after = str(tool_input.get("content") or "")
    else:
        after = current
        edits = tool_input.get("edits")
        if not edits and "new_string" in tool_input:
            edits = [{"old_string": tool_input.get("old_string", ""),
                      "new_string": tool_input.get("new_string", "")}]
        for e in edits or []:
            if isinstance(e, dict):
                old = e.get("old_string", "")
                new = e.get("new_string", "")
                if old:
                    after = after.replace(old, new, 1)
    if after is not None and weaker(current, after):
        emit("BLOCK", BLOCK_MSG)
    emit("ALLOW")

# ── Bash: catch the obvious write-the-switch-off evasions ──
# Conservative on purpose — a redirect/sed/tee that names config.yaml AND sets an
# enforcement key false. A read (grep/cat) has no such write and is not matched.
if tool == "Bash":
    cmd = str(tool_input.get("command") or "")
    names_config = re.search(r"\.sage/config\.ya?ml", cmd) is not None
    writes = re.search(r">\s*[^|]*\.sage/config\.ya?ml|"
                       r"\bsed\b[^\n]*-i|\btee\b[^\n]*\.sage/config\.ya?ml", cmd)
    turns_off = re.search(
        r"(?:%s|secrets_gate|verify_gate)\s*:?\s*false" % re.escape(MASTER),
        cmd, re.I)
    review_off = review_mode(current) == "v2" and re.search(
        r"witness_capping\s*:?\s*false|mode\s*:?\s*v1", cmd, re.I)
    if names_config and writes and (turns_off or review_off):
        emit("BLOCK", BLOCK_MSG)
    emit("ALLOW")

emit("ALLOW")
PYEOF

GATE_OUT=$(python3 "$PY_GATE")
GATE_RC=$?

if [ "$GATE_RC" -ne 0 ]; then
  echo "sage-config-gate: internal error (python exit $GATE_RC); allowing" >&2
  exit 0
fi

DECISION=$(printf '%s\n' "$GATE_OUT" | sed -n '1p')
MESSAGE=$(printf '%s\n' "$GATE_OUT" | sed -n '2,$p')

case "$DECISION" in
  BLOCK)
    printf '%s\n' "$MESSAGE" >&2
    exit 2
    ;;
  WARN)
    printf 'sage-config-gate: %s\n' "$MESSAGE" >&2
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
