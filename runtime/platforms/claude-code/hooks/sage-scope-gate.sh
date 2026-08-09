#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-scope-gate.sh — Claude Code PreToolUse hook (Scope Guard, SG-4..SG-9)
#
# The mechanical floor under declared scope: while a cycle has an approved
# plan, an Edit/Write to a path OUTSIDE that plan's derived scope
# (`scope:` block in the manifest, written by `manifest.py scope derive`)
# is blocked — with both legal exits named. Zero model calls. Scope here is
# DECLARED (plan `Files:`/`Output:` lines), never inferred from prompts.
#
# Registered with matcher Edit|Write|MultiEdit. Claude Code deny convention
# identical to the spec/tdd gates: exit 2, reason on stderr.
#
# HOOKS ARE GUARDS, NOT GATES — any internal error fails OPEN (exit 0). The
# one decision this hook exists to make fails CLOSED: an out-of-scope source
# edit does not go through silently.
#
# Allow/block matrix (ordered; first match wins) — SG-4:
#   1. not a Sage project (no .sage/)                          → allow
#   2. hard_enforcement not true, or scope_gate off/absent      → allow
#      (ships OFF: the default flips only when 30-§3's numbers land)
#   3. no active manifest, or gate_state before plan-approved,
#      or no derived scope block (pre-upgrade cycle — but an
#      armed-state cycle with NO scope block warns loudly:
#      a silently disarmed gate is how a floor rots)            → allow
#   4. target under .sage/, sage/, or outside the project root  → allow
#   5. target matches scope.globs ∪ scope.collateral            → allow
#   6. implicit_test_scope (default true) and the target is a
#      test file under a dedicated test root, or whose subject
#      maps to an in-scope source                               → allow
#      (witness/TDD tests must never be blocked by scope)
#   7. corrupt/unparseable manifest or scope block              → allow + warn
#      (scoped to that cycle: corruption in one cycle never
#      disarms another cycle that parsed cleanly)
#   8. otherwise                                                → BLOCK
#
# With several armed cycles the edit is allowed when ANY cycle's scope
# sanctions it (union — two parallel cycles must not deadlock the repo by
# intersection; probed and rejected in review round 2). The union is kept
# honest per cycle: a manifest with no sibling plan.md contributes nothing,
# and a hash-mismatched plan keeps the RECORDED scope armed with a warning —
# so neither a forged drive-by manifest nor a hand-edited plan moves the
# floor. Fabricating a coherent plan+hash pair requires running code: the
# same effort class as the documented bash-write residual (SG-9).
#
# scope_gate: off | standard+ | all. standard+ gates cycles with manifests
# and skips tier1 (the tier system's escape valve); `all` gates tier1 cycles
# too. Tier-1 work with NO manifest is never scope-gated in either mode.
#
# Stated residual (SG-9, same register as config-gate's): bash-mediated
# writes bypass Edit/Write matchers — the standing residual of every
# path-scoped gate; partially covered by the scope journal (which sees Bash)
# and by check-diff at review time. Scope quality is bounded by plan
# discipline — the plan-review scope-completeness item (SG-8) is the
# countermeasure, not a claim of completeness.
#
# Subagents (SG-7): hooks fire inside Task subagents (attested 2026-07-12);
# the gate applies there unchanged. Blocking is safe everywhere; only
# injection is not (that suppression lives in the judge, not here).
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

# SG-12: every scope hook no-ops inside the judge's own headless session —
# the judge's model call must never re-trigger (or be blocked by) scope
# machinery.
[ -n "${SAGE_JUDGE:-}" ] && exit 0

if ! command -v python3 >/dev/null 2>&1; then
  echo "sage-scope-gate: python3 not found; allowing edit" >&2
  exit 0
fi

# Temp file, not an inline heredoc in $( … ): bash 3.2 mis-parses that, and the
# hook's real stdin (the tool-call JSON) must reach python untouched.
PY_GATE=$(mktemp "${TMPDIR:-/tmp}/sage-scope-gate-XXXXXX" 2>/dev/null) || {
  echo "sage-scope-gate: could not create a temp file; allowing edit" >&2
  exit 0
}
trap 'rm -f "$PY_GATE"' EXIT

cat > "$PY_GATE" <<'PYEOF'
import glob as globmod
import hashlib
import json
import os
import re
import sys
import time


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
if not file_path:
    emit("ALLOW")

project_root = (os.environ.get("CLAUDE_PROJECT_DIR")
                or (data.get("cwd") or "").strip() or os.getcwd())
project_root = os.path.abspath(project_root)
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    emit("ALLOW")                                   # row 1 — not a Sage project

# ── 2. Config: master switch + scope_gate mode + implicit_test_scope ──
# FIRST occurrence wins for every key — the sibling gates' convention, and the
# one the config-gate's weaker() reader shares. If this read last-wins while
# the config-gate read first-wins, appending a duplicate `scope_gate: off`
# line would disarm this gate with the config-gate's blessing (found by the
# independent review's probe). The two readers must agree, and they agree on
# FIRST.
enforce = None
mode = None
implicit_tests = None
config_path = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read().lstrip("﻿")            # a BOM must not disarm
        for line in text.splitlines():
            m = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
            if m and enforce is None:
                enforce = (m.group(1).lower() == "true")
            m = re.match(r"\s*scope_gate\s*:\s*\"?([A-Za-z+]+)", line, re.I)
            if m and mode is None:
                mode = m.group(1).lower()
            m = re.match(r"\s*implicit_test_scope\s*:\s*(true|false)\b", line, re.I)
            if m and implicit_tests is None:
                implicit_tests = (m.group(1).lower() == "true")
    except OSError:
        pass
mode = mode or "off"        # absent → off: the default flips on 30-§3's numbers
implicit_tests = implicit_tests is not False        # absent → on
if enforce is not True or mode not in ("standard+", "all"):
    emit("ALLOW")                                   # row 2 — off is off

# ── 3. Resolve the target path ──
abspath = (file_path if os.path.isabs(file_path)
           else os.path.join(project_root, file_path))
abspath = os.path.normpath(abspath)
try:
    rel = os.path.relpath(abspath, project_root).replace(os.sep, "/")
except ValueError:
    emit("ALLOW")                                   # other drive etc.
if rel.startswith(".."):
    emit("ALLOW")           # row 4 — outside the repo, repo-relative scope is silent
first = rel.split("/")[0]
if first in (".sage", "sage"):
    emit("ALLOW")           # row 4 — Sage's own state and the vendored framework


# ── Manifest readers (same conventions as the sibling gates) ──
def frontmatter(path):
    """('ok'|'absent'|'corrupt'|'unreadable', frontmatter-text-or-None)."""
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
    return ("ok", m.group(1))


def field(fm, name):
    # Column-0 only — nested block homonyms never answer for a top-level
    # scalar (re-audit finding 3).
    m = re.search(r"^%s\s*:\s*\"?([A-Za-z0-9_+\-\.@]+)\"?\s*(?:#.*)?$"
                  % re.escape(name), fm, re.M)
    return m.group(1).lower() if m else None


def foreign_owner(fm):
    """True when the cycle's owner: names a DIFFERENT checkout. The parallel-
    sessions flow harvests a worktree's .sage/work/* back into the main
    checkout on removal — an in-progress harvested cycle must not conscript
    this checkout's edits into its scope. Same rule /continue applies
    (cycle-protocol: owner exclusion); absent/unreadable owner → ours."""
    m = re.search(r"^\s*owner\s*:\s*[\"']?([^\"'\n#]+)", fm, re.M)
    if not m:
        return False
    owner = m.group(1).strip()
    if not owner:
        return False
    try:
        return (os.path.realpath(os.path.expanduser(owner))
                != os.path.realpath(project_root))
    except OSError:
        return False


# The glob, then optionally ANY comment. A `# T3 name` comment carries task
# attribution; any other comment is tolerated — an entry must never fall out
# of scope because its trailing note didn't match the attribution shape
# (that would convert a cosmetic comment into a false block).
SCOPE_ITEM_RE = re.compile(
    r"^\s*-\s*(?P<glob>\S+)(?:\s+#\s*(?P<comment>.*))?\s*$")
SCOPE_TASK_RE = re.compile(r"^T(?P<task>\d+)\s*(?:—|--|-)?\s*(?P<note>.*)$")


def read_scope(fm):
    """('none'|'ok'|'corrupt', {globs, collateral}). Entries are
    (glob, task-id-or-None, note). `none` disarms the gate for that cycle —
    a pre-upgrade cycle that never ran `scope derive` is never
    surprise-blocked."""
    lines = fm.splitlines()
    start = val = None
    for i, l in enumerate(lines):
        m = re.match(r"^\s*scope\s*:\s*(.*?)\s*$", l)
        if m:
            start, val = i, m.group(1)
            break
    if start is None:
        return ("none", None)
    if val and not val.startswith("#"):
        return ("corrupt", None)        # a scalar where the machine block belongs
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = {"globs": [], "collateral": []}
    section = None
    saw_structure = False
    for l in lines[start + 1:]:
        if l.strip() and (len(l) - len(l.lstrip())) <= indent:
            break                                    # next same-level key
        s = l.strip()
        if re.match(r"^globs\s*:", s):
            section, saw_structure = "globs", True
            continue
        if re.match(r"^collateral\s*:", s):
            section, saw_structure = "collateral", True
            continue
        if re.match(r"^derived_from\s*:", s):
            saw_structure = True
            continue
        m = SCOPE_ITEM_RE.match(s)
        if m and section:
            glob_val = m.group("glob").strip('"').strip("'")   # YAML quotes
            tid, note = None, ""
            tm = SCOPE_TASK_RE.match((m.group("comment") or "").strip())
            if tm:
                tid = int(tm.group("task"))
                note = (tm.group("note") or "").strip()
            if glob_val:
                block[section].append((glob_val, tid, note))
    if not saw_structure:
        return ("corrupt", None)                     # a scope: key with garbage
    return ("ok", block)


# ── 4. Collect the derived scope of every active, gated cycle ──
KNOWN_STATES = {"pre-spec", "spec-approved", "plan-approved",
                "building", "gates-passed", "complete"}
GATED_STATES = {"plan-approved", "building", "gates-passed"}

manifests = sorted(globmod.glob(os.path.join(sage_dir, "work", "*", "manifest.md")))
if not manifests:
    emit("ALLOW")                                   # row 3 — Tier-1 / no cycle

# One entry per armed cycle, and the edit is allowed when ANY armed cycle's
# scope sanctions it (union) — two legitimate parallel cycles must not
# deadlock the repo by intersecting disjoint scopes (round-2 review,
# confirmed by probe: strictest-wins blocked every edit in any two-cycle
# project and blamed the wrong cycle).
#
# What keeps the union honest is per-cycle INTEGRITY — computed AND acted
# on (round-3's version computed the hash and then honored the scope
# anyway, which the review promptly rode straight through):
#   - no sibling plan.md, or a plan that DECLARES nothing → the cycle
#     contributes nothing. This also kills the constant-hash trick:
#     sha1 of an empty declaration list is a well-known literal, so an
#     empty plan may never authenticate anything.
#   - declaration hash matches derived_from → the recorded scope is
#     honored as written.
#   - hash MISMATCH (the plan changed after derive) → the cycle stays
#     armed with the INTERSECTION of its recorded globs and what the plan
#     still declares, plus recorded collateral — so a partial plan
#     amendment keeps every still-declared glob enforced, while a plan
#     that no longer backs a recorded glob no longer arms it.
#   - collateral entries with no literal prefix (`**`, `*…`) are dropped
#     at read time: add-collateral refuses to create them, so any present
#     were hand-forged.
# The residual, stated: a fabricated plan+manifest pair whose plan openly
# DECLARES a wide scope defeats the union — two artifact writes that a
# review cannot miss, and the same effort class as the documented
# bash-write residual (SG-9). A wholesale plan rewrite likewise disarms
# its cycle LOUDLY (stale warning per edit, artifact diff on record).
# These gates are floors under rationalization drift, not sandboxes.
cycles = []           # (slug, [(glob, task_id, note), ...])
underived = []        # armed-state cycles with no scope block yet
stale = []            # armed cycles whose plan changed since derive
undeclared_plan = []  # armed cycles whose plan declares no Files:/Output:
warned = False


def norm_glob(raw):
    """manifest.py's normalize_scope_glob, ported: the declared-set reader
    must accept exactly what derive would have accepted."""
    g = raw.strip().strip("`").strip('"').strip("'").rstrip(",").strip()
    if not g or "{" in g or "}" in g:
        return None
    g = g.replace("\\", "/")
    while g.startswith("./"):
        g = g[2:]
    if g.startswith("/") or not g:
        return None
    if any(part == ".." for part in g.split("/")):
        return None
    return g.rstrip("/") or None


def plan_declarations(plan_text):
    """(declaration_sha, declared_glob_set) from the plan's Files:/Output:
    lines — the hash basis is the stripped lines (manifest.py's _plan_sha,
    verbatim); the set is their normalized globs."""
    lines = re.findall(r"(?m)^\s*-\s*\*\*(?:Files|Output)\s*:?\*\*:?\s*(.*)$",
                       plan_text)
    full = re.findall(r"(?m)^\s*-\s*\*\*(?:Files|Output)\s*:?\*\*:?\s*.*$",
                      plan_text)
    sha = hashlib.sha1(
        "\n".join(l.strip() for l in full).encode("utf-8", errors="replace")
    ).hexdigest()[:8]
    declared = set()
    for value in lines:
        for raw in re.split(r"[,\s]+", value):
            g = norm_glob(raw)
            if g:
                declared.add(g)
    return sha, declared
for mpath in manifests:
    kind, fm = frontmatter(mpath)
    if kind in ("corrupt", "unreadable"):
        warned = True                               # row 7
        continue
    if kind == "absent":
        continue
    status = field(fm, "status")
    if status in ("complete", "completed", "abandoned"):
        continue
    if foreign_owner(fm):
        continue                    # another checkout's cycle (harvested/parallel)
    state = field(fm, "gate_state")
    if state not in GATED_STATES:
        continue                                    # row 3 — pre-plan or done
    if mode == "standard+" and field(fm, "tier") == "tier1":
        continue                                    # the tier system's escape valve
    slug = os.path.basename(os.path.dirname(mpath))
    skind, scope = read_scope(fm)
    if skind == "none":
        underived.append(slug)                      # never derived: disarmed, LOUDLY
        continue
    if skind == "corrupt":
        warned = True                               # row 7 — this cycle only
        continue
    plan_path = os.path.join(os.path.dirname(mpath), "plan.md")
    try:
        with open(plan_path, encoding="utf-8", errors="replace") as fh:
            plan_text = fh.read()
    except OSError:
        warned = True       # scope with no plan behind it contributes nothing
        continue
    plan_sha, declared_now = plan_declarations(plan_text)
    if not declared_now:
        undeclared_plan.append(slug)   # empty declarations authenticate NOTHING
        continue
    recorded = ""
    # Search the scope: block ONLY — task_graph: carries its own
    # derived_from, and a first-match-anywhere read returned the graph's
    # pin when the blocks were hand-ordered graph-first, producing a false
    # stale warning that no re-derive could clear (re-audit finding 2).
    sblock = re.search(r"(?m)^scope\s*:[ \t]*(?:#.*)?$\n((?:[ \t]+.*\n?)*)",
                       fm)
    dm = re.search(r"^\s*derived_from\s*:\s*plan@([0-9a-fA-F]+)",
                   sblock.group(1) if sblock else "", re.M)
    if dm:
        recorded = dm.group(1).lower()
    # Collateral: entries add-collateral could never have written are forged.
    coll = [e for e in scope["collateral"] if not re.match(r"[*?\[]", e[0])]
    if recorded == plan_sha:
        entries = scope["globs"] + coll
    else:
        stale.append(slug)
        entries = [e for e in scope["globs"] if e[0] in declared_now] + coll
    if not entries:
        continue            # stale-disarmed — the warning above says how back
    cycles.append((slug, entries))

if not cycles:
    if warned:
        # Row 7 — nothing could be read, so nothing can be decided: fail open.
        emit("WARN", "a cycle manifest or scope block could not be parsed; "
                     "allowing this edit")
    if undeclared_plan:
        emit("WARN", "scope_gate is on but cycle \"%s\"'s plan declares no "
                     "Files:/Output: lines — nothing to enforce (SG-8: scope "
                     "completeness is a plan-review finding); declare Files: "
                     "per task, then scope derive --refresh"
                     % undeclared_plan[0])
    if underived:
        # scope_gate is ON but the transition never ran `scope derive` — a
        # silently disarmed gate is how a floor rots. Loud, and still open.
        emit("WARN", "scope_gate is on but cycle \"%s\" has no derived scope "
                     "— run: python3 sage/runtime/tools/manifest.py scope "
                     "derive .sage/work/%s/manifest.md"
                     % (underived[0], underived[0]))
    emit("ALLOW")                                   # row 3


# ── 5. Match the target against scope ──
def glob_re(g):
    """`**` crosses separators; `*` and `?` do not. A wildcard-free glob also
    matches as a directory prefix (`src/auth` covers `src/auth/token.ts`)."""
    out, i = [], 0
    while i < len(g):
        c = g[i]
        if c == "*":
            if g[i:i + 2] == "**":
                out.append(".*")
                i += 2
                if i < len(g) and g[i] == "/":
                    i += 1                           # a/**/b also matches a/b
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(rel, g):
    if not re.search(r"[*?\[]", g):
        return rel == g or rel.startswith(g + "/")
    try:
        return bool(glob_re(g).match(rel))
    except re.error:
        return False


# ── 6. Implicit test scope (witness/TDD tests are never blocked by scope) ──
base = os.path.basename(rel)
stem = base
for suf in (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".rb", ".go", ".rs",
            ".java", ".cs", ".php", ".exs", ".sh", ".bash"):
    if stem.endswith(suf):
        stem = stem[:-len(suf)]
        break
is_test = (re.search(r"(^|/)(tests?|__tests__|spec)/", rel) is not None
           or stem.startswith(("test_", "test-"))
           or stem.endswith(("_test", "-test", ".test", ".spec")))
subject = re.sub(r"^(test[_-])", "", stem)
subject = re.sub(r"([._-]test|[._-]spec|\.test|\.spec)$", "", subject)
# A dedicated top-level test root: the `tests/**/<name>.*` shape SG-4 row 6
# names. Witness tests here are NEVER blocked — a TDD test for a module that
# does not exist yet cannot prove its subject any other way, and L3's own
# plan has tests (test_rate_limit.py) whose subject matches no module name.
in_test_root = rel.split("/")[0] in ("tests", "test", "__tests__", "spec")


def literal_prefix(g):
    m = re.search(r"[*?\[]", g)
    return g[:m.start()] if m else g


# Junk trees a subject lookup must never descend into — and a wall-clock cap,
# because the header promises <50 ms and a 30k-file repo was measured paying
# 28 ms in this walk alone (round-2 review). On cap: give up WITHOUT the
# allow — test-root witness tests are already allowed above this lookup, so
# erring closed here only affects test-shaped files outside test roots, and
# the block message names the recovery.
_WALK_PRUNE = {".git", "node_modules", ".sage", "sage", "dist", "build",
               "__pycache__", ".venv", "venv", "vendor", ".next", "target"}


def subject_in_scope(entries):
    """Row 6: the test's SUBJECT maps to an in-scope source — a concrete glob
    whose stem matches, or a `<subject>.*` file on disk under a wildcard
    glob's literal prefix (bounded walk). NOT the earlier any-wildcard-tail
    free pass: under the canonical `src/x/**` shape that allowed every
    test-shaped path anywhere (independent review, confirmed by probe)."""
    for g, _, _ in entries:
        last = g.rstrip("/").split("/")[-1]
        if "." in last and not re.search(r"[*?\[]", last) \
                and last.rsplit(".", 1)[0] == subject:
            return True
    deadline = time.time() + 0.015
    budget = [3000]
    want = subject + "."
    for g, _, _ in entries:
        if not re.search(r"[*?\[]", g):
            continue
        prefix = literal_prefix(g).rstrip("/")
        top = os.path.join(project_root, prefix) if prefix else project_root
        try:
            for dirpath, dirnames, filenames in os.walk(top):
                dirnames[:] = [d for d in dirnames if d not in _WALK_PRUNE]
                budget[0] -= len(filenames) + len(dirnames)
                for name in filenames:
                    if name.startswith(want):
                        hrel = os.path.relpath(os.path.join(dirpath, name),
                                               project_root).replace(os.sep, "/")
                        if matches(hrel, g):
                            return True
                if budget[0] < 0 or time.time() > deadline:
                    break                            # bounded, never pathological
        except OSError:
            pass
    return False


def cycle_allows(entries):
    if entries and any(matches(rel, g) for g, _, _ in entries):
        return True                                 # row 5 — in scope
    # Row 6 runs even against an EMPTY scope: "witness/TDD tests must never
    # be blocked by scope" is absolute, and an all-undeclared plan (empty
    # globs) must not make writing the first test impossible.
    if implicit_tests and is_test:
        if in_test_root:
            return True                             # row 6 — witness shape
        if entries and subject_in_scope(entries):
            return True                             # row 6 — subject maps
    return False        # incl. empty scope: a real, deliberately tiny scope


def common_prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


# UNION: any armed cycle that sanctions the edit allows it. Blame, when
# blocking, goes to the cycle whose scope sits CLOSEST to the target — the
# one the work most plausibly belongs to (SG-5's actionable-message promise).
if any(cycle_allows(entries) for _, entries in cycles):
    if stale:
        emit("WARN", "cycle \"%s\"'s plan changed after `scope derive` — the "
                     "RECORDED scope is still enforced; run: python3 "
                     "sage/runtime/tools/manifest.py scope derive "
                     ".sage/work/%s/manifest.md --refresh"
                     % (stale[0], stale[0]))
    if underived:
        emit("WARN", "scope_gate is on but cycle \"%s\" has no derived scope "
                     "— run: python3 sage/runtime/tools/manifest.py scope "
                     "derive .sage/work/%s/manifest.md"
                     % (underived[0], underived[0]))
    emit("ALLOW")


def cycle_closeness(entries):
    return max((common_prefix_len(rel, literal_prefix(g))
                for g, _, _ in entries), default=-1)


slug, entries = max(cycles, key=lambda c: cycle_closeness(c[1]))
best = max(entries, key=lambda e: common_prefix_len(rel, literal_prefix(e[0])))
_, tid, note = best
nearest = ("nearest task: T%d \"%s\"" % (tid, note) if tid and note
           else ("nearest task: T%d" % tid if tid
                 else "no task attribution on the nearest glob"))

emit("BLOCK", (
    "Sage scope-gate: %s is outside the approved plan's scope\n"
    "(cycle \"%s\", %s).\n"
    "Legal exits:\n"
    "  1. It belongs to this work → python3 sage/runtime/tools/manifest.py "
    "scope add-collateral %s --task T%s --reason \"...\"\n"
    "  2. The scope itself should grow → ask the user; amend the plan's "
    "Files: lines, then scope derive --refresh\n"
    "Rule: scope changes go through the artifact, never silently through "
    "the diff."
) % (rel, slug, nearest, rel, tid if tid else "N"))
PYEOF

GATE_OUT=$(python3 "$PY_GATE")
GATE_RC=$?

if [ "$GATE_RC" -ne 0 ]; then
  echo "sage-scope-gate: internal error (python exit $GATE_RC); allowing edit" >&2
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
    printf 'sage-scope-gate: %s\n' "$MESSAGE" >&2
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
