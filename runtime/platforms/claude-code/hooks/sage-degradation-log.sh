#!/usr/bin/env bash
# sage-degradation-log.sh — Claude Code PostToolUse hook (R29, mechanical).
#
# R29 promised that a skipped review "announces itself and logs one line to
# decisions.md — never silently". Phase 4 measured it: the announcement appeared
# in 2 of 3 runs and the decisions.md line in 1 of 3. It was instructed in prose,
# and prose is read by the same model that is deciding whether to bother.
#
# So the record is not asked for any more. It is TAKEN.
#
# When a cycle manifest declares a degraded disposition — `qa: skipped-no-subagent`
# and friends — this hook writes the audit line to .sage/decisions.md itself. The
# model does not have to remember, cannot forget, and cannot decide it isn't worth
# mentioning. Its companion is the spec-gate's completion guard, which refuses to
# let a cycle reach `complete` while its `qa:` is still `pending` — so a skip
# cannot go undeclared, and a declared skip cannot go unlogged.
#
# WHAT THIS DOES NOT DO, stated plainly: it cannot detect that the Task tool is
# missing. Tool ABSENCE is not observable from a hook payload — only the agent
# knows what it was given. The agent still has to declare the disposition
# truthfully. What changed is that it can no longer complete the cycle without
# declaring one, and that the durable record is produced by code rather than by
# good intentions. The transcript announcement remains prose; the audit trail does
# not.
#
# WHEN: after an Edit/Write of a cycle manifest, and after every Bash command —
# the sanctioned writer during a cycle is `manifest.py close-out`, a shell
# command, so the record cannot depend on the Edit tool. A Bash call checks the
# cycle manifests written in the last fifteen minutes (idempotent).
#
# I/O: PostToolUse JSON on stdin. Exit 0 ALWAYS — a logging hook that can fail a
# tool call is a worse bug than the one it fixes.

set -uo pipefail

# python3 is a hard dependency of the gates already. Without it, do nothing —
# never fail the user's tool call over an audit line.
command -v python3 >/dev/null 2>&1 || exit 0

PY=$(mktemp "${TMPDIR:-/tmp}/sage-deglog-XXXXXX" 2>/dev/null) || exit 0
trap 'rm -f "$PY"' EXIT

cat > "$PY" <<'PYEOF'
import datetime
import glob
import json
import os
import re
import sys
import time

# Dispositions that mean "a capability that should have run, did not". Each maps
# to the sentence written into decisions.md.
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
        "auto-QA waived by the user — completion accepted without independent QA.",
}

MARK = "[auto-logged by sage-degradation-log]"
RECENT_S = 900   # the Bash sweep's window: a command runs ≤ 10 min, plus margin

try:
    payload = json.load(sys.stdin)
except (ValueError, OSError):
    sys.exit(0)

tool_input = payload.get("tool_input") or {}
file_path = tool_input.get("file_path") or tool_input.get("path") or ""

project_root = os.path.abspath(
    os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
)
sage_dir = os.path.join(project_root, ".sage")
work_root = os.path.normpath(os.path.join(sage_dir, "work"))
decisions = os.path.join(sage_dir, "decisions.md")
if not os.path.isdir(sage_dir):
    sys.exit(0)                           # not a Sage project


def record(abspath):
    """Log this manifest's degraded disposition once. Returns the slug, or None."""
    # Only a cycle manifest under .sage/work/<slug>/manifest.md is interesting.
    if os.path.basename(abspath) != "manifest.md":
        return None
    try:
        # Real paths: the payload's path and the project dir can name the same
        # place differently (macOS /var → /private/var; a symlinked checkout).
        real_work = os.path.realpath(work_root)
        if os.path.commonpath([os.path.realpath(abspath), real_work]) != real_work:
            return None
        with open(abspath, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except (ValueError, OSError):
        return None

    # The frontmatter block only — a `qa:` mentioned in prose is not a declaration.
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return None
    qm = re.search(r"^\s*qa\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$", m.group(1), re.M)
    if not qm:
        return None
    disposition = qm.group(1).lower()
    if disposition not in DEGRADED:
        return None          # `passed` / `pending` — nothing to record

    slug = os.path.basename(os.path.dirname(abspath))

    # Idempotent: this cycle's disposition is recorded once, not once per manifest
    # edit — and not again after decisions.md is rotated into decisions-<date>.md,
    # or when the Hermes plugin's logger (its own marker) already recorded it.
    key = 'cycle "%s"' % slug
    try:
        with open(decisions, encoding="utf-8", errors="replace") as fh:
            existing = fh.read()
    except OSError:
        existing = ""
    # The slug where each logger puts it: `cycle "<slug>"` here, ``cycle `<slug>` ``
    # and `] <slug> qa:` in Hermes — not anywhere in the sentence (a cycle
    # named `user` is not "the user").
    logged = re.compile(r"cycle [`\"]%s[`\"]|\] %s qa:" % (re.escape(slug), re.escape(slug)))
    for path in [decisions] + sorted(glob.glob(os.path.join(sage_dir, "decisions-*.md"))):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for line in text.splitlines():
            if ("auto-logged by sage-" in line and disposition in line
                    and logged.search(line)):
                return None

    today = datetime.date.today().isoformat()
    entry = '- [%s] %s — %s (%s) %s\n' % (
        today, key, DEGRADED[disposition], disposition, MARK,
    )
    try:
        need_nl = bool(existing) and not existing.endswith("\n")
        with open(decisions, "a", encoding="utf-8") as fh:
            if need_nl:
                fh.write("\n")
            fh.write(entry)
    except OSError:
        return None
    # Surfaced on stderr so the degradation is visible in the session too, without
    # depending on the model choosing to mention it.
    sys.stderr.write(
        'Sage: recorded a degraded completion for cycle "%s" (%s) in '
        ".sage/decisions.md.\n" % (slug, disposition)
    )
    return slug


if file_path:
    abspath = file_path if os.path.isabs(file_path) else os.path.join(project_root, file_path)
    record(os.path.abspath(abspath))
elif payload.get("tool_name") == "Bash":
    # A shell command can write a manifest too — `manifest.py close-out --qa`,
    # which is the sanctioned writer while a cycle is active, or a bare sed
    # (E8, 2026-10-27: the cycle closed `qa: waived` through sed and no line was
    # logged). The command does not say which manifest it wrote, so every cycle
    # manifest written in the last RECENT_S seconds is checked — older cycles are
    # history, and a sweep must not back-fill them, dated today, on the first
    # Bash call after an upgrade. One already recorded is skipped above.
    now = time.time()
    try:
        slugs = sorted(os.listdir(work_root))
    except OSError:
        slugs = []
    for slug in slugs:
        manifest = os.path.join(work_root, slug, "manifest.md")
        try:
            if now - os.path.getmtime(manifest) > RECENT_S:
                continue
        except OSError:
            continue
        record(manifest)
sys.exit(0)
PYEOF

# stdout is suppressed (a PostToolUse hook's stdout is not a channel we want to
# use); stderr passes through, so the degradation is visible even if the model
# never mentions it. Never propagate a failure — see the exit contract above.
python3 "$PY" >/dev/null || true
exit 0
