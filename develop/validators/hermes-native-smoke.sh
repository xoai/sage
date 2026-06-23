#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(pwd)}"
ROOT="$(cd "$ROOT" && pwd -P)"
WORK="${TMPDIR:-/tmp}/sage-hermes-native-smoke-$$"
PROJECT="$WORK/project"
DEFAULT_PROJECT="$WORK/default-project"
HERMES_HOME_SMOKE="$WORK/hermes-home"
DEFAULT_HOME_SMOKE="$WORK/default-home"
PROFILE_HOME_SMOKE="$WORK/profile-home"
HOME_SMOKE="$WORK/home"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ -f "$ROOT/bin/sage" ] || fail "missing bin/sage under $ROOT"
[ -d "$ROOT/runtime/platforms/hermes" ] || fail "missing runtime/platforms/hermes"
[ ! -d "$ROOT/runtime/platforms/hermes/.claude-plugin" ] || fail "Hermes adapter must not contain .claude-plugin"
[ -f "$ROOT/runtime/platforms/hermes/setup/generate-hermes.sh" ] || fail "missing generate-hermes.sh"
[ -f "$ROOT/runtime/platforms/hermes/plugin-template/__init__.py" ] || fail "missing Hermes plugin __init__.py"

rm -rf "$WORK"
mkdir -p "$PROJECT" "$DEFAULT_PROJECT" "$HERMES_HOME_SMOKE" "$DEFAULT_HOME_SMOKE" "$PROFILE_HOME_SMOKE" "$HOME_SMOKE"
cat > "$HERMES_HOME_SMOKE/constitution.md" <<'YAML'
---
name: smoke-hermes
tier: 2
extends: opensource
---

# Constitution - smoke Hermes profile

## Project Additions

(none)
YAML

(
  cd "$PROJECT"
  HOME="$HOME_SMOKE" HERMES_HOME="$HERMES_HOME_SMOKE" bash "$ROOT/bin/sage" init --platform hermes --no-memory
)

[ -f "$PROJECT/AGENTS.md" ] || fail "AGENTS.md was not generated"
[ ! -d "$PROJECT/.claude" ] || fail ".claude must not be generated for Hermes"
[ -f "$PROJECT/.sage/config.yaml" ] || fail ".sage/config.yaml was not generated"
[ -f "$HERMES_HOME_SMOKE/plugins/sage/plugin.yaml" ] || fail "plugin.yaml was not installed"
[ -f "$HERMES_HOME_SMOKE/plugins/sage/__init__.py" ] || fail "__init__.py was not installed"
[ -f "$HERMES_HOME_SMOKE/plugins/sage/skills/build/SKILL.md" ] || fail "bundled build skill missing"
[ -f "$HERMES_HOME_SMOKE/plugins/sage/skills/autoresearch/SKILL.md" ] || fail "bundled autoresearch workflow missing"
[ -f "$HERMES_HOME_SMOKE/plugins/sage/skills/map/SKILL.md" ] || fail "bundled map workflow missing"
[ -f "$HERMES_HOME_SMOKE/skills/api/SKILL.md" ] || fail "top-level api skill missing"
[ -f "$HERMES_HOME_SMOKE/hooks/sage-session-init.sh" ] || fail "session hook missing"
[ -f "$HERMES_HOME_SMOKE/hooks/sage-inject.sh" ] || fail "pre_llm_call inject hook missing"
[ -f "$HERMES_HOME_SMOKE/hooks/sage-mark-edit.sh" ] || fail "post_tool_call edit marker hook missing"
[ -f "$HERMES_HOME_SMOKE/hooks/sage-screenshot.sh" ] || fail "screenshot helper missing"
[ -f "$HERMES_HOME_SMOKE/hooks/sage-verify.sh" ] || fail "verify gate missing"
[ -f "$HERMES_HOME_SMOKE/SOUL.md" ] || fail "profile SOUL.md missing"
[ -f "$HERMES_HOME_SMOKE/config.yaml" ] || fail "Hermes config.yaml missing"
grep -q "Sage Profile Constitution" "$HERMES_HOME_SMOKE/SOUL.md" || fail "profile constitution missing from SOUL.md"
grep -q "opensource preset" "$HERMES_HOME_SMOKE/SOUL.md" || fail "opensource constitution preset missing from SOUL.md"
grep -q "enabled:" "$HERMES_HOME_SMOKE/config.yaml" || fail "plugins.enabled missing from config"
grep -q "sage" "$HERMES_HOME_SMOKE/config.yaml" || fail "sage not enabled in config"
grep -q "on_session_start" "$HERMES_HOME_SMOKE/config.yaml" || fail "on_session_start hook missing"
grep -q "pre_llm_call" "$HERMES_HOME_SMOKE/config.yaml" || fail "pre_llm_call hook missing"
grep -q "post_tool_call" "$HERMES_HOME_SMOKE/config.yaml" || fail "post_tool_call hook missing"
grep -q "sage-inject.sh" "$HERMES_HOME_SMOKE/config.yaml" || fail "sage-inject.sh not registered"
grep -q "sage-mark-edit.sh" "$HERMES_HOME_SMOKE/config.yaml" || fail "sage-mark-edit.sh not registered"
grep -q "quick_commands:" "$HERMES_HOME_SMOKE/config.yaml" || fail "desktop quick_commands missing from config"
grep -q "sage-status:" "$HERMES_HOME_SMOKE/config.yaml" || fail "sage-status quick command missing from config"
grep -q "platform_toolsets:" "$HERMES_HOME_SMOKE/config.yaml" || fail "platform_toolsets missing from config"
grep -q "acp:" "$HERMES_HOME_SMOKE/config.yaml" || fail "ACP toolset config missing"
grep -q "hermes-acp" "$HERMES_HOME_SMOKE/config.yaml" || fail "Hermes ACP base toolset missing from config"
grep -q "sage" "$HERMES_HOME_SMOKE/config.yaml" || fail "sage toolset missing from config"
grep -q "delegation" "$HERMES_HOME_SMOKE/config.yaml" || fail "delegation toolset missing from config"
[ -f "$HERMES_HOME_SMOKE/shell-hooks-allowlist.json" ] || fail "shell hook allowlist missing"
grep -q "sage-session-init.sh" "$HERMES_HOME_SMOKE/shell-hooks-allowlist.json" || fail "session hook not allowlisted"
grep -q "sage-inject.sh" "$HERMES_HOME_SMOKE/shell-hooks-allowlist.json" || fail "inject hook not allowlisted"
grep -q "sage-mark-edit.sh" "$HERMES_HOME_SMOKE/shell-hooks-allowlist.json" || fail "mark-edit hook not allowlisted"

python3 - "$HERMES_HOME_SMOKE/plugins/sage" "$PROJECT" <<'PY'
import importlib.util
import json
import pathlib
import sys

plugin = pathlib.Path(sys.argv[1])
project = pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("sage_plugin_smoke", plugin / "__init__.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

class Context:
    def __init__(self):
        self.commands = {}
        self.skills = {}
        self.tools = {}
        self.builtins = {"status"}

    def register_command(self, name, handler, description="", args_hint=""):
        if name in self.builtins:
            return
        self.commands[name] = (handler, description, args_hint)

    def register_skill(self, name, path, description=""):
        self.skills[name] = (path, description)

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = (toolset, schema, handler, kwargs)

ctx = Context()
module.register(ctx)
for name in ["sage", "build", "fix", "architect", "review", "autoresearch", "map", "sage-status"]:
    if name not in ctx.commands:
        raise SystemExit(f"missing slash command: {name}")
if "status" in ctx.commands:
    raise SystemExit("Hermes plugin must not register conflicting /status")
if "build" not in ctx.skills:
    raise SystemExit("missing registered build skill")
for name in ["sage_spec_check", "sage_hallucination_check", "sage_verify", "sage_visual_gate", "sage_run_gates"]:
    if name not in ctx.tools:
        raise SystemExit(f"missing registered Sage tool: {name}")
if ctx.tools["sage_verify"][0] != "sage":
    raise SystemExit("Sage tools must register under the sage toolset")
gate_result = json.loads(ctx.tools["sage_run_gates"][2]({"mode": "fix", "cwd": str(project)}))
if not gate_result.get("ok"):
    raise SystemExit(f"sage_run_gates fix mode did not pass script checks: {gate_result}")
if gate_result.get("all_gates_complete"):
    raise SystemExit("sage_run_gates must require agent review after script checks")
if "hallucination-check" not in gate_result.get("active_gates", []):
    raise SystemExit("sage_run_gates did not activate hallucination-check for fix mode")
body = ctx.commands["build"][0]("")
if "Build Workflow" not in body:
    raise SystemExit("build command handler did not return workflow text")
if "sage_run_gates" not in body:
    raise SystemExit("build command handler did not include Hermes gate adapter note")
if "delegate_task" not in body:
    raise SystemExit("build command handler did not include Hermes delegate_task adapter note")
review_body = ctx.commands["review"][0]("")
if "sub-agent" in review_body.lower() and "delegate_task" not in review_body:
    raise SystemExit("review command handler did not map sub-agent work to delegate_task")
PY

SESSION_OUT="$WORK/session-init.out"
printf '{"cwd":"%s","hook_event_name":"on_session_start","session_id":"smoke"}\n' "$PROJECT" \
  | bash "$HERMES_HOME_SMOKE/hooks/sage-session-init.sh" >"$SESSION_OUT"
python3 - "$SESSION_OUT" <<'PY'
import json
import sys
data = json.loads(open(sys.argv[1], encoding="utf-8").read())
if "Sage Context" not in data.get("context", ""):
    raise SystemExit("session hook did not emit JSON Sage Context")
PY

INJECT_OUT="$WORK/sage-inject.out"
printf '{"cwd":"%s","hook_event_name":"pre_llm_call","session_id":"smoke"}\n' "$PROJECT" \
  | bash "$HERMES_HOME_SMOKE/hooks/sage-inject.sh" >"$INJECT_OUT"
python3 - "$INJECT_OUT" <<'PY'
import json
import sys
data = json.loads(open(sys.argv[1], encoding="utf-8").read())
if "Sage Context" not in data.get("context", ""):
    raise SystemExit("pre_llm_call hook did not emit JSON context")
if "Sage Routing Reminder" not in data.get("context", ""):
    raise SystemExit("pre_llm_call hook did not prepend always-on routing reminder")
PY

NON_SAGE_DIR="$WORK/non-sage"
mkdir -p "$NON_SAGE_DIR"
INJECT_FALLBACK_OUT="$WORK/sage-inject-fallback.out"
printf '{"cwd":"%s","hook_event_name":"pre_llm_call","session_id":"smoke"}\n' "$NON_SAGE_DIR" \
  | bash "$HERMES_HOME_SMOKE/hooks/sage-inject.sh" >"$INJECT_FALLBACK_OUT"
python3 - "$INJECT_FALLBACK_OUT" <<'PY'
import json
import sys
data = json.loads(open(sys.argv[1], encoding="utf-8").read())
context = data.get("context", "")
if "Sage Routing Reminder" not in context:
    raise SystemExit("pre_llm_call hook did not emit always-on routing reminder outside a Sage project")
if "Sage Context" in context:
    raise SystemExit("pre_llm_call fallback unexpectedly emitted project context outside a Sage project")
PY

printf '{"cwd":"%s","hook_event_name":"post_tool_call","session_id":"smoke","tool_name":"write_file"}\n' "$PROJECT" \
  | bash "$HERMES_HOME_SMOKE/hooks/sage-mark-edit.sh" >/dev/null
[ -f "$PROJECT/.sage/.last-edit" ] || fail "post_tool_call hook did not mark edit"

(
  cd "$DEFAULT_PROJECT"
  HOME="$DEFAULT_HOME_SMOKE" HERMES_HOME= bash "$ROOT/bin/sage" init --platform hermes --no-memory >/dev/null
)
[ -f "$DEFAULT_HOME_SMOKE/.hermes/plugins/sage/plugin.yaml" ] || fail "default ~/.hermes plugin install missing"
[ -f "$DEFAULT_HOME_SMOKE/.hermes/config.yaml" ] || fail "default ~/.hermes config missing"

HERMES_HOME="$PROFILE_HOME_SMOKE" bash "$DEFAULT_PROJECT/sage/runtime/platforms/hermes/setup/generate-hermes.sh" "$DEFAULT_PROJECT" >/dev/null
[ -f "$PROFILE_HOME_SMOKE/plugins/sage/plugin.yaml" ] || fail "profile Hermes plugin install missing"
[ -f "$PROFILE_HOME_SMOKE/config.yaml" ] || fail "profile Hermes config missing"
[ -f "$DEFAULT_HOME_SMOKE/.hermes/plugins/sage/plugin.yaml" ] || fail "default Hermes install was not preserved after profile install"

echo "PASS: Hermes native smoke"
