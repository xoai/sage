#!/usr/bin/env bash
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"
PLATFORM_DIR="$SAGE_DIR/runtime/platforms/hermes"
PLUGIN_TEMPLATE="$PLATFORM_DIR/plugin-template"
HOOKS_TEMPLATE="$PLATFORM_DIR/hooks"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_PLUGINS_DIR="$HERMES_HOME/plugins"
HERMES_PLUGIN_DIR="$HERMES_PLUGINS_DIR/sage"
HERMES_SKILLS_DIR="$HERMES_HOME/skills"
HERMES_HOOKS_DIR="$HERMES_HOME/hooks"
HERMES_CONFIG="$HERMES_HOME/config.yaml"
RUNTIME_CLI="$SAGE_DIR/runtime/tools/sage_runtime_cli.py"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FIND_BIN="find"
if [ -x /usr/bin/find ]; then
  FIND_BIN="/usr/bin/find"
fi

render_constitution_section() {
  local const_file="${1:-}"
  local section="## Engineering Principles

Base (all projects):
1. Tests before code - every behavior has a test before implementation
2. No silent failures - errors handled, logged, or propagated
3. Secrets never in code - use env vars or secret managers
4. Dependencies explicit - declared with pinned versions
5. Changes reversible - migrations reversible, deployments rollbackable"
  local principle_num=5

  if [ -f "$const_file" ]; then
    local preset=""
    preset="$(sed -n '/^---$/,/^---$/{ /^extends:/s/^extends: *//p; }' "$const_file" 2>/dev/null | head -1)"
    if [ -n "$preset" ] && [ "$preset" != "base" ] && [ "$preset" != "none" ]; then
      local preset_file="$CORE/constitution/presets/${preset}.constitution.md"
      if [ -f "$preset_file" ]; then
        local preset_principles=""
        preset_principles="$(sed -n '/^## Additions/,$ { /^[0-9]/p; }' "$preset_file" 2>/dev/null)"
        if [ -n "$preset_principles" ]; then
          section="$section

${preset} preset:"
          while IFS= read -r line; do
            [ -n "$line" ] || continue
            principle_num=$((principle_num + 1))
            local clean=""
            clean="$(printf '%s\n' "$line" | sed 's/^[0-9]*\. *//')"
            section="$section
${principle_num}. ${clean}"
          done <<< "$preset_principles"
        fi
      fi
    fi

    local project_additions=""
    project_additions="$(sed -n '/^## Project Additions/,$ { /^## Project/d; /^$/d; /^(/d; p; }' "$const_file" 2>/dev/null)"
    if [ -n "$project_additions" ]; then
      section="$section

Project additions:"
      while IFS= read -r line; do
        [ -n "$line" ] || continue
        principle_num=$((principle_num + 1))
        section="$section
${principle_num}. ${line}"
      done <<< "$project_additions"
    fi
  fi

  printf '%s\n' "$section"
}

echo ""
echo "Sage -> Hermes Setup"
echo "===================="
echo "Project:     $SAGE_ROOT"
echo "Hermes home: $HERMES_HOME"

if [ ! -d "$CORE" ]; then
  echo "ERROR: Sage framework not found at $SAGE_DIR" >&2
  exit 1
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Python 3 is required for validated Hermes setup" >&2
  exit 1
fi
if [ ! -f "$RUNTIME_CLI" ]; then
  echo "ERROR: Sage runtime CLI missing: $RUNTIME_CLI" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import yaml' >/dev/null 2>&1; then
  echo "ERROR: PyYAML is required for validated Hermes setup" >&2
  exit 1
fi
if [ ! -f "$PLUGIN_TEMPLATE/__init__.py" ] || [ ! -f "$PLUGIN_TEMPLATE/plugin.yaml" ]; then
  echo "ERROR: Hermes plugin template missing under $PLUGIN_TEMPLATE" >&2
  exit 1
fi
if [ -f "$HERMES_CONFIG" ]; then
  "$PYTHON_BIN" "$RUNTIME_CLI" hooks validate \
    --platform hermes \
    --config "$HERMES_CONFIG" >/dev/null
fi

mkdir -p "$HERMES_HOME" "$HERMES_PLUGINS_DIR" "$HERMES_SKILLS_DIR" "$HERMES_HOOKS_DIR"

echo ""
echo "Generating AGENTS.md..."
source "$SAGE_DIR/runtime/platforms/_shared/instructions-body.sh"
AGENTS_FILE="$SAGE_ROOT/AGENTS.md"
AGENTS_TMP="$(mktemp)"
emit_instructions_body > "$AGENTS_TMP"
CONST_SECTION="$(render_constitution_section "$PROJECT_SAGE/constitution.md")"

"$PYTHON_BIN" - "$AGENTS_TMP" "$CONST_SECTION" <<'PY'
import sys
path, replacement = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
text = text.replace("__CONSTITUTION_PLACEHOLDER__", replacement)
open(path, "w", encoding="utf-8").write(text)
PY

"$PYTHON_BIN" - "$AGENTS_FILE" "$AGENTS_TMP" <<'PY'
import sys
from pathlib import Path

target = Path(sys.argv[1])
generated = Path(sys.argv[2]).read_text(encoding="utf-8").rstrip() + "\n"

start = "<!-- BEGIN SAGE HERMES GENERATED -->"
end = "<!-- END SAGE HERMES GENERATED -->"
managed = f"{start}\n{generated}{end}\n"

if not target.exists():
    target.write_text(managed, encoding="utf-8")
    raise SystemExit(0)

existing = target.read_text(encoding="utf-8")
if start in existing and end in existing:
    before, rest = existing.split(start, 1)
    _, after = rest.split(end, 1)
    target.write_text(before.rstrip() + "\n\n" + managed + after.lstrip(), encoding="utf-8")
    raise SystemExit(0)

sage_heading = "# Sage — Project Instructions"
idx = existing.find(sage_heading)
if idx < 0:
    if existing and not existing.endswith("\n"):
        existing += "\n"
    target.write_text(existing.rstrip() + "\n\n" + managed, encoding="utf-8")
    raise SystemExit(0)

legacy_end = "- `gates/` — quality gate scripts and activation config"
legacy_end_idx = existing.find(legacy_end, idx)
if legacy_end_idx < 0:
    # An unknown markerless Sage block cannot be removed without risking user
    # content. Preserve it intact and append the managed block for future safe
    # replacements.
    target.write_text(existing.rstrip() + "\n\n" + managed, encoding="utf-8")
    raise SystemExit(0)

line_end = existing.find("\n", legacy_end_idx)
if line_end < 0:
    line_end = len(existing)
suffix = existing[line_end:].lstrip()
prefix = existing[:idx].rstrip()
target.write_text(prefix + "\n\n" + managed + suffix, encoding="utf-8")
PY

PROFILE_AGENTS_FILE="$HERMES_HOME/AGENTS.md"
if [ "$PROFILE_AGENTS_FILE" != "$AGENTS_FILE" ]; then
  "$PYTHON_BIN" - "$PROFILE_AGENTS_FILE" "$AGENTS_TMP" <<'PY'
import sys
from pathlib import Path

target = Path(sys.argv[1])
generated = Path(sys.argv[2]).read_text(encoding="utf-8").rstrip() + "\n"

start = "<!-- BEGIN SAGE HERMES GENERATED -->"
end = "<!-- END SAGE HERMES GENERATED -->"
managed = f"{start}\n{generated}{end}\n"

if not target.exists():
    target.write_text(managed, encoding="utf-8")
    raise SystemExit(0)

existing = target.read_text(encoding="utf-8")
if start in existing and end in existing:
    before, rest = existing.split(start, 1)
    _, after = rest.split(end, 1)
    target.write_text(before.rstrip() + "\n\n" + managed + after.lstrip(), encoding="utf-8")
else:
    if existing and not existing.endswith("\n"):
        existing += "\n"
    target.write_text(existing.rstrip() + "\n\n" + managed, encoding="utf-8")
PY
fi
rm -f "$AGENTS_TMP"
echo "  OK AGENTS.md"

echo ""
echo "Updating Hermes profile constitution..."
SOUL_FILE="$HERMES_HOME/SOUL.md"
PROFILE_CONST_FILE="$HERMES_HOME/constitution.md"
if [ ! -f "$PROFILE_CONST_FILE" ]; then
  PROFILE_CONST_FILE="$PROJECT_SAGE/constitution.md"
fi
PROFILE_CONST_SECTION="$(render_constitution_section "$PROFILE_CONST_FILE")"
if [ ! -f "$SOUL_FILE" ]; then
  cat > "$SOUL_FILE" <<'SOUL'
You are Hermes Agent, an intelligent AI assistant created by Nous Research. You are helpful, knowledgeable, and direct.
SOUL
fi
"$PYTHON_BIN" - "$SOUL_FILE" "$PROFILE_CONST_SECTION" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
section = sys.argv[2].rstrip() + "\n"
start = "<!-- BEGIN SAGE PROFILE CONSTITUTION -->"
end = "<!-- END SAGE PROFILE CONSTITUTION -->"
block = f"{start}\n# Sage Profile Constitution\n\n{section}{end}\n"

existing = path.read_text(encoding="utf-8") if path.exists() else ""
if start in existing and end in existing:
    before, rest = existing.split(start, 1)
    _, after = rest.split(end, 1)
    path.write_text(before.rstrip() + "\n\n" + block + after.lstrip(), encoding="utf-8")
else:
    path.write_text(existing.rstrip() + "\n\n" + block, encoding="utf-8")
PY
echo "  OK profile constitution: $SOUL_FILE"

echo ""
echo "Installing Hermes plugin..."
rm -rf "$HERMES_PLUGIN_DIR"
mkdir -p "$HERMES_PLUGIN_DIR"

for subdir in skills agents references scripts; do
  if [ -d "$SAGE_DIR/tools/sage-claude-plugin/$subdir" ]; then
    mkdir -p "$HERMES_PLUGIN_DIR/$subdir"
    cp -R "$SAGE_DIR/tools/sage-claude-plugin/$subdir/." "$HERMES_PLUGIN_DIR/$subdir/"
  fi
done

for workflow in "$SAGE_DIR/core/workflows/"*.workflow.md; do
  [ -f "$workflow" ] || continue
  name="$(basename "$workflow" .workflow.md)"
  dest="$HERMES_PLUGIN_DIR/skills/$name"
  if [ -f "$dest/SKILL.md" ]; then
    continue
  fi
  mkdir -p "$dest"
  cp "$workflow" "$dest/SKILL.md"
done

if [ -f "$PROJECT_SAGE/config.yaml" ] && \
   sed -n '/^multi_agent:/,/^[^[:space:]]/p' "$PROJECT_SAGE/config.yaml" | \
     grep -q '^[[:space:]]*enabled:[[:space:]]*true'; then
  for command in build-x review-spec review-plan implement review-code; do
    source_file="$SAGE_DIR/runtime/multi-agent/commands/$command.md"
    [ -f "$source_file" ] || continue
    dest="$HERMES_PLUGIN_DIR/skills/$command"
    mkdir -p "$dest"
    cp "$source_file" "$dest/SKILL.md"
  done
fi

VERSION="$(grep -m1 '^## \[' "$SAGE_DIR/CHANGELOG.md" 2>/dev/null | sed 's/.*\[\(.*\)\].*/\1/' || true)"
[ -n "$VERSION" ] || VERSION="0.0.0"
sed "s/__SAGE_VERSION__/$VERSION/g" "$PLUGIN_TEMPLATE/plugin.yaml" > "$HERMES_PLUGIN_DIR/plugin.yaml"
cp "$PLUGIN_TEMPLATE/__init__.py" "$HERMES_PLUGIN_DIR/__init__.py"
chmod +x "$HERMES_PLUGIN_DIR/scripts/sage" 2>/dev/null || true

PLUGIN_SKILLS="$("$FIND_BIN" "$HERMES_PLUGIN_DIR/skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
echo "  OK plugin: $HERMES_PLUGIN_DIR ($PLUGIN_SKILLS skills)"

echo ""
echo "Installing top-level Sage skills..."
TOP_COUNT=0
if [ -d "$SAGE_DIR/skills" ]; then
  for skill_dir in "$SAGE_DIR/skills"/*; do
    [ -d "$skill_dir" ] || continue
    [ -f "$skill_dir/SKILL.md" ] || continue
    name="$(basename "$skill_dir")"
    dest="$HERMES_SKILLS_DIR/$name"
    if [ -e "$dest" ] && [ ! -f "$dest/.sage-generated" ]; then
      echo "  SKIP $name (existing non-Sage skill preserved)"
      continue
    fi
    rm -rf "$dest"
    mkdir -p "$dest"
    cp -R "$skill_dir/." "$dest/"
    printf 'generated_by=sage\nsource=%s\n' "$skill_dir" > "$dest/.sage-generated"
    TOP_COUNT=$((TOP_COUNT + 1))
  done
fi
echo "  OK top-level skills copied: $TOP_COUNT"

echo ""
echo "Compiling validated route and composition catalogs..."
"$PYTHON_BIN" "$RUNTIME_CLI" catalog compile \
  --workflow-dir "$CORE/workflows" \
  --platform hermes \
  --command-dir "$HERMES_PLUGIN_DIR/skills" \
  --output "$PROJECT_SAGE/runtime/route-catalog.json" >/dev/null
"$PYTHON_BIN" "$RUNTIME_CLI" composition compile \
  --project "$SAGE_ROOT" \
  --platform hermes \
  --skill-root "$HERMES_PLUGIN_DIR/skills" \
  --skill-root "$HERMES_SKILLS_DIR" \
  --output "$PROJECT_SAGE/composition.json" >/dev/null
echo "  OK route-catalog.json + composition.json"

echo ""
echo "Installing shell hooks and gate scripts..."
for hook in sage-session-init.sh sage-mark-edit.sh; do
  cp "$HOOKS_TEMPLATE/$hook" "$HERMES_HOOKS_DIR/$hook"
done
rm -f "$HERMES_HOOKS_DIR/sage-inject.sh"
for hook in sage-pre-llm.py sage-pre-tool.py sage-learning-recall.py \
  sage-learning-observe.py sage-reflect-checkpoint.py; do
  cp "$HOOKS_TEMPLATE/$hook" "$HERMES_HOOKS_DIR/$hook"
done
rm -rf "$HERMES_HOOKS_DIR/sage_runtime"
cp -R "$SAGE_DIR/runtime/tools/sage_runtime" "$HERMES_HOOKS_DIR/sage_runtime"
cp "$RUNTIME_CLI" "$HERMES_HOOKS_DIR/sage_runtime_cli.py"
cp "$SAGE_DIR/runtime/tools/sage-screenshot.sh" "$HERMES_HOOKS_DIR/sage-screenshot.sh"
for gate in sage-spec-check.sh sage-verify.sh sage-hallucination-check.sh sage-visual-gate.sh; do
  cp "$CORE/gates/scripts/$gate" "$HERMES_HOOKS_DIR/$gate"
done
if [ -f "$HERMES_HOOKS_DIR/sage-visual-gate.sh" ]; then
  "$PYTHON_BIN" - "$HERMES_HOOKS_DIR/sage-visual-gate.sh" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = '''SCREENSHOT_TOOL="$SAGE_ROOT/runtime/tools/sage-screenshot.sh"
if [ ! -f "$SCREENSHOT_TOOL" ]; then
  # Try relative to gate script location
  SCREENSHOT_TOOL="$(cd "$SCRIPT_DIR/../../../runtime/tools" 2>/dev/null && pwd)/sage-screenshot.sh"
fi'''
replacement = '''SCREENSHOT_TOOL="$SCRIPT_DIR/sage-screenshot.sh"
if [ ! -f "$SCREENSHOT_TOOL" ]; then
  SCREENSHOT_TOOL="$SAGE_ROOT/runtime/tools/sage-screenshot.sh"
fi
if [ ! -f "$SCREENSHOT_TOOL" ]; then
  # Try relative to gate script location
  SCREENSHOT_TOOL="$(cd "$SCRIPT_DIR/../../../runtime/tools" 2>/dev/null && pwd)/sage-screenshot.sh"
fi'''
if needle in text and replacement not in text:
    path.write_text(text.replace(needle, replacement), encoding="utf-8")
PY
fi
if [ -f "$CORE/gates/_config/gate-modes.yaml" ]; then
  cp "$CORE/gates/_config/gate-modes.yaml" "$HERMES_HOOKS_DIR/gate-modes.yaml"
fi
chmod +x "$HERMES_HOOKS_DIR"/*.sh 2>/dev/null || true
echo "  OK hooks: $HERMES_HOOKS_DIR"

echo ""
echo "Updating Hermes config..."
"$PYTHON_BIN" - "$HERMES_CONFIG" "$HERMES_HOOKS_DIR" "$PYTHON_BIN" <<'PY'
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

config_path = Path(sys.argv[1])
hooks_dir = Path(sys.argv[2])
python_bin = sys.argv[3]

try:
    import yaml
except Exception:
    yaml = None

def command(script):
    path = (hooks_dir / script).as_posix()
    return f'bash "{path}"'

def python_command(script):
    path = (hooks_dir / script).as_posix()
    return f'"{python_bin}" "{path}"'

if yaml is None:
    raise SystemExit(
        "PyYAML is required to merge Hermes hooks safely; config was not changed"
    )

try:
    loaded = (
        yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if config_path.exists()
        else {}
    )
except (OSError, UnicodeError, yaml.YAMLError) as exc:
    raise SystemExit(
        f"malformed Hermes config {config_path}: {exc}; config was not changed"
    ) from exc
if not isinstance(loaded, dict):
    loaded = {}

plugins = loaded.setdefault("plugins", {})
if not isinstance(plugins, dict):
    plugins = {}
    loaded["plugins"] = plugins
enabled = plugins.setdefault("enabled", [])
if not isinstance(enabled, list):
    enabled = []
    plugins["enabled"] = enabled
if "sage" not in enabled:
    enabled.append("sage")

platform_toolsets = loaded.setdefault("platform_toolsets", {})
if not isinstance(platform_toolsets, dict):
    platform_toolsets = {}
    loaded["platform_toolsets"] = platform_toolsets
if not platform_toolsets:
    platform_toolsets["cli"] = ["hermes-cli"]
acp_toolsets = platform_toolsets.get("acp")
if not isinstance(acp_toolsets, list):
    acp_toolsets = ["hermes-acp"]
    platform_toolsets["acp"] = acp_toolsets
elif "hermes-acp" not in acp_toolsets:
    acp_toolsets.insert(0, "hermes-acp")
for platform, toolsets in list(platform_toolsets.items()):
    if not isinstance(toolsets, list):
        continue
    if "sage" not in toolsets:
        toolsets.append("sage")
    if "delegation" not in toolsets:
        toolsets.append("delegation")

hooks = loaded.setdefault("hooks", {})
if not isinstance(hooks, dict):
    hooks = {}
    loaded["hooks"] = hooks

managed_scripts = {
    "sage-session-init.sh",
    "sage-inject.sh",
    "sage-mark-edit.sh",
    "sage-pre-llm.py",
    "sage-pre-tool.py",
    "sage-learning-recall.py",
    "sage-learning-observe.py",
    "sage-reflect-checkpoint.py",
}

sage_quick_commands = [
    "sage",
    "build",
    "fix",
    "architect",
    "analyze",
    "learn",
    "map",
    "qa",
    "reflect",
    "research",
    "review",
    "sage-status",
    "design",
    "design-review",
    "continue",
    "autoresearch",
]

for event, current in list(hooks.items()):
    if not isinstance(current, list):
        continue
    hooks[event] = [
        item for item in current
        if not (
            isinstance(item, dict)
            and any(script in item.get("command", "") for script in managed_scripts)
        )
    ]

def upsert(event, entry):
    current = hooks.get(event)
    if not isinstance(current, list):
        current = []
    filtered = []
    for item in current:
        cmd = item.get("command", "") if isinstance(item, dict) else ""
        if any(script in cmd for script in managed_scripts):
            continue
        filtered.append(item)
    filtered.append(entry)
    hooks[event] = filtered

upsert("on_session_start", {"command": command("sage-session-init.sh"), "timeout": 10})
upsert(
    "post_tool_call",
    {
        "matcher": "write_file|patch|apply_patch|Edit|Write|MultiEdit|write|edit",
        "command": command("sage-mark-edit.sh"),
        "timeout": 10,
    },
)

def hook_mtime(script):
    path = hooks_dir / script
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return None

allowlist_path = config_path.parent / "shell-hooks-allowlist.json"
try:
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
except Exception:
    allowlist = {"approvals": []}
if not isinstance(allowlist, dict):
    allowlist = {"approvals": []}
approvals = allowlist.get("approvals")
if not isinstance(approvals, list):
    approvals = []
owned_approvals = [
    ("on_session_start", command("sage-session-init.sh"), "sage-session-init.sh"),
    ("post_tool_call", command("sage-mark-edit.sh"), "sage-mark-edit.sh"),
    ("pre_llm_call", python_command("sage-pre-llm.py"), "sage-pre-llm.py"),
    ("pre_tool_call", python_command("sage-pre-tool.py"), "sage-pre-tool.py"),
    ("pre_llm_call", python_command("sage-learning-recall.py"), "sage-learning-recall.py"),
    ("post_tool_call", python_command("sage-learning-observe.py"), "sage-learning-observe.py"),
    ("on_session_end", python_command("sage-learning-observe.py"), "sage-learning-observe.py"),
    ("on_session_finalize", python_command("sage-learning-observe.py"), "sage-learning-observe.py"),
    ("pre_verify", python_command("sage-reflect-checkpoint.py"), "sage-reflect-checkpoint.py"),
]
owned_keys = {(event, cmd) for event, cmd, _ in owned_approvals}
approvals = [
    entry for entry in approvals
    if not (
        isinstance(entry, dict)
        and (entry.get("event"), entry.get("command")) in owned_keys
    )
]
now = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
for event, cmd, script in owned_approvals:
    approvals.append({
        "event": event,
        "command": cmd,
        "approved_at": now,
        "script_mtime_at_approval": hook_mtime(script),
    })
allowlist["approvals"] = approvals
allowlist_path.write_text(json.dumps(allowlist, indent=2, sort_keys=True), encoding="utf-8")

quick_commands = loaded.setdefault("quick_commands", {})
if not isinstance(quick_commands, dict):
    quick_commands = {}
    loaded["quick_commands"] = quick_commands
for name in sage_quick_commands:
    current = quick_commands.get(name)
    if isinstance(current, dict) and current.get("_sage_generated"):
        current["type"] = "alias"
        current["target"] = f"/{name}"
        continue
    if name not in quick_commands:
        quick_commands[name] = {
            "type": "alias",
            "target": f"/{name}",
            "_sage_generated": True,
        }

temporary = config_path.with_name(f".{config_path.name}.sage.tmp")
temporary.write_text(yaml.safe_dump(loaded, sort_keys=False), encoding="utf-8")
temporary.replace(config_path)
PY
echo "  OK config: $HERMES_CONFIG"

"$PYTHON_BIN" "$RUNTIME_CLI" hooks install \
  --platform hermes \
  --config "$HERMES_CONFIG" \
  --route-command "\"$PYTHON_BIN\" \"$HERMES_HOOKS_DIR/sage-pre-llm.py\"" \
  --gate-command "\"$PYTHON_BIN\" \"$HERMES_HOOKS_DIR/sage-pre-tool.py\"" \
  --learning-recall-command "\"$PYTHON_BIN\" \"$HERMES_HOOKS_DIR/sage-learning-recall.py\"" \
  --learning-observe-command "\"$PYTHON_BIN\" \"$HERMES_HOOKS_DIR/sage-learning-observe.py\"" \
  --reflect-command "\"$PYTHON_BIN\" \"$HERMES_HOOKS_DIR/sage-reflect-checkpoint.py\"" >/dev/null
echo "  OK deterministic route, gate, recall, learning, and reflection hooks"

echo ""
echo "Sage -> Hermes setup complete"
echo "  AGENTS.md"
echo "  $HERMES_PLUGIN_DIR"
echo "  $HERMES_SKILLS_DIR"
echo "  $HERMES_HOOKS_DIR"
echo ""
echo "Next: start Hermes with HERMES_HOME=$HERMES_HOME and use /sage or /build."
