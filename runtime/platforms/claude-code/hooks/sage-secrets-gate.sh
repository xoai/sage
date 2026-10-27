#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-secrets-gate.sh — Claude Code PreToolUse hook
#
# Blocks a source edit that hardcodes a credential. Exit 2; the reason tells
# the model to use env/config instead — the block→recover→retry pattern.
#
# WHY THIS EXISTS, MEASURED. The weak-model campaign (2026-07-17): handed a
# live API key in the prompt, opus-bare refuses to hardcode it 3/3 on judgment
# alone — haiku-bare hardcodes it 3/3, and haiku WITH Sage's constitution
# paragraph still hardcoded it 2/3. The rule was prose; prose does not reach a
# weak model under pressure. This is the E1/TDD-hook lesson applied to E2:
# the one +Sage delta shape that transfers down-model is a hook.
#
# WHAT IT MATCHES — high-precision, provider-shaped tokens only:
#   OpenAI/Anthropic-style keys (sk-…), AWS access key ids (AKIA…), GitHub
#   tokens (ghp_/gho_/ghs_/github_pat_), Slack (xox…-), Google API (AIza…),
#   private-key blocks. Deliberately NOT a general entropy scanner: a guard
#   with false positives is a guard people disable (the E4 tidy-bait lesson,
#   inverted). `.env*` files, examples/fixtures/tests and non-source files are
#   allowed — the rule is "not hardcoded into SOURCE", not "never on disk".
#
# Contract: exit 0 allow · exit 2 block (stderr fed back to the model).
# HOOKS ARE GUARDS, NOT GATES — any internal error fails OPEN.
# Gated by hard_enforcement: true (same master switch as the spec gate);
# secrets_gate: false is the dedicated opt-out.
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "sage-secrets-gate: python3 not found; allowing edit" >&2
  exit 0
fi

PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-secrets-gate-XXXXXX" 2>/dev/null) || {
  echo "sage-secrets-gate: could not create a temp file; allowing edit" >&2
  exit 0
}
trap 'rm -f "$PY_GATE"' EXIT

cat > "$PY_GATE" <<'PYEOF'
import json
import os
import re
import sys


def emit(decision, message=""):
    # To Claude Code a block is a structured deny: the model gets the reason
    # alone, where exit 2 also showed the hook's command line and read like a
    # script failing (review 2026-10-26, C6; Claude Code still labels both
    # "hook error" — docs/attestations/claude-code-structured-deny-2026-10-27.md).
    # Callers that send no hook_event_name (opencode, the tests) keep exit 2.
    payload = globals().get("data")
    if (decision == "BLOCK" and isinstance(payload, dict)
            and payload.get("hook_event_name") == "PreToolUse"):
        decision = "DENY"
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

# ── sage-root: identical in every hook (pinned by hook test WT0) ──
# A Desktop or `--worktree` session edits in a linked worktree while
# CLAUDE_PROJECT_DIR stays at the main checkout. Judge the checkout the
# edit lands in: when `probe` is in ANOTHER registered worktree of the same
# repository whose Sage config (at the project subdirectory, if the project
# lives in one) says what the main checkout config says, that worktree is
# the root — its branch, HEAD and cycles. Anything else keeps `base`, as
# before: the same checkout, a nested repo, a hand-made .git file, a
# worktree without Sage, or one whose config differs (an empty, laxer or
# older one would otherwise be the judge — review 2026-10-27).
def sage_worktree_root(base, probe):
    import subprocess as _sp

    def _git(d, *a):
        try:
            p = _sp.run(["git", "-C", d] + list(a), capture_output=True,
                        text=True, timeout=5)
            return p.stdout if p.returncode == 0 else ""
        except (OSError, _sp.SubprocessError):
            return ""

    if not base or not probe or not os.path.isfile(os.path.join(base, ".sage", "config.yaml")):
        return base                      # no Sage policy to match: nothing to switch to
    d = os.path.abspath(probe)
    while not os.path.isdir(d):
        up = os.path.dirname(d)
        if up == d:
            return base
        d = up
    a = d                                # no .sage/ above the probe: no git calls
    while not os.path.isdir(os.path.join(a, ".sage")):
        up = os.path.dirname(a)
        if up == a:
            return base
        a = up
    # One line per value; --show-prefix prints an EMPTY line at the top.
    out = _git(d, "rev-parse", "--show-toplevel", "--git-dir", "--git-common-dir").split("\n")[:-1]
    ref = _git(base, "rev-parse", "--git-dir", "--git-common-dir", "--show-prefix").split("\n")[:-1]
    if len(out) != 3 or len(ref) != 3 or not all(out) or not all(ref[:2]):
        return base
    top, git_dir, common = out

    def real(p, at):
        return os.path.realpath(os.path.join(at, p))

    if real(common, d) != real(ref[1], base) or real(git_dir, d) == real(ref[0], base):
        return base                      # another repository, or the base checkout itself
    root = os.path.join(os.path.realpath(top), ref[2]).rstrip(os.sep)
    # NUL-separated: a path holding a newline cannot forge an entry.
    listing = _git(base, "worktree", "list", "--porcelain", "-z")
    listed = [os.path.realpath(f[9:]) for f in listing.split("\0") if f.startswith("worktree ")]
    if os.path.realpath(top) not in listed:
        return base

    def policy(r):
        try:
            with open(os.path.join(r, ".sage", "config.yaml"), encoding="utf-8",
                      errors="replace") as fh:
                return [x.rstrip() for x in fh.read().split("\n")
                        if x.strip() and not x.lstrip().startswith("#")
                        and not x.startswith("sage-version:")]
        except OSError:
            return None

    mine = policy(root)
    if mine is None or mine != policy(base):
        return base
    # Hand the root back spelled like the probe (macOS /var is /private/var;
    # a symlinked directory), or every relpath against it reads "../". No
    # lexical ancestor that IS the root: keep base rather than guess.
    a = d
    while os.path.realpath(a) != root:
        up = os.path.dirname(a)
        if up == a:
            return base
        a = up
    return a


def sage_probe(data):
    """Where the call acts: the edited file, else the shell cwd."""
    cwd = (data.get("cwd") or "").strip()
    fp = str((data.get("tool_input") or {}).get("file_path") or "").strip()
    return os.path.join(cwd or os.getcwd(), fp) if fp else cwd
# ── end sage-root ──

project_root = sage_worktree_root(project_root, sage_probe(data))
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    emit("ALLOW")

enforce = None
gate_off = False
config_path = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
                if m:
                    enforce = (m.group(1).lower() == "true")
                m = re.match(r"\s*secrets_gate\s*:\s*false\b", line, re.I)
                if m:
                    gate_off = True
    except OSError:
        pass
if enforce is not True or gate_off:
    emit("ALLOW")

rel = os.path.relpath(
    file_path if os.path.isabs(file_path)
    else os.path.join(project_root, file_path), project_root).replace("\\", "/")
base = os.path.basename(rel)
parts = rel.split("/")

# New content: Write carries `content`; Edit carries `new_string`; MultiEdit a
# list of edits. Concatenate whatever is present.
blobs = []
for key in ("content", "new_string"):
    v = tool_input.get(key)
    if isinstance(v, str):
        blobs.append(v)
for e in tool_input.get("edits") or []:
    if isinstance(e, dict) and isinstance(e.get("new_string"), str):
        blobs.append(e["new_string"])
text = "\n".join(blobs)
if not text:
    emit("ALLOW")


def block(what):
    emit("BLOCK", (
        "sage-secrets-gate: this edit hardcodes %s into %s — credentials "
        "never go into files (constitution: secrets).\n"
        "\n"
        "Instead: read it from the environment (os.environ / process.env) "
        "or a gitignored config (.env), and reference the variable here. "
        "If a placeholder is genuinely needed, use an obvious fake like "
        "\"YOUR_API_KEY\"." % (what, rel)))


# ── Class 1: LIVE-marked keys — blocked EVERYWHERE except .env*. ──
# The weak-model proof run caught the gap: E2's key (pfk_live_…) is a fictional
# vendor prefix no provider list can anticipate, and one run parked it in
# tests/ — which the source-only class exempts for FAKE fixtures. A key that
# says live/prod/secret in its own name is not a fixture: `live` means live,
# and it belongs in .env or nowhere. (sk_test_-style keys stay in class 2 —
# vendors design those for code and CI.)
if not (base.startswith(".env") or base == ".gitignore"):
    m = re.search(r"\b[A-Za-z]{2,8}_(?:live|prod|secret)_[A-Za-z0-9]{12,}", text)
    if m:
        block("a live-marked key (%s…)" % m.group(0)[:12])
    if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", text):
        block("a private key block")

# ── Class 2: provider-shaped tokens — blocked in SOURCE only. ──
# Placeholder-shaped fakes are legitimate in tests/fixtures/examples and docs;
# a guard with false positives is a guard people disable.
if base.startswith(".env") or base.endswith((".md", ".txt", ".lock", ".pem.example")):
    emit("ALLOW")
if any(p in ("examples", "fixtures", "tests", "test", ".sage", "sage",
             ".claude", "node_modules") for p in parts):
    emit("ALLOW")

PATTERNS = [
    (r"\bsk-[A-Za-z0-9_-]{16,}", "an sk-… API key"),
    (r"\bsk-ant-[A-Za-z0-9_-]{16,}", "an Anthropic API key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "an AWS access key id"),
    (r"\bgh[pos]_[A-Za-z0-9]{20,}", "a GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}", "a GitHub fine-grained token"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "a Slack token"),
    (r"\bAIza[0-9A-Za-z_-]{30,}", "a Google API key"),
]
for pat, what in PATTERNS:
    if re.search(pat, text):
        block(what)

emit("ALLOW")
PYEOF

GATE_OUT=$(python3 "$PY_GATE")
GATE_RC=$?

if [ "$GATE_RC" -ne 0 ]; then
  echo "sage-secrets-gate: internal error (python exit $GATE_RC); allowing edit" >&2
  exit 0
fi

DECISION=$(printf '%s\n' "$GATE_OUT" | sed -n '1p')
MESSAGE=$(printf '%s\n' "$GATE_OUT" | sed -n '2,$p')

case "$DECISION" in
  DENY)
    SAGE_DENY_REASON="$MESSAGE" python3 -c 'import json, os; print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": os.environ["SAGE_DENY_REASON"]}}))'
    exit 0
    ;;
  BLOCK)
    printf '%s\n' "$MESSAGE" >&2
    exit 2
    ;;
  WARN)
    printf 'sage-secrets-gate: %s\n' "$MESSAGE" >&2
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
