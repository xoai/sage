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
import json
import os
import re
import sys

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

try:
    payload = json.load(sys.stdin)
except (ValueError, OSError):
    sys.exit(0)

tool_input = payload.get("tool_input") or {}
file_path = tool_input.get("file_path") or tool_input.get("path") or ""
if not file_path:
    sys.exit(0)

project_root = os.path.abspath(
    os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
)
abspath = file_path if os.path.isabs(file_path) else os.path.join(project_root, file_path)
abspath = os.path.abspath(abspath)

# Only a cycle manifest under .sage/work/<slug>/manifest.md is interesting.
if os.path.basename(abspath) != "manifest.md":
    sys.exit(0)
sage_dir = os.path.join(project_root, ".sage")
work_root = os.path.normpath(os.path.join(sage_dir, "work"))
try:
    if os.path.commonpath([abspath, work_root]) != work_root:
        sys.exit(0)
except ValueError:
    sys.exit(0)

if not os.path.isfile(abspath):
    sys.exit(0)

try:
    with open(abspath, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
except OSError:
    sys.exit(0)

# The frontmatter block only — a `qa:` mentioned in prose is not a declaration.
m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
if not m:
    sys.exit(0)
fm = m.group(1)

qm = re.search(r"^\s*qa\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$", fm, re.M)
if not qm:
    sys.exit(0)
disposition = qm.group(1).lower()
if disposition not in DEGRADED:
    sys.exit(0)          # `passed` / `pending` — nothing to record

slug = os.path.basename(os.path.dirname(abspath))
decisions = os.path.join(sage_dir, "decisions.md")

# Idempotent: this cycle's disposition is recorded once, not once per manifest edit.
key = 'cycle "%s"' % slug
try:
    with open(decisions, encoding="utf-8", errors="replace") as fh:
        existing = fh.read()
except OSError:
    existing = ""
for line in existing.splitlines():
    if MARK in line and key in line and disposition in line:
        sys.exit(0)

today = datetime.date.today().isoformat()
entry = '- [%s] %s — %s (%s) %s\n' % (
    today, key, DEGRADED[disposition], disposition, MARK,
)

try:
    if not os.path.isdir(sage_dir):
        sys.exit(0)                       # not a Sage project
    need_nl = bool(existing) and not existing.endswith("\n")
    with open(decisions, "a", encoding="utf-8") as fh:
        if need_nl:
            fh.write("\n")
        fh.write(entry)
except OSError:
    sys.exit(0)

# Surfaced on stderr so the degradation is visible in the session too, without
# depending on the model choosing to mention it.
sys.stderr.write(
    'Sage: recorded a degraded completion for cycle "%s" (%s) in '
    ".sage/decisions.md.\n" % (slug, disposition)
)
sys.exit(0)
PYEOF

# stdout is suppressed (a PostToolUse hook's stdout is not a channel we want to
# use); stderr passes through, so the degradation is visible even if the model
# never mentions it. Never propagate a failure — see the exit contract above.
python3 "$PY" >/dev/null || true
exit 0
