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

# A cycle may complete only once its `qa:` says what became of independent QA.
# `pending` is not terminal — that is the whole point: silence is the failure
# mode R29 was written to prevent, and the one it did not prevent.
QA_TERMINAL = {
    "passed", "skipped-no-subagent", "skipped-disabled", "skipped-timeout", "waived",
}


def manifest_field(path, name):
    """One frontmatter scalar, lowercased — or None if absent/unreadable.

    None means "this manifest does not speak this field", which for an older cycle
    written before the field existed must NOT be treated as a violation. The hook
    never surprise-blocks a project that was mid-flight when Sage upgraded.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text.lstrip("﻿"), re.S)
    if not m:
        return None
    fm = re.search(
        r"^\s*%s\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$" % re.escape(name),
        m.group(1), re.M,
    )
    return fm.group(1).lower() if fm else None


def parse_ledger(text):
    """The subagent task ledger from a manifest's frontmatter (R101).

    Returns a list of {id, status, review} dicts, or None when the manifest has
    no ledger at all. None and [] mean different things and are not
    interchangeable: None is "this cycle does not use a task ledger" (every
    manifest written before v1.3.0, and every inline-mode cycle), while [] is "it
    has one and it is empty". Only None disables the guard.

    The frontmatter shape:

        tasks:
          - id: 1
            status: done
            review: approved
            commits: abc1234..def5678

    The other hook parsers read flat scalars only, which is why this is separate
    rather than an extra regex bolted onto manifest_field().
    """
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text.lstrip("﻿"), re.S)
    if not m:
        return None
    block = m.group(1)
    if not re.search(r"^\s*tasks\s*:", block, re.M):
        return None

    tasks = []
    in_ledger = False
    current = None
    for line in block.splitlines():
        if re.match(r"^\s*tasks\s*:", line):
            in_ledger = True
            continue
        if not in_ledger:
            continue
        # A new top-level key (no indent, not a list item) ends the ledger.
        if line.strip() and not line.startswith((" ", "\t", "-")):
            break
        item = re.match(r"^\s*-\s*(.*)$", line)
        if item:
            if current:
                tasks.append(current)
            current = {}
            rest = item.group(1).strip()
            if rest:
                kv = re.match(r"^([A-Za-z_]+)\s*:\s*\"?([^\"#]*)\"?", rest)
                if kv:
                    current[kv.group(1).lower()] = kv.group(2).strip().lower()
            continue
        if current is not None:
            kv = re.match(r"^\s+([A-Za-z_]+)\s*:\s*\"?([^\"#]*)\"?", line)
            if kv:
                current[kv.group(1).lower()] = kv.group(2).strip().lower()
    if current:
        tasks.append(current)
    return tasks


def ledger_incomplete(tasks):
    """The tasks that are not (done AND approved). These block gates-passed."""
    bad = []
    for t in tasks:
        status = (t.get("status") or "").strip()
        review = (t.get("review") or "").strip()
        if status != "done" or review != "approved":
            bad.append((t.get("id", "?"), status or "?", review or "?"))
    return bad


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

    # ── Ledger guard (R101, subagent execution) ──
    #
    # A cycle running under subagent execution carries a task ledger. It may not
    # reach `gates-passed` while any task in that ledger is not done AND approved.
    #
    # This fires on gates-passed rather than on complete, deliberately and one step
    # earlier than the two guards below: gates-passed is the state that ASSERTS the
    # quality chain ran. A cycle that reaches it with an unreviewed task has made a
    # false claim already, and blocking only at `complete` would let that claim sit
    # in the manifest — where /continue, the branch reviewer, and the next session
    # all read it as true.
    #
    # Backward compatible by construction: parse_ledger() returns None for every
    # manifest that has no `tasks:` block, which is every manifest written before
    # v1.3.0 and every inline-mode cycle. None disables the guard entirely. A
    # project that was mid-flight when Sage upgraded is never surprise-blocked.
    wants_gates_passed = bool(
        re.search(r"gate_state\s*:\s*\"?gates-passed\b", new_text, re.I)
    )
    if wants_gates_passed:
        # A Write carries the whole new manifest, so the ledger it declares is in
        # new_text. An Edit may touch only gate_state, leaving the ledger on disk.
        # Prefer the incoming text when it actually declares one.
        ledger = parse_ledger(new_text)
        if ledger is None:
            try:
                with open(abspath, encoding="utf-8", errors="replace") as fh:
                    ledger = parse_ledger(fh.read())
            except OSError:
                ledger = None

        # A cycle running in SUBAGENT mode with no ledger at all is not a
        # backward-compatible cycle — it is a subagent cycle that never wrote its
        # ledger, and the guard below would wave it straight through.
        #
        # E9 found this. The agent ran in subagent mode, never produced a `tasks:`
        # block, and reached for gates-passed; parse_ledger() returned None, the
        # guard disabled itself, and nothing complained. The check that was
        # supposed to prove every task got an independent review was opt-in by the
        # very agent it polices.
        #
        # `execution_mode: subagent` is the discriminator: pre-1.3.0 manifests and
        # inline cycles never carry it, so they stay exempt exactly as before.
        mode = manifest_field(abspath, "execution_mode")
        if mode is None:
            m = re.search(r"^\s*execution_mode\s*:\s*\"?([A-Za-z0-9_-]+)",
                          new_text, re.M)
            mode = m.group(1).lower() if m else None

        if mode == "subagent" and ledger is None:
            slug = os.path.basename(os.path.dirname(abspath))
            emit(
                "BLOCK",
                (
                    'Sage spec-gate: cannot set gate_state: gates-passed on "%s" —\n'
                    "the cycle is in subagent execution and has NO task ledger.\n\n"
                    "R101: subagent mode's entire claim is that every task was\n"
                    "implemented by a fresh context and independently reviewed by\n"
                    "another. The ledger is the only record of that. A cycle with no\n"
                    "ledger is not a cycle that passed review — it is a cycle with no\n"
                    "evidence it was reviewed at all.\n\n"
                    "Write the `tasks:` block, or set execution_mode: inline and stop\n"
                    "claiming the subagent chain ran."
                ) % slug,
            )

        if ledger is not None:
            incomplete = ledger_incomplete(ledger)
            if incomplete:
                slug = os.path.basename(os.path.dirname(abspath))
                rows = "\n".join(
                    "  task %s — status: %s, review: %s" % row for row in incomplete[:8]
                )
                emit(
                    "BLOCK",
                    (
                        'Sage spec-gate: cannot set gate_state: gates-passed on "%s" —\n'
                        "%d ledger task(s) are not done+approved:\n\n%s\n\n"
                        "R101: in subagent execution, a task is finished when an INDEPENDENT\n"
                        "reviewer approved it, not when the implementer said it was done.\n"
                        "gates-passed asserts the quality chain ran. Finish or fix the tasks\n"
                        "above, or record why they are abandoned — but do not claim the chain\n"
                        "ran on tasks it never saw."
                    ) % (slug, len(incomplete), rows),
                )

    wants_complete = bool(
        re.search(r"(?:gate_state|status)\s*:\s*\"?complete\b", new_text, re.I)
    )
    if wants_complete:
        cur_kind, cur_state = manifest_gate_state(abspath)
        slug = os.path.basename(os.path.dirname(abspath))

        # Block only a real backwards jump: an existing cycle that has not yet
        # reached gates-passed. A fresh/unreadable manifest, or one already at
        # gates-passed/complete, is not blocked (fail toward not blocking).
        if cur_kind == "ok" and cur_state not in ("gates-passed", "complete"):
            emit(
                "BLOCK",
                (
                    'Sage spec-gate: cannot mark cycle "%s" complete — gate_state is\n'
                    '"%s", not gates-passed. Rule 5: run the quality gates and verify\n'
                    "before claiming done. Run the gates, set gate_state: gates-passed,\n"
                    "then complete."
                ) % (slug, cur_state),
            )

        # ── QA disposition guard (R29, mechanical) ──
        # A cycle may not complete while it is silent about what happened to its
        # independent QA. R29 promised a skipped review "announces itself and logs
        # to decisions.md — never silently"; Phase 4 measured the log at 1 run in 3,
        # because it was prose and prose is read by the model that is deciding
        # whether to bother. It is not asked for any more.
        #
        # This does not detect a missing Task tool — absence is not observable from
        # a hook. It makes an UNDECLARED skip impossible, which is the half that can
        # be enforced. Once declared, sage-degradation-log.sh writes the audit line
        # itself, so a declared skip cannot go unlogged either.
        qa_state = manifest_field(abspath, "qa")
        new_qa = re.search(
            r"^\s*qa\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$", new_text, re.M
        )
        if new_qa:
            qa_state = new_qa.group(1).lower()

        # An older cycle that predates the field is not blocked: the hook must never
        # surprise a project that was mid-flight when Sage upgraded (fail open).
        if cur_kind == "ok" and qa_state is not None and qa_state not in QA_TERMINAL:
            emit(
                "BLOCK",
                (
                    'Sage spec-gate: cannot mark cycle "%s" complete — qa is "%s".\n'
                    "R29: a completion must say what happened to independent QA; it may\n"
                    "not stay silent about it. Set one of:\n"
                    "  qa: passed                 auto-QA ran and passed\n"
                    "  qa: skipped-no-subagent    no sub-agent dispatch on this platform\n"
                    "  qa: skipped-disabled       auto_qa is off in .sage/config.yaml\n"
                    "  qa: skipped-timeout        the sub-agent timed out\n"
                    "  qa: waived                 the user accepted completion without it\n"
                    "Any value but `passed` is logged to .sage/decisions.md automatically."
                ) % (slug, qa_state),
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
