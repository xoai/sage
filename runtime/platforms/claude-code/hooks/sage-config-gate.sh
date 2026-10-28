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
# its own review floor — or raise/zero cycle_round_budget or gate_retry_cap —
# an agent must not lift its own stop; with the scope
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
OPT_OUT = ("secrets_gate", "verify_gate", "branch_gate")
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


# The cycle's stop (review 2026-10-26, L1): the round budget and the gate
# retry cap end a loop that would otherwise run on every "continue". Raising
# either, zeroing or negating it (≤ 0 = no limit), or any edit that makes
# review.py READ a looser value (a re-indent it no longer parses, a later
# review_loop: block without the key, "+99", "9_9") lets the loop run on —
# the human's call, made in their own editor. So the value compared is the
# one review.py's load_config() actually reads, computed the same way.
BUDGET_KNOBS = (("cycle_round_budget", 10), ("gate_retry_cap", 3))
_RL_BLOCK = re.compile(r"^review_loop:\s*$", re.MULTILINE)
_RL_ITEM = re.compile(r"^\s{2}([a-z_]+):\s*([^\s#]+)")


def review_loop_int(text, key, default):
    """review.py load_config(), for one int key: the LAST review_loop: block
    wins; items sit at exactly two spaces until the first dedented line; the
    value is whatever Python's int() makes of it."""
    blocks = list(_RL_BLOCK.finditer(text or ""))
    if not blocks:
        return default
    value = default
    for line in text[blocks[-1].end():].splitlines():
        if line.strip() and not line.startswith("  "):
            break
        m = _RL_ITEM.match(line)
        if m and m.group(1) == key:
            try:
                value = int(m.group(2))
            except ValueError:
                pass
    return value


def effective_limit(text, key, default):
    v = review_loop_int(text, key, default)
    return float("inf") if v <= 0 else v


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
        for key, default in BUDGET_KNOBS:
            if effective_limit(after, key, default) > effective_limit(before, key, default):
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

# Worktree sessions: the session's project (base_root) and the checkout the
# call acts in (project_root) can differ. The switch is protected while EITHER
# has enforcement on — judged from the acting checkout alone, a worktree with a
# lax config could rewrite the main checkout's (review 2026-10-27).
base_root = project_root
project_root = sage_worktree_root(project_root, sage_probe(data))


def read_config(root):
    try:
        with open(os.path.join(root, ".sage", "config.yaml"),
                  encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def git_lines(d, *args):
    import subprocess as _sp
    try:
        q = _sp.run(["git", "-C", d] + list(args), capture_output=True, text=True, timeout=5)
    except (OSError, _sp.SubprocessError):
        return []
    return q.stdout.split("\n")[:-1] if q.returncode == 0 else []


def checkout_configs():
    """The Sage config path of every registered checkout of this repository —
    at the project subdirectory when the project lives in one."""
    ref = git_lines(base_root, "rev-parse", "--show-prefix")
    prefix = ref[0] if ref else ""
    import subprocess as _sp
    try:
        q = _sp.run(["git", "-C", base_root, "worktree", "list", "--porcelain", "-z"],
                    capture_output=True, text=True, timeout=5)
    except (OSError, _sp.SubprocessError):
        return []
    return [os.path.join(os.path.realpath(f[9:]), prefix, ".sage", "config.yaml")
            for f in (q.stdout.split("\0") if q.returncode == 0 else [])
            if f.startswith("worktree ")]


def checkout_config(path):
    """The path is the Sage config of one of this repository's checkouts —
    the session's, the acting one, or another worktree (one without Sage yet
    included: writing a config there is how a worktree would escape). A
    fixture's .sage/ elsewhere in the tree is not one."""
    if not path:
        return None
    p = os.path.abspath(path if os.path.isabs(path)
                        else os.path.join((data.get("cwd") or "").strip() or project_root, path))
    if not re.search(r"(^|/)\.sage/config\.ya?ml$", p.replace(os.sep, "/")):
        return None
    real = os.path.join(os.path.realpath(os.path.dirname(os.path.dirname(p))), ".sage", "config.yaml")
    known = checkout_configs() + [os.path.join(os.path.realpath(r), ".sage", "config.yaml")
                                  for r in (base_root, project_root)]
    return p if real in known or real[:-5] + ".yml" in [k[:-5] + ".yml" for k in known] else None


configs = [c for c in (read_config(project_root), read_config(base_root)) if c is not None]
# A call may reach another checkout's config — the shell's cwd is not
# necessarily the checkout it writes (review 2026-10-27). Its enforcement
# counts too: for an Edit/Write, the target's own config; for a shell, every
# checkout config the command names. A stale worktree's switch never reaches
# a call that does not touch it.
shell_cwd = (data.get("cwd") or "").strip() or project_root
named = []
if tool == "Bash" and re.search(r"\.sage/config\.ya?ml", str(tool_input.get("command") or "")):
    cmd_text = str(tool_input.get("command") or "")
    named = [c for c in checkout_configs()
             if c in cmd_text or os.path.relpath(c, os.path.realpath(shell_cwd)) in cmd_text]
elif tool in ("Edit", "Write", "MultiEdit"):
    fp = str(tool_input.get("file_path") or "")
    if re.search(r"(^|/)\.sage/config\.ya?ml$", fp):
        named = [os.path.abspath(os.path.join(shell_cwd, fp))]
for path in named:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            configs.append(fh.read())
    except OSError:
        pass
if not configs:
    emit("ALLOW")
current = configs[0]
reference = next((c for c in configs if enabled(c, MASTER)), None)

# Only active while enforcement is currently ON — nothing to protect otherwise,
# and this is what makes turning enforcement ON (off→on) always allowed.
if reference is None:
    emit("ALLOW")


# ── Edit/Write/MultiEdit: reconstruct the resulting file and compare ──
if tool in ("Edit", "Write", "MultiEdit"):
    target = checkout_config(str(tool_input.get("file_path") or ""))
    if target is None:
        emit("ALLOW")
    # A checkout without a Sage config gets one from .worktreeinclude or
    # `sage worktree` — never from the agent: a fresh config is how a
    # worktree would shed the main checkout's cycles (review 2026-10-27).
    if not os.path.isfile(target):
        emit("BLOCK", (
            "sage-config-gate: %s does not exist, and enforcement is on. A "
            "worktree's Sage config comes from .worktreeinclude (Claude Code "
            "copies it when it makes the worktree) or from `sage worktree` — not "
            "from the agent. Tell the user; they run `sage update` in the main "
            "checkout, then start a new worktree session." % target))
    # Judged against the file it replaces.
    try:
        with open(target, encoding="utf-8", errors="replace") as fh:
            current = fh.read()
    except OSError:
        pass
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


def sed_in_place(cmd):
    """True when some `sed` in cmd edits a file in place (-i, -Ei, --in-place).

    One command segment at a time: matched across the whole line, `sed -n 1,9p f;
    grep -i x .sage/config.yaml` read grep's -i as sed's and blocked a read (E8,
    2026-10-27). Segments split only OUTSIDE quotes — a quoted `s/a/b/;s/c/d/`
    before `-i` is still one sed — and quoted text is kept, so
    `sh -c 'sed -i.bak … config.yaml'` still reads as the edit it is."""
    return any(re.search(r"\bsed\b.*\s(?:-[A-Za-z]*i|--in-place)", seg)
               for seg in split_unquoted(cmd))


def split_unquoted(cmd):
    """cmd cut at ; & | and newlines that sit outside quotes."""
    segs, cur, quote, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            if c == "\\" and quote == '"' and i + 1 < len(cmd):
                cur.append(cmd[i:i + 2])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c in ";&|\n":
            segs.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    segs.append("".join(cur))
    return segs


# ── Bash: catch the obvious write-the-switch-off evasions ──
# Conservative on purpose — a redirect/sed/tee that names config.yaml AND sets an
# enforcement key false. A read (grep/cat) has no such write and is not matched.
if tool == "Bash":
    cmd = str(tool_input.get("command") or "")
    # The gates' own records (review 2026-10-26): deleting or rewriting a
    # cycle's baseline re-opens recording over the cycle's own failures, and
    # rewriting its ledger refunds the budget. The tools that own them
    # (sage-verify.sh, review.py) write them; a shell does not. Reads pass.
    # By name, and by any delete reaching into .sage/work (a glob, a whole
    # cycle dir, `rm -r .sage`) — the records are inside, whatever the path.
    names_record = (re.search(r"(?:verify-baseline|review-ledger)\.json", cmd)
                    or (re.search(r"\.sage/work\b|\.sage/?(?:[\s;&|]|$)", cmd)
                        and re.search(r"\b(?:rm|mv|unlink|shred|truncate)\b", cmd)))
    destroys = re.search(
        r"\b(?:rm|mv|cp|tee|truncate|ln|dd|unlink|shred)\b|"
        r"\b(?:python3?|node|perl|ruby)\s+-[ce]\b|"
        r"\b(?:python[0-9.]*|node|perl|ruby)(?:\s+-(?=\s|$)|\b[^\n|;&]*<<(?!<))|"
        r">\s*\S*(?:verify-baseline|review-ledger)\.json", cmd) or sed_in_place(cmd)
    if names_record and destroys:
        emit("BLOCK", (
            "sage-config-gate: a cycle's verify-baseline.json and review-ledger.json "
            "are the gates' own records — only sage-verify.sh and review.py write "
            "them. Deleting or rewriting one would excuse the cycle's own failures "
            "or refund its budget. If one is wrong, tell the user; they fix it "
            "outside the agent."))
    # A worktree the agent makes for itself starts without the cycle the
    # session is in, and the gates judge a worktree by its own cycles — so
    # while a cycle is in progress, making one is the user's call. Desktop
    # makes its session worktrees itself, and lanes use `sage worktree`;
    # neither runs through here (review 2026-10-27).
    if re.search(r"\bgit\b[^;&|\n]*\bworktree\s+add\b", cmd):
        active = []
        for root in {os.path.realpath(base_root), os.path.realpath(project_root)}:
            work = os.path.join(root, ".sage", "work")
            for slug in (os.listdir(work) if os.path.isdir(work) else []):
                try:
                    with open(os.path.join(work, slug, "manifest.md"), encoding="utf-8",
                              errors="replace") as fh:
                        head = fh.read(4000)
                except OSError:
                    continue
                if re.search(r"(?m)^status:\s*\"?in-progress", head):
                    active.append(slug)
        if active:
            emit("BLOCK", (
                "sage-config-gate: `git worktree add` while cycle %s is in progress. "
                "A worktree is judged by its own cycles, so a new one would start "
                "outside this one's spec and plan. Ask the user: they can start a "
                "Desktop worktree session, or run `sage worktree <slug>`; finish or "
                "pause the cycle first otherwise." % ", ".join(sorted(active))))
    names_config = re.search(r"\.sage/config\.ya?ml", cmd) is not None
    # While enforcement is on, the shell does not write the config at all.
    # Matching what a write SAYS was a losing game — `sed s/budget: 10/
    # budget: 0/`, a python one-liner, `git checkout <rev> -- …` each loosened
    # a floor without naming its key (final review, 2026-10-26). The Edit and
    # Write paths stay open and are judged exactly, by weaker() above; reads
    # (cat, grep) never match.
    writes = re.search(
        r">\s*[^|&;]*\.sage/config\.ya?ml|\btee\b|"
        r"\b(?:cp|mv|install|ln|truncate|dd|rm|unlink)\b|"
        r"\b(?:python3?|node|perl|ruby)\s+-[ce]\b|"
        r"\b(?:python[0-9.]*|node|perl|ruby)(?:\s+-(?=\s|$)|\b[^\n|;&]*<<(?!<))|"
        r"\bgit\s+(?:checkout|restore|stash|reset|apply)\b", cmd) or sed_in_place(cmd)
    if names_config and writes:
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
  DENY)
    SAGE_DENY_REASON="$MESSAGE" python3 -c 'import json, os; print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": os.environ["SAGE_DENY_REASON"]}}))'
    exit 0
    ;;
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
