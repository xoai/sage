#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-spec-gate.sh — Claude Code PreToolUse hook (ADR-4)
#
# Makes Rule 3 mechanical: while a Sage cycle is pre-spec, block edits to
# source files instead of trusting the model to remember not to. The hook
# enforces only what the constitution already declares, and only when Sage
# itself says a cycle is active.
#
# Registered by the claude-code generator with matcher Edit|Write|MultiEdit.
# Reads the tool-call JSON on stdin (fields: tool_name, tool_input.file_path,
# cwd) and decides in one python3 pass. No network, bash-3.2 + python3-stdlib.
#
# Contract (verified against code.claude.com/docs/en/hooks):
#   exit 0  → allow (the normal permission flow still applies)
#   exit 2  → block; the reason on stderr is fed back to the model
#
# HOOKS ARE GUARDS, NOT GATES. Any internal error fails OPEN (exit 0 with one
# warning line) — a broken hook must never brick a user's editor loop. Gates
# fail closed; hooks fail open.
#
# Allowed unconditionally (see the python block for the full matrix):
#   - not a Sage project (no .sage/)
#   - hard_enforcement is not explicitly true in .sage/config.yaml
#   - the target is under .sage/ or the vendored sage/ tree
#   - the target is not a recognized source file (docs, config, unknown ext)
#   - no active cycle manifest exists (Tier-1 work never creates one)
#   - every active cycle has a spec (gate_state past pre-spec)
#
# Multi-cycle limitation (R26): the hook does NOT attribute an edit to a
# specific cycle. If ANY active cycle is pre-spec, source edits are blocked.
# Escape by advancing/completing that cycle, marking it tier1 (delete its
# manifest), or setting hard_enforcement: false.
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

# Without python3 there is nothing to parse with — fail open.
if ! command -v python3 >/dev/null 2>&1; then
  echo "sage-spec-gate: python3 not found; allowing edit" >&2
  exit 0
fi

# The decision logic goes to a temp file rather than an inline heredoc inside
# $(python3 <<'PY' … ): bash 3.2 mis-parses a heredoc nested in a command
# substitution. Writing the script via its own heredoc leaves the hook's real
# stdin (the tool-call JSON) intact for the python invocation below.
PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-spec-gate-XXXXXX" 2>/dev/null) || {
  echo "sage-spec-gate: could not create a temp file; allowing edit" >&2
  exit 0
}
trap 'rm -f "$PY_GATE"' EXIT

cat > "$PY_GATE" <<'PYEOF'
import glob
import json
import os
import re
import sys


def emit(decision, message=""):
    sys.stdout.write(decision + "\n")
    if message:
        sys.stdout.write(message)
    sys.exit(0)


# ── 1. Parse the tool-call JSON ──
try:
    data = json.load(sys.stdin)
except Exception:
    emit("WARN", "could not parse hook input JSON")

if not isinstance(data, dict):
    emit("WARN", "hook input was not a JSON object")

tool_input = data.get("tool_input") or {}
file_path = (tool_input.get("file_path") or "").strip()
stdin_cwd = (data.get("cwd") or "").strip()

# ── 2. Resolve the project root ──
# CWD is not guaranteed to be the project root (Claude can cd), so prefer the
# documented CLAUDE_PROJECT_DIR, then the cwd handed to us, then $PWD.
project_root = (os.environ.get("CLAUDE_PROJECT_DIR") or stdin_cwd or os.getcwd())
project_root = os.path.abspath(project_root)

sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    emit("ALLOW")  # not a Sage project

# ── 3. hard_enforcement ──
# Only an explicit `hard_enforcement: true` enforces. Absent or false → allow,
# so the hook never surprise-blocks an older or opted-out project.
enforce = None
config_path = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
                if m:
                    enforce = (m.group(1).lower() == "true")
                    break
    except OSError:
        pass
if enforce is not True:
    emit("ALLOW")

# ── Manifest state reader (used by the completion guard and the spec gate) ──
KNOWN_STATES = {
    "pre-spec", "spec-approved", "plan-approved",
    "building", "gates-passed", "complete",
}


def manifest_gate_state(path):
    """Return ('ok', state) | ('absent', None) | ('corrupt', None) | ('unreadable', None)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ("unreadable", None)

    text = text.lstrip("﻿")
    if not text.lstrip().startswith("---"):
        return ("absent", None)  # no frontmatter — old/hand-written manifest
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not m:
        return ("corrupt", None)  # opened frontmatter, never closed
    block = m.group(1)
    fm = re.search(
        r"^\s*gate_state\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$", block, re.M
    )
    if not fm:
        return ("absent", None)  # frontmatter present but no gate_state (forward-compat)
    val = fm.group(1).lower()
    if val not in KNOWN_STATES:
        return ("corrupt", None)
    return ("ok", val)


# ── 4. Classify the target path ──
if not file_path:
    emit("ALLOW")  # no file to gate (some tool calls carry none)

abspath = file_path if os.path.isabs(file_path) else os.path.join(project_root, file_path)
abspath = os.path.normpath(abspath)

# ── Completion guard (R25) ──
# Narrowly scoped to edits of a cycle manifest: block marking a cycle complete
# while its gate_state has not reached gates-passed. This is Rule 5 (verify
# before claiming done) made mechanical. It runs before the ".sage/ → allow"
# rule below, which would otherwise wave every manifest edit through.
work_root = os.path.normpath(os.path.join(sage_dir, "work"))
is_manifest = os.path.basename(abspath) == "manifest.md"
under_work = False
if is_manifest:
    try:
        under_work = os.path.commonpath([abspath, work_root]) == work_root
    except ValueError:
        under_work = False

if is_manifest and under_work:
    # The content this edit would write. Write carries `content`; Edit carries
    # `new_string`; MultiEdit carries an `edits` array of new_strings.
    new_text = ""
    if isinstance(tool_input.get("content"), str):
        new_text += tool_input["content"]
    if isinstance(tool_input.get("new_string"), str):
        new_text += "\n" + tool_input["new_string"]
    for e in (tool_input.get("edits") or []):
        if isinstance(e, dict) and isinstance(e.get("new_string"), str):
            new_text += "\n" + e["new_string"]

    wants_complete = bool(
        re.search(r"(?:gate_state|status)\s*:\s*\"?complete\b", new_text, re.I)
    )
    if wants_complete:
        cur_kind, cur_state = manifest_gate_state(abspath)
        # Block only a real backwards jump: an existing cycle that has not yet
        # reached gates-passed. A fresh/unreadable manifest, or one already at
        # gates-passed/complete, is not blocked (fail toward not blocking).
        if cur_kind == "ok" and cur_state not in ("gates-passed", "complete"):
            slug = os.path.basename(os.path.dirname(abspath))
            emit(
                "BLOCK",
                (
                    'Sage spec-gate: cannot mark cycle "%s" complete — gate_state is\n'
                    '"%s", not gates-passed. Rule 5: run the quality gates and verify\n'
                    "before claiming done. Run the gates, set gate_state: gates-passed,\n"
                    "then complete."
                ) % (slug, cur_state),
            )

# Writing Sage's own state or the vendored framework is never gated.
try:
    rel = os.path.relpath(abspath, project_root)
except ValueError:
    rel = file_path
first = rel.split(os.sep)[0]
if first in (".sage", "sage"):
    emit("ALLOW")

# Block only recognized SOURCE files. Docs, config, and unknown extensions are
# allowed — writing specs/plans/notes must never be blocked, and an unknown
# extension errs toward not blocking (hooks fail open).
SOURCE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rs",
    ".java", ".rb", ".php", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp",
    ".cs", ".swift", ".kt", ".kts", ".dart", ".vue", ".svelte", ".scala",
    ".ex", ".exs", ".sh", ".bash", ".zsh", ".sql", ".css", ".scss", ".sass",
    ".less", ".html", ".htm", ".m", ".mm", ".r", ".jl", ".lua", ".pl",
}
ext = os.path.splitext(abspath)[1].lower()
if ext not in SOURCE_EXT:
    emit("ALLOW")

# ── 5. Inspect active cycle manifests ──
manifests = sorted(glob.glob(os.path.join(sage_dir, "work", "*", "manifest.md")))
if not manifests:
    emit("ALLOW")  # no active cycle / Tier-1 work

pre_spec = []
warned = False
for mpath in manifests:
    kind, state = manifest_gate_state(mpath)
    if kind in ("corrupt", "unreadable"):
        warned = True
        continue
    if kind == "absent":
        continue  # treat like an opted-out cycle — never block on it
    if state == "complete":
        continue  # finished cycle
    if state == "pre-spec":
        pre_spec.append(os.path.basename(os.path.dirname(mpath)))

# ── 6. Decide ──
if pre_spec:
    slug = pre_spec[0]
    message = (
        'Sage spec-gate: cycle "%s" is pre-spec. Rule 3: spec.md must exist and\n'
        "be approved before implementation. Write .sage/work/%s/spec.md and get\n"
        "[A] approval, or set tier: tier1 in the manifest if this is genuinely\n"
        "trivial, or set hard_enforcement: false in .sage/config.yaml to disable.\n"
        "(Blocked edit: %s)"
    ) % (slug, slug, rel)
    if len(pre_spec) > 1:
        message += "\nOther pre-spec cycles: " + ", ".join(pre_spec[1:])
    emit("BLOCK", message)

if warned:
    emit("WARN", "a cycle manifest could not be parsed; allowing this edit")

emit("ALLOW")
PYEOF

# Run the decision. python3 inherits the hook's stdin (the tool-call JSON);
# the heredoc above fed cat, not python.
GATE_OUT=$(python3 "$PY_GATE")
GATE_RC=$?

if [ "$GATE_RC" -ne 0 ]; then
  echo "sage-spec-gate: internal error (python exit $GATE_RC); allowing edit" >&2
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
    printf 'sage-spec-gate: %s\n' "$MESSAGE" >&2
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
