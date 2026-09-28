#!/usr/bin/env bash
# sage-manifest-sync.sh — Claude Code PostToolUse hook (R120, mechanical).
#
# L1 measured resume fidelity for the first time and found the manifest lying.
# Three runs of the identical cycle, all three completing and committing all three
# tasks:
#
#     run 1    gate_state: gates-passed
#     run 2    gate_state: plan-approved     <-- "plan approved, no tasks started"
#     run 3    gate_state: complete
#
# Run 2 is the bug. A session resuming from that manifest reads "no tasks started"
# and does the work again. The artifact whose whole job is to carry work across a
# context boundary had drifted from the tree beside it.
#
# cycle-protocol.md said "Advance it at every checkpoint", in prose — and prose is
# read by the same model that is deciding whether to bother. So the manifest is not
# asked to advance any more. It ADVANCES, because the agent wrote source code, and
# the hook firing IS the evidence that it did.
#
# Third time for this exact bug, and the third fix of the same shape:
#
#     R29     degradation record   prose -> logged 1 of 3 runs   -> now a hook
#     ADR-10  task ledger          prose -> written 2 of 3 runs  -> now a script
#     R120    manifest gate_state  prose -> correct 1 of 3 runs  -> now this
#
# WHAT IT WILL NOT DO: advance a cycle to `gates-passed` or `complete`. Those are
# APPROVAL states — a human grants them, or the quality-locked loop does after the
# gates actually run. A hook that advanced a cycle to `gates-passed` because the
# files looked finished would forge the signature the gate exists to collect. It
# reports that work HAS BEGUN. It never reports that work has been APPROVED.
#
# I/O: PostToolUse JSON on stdin. Exit 0 ALWAYS — a bookkeeping hook that can fail
# a user's tool call is a worse bug than the one it fixes.

set -uo pipefail

command -v python3 >/dev/null 2>&1 || exit 0

# The logic lives in ONE place (runtime/tools/manifest.py) and this hook delegates
# to it. Inlining it here would make a second copy of a state machine, and a second
# copy of a thing with a canonical source is what ADR-5 exists to forbid — the
# navigator was exactly that, and it drifted for two releases.
project="${CLAUDE_PROJECT_DIR:-$PWD}"
tool=""
for candidate in \
  "$project/sage/runtime/tools/manifest.py" \
  "${CLAUDE_PLUGIN_ROOT:-}/tools/manifest.py"
do
  if [ -f "$candidate" ]; then tool="$candidate"; break; fi
done
[ -n "$tool" ] || exit 0

payload=$(cat) || exit 0

# The path that was just written, out of the PostToolUse payload.
wrote=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    p = json.load(sys.stdin)
except (ValueError, OSError):
    sys.exit(0)
ti = p.get("tool_input") or {}
print(ti.get("file_path") or ti.get("path") or "")
' 2>/dev/null) || exit 0

[ -n "$wrote" ] || exit 0

# Every ACTIVE cycle. The hook does not attribute an edit to a specific cycle (the
# spec-gate has the same limitation, R26) — but the failure being fixed is a cycle
# claiming no work has started while work plainly has, and that is true of any
# active cycle in a repo where source is being written.
for manifest in "$project"/.sage/work/*/manifest.md; do
  [ -f "$manifest" ] || continue
  python3 "$tool" advance "$manifest" --wrote "$wrote" >/dev/null 2>&1 || true
done

exit 0
