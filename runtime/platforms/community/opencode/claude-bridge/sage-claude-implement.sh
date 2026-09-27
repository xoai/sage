#!/usr/bin/env bash
# sage-claude-implement.sh — run ONE Sage implementer task through Claude Code
# headless (`claude -p`). Run by the claude-cli bridge (claude-cli-bridge.py,
# installed with `sage setup claude-bridge`); also usable directly.
#
# Usage:  sage-claude-implement.sh <workdir>  < task-packet
#   The task packet (the Sage implementer prompt, verbatim) arrives on stdin.
#   <workdir> is the project root — or the task's lane worktree under
#   --parallel. Claude runs THERE, so Sage's Claude Code hooks from that
#   tree's .claude/settings.json police every edit (spec/tdd/scope/secrets/
#   bookkeeping/verify gates — the same scripts opencode's plugin runs).
#
# Output: Claude's final message VERBATIM between markers, then run metadata
# (model, turns, gate blocks, transcript path). The full stream-json
# transcript is kept under <workdir>/.sage/tmp/claude-implementer/ for audit.
#
# Environment knobs:
#   SAGE_CLAUDE_MODEL     model for claude (default: sonnet)
#   SAGE_CLAUDE_TIMEOUT   seconds before the run is killed (default: 1500),
#                         after which a structured STATUS: BLOCKED report is
#                         returned (partial edits may remain).
#   SAGE_CLAUDE_TOOLS     full --allowedTools override (comma-separated).
#   <workdir>/.sage/claude-implementer.tools   extra allowed tools, one per
#                         line (e.g. `Bash(cargo test:*)`), appended.
#
# Exit: 0 Claude finished (read its STATUS line) | 1 Claude errored |
#       2 bad invocation | 3 timed out (killed; partial work may exist).

set -uo pipefail

WORKDIR="${1:-}"
if [ -z "$WORKDIR" ] || [ ! -d "$WORKDIR" ]; then
  # Every refusal carries a STATUS line — the orchestrator parses it.
  echo "STATUS: BLOCKED"
  echo "sage-claude-implement.sh: working directory '${WORKDIR}' does not exist."
  echo "usage: sage-claude-implement.sh <workdir> < task-packet"
  exit 2
fi
WORKDIR=$(cd "$WORKDIR" && pwd)
if ! command -v claude >/dev/null 2>&1; then
  echo "STATUS: BLOCKED"
  echo "claude CLI is not on PATH — the Claude implementer cannot run."
  exit 2
fi

# Refuse to run ungated. Claude edits in its own process, so opencode's sage
# plugin never sees those edits — the ONLY enforcement is sage's Claude Code
# hooks in <workdir>/.claude/settings.json. A project installed for opencode
# alone would give Claude free rein, silently.
if ! grep -q "sage-tdd-gate.sh" "$WORKDIR/.claude/settings.json" 2>/dev/null; then
  echo "STATUS: BLOCKED"
  echo "Sage's Claude Code hooks are not installed in $WORKDIR (.claude/settings.json"
  echo "has no sage-tdd-gate). Claude's edits would bypass every Sage gate. Fix:"
  echo "  sage update --platform opencode,claude-code"
  exit 2
fi

PACKET=$(cat)
if [ -z "${PACKET//[[:space:]]/}" ]; then
  echo "STATUS: BLOCKED"
  echo "empty task packet on stdin — nothing to implement."
  exit 2
fi

MODEL="${SAGE_CLAUDE_MODEL:-sonnet}"
LIMIT="${SAGE_CLAUDE_TIMEOUT:-1500}"

DEFAULT_TOOLS="Read,Edit,Write,MultiEdit,Glob,Grep,\
Bash(git status:*),Bash(git diff:*),Bash(git log:*),Bash(git show:*),\
Bash(git add:*),Bash(git commit:*),\
Bash(python3 -m pytest:*),Bash(python -m pytest:*),Bash(pytest:*),\
Bash(go test:*),Bash(go build:*),Bash(go vet:*),\
Bash(npm test:*),Bash(npm run test:*),Bash(npx vitest:*),Bash(npx jest:*),\
Bash(cargo test:*),Bash(flutter test:*),Bash(make test:*),\
Bash(bash .sage/gates/scripts/sage-verify.sh:*),\
Bash(ls:*),Bash(cat:*),Bash(head:*),Bash(tail:*),Bash(wc:*)"
TOOLS="${SAGE_CLAUDE_TOOLS:-$DEFAULT_TOOLS}"
if [ -z "${SAGE_CLAUDE_TOOLS:-}" ] && [ -f "$WORKDIR/.sage/claude-implementer.tools" ]; then
  while IFS= read -r line; do
    line="${line%%#*}"; line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ -n "$line" ] && TOOLS="$TOOLS,$line"
  done < "$WORKDIR/.sage/claude-implementer.tools"
fi

ROLE_LOCK="You are the Sage IMPLEMENTER subagent for exactly ONE plan task, \
dispatched headless by an opencode orchestrator. You are NOT the Sage \
orchestrator: do not classify or route, do not run /sage, /build or any Sage \
workflow, do not dispatch subagents, and do not edit anything under .sage/ \
(bookkeeping belongs to the orchestrator; the bookkeeping gate will block \
you). Follow the task packet exactly. Write the failing test FIRST, then the \
code — Sage's hooks block source edits without a test. Run the tests. Commit \
once when green. If a Sage gate blocks you, obey its message; never try to \
bypass it. Start no long-lived processes (no servers, no watch modes; run \
suites once, CI=true). End with the report format the packet specifies: a \
STATUS: DONE | BLOCKED line and the evidence block with PASTED test output."

LOGDIR="$WORKDIR/.sage/tmp/claude-implementer"
mkdir -p "$LOGDIR"
# Transcripts are audit artifacts, never project content: `.sage/tmp/` is not
# gitignored by default, and an implementer running `git add -A` would commit
# them. A self-ignoring directory keeps them out of every commit.
[ -f "$LOGDIR/.gitignore" ] || printf '*\n' > "$LOGDIR/.gitignore"
TS=$(date +%Y%m%d-%H%M%S)
TRANSCRIPT="$LOGDIR/$TS-$$.jsonl"

PACKET_FILE="$LOGDIR/$TS-$$.packet.md"
printf '%s' "$PACKET" > "$PACKET_FILE"

# `exec` matters: $CPID must BE the claude process. With an intermediate
# subshell (the first version piped printf into claude inside a function),
# killing the subshell orphaned claude to init — the pilot caught a claude
# still running after the wrapper had been killed.
( cd "$WORKDIR" && CI=true exec claude -p \
    --output-format stream-json --verbose \
    --model "$MODEL" \
    --allowedTools "$TOOLS" \
    --append-system-prompt "$ROLE_LOCK" \
    < "$PACKET_FILE" > "$TRANSCRIPT" 2>"$TRANSCRIPT.stderr" ) &
CPID=$!

# Children FIRST, then the parent: kill the parent first and its children
# reparent to init, where `pkill -P` can no longer find them (the same
# ordering class as sage v1.3.21's watchdog fix).
kill_tree() {
  pkill "-$1" -P "$2" 2>/dev/null
  kill "-$1" "$2" 2>/dev/null
}

# If opencode kills THIS script (its bash-tool timeout sends TERM), take
# Claude down with it — an orphaned claude still editing files after the caller
# has reported would be worse than a failed run.
on_term() {
  kill_tree TERM "$CPID"; sleep 3; kill_tree KILL "$CPID"
  exit 3
}
trap on_term TERM INT HUP

(
  sleep "$LIMIT"
  kill -0 "$CPID" 2>/dev/null || exit 0     # finished in the meantime
  : > "$TRANSCRIPT.timeout"
  kill_tree TERM "$CPID"; sleep 10; kill_tree KILL "$CPID"
) >/dev/null 2>&1 &
WPID=$!
wait "$CPID"
RC=$?
# Watcher first, then its sleep (sweeping the sleep first lets the watcher
# advance and write a spurious sentinel); orphaned sleeps are harmless.
kill "$WPID" 2>/dev/null; pkill -P "$WPID" 2>/dev/null; wait "$WPID" 2>/dev/null
trap - TERM INT HUP
# A sentinel only means "timed out" if the run actually failed.
[ "$RC" -eq 0 ] && rm -f "$TRANSCRIPT.timeout"

python3 - "$TRANSCRIPT" "$RC" "$MODEL" "$LIMIT" <<'PYEOF'
import json, os, re, sys
path, rc, model, limit = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
timed_out = os.path.exists(path + ".timeout")
result, meta, blocks, tool_calls = None, {}, [], 0
try:
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
except OSError:
    lines = []
for line in lines:
    try:
        ev = json.loads(line)
    except ValueError:
        continue
    t = ev.get("type")
    if t == "assistant":
        for c in (ev.get("message") or {}).get("content") or []:
            if c.get("type") == "tool_use":
                tool_calls += 1
    elif t == "user":
        for c in (ev.get("message") or {}).get("content") or []:
            if c.get("type") == "tool_result" and c.get("is_error"):
                txt = c.get("content")
                if isinstance(txt, list):
                    txt = " ".join(x.get("text", "") for x in txt if isinstance(x, dict))
                txt = str(txt or "")
                # A hook DENIAL, precisely — not any failed tool call. A red
                # test run is expected TDD, and matching on "sage" misfired
                # on project paths containing it (pilot, 2026-09-27).
                if re.search(r"PreToolUse:\w+ hook error|hooks/sage-[\w-]+\.sh", txt):
                    blocks.append(" ".join(txt.split())[:220])
    elif t == "result":
        result = ev.get("result")
        meta = ev
print("=== CLAUDE IMPLEMENTER REPORT (verbatim) ===")
if result:
    print(result)
else:
    print("STATUS: BLOCKED")
    print("Claude produced no final report" + (" — the run TIMED OUT after %ss and was killed; partial edits may exist in the working tree." % limit if timed_out else "."))
    try:
        err = open(path + ".stderr", encoding="utf-8", errors="replace").read().strip()
        if err:
            print("claude stderr (tail):"); print("\n".join(err.splitlines()[-15:]))
    except OSError:
        pass
print("=== END REPORT ===")
print("--- run metadata ---")
print("implementer: claude -p (Claude Code), model=%s" % model)
print("turns=%s tool_calls=%d is_error=%s timed_out=%s exit=%d" % (
    meta.get("num_turns", "?"), tool_calls, meta.get("is_error", "?"), timed_out, rc))
print("sage gate blocks during the run: %d" % len(blocks))
for b in blocks[:8]:
    print("  - " + b)
print("transcript: %s" % path)
sys.exit(3 if timed_out else (0 if result and not meta.get("is_error") else 1))
PYEOF
