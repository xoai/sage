"""sage-gates — Sage mechanical gates as a Hermes plugin.

Ported from the claude-code POSIX hooks (runtime/platforms/claude-code/hooks/)
to Hermes's plugin surface:

  pre_tool_call  -> spec-gate (Rule 3), tdd-gate (Rule 1), secrets-gate
  post_tool_call -> R29 degradation audit (decisions.md written by code)

Hermes block contract (verified against hermes_cli/plugins.py):
  return {"action": "block", "message": "..."} from pre_tool_call and the tool
  call is vetoed; `message` becomes the tool result the model sees. Anything
  else (None, {}, exceptions) lets the call proceed.

HOOKS ARE GUARDS, NOT GATES: every code path here fails OPEN on internal
error — a broken hook must never brick the editor. Gates opt in via
.sage/config.yaml (hard_enforcement: true is the master switch), exactly like
the claude-code hooks, so this plugin never surprise-blocks a project that
has not asked for enforcement.

Hermes tool mapping (verified against the live tool schemas):
  write_file -> args["path"], args["content"]
  patch      -> args["path"], args["new_string"] (replace mode),
                args["patch"] (V4A patch mode — new_text is the patch body)
Everything else (terminal, execute_code, …) is not gated — the same documented
hole the claude-code hooks have (they matched Edit|Write|MultiEdit only).
"""

from __future__ import annotations

import datetime
import glob
import os
import re
import subprocess

# ── Shared classification ────────────────────────────────────────────────────

SKIP_PREFIX = (".sage/", "sage/", ".claude/", ".hermes/", "node_modules/",
               "vendor/", ".git/")

SOURCE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".rs",
    ".java", ".rb", ".php", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp",
    ".cs", ".swift", ".kt", ".kts", ".dart", ".vue", ".svelte", ".scala",
    ".ex", ".exs", ".sh", ".bash", ".zsh", ".sql", ".css", ".scss",
    ".sass", ".less", ".html", ".htm", ".m", ".mm", ".r", ".jl", ".lua",
    ".pl",
}

TEST_RE = re.compile(
    r"(^|/)tests?/|(^|/)__tests__/|(^|/)spec/"
    r"|(^|/)test_[^/]+$|[^/]*_test\.[a-z]+$"
    r"|[^/]*\.(test|spec)\.[a-z]+$",
    re.I,
)

KNOWN_STATES = {
    "pre-spec", "spec-approved", "plan-approved",
    "building", "gates-passed", "complete",
}

QA_TERMINAL = {
    "passed", "skipped-no-subagent", "skipped-disabled",
    "skipped-timeout", "waived",
}

DEGRADED = {
    "skipped-no-subagent":
        "auto-QA skipped (no sub-agent dispatch on this platform) — "
        "completion accepted without independent QA.",
    "skipped-disabled":
        "auto-QA skipped (auto_qa disabled in .sage/config.yaml) — "
        "completion accepted without independent QA.",
    "skipped-timeout":
        "auto-QA skipped (sub-agent timed out) — "
        "completion accepted without independent QA.",
    "waived":
        "auto-QA waived by the user — completion accepted without "
        "independent QA.",
}

DEGLOG_MARK = "[auto-logged by sage-gates post_tool_call]"

# sk-ant- MUST precede sk-: the generic sk- pattern would otherwise match
# first and mislabel Anthropic keys.
SECRET_PATTERNS = [
    (r"\bsk-ant-[A-Za-z0-9_-]{16,}", "an Anthropic API key"),
    (r"\bsk-[A-Za-z0-9_-]{16,}", "an sk-… API key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "an AWS access key id"),
    (r"\bgh[pos]_[A-Za-z0-9]{20,}", "a GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}", "a GitHub fine-grained token"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "a Slack token"),
    (r"\bAIza[0-9A-Za-z_-]{30,}", "a Google API key"),
]

# Hermes edit tools → how to pull (path, incoming new text) out of args.
_EDIT_TOOLS = ("write_file", "patch")


# ── Small helpers ────────────────────────────────────────────────────────────

def _allow():
    return None


def _block(gate, message, project_root, rel):
    """A block is an enforcement event: it gets an audit line, then the veto."""
    try:
        _log_block(project_root, gate, rel, message)
    except Exception:
        pass  # never let auditing break enforcement
    return {"action": "block", "message": message}


def _log_block(project_root, gate, rel, message):
    log_dir = os.path.join(project_root, ".sage", "gates")
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    first = (message or "").splitlines()[0][:160]
    with open(os.path.join(log_dir, "gate-blocks.log"), "a",
              encoding="utf-8") as fh:
        fh.write("%s [%s] %s — %s\n" % (ts, gate, rel, first))


def _target(tool_name, args):
    """(path, new_text) for a gated Hermes edit call, or (None, None)."""
    if tool_name not in _EDIT_TOOLS or not isinstance(args, dict):
        return None, None
    path = args.get("path") or args.get("file_path") or ""
    if not isinstance(path, str) or not path.strip():
        return None, None
    blobs = []
    for key in ("content", "new_string"):
        v = args.get(key)
        if isinstance(v, str):
            blobs.append(v)
    for e in args.get("edits") or []:
        if isinstance(e, dict) and isinstance(e.get("new_string"), str):
            blobs.append(e["new_string"])
    v = args.get("patch")  # V4A patch mode: the patch body carries new content
    if isinstance(v, str):
        blobs.append(v)
    return path.strip(), "\n".join(blobs)


def _resolve(project_root, file_path):
    abspath = file_path if os.path.isabs(file_path) else os.path.join(
        project_root, file_path)
    abspath = os.path.normpath(abspath)
    try:
        rel = os.path.relpath(abspath, project_root)
    except ValueError:
        return abspath, None  # different drive on Windows — outside project
    if rel.startswith(".."):
        return abspath, None
    return abspath, rel.replace(os.sep, "/")


def _config(project_root):
    """(.sage exists, {flag: value}) — only explicit `true` opts enforcement in."""
    sage_dir = os.path.join(project_root, ".sage")
    flags = {}
    if not os.path.isdir(sage_dir):
        return None, flags
    config = os.path.join(sage_dir, "config.yaml")
    if os.path.isfile(config):
        try:
            with open(config, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = re.match(r"\s*([a-z_]+)\s*:\s*(true|false)\b", line, re.I)
                    if m:
                        key = m.group(1).lower()
                        # FIRST occurrence wins — same direction the gate's
                        # _cfg_read_flag() reads. A duplicate key with both
                        # values is a reader-divergence bomb; the config-gate
                        # refuses to create one, and both readers agreeing on
                        # first-wins means a stray duplicate cannot disarm the
                        # gates even if one appears.
                        if key not in flags:
                            flags[key] = (m.group(2).lower() == "true")
        except OSError:
            pass
    return sage_dir, flags


def _is_enrolled_project(root):
    config = os.path.join(root, ".sage", "config.yaml")
    if not os.path.isfile(config):
        return False

    # ~/.sage is also Sage's global CLI/framework home. A config there applies
    # to that installation; it must not enroll every descendant of $HOME.
    home = os.path.normcase(os.path.abspath(os.path.expanduser("~")))
    candidate = os.path.normcase(os.path.abspath(root))
    global_framework = os.path.isdir(os.path.join(root, ".sage", "framework"))
    return not (candidate == home and global_framework)


def _find_project_root(abspath):
    """Nearest explicitly enrolled Sage project for the target or cwd.

    ``~/.sage`` is Sage's global framework install, so directory presence alone
    is not a project marker. Only ``.sage/config.yaml`` enrolls a project and
    activates Hermes context/gates there.
    """
    cur = os.path.dirname(abspath)
    while True:
        if _is_enrolled_project(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    cwd = os.path.abspath(os.getcwd())
    if _is_enrolled_project(cwd):
        return cwd
    return None


def _is_test(path):
    if any(path.startswith(p) for p in SKIP_PREFIX):
        return False
    return bool(TEST_RE.search(path))


def _is_source(path):
    if any(path.startswith(p) for p in SKIP_PREFIX):
        return False
    return os.path.splitext(path)[1].lower() in SOURCE_EXT


def _manifest_field(text, name):
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text.lstrip("﻿"), re.S)
    if not m:
        return None
    fm = re.search(
        r"^\s*%s\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$" % re.escape(name),
        m.group(1), re.M)
    return fm.group(1).lower() if fm else None


def _manifest_gate_state(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ("unreadable", None)
    text = text.lstrip("﻿")
    if not text.lstrip().startswith("---"):
        return ("absent", None)
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not m:
        return ("corrupt", None)
    fm = re.search(
        r"^\s*gate_state\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$",
        m.group(1), re.M)
    if not fm:
        return ("absent", None)
    val = fm.group(1).lower()
    if val not in KNOWN_STATES:
        return ("corrupt", None)
    return ("ok", val)


def _parse_ledger(text):
    """The subagent task ledger from a manifest's frontmatter (R101).

    None = no `tasks:` block (guard disabled); [] = ledger present and empty.
    """
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text.lstrip("﻿"), re.S)
    if not m:
        return None
    block = m.group(1)
    if not re.search(r"^\s*tasks\s*:", block, re.M):
        return None
    tasks, in_ledger, current = [], False, None
    for line in block.splitlines():
        if re.match(r"^\s*tasks\s*:", line):
            in_ledger = True
            continue
        if not in_ledger:
            continue
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


def _git(project_root, *args):
    try:
        p = subprocess.run(["git", "-C", project_root, *args],
                           capture_output=True, text=True, timeout=5)
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ── Gate 1: secrets-gate (hardcoded credentials in source) ───────────────────

def _secrets_gate(project_root, rel, new_text):
    base = os.path.basename(rel)
    parts = rel.split("/")

    # Class 1: live-marked keys — blocked EVERYWHERE except .env*/.gitignore.
    if not (base.startswith(".env") or base == ".gitignore"):
        m = re.search(r"\b[A-Za-z]{2,8}_(?:live|prod|secret)_[A-Za-z0-9]{12,}",
                      new_text)
        if m:
            return "a live-marked key (%s…)" % m.group(0)[:12]
        if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", new_text):
            return "a private key block"

    # Class 2: provider-shaped tokens — blocked in SOURCE only.
    if base.startswith(".env") or base.endswith(
            (".md", ".txt", ".lock", ".pem.example")):
        return None
    if any(p in ("examples", "fixtures", "tests", "test", ".sage", "sage",
                 ".claude", ".hermes", "node_modules") for p in parts):
        return None
    for pat, what in SECRET_PATTERNS:
        if re.search(pat, new_text):
            return what
    return None


# ── Gate 2: spec-gate (Rule 3 — pre-spec cycles block source edits) ─────────

def _spec_gate(project_root, sage_dir, abspath, rel, new_text):
    # ── Completion guard (R25): manifest edits, checked before anything else ──
    work_root = os.path.normpath(os.path.join(sage_dir, "work"))
    is_manifest = os.path.basename(abspath) == "manifest.md"
    under_work = False
    if is_manifest:
        try:
            under_work = os.path.commonpath([abspath, work_root]) == work_root
        except ValueError:
            under_work = False

    if is_manifest and under_work:
        slug = os.path.basename(os.path.dirname(abspath))

        # ── Ledger guard (R101): subagent cycles need done+approved tasks ──
        if re.search(r"gate_state\s*:\s*\"?gates-passed\b", new_text or "", re.I):
            ledger = _parse_ledger(new_text or "")
            if ledger is None:
                try:
                    with open(abspath, encoding="utf-8", errors="replace") as fh:
                        ledger = _parse_ledger(fh.read())
                except OSError:
                    ledger = None
            mode = None
            if os.path.isfile(abspath):
                try:
                    with open(abspath, encoding="utf-8", errors="replace") as fh:
                        mode = _manifest_field(fh.read(), "execution_mode")
                except OSError:
                    mode = None
            if mode is None:
                m = re.search(r"^\s*execution_mode\s*:\s*\"?([A-Za-z0-9_-]+)",
                              new_text or "", re.M)
                mode = m.group(1).lower() if m else None
            if mode == "subagent" and ledger is None:
                return (
                    'Sage spec-gate: cannot set gate_state: gates-passed on "%s" —\n'
                    "the cycle is in subagent execution and has NO task ledger.\n\n"
                    "R101: subagent mode's entire claim is that every task was "
                    "implemented by a fresh context and independently reviewed by "
                    "another. The ledger is the only record of that. A cycle with no "
                    "ledger is not a cycle that passed review — it is a cycle with no "
                    "evidence it was reviewed at all.\n\n"
                    "Write the `tasks:` block, or set execution_mode: inline and stop "
                    "claiming the subagent chain ran." % slug)
            if ledger is not None:
                bad = [(t.get("id", "?"), t.get("status") or "?", t.get("review") or "?")
                       for t in ledger
                       if (t.get("status") or "").strip() != "done"
                       or (t.get("review") or "").strip() != "approved"]
                if bad:
                    rows = "\n".join("  task %s — status: %s, review: %s" % r
                                     for r in bad[:8])
                    return (
                        'Sage spec-gate: cannot set gate_state: gates-passed on "%s" —\n'
                        "%d ledger task(s) are not done+approved:\n\n%s\n\n"
                        "R101: in subagent execution, a task is finished when an "
                        "INDEPENDENT reviewer approved it, not when the implementer "
                        "said it was done. gates-passed asserts the quality chain ran. "
                        "Finish or fix the tasks above, or record why they are "
                        "abandoned — but do not claim the chain ran on tasks it "
                        "never saw." % (slug, len(bad), rows))

        # ── Rule 5 + QA disposition (R29): completing a cycle ──
        if re.search(r"(?:gate_state|status)\s*:\s*\"?complete\b",
                     new_text or "", re.I):
            cur_kind, cur_state = _manifest_gate_state(abspath)
            if cur_kind == "ok" and cur_state not in ("gates-passed", "complete"):
                return (
                    'Sage spec-gate: cannot mark cycle "%s" complete — gate_state is\n'
                    '"%s", not gates-passed. Rule 5: run the quality gates and verify\n'
                    "before claiming done. Run the gates, set gate_state: gates-passed,\n"
                    "then complete." % (slug, cur_state))
            qa_state = None
            if os.path.isfile(abspath):
                try:
                    with open(abspath, encoding="utf-8", errors="replace") as fh:
                        qa_state = _manifest_field(fh.read(), "qa")
                except OSError:
                    qa_state = None
            new_qa = re.search(
                r"^\s*qa\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$",
                new_text or "", re.M)
            if new_qa:
                qa_state = new_qa.group(1).lower()
            if cur_kind == "ok" and qa_state is not None \
                    and qa_state not in QA_TERMINAL:
                return (
                    'Sage spec-gate: cannot mark cycle "%s" complete — qa is "%s".\n'
                    "R29: a completion must say what happened to independent QA; it may\n"
                    "not stay silent about it. Set one of:\n"
                    "  qa: passed                 auto-QA ran and passed\n"
                    "  qa: skipped-no-subagent    no sub-agent dispatch on this platform\n"
                    "  qa: skipped-disabled       auto_qa is off in .sage/config.yaml\n"
                    "  qa: skipped-timeout        the sub-agent timed out\n"
                    "  qa: waived                 the user accepted completion without it\n"
                    "Any value but `passed` is logged to .sage/decisions.md "
                    "automatically." % (slug, qa_state))
        return None  # manifest edits that pass the guards are never gated

    # ── Rule 3: source edits while any active cycle is pre-spec ──
    first = rel.split("/")[0]
    if first in (".sage", "sage", ".hermes"):
        return None
    if not _is_source(rel):
        return None

    manifests = sorted(glob.glob(os.path.join(sage_dir, "work", "*", "manifest.md")))
    pre_spec = []
    for mpath in manifests:
        kind, state = _manifest_gate_state(mpath)
        if kind in ("corrupt", "unreadable", "absent"):
            continue
        if state == "complete":
            continue
        if state == "pre-spec":
            pre_spec.append(os.path.basename(os.path.dirname(mpath)))

    if pre_spec:
        slug = pre_spec[0]
        msg = (
            'Sage spec-gate: cycle "%s" is pre-spec. Rule 3: spec.md must exist and\n'
            "be approved before implementation. Write .sage/work/%s/spec.md and get\n"
            "[A] approval, or set tier: tier1 in the manifest if this is genuinely\n"
            "trivial, or set hard_enforcement: false in .sage/config.yaml to disable.\n"
            "(Blocked edit: %s)" % (slug, slug, rel))
        if len(pre_spec) > 1:
            msg += "\nOther pre-spec cycles: " + ", ".join(pre_spec[1:])
        return msg
    return None


# ── Gate 3: tdd-gate (Rule 1 — tests before code) ────────────────────────────

def _tdd_gate(project_root, sage_dir, rel):
    if _is_test(rel):
        return None  # writing the test IS the point

    # A tier1 cycle is exempt: genuinely trivial work opts out of the process.
    for mpath in glob.glob(os.path.join(sage_dir, "work", "*", "manifest.md")):
        try:
            with open(mpath, encoding="utf-8", errors="replace") as fh:
                head = fh.read(2048)
        except OSError:
            continue
        state = _manifest_field(head, "gate_state")
        if state and state.lower() == "complete":
            continue
        tier = _manifest_field(head, "tier")
        if tier and tier.lower() == "tier1":
            return None

    if not _git(project_root, "rev-parse", "--git-dir").strip():
        return None  # not a git repo — nothing to compare against, fail open

    tracked = _git(project_root, "ls-files")
    if not any(_is_test(p) for p in tracked.splitlines() if p.strip()):
        return None  # no test suite at all — nothing to be test-first about yet

    # ALLOW 1: a test is already written but not committed.
    for line in _git(project_root, "status", "--porcelain").splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path and _is_test(path.replace(os.sep, "/")):
            return None

    # ALLOW 2: the previous commit was the RED commit — a test, and only a test.
    head_files = [p.strip() for p in
                  _git(project_root, "show", "--name-only", "--format=", "HEAD")
                  .splitlines() if p.strip()]
    if head_files:
        tests_in_head = [p for p in head_files if _is_test(p.replace(os.sep, "/"))]
        source_in_head = [p for p in head_files
                          if _is_source(p.replace(os.sep, "/"))
                          and not _is_test(p.replace(os.sep, "/"))]
        if tests_in_head and not source_in_head:
            return None

    return (
        "Sage TDD gate: tests before code — no test has been written for this change.\n"
        "Constitution principle 1: every behavior has a test written BEFORE the\n"
        "implementation. Write a test that FAILS without this change, then make it pass.\n"
        '"It is only one number", "it is just config" and "the tests already cover it"\n'
        "are the excuses this rule exists to refuse — measured, they were used in 3 runs\n"
        "out of 3.\n\n"
        "Blocked edit: %s\n\n"
        "To proceed, do ONE of:\n"
        "  - write or update a test (that is the intended path)\n"
        "  - set `tier: tier1` on the active manifest, if this is genuinely trivial\n"
        "  - set `tdd_enforcement: false` in .sage/config.yaml to disable this gate"
        % rel)


# ── Gate 4: bookkeeping-gate (close-out economy, one-command writer) ─────────

def _bookkeeping_gate(project_root, sage_dir, abspath, rel, new_text):
    # Only a cycle's manifest.md / decisions.md, and only if it already exists.
    m = re.match(r"^\.sage/work/([^/]+)/(manifest\.md|decisions\.md)$", rel)
    if not m:
        return None
    if not os.path.isfile(abspath):
        return None  # creation is authoring, not bookkeeping

    # Only while that cycle is ACTIVE.
    manifest_path = os.path.join(project_root, ".sage", "work", m.group(1),
                                 "manifest.md")
    status = None
    try:
        with open(manifest_path, encoding="utf-8", errors="replace") as fh:
            status = _manifest_field(fh.read(), "status")
    except OSError:
        pass
    if status in ("complete", "completed", "abandoned"):
        return None

    # gate_state transitions are APPROVAL flow — the spec-gate's completion
    # guard already polices them. Yield to it.
    if "gate_state" in (new_text or ""):
        return None

    return (
        "sage-bookkeeping-gate: don't hand-edit %s during an active cycle — apply "
        "the whole update in ONE pass instead (this is the close-out economy's "
        "bookkeeping rule, made mechanical):\n\n"
        "  python3 sage/runtime/tools/manifest.py close-out "
        ".sage/work/%s/manifest.md \\\n"
        "    --summary \"...\" --next-step \"...\" --decision \"...\" "
        "--complete-task N \\\n"
        "    [--phase X] [--status blocked --blocked-on \"the question, the "
        "options, whose call\"]\n\n"
        "One command writes the manifest prose, prepends decisions (Rule 7), and "
        "checks plan boxes. gate_state and updated: are machine-owned — never set "
        "them by hand. Compose everything first, then run it once."
        % (rel, m.group(1)))


# ── Gate 5: config-gate (the meta-gate — no self-disarmament) ────────────────

_CONFIG_BLOCK_MSG = (
    "sage-config-gate: this would turn OFF enforcement that is currently on — "
    "an agent under enforcement cannot disable its own gates.\n\n"
    "If enforcement genuinely needs to change, a human edits .sage/config.yaml "
    "directly (outside the agent). If a gate is blocking legitimate work, fix "
    "the work it is pointing at — that is what it is for.")

_CFG_MASTER = "hard_enforcement"
_CFG_OPT_OUT = ("secrets_gate", "verify_gate")
_CFG_OPT_IN = ("tdd_enforcement",)


def _cfg_read_flag(text, key):
    m = re.search(r"(?mi)^\s*%s\s*:\s*(true|false)\b" % re.escape(key), text or "")
    return None if not m else (m.group(1).lower() == "true")


def _cfg_enabled(text, key):
    v = _cfg_read_flag(text, key)
    if key == _CFG_MASTER or key in _CFG_OPT_IN:
        return v is True
    return v is not False


def _cfg_review_mode(text, absent="v2"):
    blocks = re.findall(r"(?m)^review_loop:[ \t]*$((?:\n[ \t]+.*)*)", text or "")
    for block in reversed(blocks):
        mm = re.search(r"(?mi)^[ \t]+mode[ \t]*:[ \t]*(\S+)", block)
        if mm:
            return mm.group(1).lower()
    return absent


def _cfg_witness_capping(text):
    return _cfg_read_flag(text, "witness_capping") is not False


def _cfg_contradictory_flag(text, key):
    """The same key with BOTH values in one file is a reader-divergence
    bomb: first-wins readers stay armed while last-wins readers disarm.
    Ported from the canonical sage-config-gate.sh (round-2 review). A config
    in that state may not be CREATED through this gate."""
    vals = {v.lower() for v in re.findall(
        r"(?mi)^\s*%s\s*:\s*(true|false)\b" % re.escape(key), text or "")}
    return len(vals) > 1


def _cfg_weaker(before, after):
    for key in (_CFG_MASTER,) + _CFG_OPT_OUT + _CFG_OPT_IN:
        if _cfg_enabled(before, key) and not _cfg_enabled(after, key):
            return True
    # Introducing a contradictory duplicate of an enforcement flag is
    # weakening even though first-wins readers don't move: any last-wins
    # reader reads the appended value. Same rule as the canonical gate.
    for key in (_CFG_MASTER,) + _CFG_OPT_OUT + _CFG_OPT_IN:
        if (not _cfg_contradictory_flag(before, key)
                and _cfg_contradictory_flag(after, key)):
            return True
    if _cfg_review_mode(before) == "v2":
        if _cfg_review_mode(after) != "v2":
            return True
        if _cfg_witness_capping(before) and not _cfg_witness_capping(after):
            return True
    return False


def _config_gate(project_root, sage_dir, tool_name, args, path, new_text):
    config_path = os.path.normpath(os.path.join(sage_dir, "config.yaml"))
    if not os.path.isfile(config_path):
        return None
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            current = fh.read()
    except OSError:
        return None

    # Only active while enforcement is currently ON.
    if not _cfg_enabled(current, _CFG_MASTER):
        return None

    # ── write_file / patch: reconstruct the resulting file and compare ──
    if tool_name in _EDIT_TOOLS:
        abspath = path if os.path.isabs(path) else os.path.normpath(
            os.path.join(os.path.abspath(os.getcwd()), path))
        if os.path.normpath(abspath) != config_path:
            return None
        after = None
        if tool_name == "write_file":
            after = args.get("content") if isinstance(args.get("content"), str) else None
        else:  # patch — apply old→new replacements onto current
            after = current
            edits = []
            if isinstance(args.get("new_string"), str):
                edits.append((args.get("old_string", ""), args["new_string"]))
            for e in args.get("edits") or []:
                if isinstance(e, dict):
                    edits.append((e.get("old_string", ""), e.get("new_string", "")))
            body = args.get("patch")
            if isinstance(body, str):
                # V4A patch mode: approximate by pairing -/+ lines in order.
                # CAVEAT (maintainer review 2026-08-05): a reordered patch can
                # mispair and slip a weakening past this reconstruction. The
                # main write_file path and the contradictory-flag check are the
                # real defense; this stays fail-open by design.
                removals, additions = [], []
                for ln in body.splitlines():
                    if ln.startswith("-") and not ln.startswith("---"):
                        removals.append(ln[1:])
                    elif ln.startswith("+") and not ln.startswith("+++"):
                        additions.append(ln[1:])
                for old, new in zip(removals, additions):
                    edits.append((old, new))
            for old, new in edits:
                if old:
                    after = after.replace(old, new, 1)
        if after is not None and _cfg_weaker(current, after):
            return _CONFIG_BLOCK_MSG
        return None

    # ── terminal: catch the obvious write-the-switch-off evasions ──
    if tool_name == "terminal":
        cmd = str(args.get("command") or "")
        names_config = re.search(r"\.sage/config\.ya?ml", cmd) is not None
        writes = re.search(r">\s*[^|]*\.sage/config\.ya?ml|"
                           r"\bsed\b[^\n]*-i|\btee\b[^\n]*\.sage/config\.ya?ml", cmd)
        turns_off = re.search(
            r"(?:%s|secrets_gate|verify_gate)\s*:?\s*false" % re.escape(_CFG_MASTER),
            cmd, re.I)
        review_off = _cfg_review_mode(current, absent="v1") == "v2" and re.search(
            r"witness_capping\s*:?\s*false|mode\s*:?\s*v1", cmd, re.I)
        if names_config and writes and (turns_off or review_off):
            return _CONFIG_BLOCK_MSG
    return None


# ── Gate 6: verify-gate + verify-tracker (Rule 5, commit-time evidence) ──────

_CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
             ".java", ".rb", ".dart", ".c", ".cc", ".cpp", ".h", ".swift", ".kt")

_TEST_CMD_RE = re.compile(
    r"\b(pytest|py\.test|unittest|jest|vitest|mocha|ava|npm\s+(run\s+)?test|"
    r"yarn\s+(run\s+)?test|pnpm\s+(run\s+)?test|cargo\s+test|go\s+test|ctest|"
    r"mvn\s+(test|verify)|gradle(w)?\s+test|mix\s+test|rspec|phpunit|"
    r"dotnet\s+test)\b", re.I)


def _verify_state_path(sage_dir):
    return os.path.join(sage_dir, "tmp", "verify-state")


def _verify_read_state(sage_dir):
    out = {}
    try:
        with open(_verify_state_path(sage_dir), encoding="utf-8",
                  errors="replace") as fh:
            for line in fh:
                k, _, v = line.strip().partition("=")
                if k and v.isdigit():
                    out[k] = int(v)
    except OSError:
        pass
    return out


def _verify_write_state(sage_dir, key):
    import time as _t
    state_path = _verify_state_path(sage_dir)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    state = _verify_read_state(sage_dir)
    state[key] = int(_t.time())
    lines = "".join("%s=%d\n" % (k, v) for k, v in sorted(state.items()))
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(lines)
    os.replace(tmp, state_path)


def _verify_gate(project_root, sage_dir, args):
    cmd = str(args.get("command") or "")
    if "git" not in cmd or not re.search(r"\bgit\b[^|\n;]*\bcommit\b", cmd):
        return None
    # The command ITSELF running tests is the verify-then-commit discipline.
    if _TEST_CMD_RE.search(cmd):
        return None
    state = _verify_read_state(sage_dir)
    if not state:
        return None  # no tracker evidence — older install or docs session
    last_edit = state.get("last_source_edit", 0)
    last_test = state.get("last_test_run", 0)
    # Staged diff touching no code file → docs-only commit.
    staged = _git(project_root, "diff", "--cached", "--name-only")
    code_staged = [p for p in staged.splitlines()
                   if os.path.splitext(p.strip())[1].lower() in _CODE_EXT]
    if staged and not code_staged:
        return None
    if last_edit and last_test >= last_edit:
        return None  # tests ran AFTER the last source edit — the point
    return (
        "sage-verify-gate: source changed after the last test run — the "
        "verify-before-claiming rule, made mechanical.\n\n"
        "The recorded evidence (.sage/tmp/verify-state) says: last source edit "
        "is NEWER than the last test run. Run the tests first, then commit — or "
        "chain them: `pytest && git commit` is the discipline, not a violation.\n"
        "If the project has no suite, add one test for the thing you changed; if "
        "this gate misfires, a human sets verify_gate: false in .sage/config.yaml.")


# ── manifest-sync delegation (R120 — the manifest advances, never forges) ────

def _resolve_runtime_tool(project_root, *parts):
    candidates = [
        os.path.join(project_root, "sage", "runtime", *parts),
        os.path.join(os.environ.get("SAGE_HOME", ""), "framework", "runtime", *parts),
        os.path.join(os.path.expanduser("~"), ".sage", "framework", "runtime", *parts),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _manifest_sync(project_root, sage_dir, wrote_path):
    tool = _resolve_runtime_tool(project_root, "tools", "manifest.py")
    if not tool:
        return
    import glob as _g
    for manifest in _g.glob(os.path.join(sage_dir, "work", "*", "manifest.md")):
        try:
            subprocess.run(
                ["python3", tool, "advance", manifest, "--wrote", wrote_path],
                capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass


# ── Hermes hook entry points ─────────────────────────────────────────────────

def _on_pre_tool_call(tool_name=None, args=None, **_kwargs):
    try:
        path, new_text = _target(tool_name, args)
        cwd = os.path.abspath(os.getcwd())

        # Terminal calls carry no path — config-gate's evasion half and the
        # verify-gate still apply. Resolve the project from cwd for those.
        if tool_name == "terminal":
            if not isinstance(args, dict):
                return _allow()
            project_root = _find_project_root(os.path.join(cwd, ".probe"))
            if project_root is None:
                return _allow()
            sage_dir, flags = _config(project_root)
            if sage_dir is None:
                return _allow()
            msg = _config_gate(project_root, sage_dir, tool_name, args, "", "")
            if msg:
                return _block("config-gate", msg, project_root, ".sage/config.yaml")
            if flags.get("hard_enforcement") is True \
                    and flags.get("verify_gate", True) is not False:
                msg = _verify_gate(project_root, sage_dir, args)
                if msg:
                    return _block("verify-gate", msg, project_root, "git commit")
            return _allow()

        if not path:
            return _allow()
        abspath = path if os.path.isabs(path) else os.path.normpath(
            os.path.join(cwd, path))
        project_root = _find_project_root(abspath)
        if project_root is None:
            return _allow()  # not a Sage project
        sage_dir, flags = _config(project_root)
        if sage_dir is None:
            return _allow()

        # config-gate (the meta-gate) — guards the switches themselves; fires
        # only while hard_enforcement is currently true, and has no opt-out.
        msg = _config_gate(project_root, sage_dir, tool_name, args, path,
                           new_text or "")
        if msg:
            return _block("config-gate", msg, project_root,
                          os.path.join(".sage", "config.yaml"))

        if flags.get("hard_enforcement") is not True:
            return _allow()  # enforcement is opt-in, never a surprise

        _abspath, rel = _resolve(project_root, abspath)
        if rel is None:
            return _allow()  # outside the project

        # secrets-gate: master switch on + not individually disabled.
        if new_text and flags.get("secrets_gate", True) is not False:
            what = _secrets_gate(project_root, rel, new_text)
            if what:
                return _block("secrets-gate", (
                    "sage-secrets-gate: this edit hardcodes %s into %s — credentials "
                    "never go into files (constitution: secrets).\n\n"
                    "Instead: read it from the environment (os.environ / process.env) "
                    "or a gitignored config (.env), and reference the variable here. "
                    "If a placeholder is genuinely needed, use an obvious fake like "
                    "\"YOUR_API_KEY\"." % (what, rel)), project_root, rel)

        # bookkeeping-gate: hand-edits to an active cycle's manifest/decisions
        # redirect to the one-command close-out writer.
        if flags.get("bookkeeping_gate", True) is not False:
            msg = _bookkeeping_gate(project_root, sage_dir, abspath, rel,
                                    new_text or "")
            if msg:
                return _block("bookkeeping-gate", msg, project_root, rel)

        # spec-gate (Rule 3 + completion guards)
        msg = _spec_gate(project_root, sage_dir, abspath, rel, new_text or "")
        if msg:
            return _block("spec-gate", msg, project_root, rel)

        # tdd-gate (Rule 1) — separate opt-in flag, same as claude-code.
        if flags.get("tdd_enforcement") is True and _is_source(rel) \
                and not _is_test(rel):
            msg = _tdd_gate(project_root, sage_dir, rel)
            if msg:
                return _block("tdd-gate", msg, project_root, rel)

        return _allow()
    except Exception:
        return _allow()  # hooks fail OPEN — never brick the editor


def _on_post_tool_call(tool_name=None, args=None, **_kwargs):
    """Observers: verify-tracker (evidence), manifest-sync (R120 advance),
    R29 degradation audit. None of these may raise or block — ever."""
    try:
        cwd = os.path.abspath(os.getcwd())

        # ── verify-tracker: record evidence for the commit-time gate ──
        if tool_name == "terminal" and isinstance(args, dict):
            cmd = str(args.get("command") or "")
            root = _find_project_root(os.path.join(cwd, ".probe"))
            if root is not None and _TEST_CMD_RE.search(cmd):
                sage_dir, _ = _config(root)
                if sage_dir is not None:
                    _verify_write_state(sage_dir, "last_test_run")
        else:
            path, _ = _target(tool_name, args)
            if path:
                abspath = path if os.path.isabs(path) else os.path.normpath(
                    os.path.join(cwd, path))
                root = _find_project_root(abspath)
                if root is not None:
                    if os.path.splitext(abspath)[1].lower() in _CODE_EXT:
                        sage_dir, _ = _config(root)
                        if sage_dir is not None:
                            _verify_write_state(sage_dir, "last_source_edit")
                            # ── manifest-sync: the cycle advances because
                            # work plainly happened (never to approval states).
                            _manifest_sync(root, sage_dir, abspath)
    except Exception:
        pass

    # ── R29 degradation audit: a declared skip cannot go unlogged ──
    try:
        path, _ = _target(tool_name, args)
        if not path:
            return None
        cwd = os.path.abspath(os.getcwd())
        abspath = path if os.path.isabs(path) else os.path.normpath(
            os.path.join(cwd, path))
        project_root = _find_project_root(abspath)
        if project_root is None:
            return None
        sage_dir, _flags = _config(project_root)
        if sage_dir is None:
            return None
        if os.path.basename(abspath) != "manifest.md":
            return None
        work_root = os.path.normpath(os.path.join(sage_dir, "work"))
        try:
            if os.path.commonpath([abspath, work_root]) != work_root:
                return None
        except ValueError:
            return None
        if not os.path.isfile(abspath):
            return None

        with open(abspath, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        qa = _manifest_field(text, "qa")
        if qa not in DEGRADED:
            return None

        slug = os.path.basename(os.path.dirname(abspath))
        decisions = os.path.join(sage_dir, "decisions.md")
        marker = "%s %s qa:%s" % (DEGLOG_MARK, slug, qa)
        existing = ""
        if os.path.isfile(decisions):
            try:
                with open(decisions, encoding="utf-8", errors="replace") as fh:
                    existing = fh.read()
            except OSError:
                existing = ""
        if marker in existing:
            return None  # already logged — idempotent

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        line = ("\n- **%s** — cycle `%s`: %s %s\n"
                % (ts, slug, DEGRADED[qa], marker))
        with open(decisions, "a", encoding="utf-8") as fh:
            fh.write(line)
        return None
    except Exception:
        return None


# ── Context injection (pre_llm_call) ────────────────────────────────────────
# CLI sessions don't have the gateway's session:start hook, so we inject
# context here for every turn. Returns {"context": str} to prepend to the
# user message, or None for no injection.

def _on_pre_llm_call(session_id=None, user_message=None, is_first_turn=False,
                     platform=None, **_kwargs):
    """Inject Sage context into every turn for CLI sessions.

    Gateway sessions get context via the session:start hook writing
    session-pickup.md. CLI sessions need this hook to inject directly.
    """
    try:
        # Only inject for CLI — gateway already has session:start hook
        if platform and platform != "cli":
            return None

        cwd = os.path.abspath(os.getcwd())
        project_root = _find_project_root(os.path.join(cwd, ".probe"))
        if project_root is None:
            return None  # not a Sage project

        sage_dir = os.path.join(project_root, ".sage")
        if not os.path.isdir(sage_dir):
            return None

        # Read the actual enforcement state from the project's config — the
        # injected text must never claim more than the gates will actually do.
        _, _flags = _config(project_root)
        _enforced = _flags.get("hard_enforcement") is True

        parts = []

        # ── Always-on rules (eager core) ──
        parts.append("""## Sage — Always-On Rules

You are running under Sage. Mechanical gates enforce quality:
- **spec-gate** blocks source edits before a spec exists
- **tdd-gate** blocks source edits before tests exist
- **secrets-gate** blocks hardcoded credentials
- **config-gate** blocks edits that would disable enforcement
- **verify-gate** blocks commits without fresh test evidence

All gates are opt-in via .sage/config.yaml. Enforcement is currently: {status}.

## Available Commands
Use skill_view("sage:<name>") to load workflow skills:
- sage:sage — route via keywords → classify → confirm
- sage:build — spec → plan → build-loop → quality gates
- sage:fix — diagnose → scope → fix → verify
- sage:architect — elicit → design → milestone plan
- sage:review — independent evaluation
- sage:learn — codebase scan → memory
- sage:continue — resume an active cycle""".format(
            status="ENABLED (hard_enforcement: true)" if _enforced else
                   "DISABLED (set hard_enforcement: true in .sage/config.yaml to opt in)"))

        # ── Session pickup (same as gateway hook) ──
        pickup = os.path.join(sage_dir, "gates", "session-pickup.md")
        if os.path.isfile(pickup):
            try:
                with open(pickup, encoding="utf-8", errors="replace") as fh:
                    pickup_text = fh.read().strip()
                if pickup_text:
                    parts.append("## Active Session Context\n" + pickup_text)
            except OSError:
                pass

        if not parts:
            return None

        return {"context": "\n\n".join(parts)}
    except Exception:
        return None  # fail silent — never break the agent


def register(ctx) -> None:
    """Wire schemas, hooks, commands, and skills into Hermes."""

    import logging
    logger = logging.getLogger(__name__)

    # ── Register hooks ──
    # pre_tool_call: THE critical veto hook — blocks edits before they happen
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)

    # post_tool_call: audit trail — logs decisions, tracks degradation
    ctx.register_hook("post_tool_call", _on_post_tool_call)

    # pre_llm_call: context injection for CLI sessions
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)

    # Slash commands removed 2026-08-05: bare /fix, /build, /review etc. echoed
    # instruction strings instead of running the workflow, and collided with the
    # native skill slash commands (/sage-fix, /sage-build, ...) that Hermes
    # auto-generates from the skills registered below. Those native skill
    # commands ARE the delivery path on Hermes - they load the full SKILL.md
    # into the turn. Use /sage to route, /sage-fix etc. to run.

    # ── Register bundled skills ──
    # The plugin IS the whole repo, so skills/ also holds the framework's
    # own domain skills (api, web, nextjs, react, ...). Only the 21
    # hermes-platform skills belong here — same set declared in
    # build_plugin.py SKILLS_NOT_IN_PLUGIN and coverage.yaml. Registering
    # the rest would drag the claude-code build's skills (and the
    # sage-memory MCP dependency) into Hermes.
    _HERMES_SKILLS = frozenset({
        "sage", "sage-analyst", "sage-architect", "sage-autoresearch",
        "sage-build", "sage-checkpoints", "sage-classifier",
        "sage-constitution", "sage-continue", "sage-debugger",
        "sage-decisions", "sage-developer", "sage-fix", "sage-gates",
        "sage-learn", "sage-reflect", "sage-review", "sage-reviewer",
        "sage-routing", "sage-tiers", "sage-using-memory",
    })
    try:
        from pathlib import Path
        _plugin_dir = Path(__file__).parent
        _skills_dir = _plugin_dir / "skills"
        if _skills_dir.is_dir():
            for child in sorted(_skills_dir.iterdir()):
                skill_md = child / "SKILL.md"
                if (child.is_dir() and skill_md.exists()
                        and child.name in _HERMES_SKILLS):
                    try:
                        # Hermes auto-namespaces: "sage:" prefix comes from plugin name
                        ctx.register_skill(child.name, skill_md)
                    except Exception as e:
                        logger.warning("Failed to register skill '%s': %s", child.name, e)
    except ImportError:
        pass  # pathlib not available, skip skill registration
