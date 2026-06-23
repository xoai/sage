#!/usr/bin/env bash
set -euo pipefail

# Hermes pre_llm_call hook.
# Adapts Sage's canonical session context output to Hermes' {"context": "..."}
# response shape. The context body itself comes from sage-session-init.sh.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
SESSION_INIT="$SCRIPT_DIR/sage-session-init.sh"
PAYLOAD="$(cat - 2>/dev/null || true)"

if [ -n "$PAYLOAD" ] && command -v python3 >/dev/null 2>&1; then
  HOOK_CWD="$(printf '%s' "$PAYLOAD" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("cwd") or ""))' 2>/dev/null || true)"
  if [ -n "${HOOK_CWD:-}" ]; then
    cd "$HOOK_CWD" 2>/dev/null || true
  fi
fi

if [ ! -f "$SESSION_INIT" ]; then
  CONTEXT=""
else
  CONTEXT="$(printf '%s' "$PAYLOAD" | SAGE_SESSION_INIT_RAW=1 bash "$SESSION_INIT" 2>/dev/null || true)"
fi

AUTO_ROUTE_CONTEXT=""
if [ -n "$PAYLOAD" ] && command -v python3 >/dev/null 2>&1; then
  AUTO_ROUTE_CONTEXT="$(SAGE_HERMES_PAYLOAD="$PAYLOAD" python3 <<'PY' 2>/dev/null || true
import json
import os

payload = json.loads(os.environ.get("SAGE_HERMES_PAYLOAD") or "{}")
extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
message = str(payload.get("user_message") or extra.get("user_message") or "").lower()

rules = [
    ("/design-review", "design-review", ["design review", "design audit", "design check", "visual audit", "slop check"]),
    ("/build", "build", ["build", "implement", "create", "add", "develop", "ship", "code", "feature"]),
    ("/fix", "fix", ["fix", "bug", "broken", "error", "crash", "failing", "debug", "issue"]),
    ("/architect", "architect", ["architect", "redesign", "system design", "migrate", "rewrite"]),
    ("/research", "research", ["understand", "research", "interview", "discover", "user needs", "jobs to be done"]),
    ("/design", "design", ["design", "wireframe", "brief", "ux", "prd", "prototype", "mockup"]),
    ("/analyze", "analyze", ["audit", "evaluate", "assess", "analyze", "measure", "funnel", "usability"]),
    ("/reflect", "reflect", ["reflect", "retro", "retrospective", "lessons", "what did we learn", "look back"]),
    ("/continue", "continue", ["continue", "resume", "pick up", "where was i", "what was i doing"]),
    ("/qa", "qa", ["qa", "test the app", "smoke test", "browser test", "functional test"]),
    ("/map", "map", ["map", "ontology", "graph", "dependencies", "structure", "what connects", "what depends"]),
    ("/autoresearch", "autoresearch", ["optimize", "reduce", "increase", "minimize", "maximize", "improve", "iterate until", "autoresearch"]),
]

matches = []
for command, workflow, keywords in rules:
    hit = next((keyword for keyword in keywords if keyword in message), None)
    if not hit:
        continue
    if command == "/design" and any(existing[0] == "/design-review" for existing in matches):
        continue
    matches.append((command, workflow, hit))

if len(matches) == 1:
    command, workflow, keyword = matches[0]
    print(
        "## Sage Auto-Route (deterministic, binding)\n\n"
        f"Latest user message matched keyword `{keyword}`. Required route: `{command}`.\n"
        f"Start `Sage -> {workflow} workflow` unless the user explicitly typed a different slash command.\n"
        "Use the required top-level Sage workflow route. Do not substitute lower-level skill commands "
        "such as `/jtbd`, `/ux-evaluate`, `/analyze-funnel`, `/sage-auto-route`, or `/skills`."
    )
elif len(matches) > 1:
    options = ", ".join(f"{command} ({keyword})" for command, _workflow, keyword in matches)
    print(
        "## Sage Auto-Route (deterministic, binding)\n\n"
        f"Latest user message matched multiple workflows: {options}.\n"
        "Present the matched workflow options instead of choosing silently."
    )
PY
)"
fi

ROUTING_CONTEXT="$(cat <<'EOF'
## Sage Routing Reminder (Hermes always-on)

Before answering the user, classify the latest ask. Do not wait for an explicit slash command.

- explicit slash commands win.
- design review/design audit/design check/visual audit/slop check -> start `Sage -> design-review workflow`
- build/implement/create/add/develop/ship/code/feature -> start `Sage -> build workflow`
- fix/bug/broken/error/crash/failing/debug/issue -> start `Sage -> fix workflow`
- architect/redesign/system design/migrate/rewrite -> start `Sage -> architect workflow`
- understand/research/interview/discover/user needs/jobs to be done -> start `Sage -> research workflow`
- design/wireframe/brief/UX/PRD/prototype/mockup -> start `Sage -> design workflow`
- audit/evaluate/assess/analyze/measure/funnel/usability -> start `Sage -> analyze workflow`
- reflect/retro/retrospective/lessons/what did we learn/look back -> start `Sage -> reflect workflow`
- continue/resume/pick up/where was I/what was I doing -> start `Sage -> continue workflow`
- qa/test the app/smoke test/browser test/functional test -> start `Sage -> qa workflow`
- map/ontology/graph/dependencies/structure/what connects/what depends -> start `Sage -> map workflow`
- optimize/reduce/increase/minimize/maximize/improve/iterate until/autoresearch -> start `Sage -> autoresearch workflow`

If multiple non-explicit workflows match, present the matched workflows as options instead of choosing silently.

For coding work: inspect real files/logs first, patch narrowly, verify with actual output, and restart/check services when runtime behavior changes.
EOF
)"

if [ -n "$AUTO_ROUTE_CONTEXT" ]; then
  ROUTING_CONTEXT="$AUTO_ROUTE_CONTEXT

$ROUTING_CONTEXT"
fi

if [ -z "$CONTEXT" ]; then
  CONTEXT="$ROUTING_CONTEXT"
else
  CONTEXT="$ROUTING_CONTEXT

$CONTEXT"
fi

if command -v python3 >/dev/null 2>&1; then
  printf '%s' "$CONTEXT" | python3 -c 'import json,sys; print(json.dumps({"context": sys.stdin.read()}))'
else
  printf '{}\n'
fi
