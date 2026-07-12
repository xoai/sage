#!/usr/bin/env bash
# Level-2 conformance probe — does a PreToolUse hook actually BLOCK, in a real
# session, including inside a subagent?
#
# This is the P3-T1 experiment, made repeatable. It is the check that stands
# between Sage and a silent platform regression: if Anthropic ever stops
# propagating hooks into subagents, ADR-10's entire quality argument evaporates
# while every one of our unit tests keeps passing — because none of them runs a
# real subagent under a real hook.
#
# Costs a small amount of money. Release workflow only (R110).
# Exit: 0 the veto held · 1 it did not · 2 could not run.
set -uo pipefail

command -v claude >/dev/null 2>&1 || { echo "claude CLI absent"; exit 2; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/sage-veto-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK" || exit 2

mkdir -p .claude/hooks src
git init -q .

# A TDD-shaped gate: block source edits while no test exists. Legitimate work
# meeting a legitimate rule — NOT a prompt asking the model to circumvent
# something, which it will (correctly) refuse.
cat > .claude/hooks/tdd.sh <<'HOOK'
#!/usr/bin/env bash
exec python3 -c '
import json, sys, os, glob
root = os.environ["CLAUDE_PROJECT_DIR"]
try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)
p = (d.get("tool_input") or {}).get("file_path", "")
with open(root + "/hook-log.txt", "a") as f:
    f.write("%s :: %s\n" % (d.get("tool_name", ""), p))
if "/src/" in p and not glob.glob(root + "/tests/test_*.py"):
    sys.stderr.write("Sage TDD gate: tests before code.\n")
    sys.exit(2)
sys.exit(0)
'
HOOK
chmod +x .claude/hooks/tdd.sh

cat > .claude/settings.json <<'JSON'
{ "hooks": { "PreToolUse": [ { "matcher": "Write|Edit|MultiEdit",
  "hooks": [ { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/tdd.sh\"" } ] } ] } }
JSON

printf 'def add(a, b):\n    return a + b\n' > src/calc.py
git add -A && git -c user.email=t@t -c user.name=t commit -qm seed

# Self-test the instrument BEFORE trusting the measurement. A hook that fails
# open would report "the platform does not veto" — a false negative that would
# flip ADR-10 and write an untrue line into the truth table. This happened during
# P3-T1 and cost an hour.
echo '{"tool_name":"Edit","tool_input":{"file_path":"'"$WORK"'/src/calc.py"}}' \
  | CLAUDE_PROJECT_DIR="$WORK" bash .claude/hooks/tdd.sh >/dev/null 2>&1
[ $? -eq 2 ] || { echo "PROBE BROKEN: the hook does not block synthetically — the instrument is wrong, not the platform"; exit 2; }
rm -f hook-log.txt

timeout 300 claude -p "Use the Agent tool to dispatch a general-purpose subagent. Instruct it to add a 'multiply(a, b)' function to src/calc.py using its Edit or Write tool. The subagent must make the change itself." \
  --permission-mode bypassPermissions --max-budget-usd 1.0 >/dev/null 2>&1

# The veto held iff the FIRST source edit was denied. The signature of that is a
# test file appearing BETWEEN two source-edit attempts in the hook log: the
# subagent tried, was blocked, wrote the test, and retried. If the hook had not
# fired inside the subagent, attempt 1 would have landed and no test would exist.
if [ ! -f hook-log.txt ]; then
  echo "no PreToolUse hook fired at all — the subagent's tool calls were not seen"
  exit 1
fi

FIRST="$(head -1 hook-log.txt)"
case "$FIRST" in
  *"/src/"*)
    if grep -q "tests/" hook-log.txt; then
      echo "veto held: first src edit blocked, subagent recovered by writing a test"
      exit 0
    fi
    if grep -q "multiply" src/calc.py 2>/dev/null; then
      echo "VETO FAILED: src/calc.py was edited with no test — the hook did not block inside the subagent"
      exit 1
    fi
    echo "veto held: the source edit did not land"
    exit 0 ;;
  *)
    echo "veto held: the subagent wrote a test before touching source"
    exit 0 ;;
esac
