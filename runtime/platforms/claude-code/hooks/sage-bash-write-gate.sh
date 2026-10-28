#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-bash-write-gate.sh — PreToolUse hook on Bash (Claude Code; opencode's
# bash gates run it too)
#
# A shell command that WRITES a source file is an edit, and is judged as one.
# The edit gates (spec, TDD, scope) match Edit/Write/MultiEdit only, so
# `cat > src/x.py <<EOF`, `sed -i … src/x.py`, `tee`, `cp`/`mv` onto a source
# path, and plain `>`/`>>` redirects walked past every one of them. The
# review that found it watched Claude write source through Bash in 3 of 27
# runs, once inside /build (review 2026-10-26, X1).
#
# How: find the source files the command would write, and for each one run
# the sibling edit gates (spec, TDD, scope, branch) on the Write it amounts
# to. Any block is this command's block, with that gate's reason. No second
# copy of any rule lives here — this hook only translates a shell write into
# the edit it is.
#
# How it reads: the command is tokenized as the shell would (quoted text stays
# text; heredoc BODIES are dropped as data; a trailing `\` continues a line),
# relative paths resolve against the shell's working directory (Claude Code
# keeps it between calls; a `cd` moves it, `cd -` returns only within the
# command), and `~` expands. Writes it sees: redirects (`>`, `>>`, `>|`,
# `&>`, `n>`, `>& file`), `tee`, `touch`, `truncate`, `sed -i` / `perl -i` /
# `gawk -i inplace`, `cp`/`mv`/`install`/`ln`/`rsync` destinations (incl.
# `-t`/`--target-directory`), `dd of=`, `sort -o`, `curl -o`, `wget -O`, and
# `git checkout|restore <path>` (not `restore --staged` alone) — also behind
# `sudo`/`env`/`nice`/`timeout`/`time`/`nohup`/`stdbuf`.
#
# Not seen, so not gated — stated, not hidden: writes from inside an
# interpreter (`python -c "open(…, 'w')"`, `node -e`), a script file the
# command runs, `xargs` / `find -exec` argument lists, `$VAR` paths, patch
# and archive tools (`git apply`, `git stash pop`, `patch`, `tar`, `unzip`),
# and `ed`/`ex`. Those writes still meet the commit gates.
#
# A test-only commit's TDD unlock (one source file, X2) is spent here by the
# first source file an allowed command writes — the tracker only sees Edits.
# Under the plugin the scope gate is not shipped; the project's own copy in
# .claude/hooks/ (registered by `sage init`) is used instead.
#
# Contract: exit 0 allow · a block is exit 2 (stderr) — or Claude Code's
# structured deny when the input names hook_event_name (C6). Fails open on any
# internal error, like every hook.
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-bash-write-gate-XXXXXX" 2>/dev/null) || exit 0
trap 'rm -f "$PY_GATE"' EXIT

cat > "$PY_GATE" <<'PYEOF'
import json
import os
import re
import shlex
import subprocess
import sys

hook_dir = sys.argv[1]

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(data, dict) or data.get("tool_name") != "Bash":
    sys.exit(0)
command = str((data.get("tool_input") or {}).get("command") or "")
if not command.strip():
    sys.exit(0)

project_root = os.environ.get("CLAUDE_PROJECT_DIR") or ""
if not project_root:
    # No project dir named: the project is the nearest ancestor of the
    # shell's cwd that holds .sage/ (the shell may sit in a subdirectory).
    probe = os.path.abspath((data.get("cwd") or "").strip() or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(probe, ".sage")):
            project_root = probe
            break
        parent = os.path.dirname(probe)
        if parent == probe:
            sys.exit(0)
        probe = parent
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

# Each written path is judged in the checkout it lands in (a command run from
# a worktree may write into the main checkout, or the reverse): base_root is
# the session's project, and every target resolves its own root from it.
base_root = project_root
project_root = sage_worktree_root(project_root, sage_probe(data))
if not os.path.isdir(os.path.join(project_root, ".sage")):
    sys.exit(0)
# Claude Code keeps the shell's working directory between calls: a relative
# path resolves against where the shell IS, not the project root.
shell_cwd = os.path.abspath((data.get("cwd") or "").strip() or project_root)

SOURCE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".rb", ".php", ".swift", ".kt", ".kts", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".cs", ".scala", ".ex", ".exs", ".dart",
}
SKIP_PREFIX = (".sage/", "sage/", ".claude/", "node_modules/", "vendor/", ".git/",
               ".opencode/")
targets = []


def add(path, base):
    """Record `path` if it names a project source file."""
    if not path or path.startswith("&") or path.startswith("/dev/") or "$" in path:
        return
    path = os.path.expanduser(path)
    abspath = os.path.normpath(path if os.path.isabs(path) else os.path.join(base, path))
    if os.path.splitext(abspath)[1].lower() not in SOURCE_EXT:
        return                                 # before resolving: the cheap test first
    root = sage_worktree_root(base_root, abspath)
    rel = os.path.relpath(abspath, root).replace(os.sep, "/")
    if rel.startswith("..") or any(rel.startswith(p) for p in SKIP_PREFIX):
        return
    if os.path.splitext(rel)[1].lower() in SOURCE_EXT and (root, rel) not in targets:
        targets.append((root, rel))


# Heredoc BODIES are data, not commands: `cat > notes.md <<'EOF'` whose body
# mentions "> src/out.py" writes notes.md and nothing else. Drop each body
# (the line after the `<<WORD` line, through the WORD line) before parsing.
# A trailing backslash continues the command on the next line (outside a body).
lines, body_end, pending = [], None, ""
for line in command.split("\n"):
    if body_end is not None:
        if line.strip() == body_end:
            body_end = None
        continue
    line = pending + line
    if re.search(r"(?<!\\)(\\\\)*\\$", line):
        pending = line[:-1]
        continue
    pending = ""
    lines.append(line)
    # `<<<` is a here-string (one word, no body); only `<<WORD` opens a body.
    m = re.search(r"(?<!<)<<-?(?!<)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line)
    if m:
        body_end = m.group(2)
if pending:
    lines.append(pending)
text = " ; ".join(lines)

# Tokenize as the shell would: quotes keep their contents whole (a ">" inside
# a string is text), and operators are tokens of their own.
lex = shlex.shlex(text, posix=True, punctuation_chars=";&|<>()")
lex.whitespace_split = True
try:
    tokens = list(lex)
except ValueError:
    sys.exit(0)                                  # unbalanced quotes: not judged

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", ";;", "|&"}
WRAPPERS = {"sudo", "env", "command", "builtin", "exec", "nohup", "time",
            "nice", "stdbuf", "timeout", "doas"}
segments, cur = [], []
for tok in tokens:
    if tok in SEPARATORS:
        if cur:
            segments.append(cur)
        cur = []
    else:
        cur.append(tok)
if cur:
    segments.append(cur)


def option_value(args, short, long):
    """The value of -o FILE / -oFILE / --output FILE / --output=FILE."""
    out = []
    for i, a in enumerate(args):
        if a in short + long and i + 1 < len(args):
            out.append(args[i + 1])
        for s_ in short:
            if a.startswith(s_) and len(a) > len(s_) and not a.startswith("--"):
                out.append(a[len(s_):])
        for l_ in long:
            if a.startswith(l_ + "="):
                out.append(a.split("=", 1)[1])
    return out


base, prev_base = shell_cwd, None
for seg in segments:
    words, i = [], 0
    while i < len(seg):                          # redirections: op + target
        t = seg[i]
        if re.fullmatch(r"\d*(>>?|>\||&>>?)", t):
            if i + 1 < len(seg):
                add(seg[i + 1], base)
            i += 2
            continue
        if t == ">&":                            # >&2 duplicates; >& file writes
            if i + 1 < len(seg) and not re.fullmatch(r"\d+|-", seg[i + 1]):
                add(seg[i + 1], base)
            i += 2
            continue
        if t in ("<", "<<", "<<<", "<&", "<<-"):
            i += 2                               # fd dup / input / heredoc word
            continue
        words.append(t)
        i += 1
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]                        # VAR=x cmd …
    while words and os.path.basename(words[0]) in WRAPPERS:
        w = os.path.basename(words[0])
        words = words[1:]
        while words and words[0].startswith("-"):
            flag = words.pop(0)                  # wrapper options (nice -n 5 …)
            if flag in ("-n", "-u", "-k", "-s", "-i", "-o", "-e") and words:
                words.pop(0)
        if w == "timeout" and words:
            words = words[1:]                    # the duration
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            words = words[1:]
    if not words:
        continue
    cmd, args = os.path.basename(words[0]), words[1:]
    plain = [a for a in args if not a.startswith("-")]
    if cmd == "cd":
        if args[:1] == ["-"]:
            # Back to the previous directory — known only if this command
            # left it; otherwise stay put rather than guess.
            if prev_base is not None:
                base, prev_base = prev_base, base
            continue
        target = os.path.expanduser(plain[0]) if plain else os.path.expanduser("~")
        prev_base, base = base, os.path.normpath(
            target if os.path.isabs(target) else os.path.join(base, target))
        continue
    if cmd in ("tee", "touch", "truncate"):
        for a in plain:
            add(a, base)
    elif cmd in ("sed", "gsed", "perl") and any(
            a == "-i" or a.startswith("-i") or a.startswith("--in-place")
            or (a.startswith("-") and not a.startswith("--") and "i" in a[1:])
            for a in args):
        for a in plain:
            add(a, base)                         # the script is never a source path
    elif cmd in ("awk", "gawk") and "inplace" in args:
        for a in plain:
            add(a, base)
    elif cmd in ("cp", "mv", "install", "ln", "rsync"):
        dirs = option_value(args, ["-t"], ["--target-directory"])
        if dirs:
            srcs = [a for a in plain if a not in dirs]
            for s_ in srcs:
                add(os.path.join(dirs[0], os.path.basename(s_)), base)
        elif len(plain) >= 2:
            dest, srcs = plain[-1], plain[:-1]
            dest_abs = os.path.join(base, os.path.expanduser(dest))
            if os.path.isdir(dest_abs) or dest.endswith("/"):
                for s_ in srcs:
                    add(os.path.join(dest, os.path.basename(s_)), base)
            else:
                add(dest, base)
    elif cmd == "dd":
        for a in args:
            if a.startswith("of="):
                add(a[3:], base)
    elif cmd == "sort":
        for v in option_value(args, ["-o"], ["--output"]):
            add(v, base)
    elif cmd == "curl":
        for v in option_value(args, ["-o"], ["--output"]):
            add(v, base)
    elif cmd == "wget":
        for v in option_value(args, ["-O"], ["--output-document"]):
            add(v, base)
    elif cmd == "git" and args and args[0] in ("checkout", "restore"):
        # Restoring a file over the working tree rewrites it. `git restore
        # --staged` alone only unstages: no working-tree write.
        flags = [a for a in args[1:] if a.startswith("-")]
        short = "".join(a[1:] for a in flags if not a.startswith("--"))
        staged = "--staged" in flags or "S" in short
        worktree = "--worktree" in flags or "W" in short
        if args[0] == "restore" and staged and not worktree:
            continue
        for a in args[1:]:
            if not a.startswith("-"):
                add(a, base)

if not targets:
    sys.exit(0)

GATES = ("sage-spec-gate.sh", "sage-tdd-gate.sh", "sage-scope-gate.sh",
         "sage-branch-gate.sh")


def gate_script(name):
    """This hook's sibling, else the project's own copy: under the plugin the
    scope gate is not shipped — `sage init` registers it in .claude/hooks/."""
    for d in (hook_dir, os.path.join(base_root, ".claude", "hooks")):
        if os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    return None


# The TDD gate's red-commit unlock buys ONE source file (X2); the verify
# tracker spends it after an Edit, and a shell write spends it here — before
# the next target is judged, so one command cannot write two files on it.
TEST_RE = re.compile(r"(^|/)tests?/|(^|/)__tests__/|(^|/)spec/|(^|/)test_[^/]+$"
                     r"|[^/]*_test\.[a-z]+$|[^/]*\.(test|spec)\.[a-z]+$", re.I)
# Per checkout: each root has its own HEAD and its own unlock record.
unlock = {}


def unlock_state(root):
    key = os.path.realpath(root)               # one record per checkout, however spelled
    if key not in unlock:
        red_path = os.path.join(root, ".sage", "tmp", "tdd-red")
        try:
            with open(red_path, encoding="utf-8") as fh:
                before = fh.read()
        except OSError:
            before = None
        try:
            h = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=5)
            h = h.stdout.strip() if h.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            h = ""
        unlock[key] = (red_path, before, h)
    return unlock[key]


def spend_unlock(project_root, rel):
    red_path, _, head = unlock_state(project_root)
    if not head or TEST_RE.search(rel):
        return
    try:
        with open(red_path, encoding="utf-8") as fh:
            if fh.read().partition("\t")[0].strip() == head:
                return                               # already spent at this HEAD
    except OSError:
        pass
    real = os.path.relpath(os.path.realpath(os.path.join(project_root, rel)),
                           os.path.realpath(project_root)).replace(os.sep, "/")
    try:
        os.makedirs(os.path.dirname(red_path), exist_ok=True)
        ignore = os.path.join(os.path.dirname(red_path), ".gitignore")
        if not os.path.exists(ignore):               # hook scratch (as the tracker)
            with open(ignore, "w", encoding="utf-8") as fh:
                fh.write("*\n")
        with open(red_path, "w", encoding="utf-8") as fh:
            fh.write("%s\t%s\n" % (head, real))
    except OSError:
        pass


def restore_unlock():
    """A blocked command wrote nothing, so it spends nothing."""
    for red_path, red_before, _ in unlock.values():
        try:
            if red_before is None:
                if os.path.exists(red_path):
                    os.remove(red_path)
            else:
                with open(red_path, "w", encoding="utf-8") as fh:
                    fh.write(red_before)
        except OSError:
            pass


for project_root, rel in targets:
    unlock_state(project_root)
    synthetic = {"tool_name": "Write",
                 "tool_input": {"file_path": rel, "content": ""},
                 "cwd": project_root}
    for gate in GATES:
        script = gate_script(gate)
        if script is None:
            continue
        try:
            p = subprocess.run(["bash", script], input=json.dumps(synthetic),
                               capture_output=True, text=True, timeout=30,
                               cwd=project_root)
        except (OSError, subprocess.SubprocessError):
            continue
        if p.returncode == 2:
            restore_unlock()
            print("BLOCK")
            print("Sage: this command writes %s — a source file — so it is judged as "
                  "the edit it is, and %s blocks that edit:\n\n%s\n\nUse the Edit/"
                  "Write tool for source changes once the gate allows them."
                  % (rel, gate.replace(".sh", ""), (p.stderr or "").strip()))
            sys.exit(0)
    spend_unlock(project_root, rel)
sys.exit(0)
PYEOF

INPUT=$(cat)
GATE_OUT=$(printf '%s' "$INPUT" | python3 "$PY_GATE" "$HOOK_DIR")
[ $? -eq 0 ] || exit 0

DECISION=$(printf '%s\n' "$GATE_OUT" | sed -n '1p')
MESSAGE=$(printf '%s\n' "$GATE_OUT" | sed -n '2,$p')
[ "$DECISION" = BLOCK ] || exit 0

# Claude Code's structured deny (C6) when the input came from Claude Code.
if printf '%s' "$INPUT" | grep -q '"hook_event_name"[[:space:]]*:[[:space:]]*"PreToolUse"'; then
  SAGE_DENY_REASON="$MESSAGE" python3 -c 'import json, os; print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": os.environ["SAGE_DENY_REASON"]}}))'
  exit 0
fi
printf '%s\n' "$MESSAGE" >&2
exit 2
