#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-config-gate.sh — Claude Code PreToolUse hook (the meta-gate)
#
# Blocks a gated agent from turning OFF its own enforcement. While
# `hard_enforcement: true`, an agent Edit/Write to .sage/config.yaml that would
# reduce any gate's effective-enabled state (flip hard_enforcement true→false,
# add a *_gate: false opt-out, remove tdd_enforcement: true; with the v2
# review loop active, flip review_loop mode v2→v1, witness_capping
# true→false, or disputed_disposition true→false — an agent must not soften
# its own review floor; with the scope
# gate armed, lower scope_gate's rank or flip implicit_test_scope, or flip
# scope_judge true→false — an agent must not soften its own scope floor,
# SG-3) exits 2. Also
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
#   opt_in  tdd_enforcement / scope_judge — default OFF; ON only when explicitly true.
#   ranked  scope_gate — off < standard+ < all; lowering the rank is weakening.
MASTER = "hard_enforcement"
OPT_OUT = ("secrets_gate", "verify_gate")
OPT_IN = ("tdd_enforcement", "scope_judge")
SCOPE_RANK = {"off": 0, "standard+": 1, "all": 2}


def read_flag(text, key):
    """None if the key is absent, else True/False (FIRST occurrence)."""
    m = re.search(r"(?mi)^\s*%s\s*:\s*(true|false)\b" % re.escape(key), text or "")
    return None if not m else (m.group(1).lower() == "true")


def contradictory_flag(text, key):
    """The same key with BOTH values in one file is a reader-divergence bomb:
    first-wins readers stay armed while last-wins readers disarm (round-2
    review probed exactly that split across the sibling gates). A config in
    that state may not be CREATED through this gate."""
    vals = {v.lower() for v in re.findall(
        r"(?mi)^\s*%s\s*:\s*(true|false)\b" % re.escape(key), text or "")}
    return len(vals) > 1


def enabled(text, key):
    v = read_flag(text, key)
    if key == MASTER or key in OPT_IN:
        return v is True                       # default off
    return v is not False                      # opt-out: default on


def review_mode(text, absent="v2"):
    """The review_loop: block's mode. The LAST block wins, matching
    review.py's duplicate-key convention. Since the RR-28 flip, an ABSENT
    block means v2 on the Edit/Write path (deleting the block is not an
    escape); the coarse Bash matcher passes absent="v1" and only guards
    explicitly-v2 configs — consistent with its obvious-evasions-only
    remit."""
    blocks = re.findall(r"(?m)^review_loop:[ \t]*$((?:\n[ \t]+.*)*)", text or "")
    for block in reversed(blocks):
        mm = re.search(r"(?mi)^[ \t]+mode[ \t]*:[ \t]*(\S+)", block)
        if mm:
            return mm.group(1).lower()
    return absent


def witness_capping(text):
    return read_flag(text, "witness_capping") is not False   # default on


def disputed_guard(text):
    """review_loop.disputed_disposition — default on. Flipping it false
    restores the pre-hardening vanish (a cannot-reproduce'd critical
    closing STOP_CLEAN), which is exactly the escape a pressured fixer
    would reach for; while v2 is active the knob is the floor."""
    return read_flag(text, "disputed_disposition") is not False


def scope_mode(text):
    """The scope_gate mode. Absent → off (the gate SHIPS off; the default
    flips only when 30-§3's numbers land)."""
    m = re.search(r"(?mi)^\s*scope_gate\s*:\s*\"?([A-Za-z+]+)", text or "")
    v = m.group(1).lower() if m else "off"
    return v if v in SCOPE_RANK else "off"


def implicit_test_scope(text):
    return read_flag(text, "implicit_test_scope") is not False   # default on


JUDGE_KNOBS = ("judge_cmd", "judge_every", "judge_window",
               "judge_cooldown", "judge_timeout")


def judge_knobs(text):
    out = {}
    for key in JUDGE_KNOBS:
        m = re.search(r"(?mi)^\s*%s\s*:\s*(.+?)\s*(?:#.*)?$" % key, text or "")
        out[key] = m.group(1).strip() if m else None
    return out


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
        if disputed_guard(before) and not disputed_guard(after):
            return True
    # The scope floor (SG-3): lowering scope_gate's rank is an agent widening
    # its own permitted diff. And while the scope gate is armed, the
    # implicit_test_scope knob belongs to the human — flipping it EITHER way
    # reshapes the floor (false→true widens the test escape; true→false
    # breaks the witness-test guarantee the gate promises TDD).
    if SCOPE_RANK[scope_mode(after)] < SCOPE_RANK[scope_mode(before)]:
        return True
    if (scope_mode(before) != "off"
            and implicit_test_scope(before) != implicit_test_scope(after)):
        return True
    # While the judge is armed, its knobs are the judge: judge_cooldown:
    # 999999 is "never correct me", judge_every: 999999 is "never look", and
    # judge_cmd is a verdict oracle the agent would control. All of them
    # belong to the human while scope_judge is on.
    if enabled(before, "scope_judge") and judge_knobs(before) != judge_knobs(after):
        return True
    # Introducing a contradictory duplicate of an enforcement flag is
    # weakening even though first-wins readers don't move: any last-wins
    # reader (three sibling gates historically) reads the appended value.
    # The review-floor booleans are in the list because review.py itself
    # is a last-wins reader (documented duplicate-key convention) while
    # this gate reads first-wins — the exact divergence the bomb exploits.
    for key in (MASTER,) + OPT_OUT + OPT_IN + ("witness_capping",
                                               "disputed_disposition"):
        if not contradictory_flag(before, key) and contradictory_flag(after, key):
            return True
    # Same rule for the ranked scope_gate: a file saying both standard+ and
    # off is a reader-divergence bomb even when every current reader picks
    # the first.
    def scope_vals(text):
        return {v.lower() for v in re.findall(
            r"(?mi)^\s*scope_gate\s*:\s*\"?([A-Za-z+]+)", text or "")
            if v.lower() in SCOPE_RANK}
    if len(scope_vals(before)) <= 1 and len(scope_vals(after)) > 1:
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
    review_off = review_mode(current, absent="v1") == "v2" and re.search(
        r"witness_capping\s*:?\s*false|disputed_disposition\s*:?\s*false"
        r"|mode\s*:?\s*v1", cmd, re.I)
    scope_off = (scope_mode(current) != "off" and re.search(
        r"scope_gate\s*:?\s*\"?off|implicit_test_scope\s*:?\s*(true|false)",
        cmd, re.I))
    # A rank DECREASE written through a redirect (all → standard+) is the same
    # softening the Edit path catches via weaker().
    if not scope_off and scope_mode(current) == "all":
        scope_off = re.search(r"scope_gate\s*:?\s*\"?standard", cmd, re.I)
    judge_off = enabled(current, "scope_judge") and re.search(
        r"scope_judge\s*:?\s*false|judge_(cmd|every|window|cooldown|timeout)\s*:",
        cmd, re.I)
    if names_config and writes and (turns_off or review_off or scope_off
                                    or judge_off):
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
