#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# sage-scope-journal.sh — Claude Code PostToolUse hook (Scope Guard, SG-10)
#
# The scope judge's event capture + delivery channel, in one non-blocking
# hook. Appends one JSONL line per tool call to the active cycle's
# .sage/work/<slug>/scope-journal.jsonl (Bash calls too — this is the partial
# coverage for the scope gate's bash-writes residual, SG-9), then returns
# immediately. When the background judge has queued a `drift` correction, the
# NEXT firing of this hook emits it as hookSpecificOutput.additionalContext
# (Claude Code ≥ 2.1.196), subject to the anti-nag invariants (SG-17).
#
# All behavior lives in runtime/tools/scope_judge.py — this wrapper only
# guards and delegates:
#   - SAGE_JUDGE set → exit 0 (SG-12 recursion guard: the judge's own model
#     call fires hooks in its headless session; they must no-op)
#   - scope_judge not `true` in .sage/config.yaml → exit 0 (ships FALSE;
#     stays false — E-JUDGE-1 measured 1 false positive in 4 clean runs
#     and detection was unmeasurable, 30-§3)
#   - python3 or the tool missing → exit 0
#
# This hook NEVER blocks and NEVER exits non-zero: it records and relays.
# Subagent events (agent_id/agent_type in the hook input) are journaled with
# sub: true and are otherwise inert — a packet-scoped implementer receiving
# cycle-scope corrections is being derailed, not helped (SG-11; Scopey's
# finding, adopted).
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

# SG-12: the recursion guard — cheapest check first.
[ -n "${SAGE_JUDGE:-}" ] && exit 0

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
CONFIG="$PROJECT_ROOT/.sage/config.yaml"

# Ships off: without an explicit scope_judge: true, this hook costs one grep.
grep -Eq '^[[:space:]]*scope_judge:[[:space:]]*true' "$CONFIG" 2>/dev/null || exit 0

command -v python3 >/dev/null 2>&1 || exit 0

# The vendored framework first (a user project), then a source checkout.
TOOL="${SAGE_SCOPE_JUDGE_TOOL:-}"
if [ -z "$TOOL" ]; then
  for cand in "$PROJECT_ROOT/sage/runtime/tools/scope_judge.py" \
              "$PROJECT_ROOT/runtime/tools/scope_judge.py"; do
    [ -f "$cand" ] && TOOL="$cand" && break
  done
fi
[ -z "$TOOL" ] && exit 0

python3 "$TOOL" hook 2>/dev/null
exit 0
