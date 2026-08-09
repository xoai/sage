#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-bookkeeping-gate.sh — Claude Code PreToolUse hook
#
# Makes the close-out economy's bookkeeping rule mechanical: during an active
# cycle, a direct Edit/Write to that cycle's manifest.md or decisions.md is
# redirected (exit 2, reason on stderr) to the one-command writer:
#
#     python3 sage/runtime/tools/manifest.py close-out <manifest> \
#       --summary ... --next-step ... --decision ... --complete-task N \
#       [--status blocked --blocked-on "..."]
#
# WHY A HOOK AND NOT A PARAGRAPH. The 2026-07-15/16 profiles measured it twice:
# `batch_bookkeeping` prose → 8 incremental edits (~29% of the resume session's
# cost); then the close-out command shipped with instructions in cycle-protocol,
# build-loop, build.workflow AND the resume brief — and the next kept run made
# ZERO close-out calls, because the session read none of those documents (it
# read the manifest directly and never ran `manifest.py resume`). The only
# channel that provably reaches every session is this one: the tool call
# itself. Block → the reason names the command → the model recovers and runs
# it. That block→recover→retry loop is the proven pattern (the TDD gate
# attestation watched it work inside a subagent).
#
# Contract: exit 0 allow · exit 2 block (stderr fed back to the model).
# HOOKS ARE GUARDS, NOT GATES — any internal error fails OPEN.
#
# Allowed unconditionally:
#   - not a Sage project; python3 missing; unparseable input
#   - hard_enforcement is not explicitly true (same switch as the spec gate),
#     or bookkeeping_gate is explicitly false (dedicated opt-out)
#   - the target file DOES NOT EXIST yet — creation is authoring, not
#     bookkeeping; the first checkpoint must be able to write the manifest
#   - the cycle is not active (status complete/abandoned)
#   - anything outside .sage/work/*/{manifest.md,decisions.md} — plan.md stays
#     free (it is authored and revised as an artifact; its checkboxes go
#     through close-out but blocking plan edits would break the plan phase),
#     and the global .sage/decisions.md stays free (cross-initiative log)
#   - Bash is never matched — manifest.py's own writes pass by construction
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "sage-bookkeeping-gate: python3 not found; allowing edit" >&2
  exit 0
fi

# Temp file, not an inline heredoc in $( … ): bash 3.2 mis-parses that, and the
# hook's real stdin (the tool-call JSON) must reach python untouched.
PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-bookkeeping-gate-XXXXXX" 2>/dev/null) || {
  echo "sage-bookkeeping-gate: could not create a temp file; allowing edit" >&2
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


try:
    data = json.load(sys.stdin)
except Exception:
    emit("WARN", "could not parse hook input JSON")
if not isinstance(data, dict):
    emit("WARN", "hook input was not a JSON object")

tool_input = data.get("tool_input") or {}
file_path = (tool_input.get("file_path") or "").strip()
if not file_path:
    emit("ALLOW")

project_root = (os.environ.get("CLAUDE_PROJECT_DIR")
                or (data.get("cwd") or "").strip() or os.getcwd())
project_root = os.path.abspath(project_root)
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    emit("ALLOW")

# Same master switch as the spec gate, plus a dedicated opt-out.
enforce = None
gate_off = False
config_path = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # FIRST occurrence wins — the config-gate's reader convention.
                # A last-wins read here let an appended duplicate
                # `hard_enforcement: false` silence THIS gate (the scope
                # block's guard) while the first-wins gates stayed armed.
                m = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
                if m and enforce is None:
                    enforce = (m.group(1).lower() == "true")
                m = re.match(r"\s*bookkeeping_gate\s*:\s*false\b", line, re.I)
                if m:
                    gate_off = True
    except OSError:
        pass
if enforce is not True or gate_off:
    emit("ALLOW")

# Only a cycle's manifest.md / decisions.md, and only if it already exists.
abspath = (file_path if os.path.isabs(file_path)
           else os.path.join(project_root, file_path))
abspath = os.path.abspath(abspath)
rel = os.path.relpath(abspath, project_root).replace("\\", "/")
m = re.match(r"^\.sage/work/([^/]+)/(manifest\.md|decisions\.md)$", rel)
if not m:
    emit("ALLOW")
if not os.path.isfile(abspath):
    emit("ALLOW")          # creation is authoring, not bookkeeping

# Only while that cycle is ACTIVE (a post-mortem edit of a dead cycle is fine).
manifest_path = os.path.join(project_root, ".sage", "work", m.group(1), "manifest.md")
status = None
try:
    with open(manifest_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    fm = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text.lstrip("﻿"), re.S)
    if fm:
        sm = re.search(r"^\s*status\s*:\s*\"?([A-Za-z-]+)", fm.group(1), re.M)
        status = sm.group(1).lower() if sm else None
except OSError:
    pass
if status in ("complete", "completed", "abandoned"):
    emit("ALLOW")

# gate_state transitions are APPROVAL flow, not bookkeeping — the spec-gate's
# completion guard already polices them (QA field, ledger). Blocking them here
# would strand a cycle that legitimately needs to record gates-passed. Yield —
# but NOT for an edit that also touches the scope or task_graph block: merely
# mentioning `gate_state` in the payload must not become a skeleton key for
# widening `scope:` — or rewiring `task_graph:` dependencies (A8: a hand-cut
# edge dispatches coupled tasks into concurrent lanes) — by hand (independent
# review, confirmed by probe). Both blocks are amended through
# `manifest.py scope …` / `manifest.py graph derive`, which write via Bash
# and never meet this gate.
#
# "Touches the block" is decided by RECONSTRUCTION, not substrings
# (the config-gate's pattern): apply the edit, parse the section
# before and after, compare. A structure-key regex was probed twice and
# lost both ways — prose saying "out of scope:" stranded legit transitions,
# and a widening that adds only a list item (`    - src/**`) carries no
# structure key at all (round-3 review, confirmed). A Write replaces the
# whole file, so for Write the yield requires the content to carry NO scope
# or task_graph block — a full-manifest rewrite is bookkeeping whatever
# else it says.


# MULTILINE only, NOT DOTALL: with (?s) the `.` in the body pattern crossed
# newlines and each "section" greedily captured to end-of-file, so the
# compare only worked because gate_state happens to sit above the guarded
# blocks in the real template (independent review, finding 3 side-note).
# Without `s`, the capture is the actual indented block and nothing else.
def scope_section(text):
    m = re.search(r"(?m)^[ \t]*scope\s*:\s*$\n((?:[ \t]+.*\n?)*)", text or "")
    return m.group(0) if m else ""


def graph_section(text):
    m = re.search(r"(?m)^[ \t]*task_graph\s*:\s*$\n((?:[ \t]+.*\n?)*)", text or "")
    return m.group(0) if m else ""


def lanes_section(text):
    m = re.search(r"(?m)^[ \t]*lanes\s*:\s*$\n((?:[ \t]+.*\n?)*)", text or "")
    return m.group(0) if m else ""


def guarded_sections(text):
    return "\x00".join((scope_section(text), graph_section(text),
                        lanes_section(text)))


edit_texts = []
if isinstance(tool_input.get("content"), str):
    edit_texts.append(tool_input["content"])
for key in ("old_string", "new_string"):
    if isinstance(tool_input.get(key), str):
        edit_texts.append(tool_input[key])
for e in (tool_input.get("edits") or []):
    if isinstance(e, dict):
        for key in ("old_string", "new_string"):
            if isinstance(e.get(key), str):
                edit_texts.append(e[key])
edit_text = "\n".join(edit_texts)

if "gate_state" in edit_text:
    tool = data.get("tool_name") or ""
    if tool == "Write":
        content = str(tool_input.get("content") or "")
        if not (scope_section(content) or graph_section(content)
                or lanes_section(content)):
            emit("ALLOW")
    else:
        try:
            with open(abspath, encoding="utf-8", errors="replace") as fh:
                current = fh.read()
        except OSError:
            current = ""
        after = current
        edits = tool_input.get("edits")
        if not edits and "new_string" in tool_input:
            edits = [{"old_string": tool_input.get("old_string", ""),
                      "new_string": tool_input.get("new_string", "")}]
        for e in edits or []:
            if isinstance(e, dict) and e.get("old_string"):
                # Model the edit FAITHFULLY: replace_all replaces every
                # occurrence. The count=1 model let a replace_all edit whose
                # old_string also occurs above the guarded blocks mutate a
                # task_graph dependency edge while the gate compared an
                # unchanged reconstruction (independent review, finding 3).
                count = -1 if e.get("replace_all") else 1
                after = after.replace(e["old_string"],
                                      e.get("new_string", ""), count)
        if guarded_sections(current) == guarded_sections(after):
            emit("ALLOW")

emit("BLOCK", (
    "sage-bookkeeping-gate: don't hand-edit %s during an active cycle — apply "
    "the whole update in ONE pass instead (this is the close-out economy's "
    "bookkeeping rule, made mechanical):\n"
    "\n"
    "  python3 sage/runtime/tools/manifest.py close-out "
    ".sage/work/%s/manifest.md \\\n"
    "    --summary \"...\" --next-step \"...\" --decision \"...\" "
    "--complete-task N \\\n"
    "    [--phase X] [--status blocked --blocked-on \"the question, the "
    "options, whose call\"]\n"
    "\n"
    "One command writes the manifest prose, prepends decisions (Rule 7), and "
    "checks plan boxes. gate_state and updated: are machine-owned — never set "
    "them by hand. Compose everything first, then run it once."
    % (rel, m.group(1))
))
PYEOF

GATE_OUT=$(python3 "$PY_GATE")
GATE_RC=$?

if [ "$GATE_RC" -ne 0 ]; then
  echo "sage-bookkeeping-gate: internal error (python exit $GATE_RC); allowing edit" >&2
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
    printf 'sage-bookkeeping-gate: %s\n' "$MESSAGE" >&2
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
