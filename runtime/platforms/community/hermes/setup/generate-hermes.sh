#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# generate-hermes.sh — generate Sage artifacts for Hermes Agent
#
# Usage:
#   sage init --platform hermes
#   bash runtime/platforms/community/hermes/setup/generate-hermes.sh <project-root>
#
# What it does (parity with generate-claude-code.sh):
#   1. Creates .sage/ directory structure (work, gates, tmp)
#   2. Writes <workspace>/.hermes.md from the canonical shared
#      instructions body (spec 3/5.2.2; Hermes loads it as project
#      instructions — same role CLAUDE.md plays on Claude Code).
#      Hermes-only generation never creates a workspace SOUL.md.
#   3. Copies gate hook scripts to .sage/gates/ (claude-code parity:
#      it copies hook scripts into the project so they travel with it)
#   4. Installs the Sage plugin into the active Hermes profile
#      (copy + `hermes plugins enable sage`) — Hermes has no plugin
#      marketplace, so file-copy IS the distribution path
#   5. Verifies the plugin is registered and prints next steps
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT_ROOT="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Layout resolution: in a repo checkout this script sits at
# runtime/platforms/community/hermes/setup/ (5 dirs below the root);
# in a vendored install the same tree lives under <project>/sage/.
# Walk up until we find runtime/platforms to anchor everything else.
_probe="$SCRIPT_DIR"
SAGE_ROOT=""
for _ in 1 2 3 4 5 6 7 8; do
  if [ -d "$_probe/runtime/platforms" ]; then SAGE_ROOT="$_probe"; break; fi
  _probe="$(dirname "$_probe")"
  [ "$_probe" = "/" ] || [ "$_probe" = "." ] && break
done
if [ -z "$SAGE_ROOT" ]; then
  echo -e "  \033[0;33m⚠ Could not locate the sage framework root — run from a sage checkout or vendored install\033[0m" >&2
  exit 1
fi
PLATFORM_ROOT="$SAGE_ROOT/runtime/platforms"
HERMES_PLATFORM_ROOT="$PLATFORM_ROOT/community/hermes"
SHARED="$PLATFORM_ROOT/_shared"
# core/ lives at the repo root in a checkout, under sage/ when vendored
if [ -d "$SAGE_ROOT/sage/core" ]; then
  CORE="$SAGE_ROOT/sage/core"
else
  CORE="$SAGE_ROOT/core"
fi

# Hermes generation is always one explicitly bound profile.  Validate the
# complete selection before creating project state or touching any profile;
# direct/non-interactive invocation must never fall back to profile discovery.
for _required in SAGE_HERMES_COLLECTION_ROOT SAGE_HERMES_PROFILE \
                 SAGE_HERMES_PROFILE_ROOT SAGE_HERMES_WORKSPACE_ROOT; do
  if [ -z "${!_required:-}" ]; then
    echo "  explicit Hermes profile binding is required before generation" >&2
    echo "  Run: sage init --platform hermes --hermes-home <collection> --hermes-profile <name>" >&2
    exit 1
  fi
done
if ! [[ "$SAGE_HERMES_PROFILE" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]]; then
  echo "  invalid Hermes profile name: $SAGE_HERMES_PROFILE" >&2
  exit 1
fi
for _required_dir in "$PROJECT_ROOT" "$SAGE_HERMES_COLLECTION_ROOT" \
                     "$SAGE_HERMES_PROFILE_ROOT" "$SAGE_HERMES_WORKSPACE_ROOT"; do
  if [ ! -d "$_required_dir" ]; then
    echo "  Hermes binding directory does not exist: $_required_dir" >&2
    exit 1
  fi
done

PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd -P)"
SAGE_HERMES_COLLECTION_ROOT="$(cd "$SAGE_HERMES_COLLECTION_ROOT" && pwd -P)"
SAGE_HERMES_PROFILE_ROOT="$(cd "$SAGE_HERMES_PROFILE_ROOT" && pwd -P)"
SAGE_HERMES_WORKSPACE_ROOT="$(cd "$SAGE_HERMES_WORKSPACE_ROOT" && pwd -P)"
_expected_profile="$SAGE_HERMES_COLLECTION_ROOT/profiles/$SAGE_HERMES_PROFILE"
_expected_workspace="$_expected_profile/workspace"
if [ ! -d "$_expected_profile" ] || \
   [ "$(cd "$_expected_profile" && pwd -P)" != "$SAGE_HERMES_PROFILE_ROOT" ]; then
  echo "  Hermes profile binding does not match collection/profiles/profile_id" >&2
  exit 1
fi
if [ ! -d "$_expected_workspace" ] || \
   [ "$(cd "$_expected_workspace" && pwd -P)" != "$SAGE_HERMES_WORKSPACE_ROOT" ]; then
  echo "  Hermes workspace binding must be the selected profile's workspace" >&2
  exit 1
fi
if [ "$PROJECT_ROOT" != "$SAGE_HERMES_WORKSPACE_ROOT" ]; then
  echo "  Hermes generation must target the selected profile workspace" >&2
  echo "  selected: $SAGE_HERMES_WORKSPACE_ROOT" >&2
  echo "  target:   $PROJECT_ROOT" >&2
  exit 1
fi
HERMES_HOME="$SAGE_HERMES_COLLECTION_ROOT"
export HERMES_HOME SAGE_HERMES_COLLECTION_ROOT SAGE_HERMES_PROFILE \
  SAGE_HERMES_PROFILE_ROOT SAGE_HERMES_WORKSPACE_ROOT

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RESET='\033[0m'

echo ""
echo -e "  ${BOLD}Sage for Hermes Agent${RESET}"
echo ""

# ── Create .sage directory structure ──
mkdir -p "$PROJECT_ROOT/.sage"/{work,gates,tmp}
echo -e "  ${GREEN}✓${RESET} Created .sage/ directory"

# ── Write default config.yaml (gates are opt-in per project) ──
CONFIG="$PROJECT_ROOT/.sage/config.yaml"
if [ ! -f "$CONFIG" ]; then
  cat > "$CONFIG" << 'EOF'
# Sage enforcement configuration
# All gates are opt-in — set to true to enable enforcement.
# Gates only fire in sessions whose cwd contains this file:
# enrolling a project never locks down anything outside it.

hard_enforcement: true    # master switch — gates are inert when false
tdd_enforcement: true     # tdd-gate: tests before code (Rule 1)
secrets_gate: true        # secrets-gate: no hardcoded credentials
verify_gate: true         # verify-gate: verify before claiming (Rule 5)
bookkeeping_gate: true    # bookkeeping-gate: one-command close-out

# Review loop configuration
review_loop:
  mode: v2                # v2 = witness capping, v1 = unlimited
  witness_capping: true   # cap witnesses to prevent runaway review

# Auto-QA configuration
auto_qa: true             # dispatch subagent for independent review (when available)
EOF
  echo -e "  ${GREEN}✓${RESET} Wrote .sage/config.yaml"
else
  echo -e "  ${CYAN}⊘${RESET} .sage/config.yaml already exists, skipping"
fi

# ── Write .gitignore for .sage ──
GITIGNORE="$PROJECT_ROOT/.sage/.gitignore"
if [ ! -f "$GITIGNORE" ]; then
  cat > "$GITIGNORE" << 'EOF'
# Sage runtime state
.session-lock
tmp/
gates/session-pickup.md
gates/session-log
gates/gate-blocks.log
EOF
  echo -e "  ${GREEN}✓${RESET} Wrote .sage/.gitignore"
fi

# ── Write .hermes.md from the canonical shared instructions body ──
# Spec 3: Hermes-only generation MUST NOT create CLAUDE.md, .claude, or a
# workspace SOUL.md. The canonical Hermes instructions surface is
# <workspace>/.hermes.md (spec 5.2.2), loaded by Hermes as project
# instructions. Claude Code parity: generate-claude-code.sh emits the same
# body into CLAUDE.md via emit_instructions_body, then merges the
# constitution section.
HERMES_MD="$PROJECT_ROOT/.hermes.md"
if [ ! -f "$HERMES_MD" ]; then
  if [ -f "$SHARED/instructions-body.sh" ] && [ -f "$SHARED/constitution.sh" ]; then
    # shellcheck source=../../../_shared/instructions-body.sh
    source "$SHARED/instructions-body.sh"
    # shellcheck source=../../../_shared/constitution.sh
    source "$SHARED/constitution.sh"
    emit_instructions_body > "$HERMES_MD"
    CONST_SECTION="$(build_constitution_section "$CORE" "$PROJECT_ROOT/.sage")"
    if [ -n "$CONST_SECTION" ]; then
      # MSYS guard: python3 on Windows needs a native path for the file.
      if command -v cygpath >/dev/null 2>&1; then
        HERMES_MD_ARG="$(cygpath -w "$HERMES_MD")"
      else
        HERMES_MD_ARG="$HERMES_MD"
      fi
      python3 - "$HERMES_MD_ARG" "$CONST_SECTION" << 'PYEOF'
import sys
path, section = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    content = fh.read()
content = content.replace("__CONSTITUTION_PLACEHOLDER__", section)
with open(path, "w", encoding="utf-8") as fh:
    fh.write(content)
PYEOF
    fi
    echo -e "  ${GREEN}✓${RESET} Wrote .hermes.md (canonical instructions + constitution)"
  else
    echo -e "  ${YELLOW}⚠ Shared emitters not found — .hermes.md not generated (run from a full sage checkout)${RESET}"
  fi
else
  echo -e "  ${CYAN}⊘${RESET} .hermes.md already exists, skipping"
fi

# ═══════════════════════════════════════════════════════════════
# Enforcement hooks — canonical registration (claude-code parity)
# ═══════════════════════════════════════════════════════════════
# On Claude Code, generate-claude-code.sh copies the gate scripts into
# .claude/hooks/ and registers them in settings.json OUTSIDE the plugin.
# On Hermes the canonical equivalent (docs: user-guide/features/hooks) is:
#   1. scripts live in the selected profile's hook directory
#   2. registration via the hooks: block in the profile's config.yaml
#   3. JSON wire protocol: {"decision":"block","reason":...} on stdout
#
# The claude-code gate scripts speak their own wire format (exit 2 +
# stderr, tool_input.file_path), so we ship ONE adapter
# (sage-hermes-gate.sh) that translates Hermes payloads and decisions.
# The gate scripts stay the single source of decision logic.
#
# Registration is PER PROFILE — the CLI has already frozen exactly one profile
# and workspace, and this generator must not enumerate or infer siblings.

CC_HOOKS_SRC="$SAGE_ROOT/runtime/platforms/claude-code/hooks"
HERMES_HOOKS_SRC="$HERMES_PLATFORM_ROOT/hooks"
ADAPTER_SRC="$HERMES_HOOKS_SRC/sage-hermes-gate.sh"

# (event, matcher, script) — mirrors the claude-code WANTED table so
# enforcement behavior is identical across platforms. Matchers use
# Hermes tool names: write_file|patch (file edits), terminal (shell).
# The on_session_start entry uses matcher=null: the session script is
# dispatched directly (no sage-hermes-gate.sh adapter), matching
# profile_installer._command_value's command shape for sage-session-init.sh.
HOOKS_WANTED='[
  ["on_session_start", null, "sage-session-init.sh"],
  ["pre_tool_call",  "write_file|patch", "sage-spec-gate.sh"],
  ["pre_tool_call",  "write_file|patch", "sage-tdd-gate.sh"],
  ["pre_tool_call",  "write_file|patch", "sage-bookkeeping-gate.sh"],
  ["pre_tool_call",  "write_file|patch", "sage-secrets-gate.sh"],
  ["pre_tool_call",  "terminal",         "sage-verify-gate.sh"],
  ["post_tool_call", "write_file|patch|terminal", "sage-verify-tracker.sh"],
  ["pre_tool_call",  "write_file|patch|terminal", "sage-config-gate.sh"],
  ["pre_tool_call",  "write_file|patch", "sage-scope-gate.sh"],
  ["post_tool_call", "write_file|patch", "sage-degradation-log.sh"],
  ["post_tool_call", "write_file|patch", "sage-manifest-sync.sh"],
  ["post_tool_call", "write_file|patch|terminal", "sage-scope-journal.sh"]
]'

if [ ! -d "$CC_HOOKS_SRC" ]; then
  echo -e "  ${YELLOW}⚠ claude-code hook sources not found at $CC_HOOKS_SRC — skipping hook install${RESET}"
else
  SELECTED_PROFILES=("$SAGE_HERMES_PROFILE")
  SKIPPED_PROFILES=()

  echo ""
  echo -e "  Installing Sage for profiles: ${SELECTED_PROFILES[*]+"${SELECTED_PROFILES[*]}"}"
  echo ""

  for PROFILE in ${SELECTED_PROFILES[@]+"${SELECTED_PROFILES[@]}"}; do
    echo -e "  ${BOLD}── Profile: $PROFILE${RESET}"
    PROF_ROOT="$SAGE_HERMES_PROFILE_ROOT"
    DEST_HOOKS="$PROF_ROOT/hooks"
    DEST_PLUGIN="$PROF_ROOT/plugins/sage"

    # Preflight Git ownership before touching hooks, config, plugin bytes, or
    # enablement.  A refused profile must be wholly skipped, never left with a
    # half-installed registry pointing at a checkout Sage did not update.
    if [ -e "$DEST_PLUGIN/.git" ] &&
       [ "$(cd "$DEST_PLUGIN" && pwd -P)" != "$(cd "$SAGE_ROOT" && pwd -P)" ]; then
      echo -e "    ${YELLOW}⚠ Refusing to overwrite Git-managed plugin at $DEST_PLUGIN${RESET}" >&2
      echo "      Update that checkout directly; Sage cannot verify it from a separate framework copy." >&2
      SKIPPED_PROFILES+=("$PROFILE")
      continue
    fi

    if [ "${SAGE_HERMES_TRANSACTIONAL_INIT:-0}" = "1" ]; then
      # Transactional init (T26/BD-4): profile_installer.install owns the
      # profile's hook scripts, plugin bytes, and the exact 7+4 registry.
      # The generator contributes workspace surfaces + the binding block only.
      echo -e "    ${CYAN}⊘${RESET} Transactional init: hook/plugin bytes owned by profile_installer.install"
    else
    # 1. Gate scripts + adapter → <profile>/hooks/ (flat — Hermes hook
    #    homes carry no bundle subfolders, per the 2026-08-10 layout ruling)
    mkdir -p "$DEST_HOOKS"
    for g in sage-spec-gate.sh sage-tdd-gate.sh sage-secrets-gate.sh \
             sage-bookkeeping-gate.sh sage-config-gate.sh sage-verify-gate.sh \
             sage-verify-tracker.sh sage-degradation-log.sh sage-manifest-sync.sh \
             sage-scope-gate.sh sage-scope-journal.sh; do
      [ -f "$CC_HOOKS_SRC/$g" ] && cp "$CC_HOOKS_SRC/$g" "$DEST_HOOKS/$g"
    done
    cp "$ADAPTER_SRC" "$DEST_HOOKS/sage-hermes-gate.sh"
    cp "$HERMES_HOOKS_SRC/sage-session-init.sh" "$DEST_HOOKS/" 2>/dev/null || true
    chmod +x "$DEST_HOOKS"/*.sh 2>/dev/null || true
    echo -e "    ${GREEN}✓${RESET} Gate scripts → $DEST_HOOKS"

    # 2. Plugin → <profile>/plugins/sage (skills, injection, commands)
    mkdir -p "$(dirname "$DEST_PLUGIN")"
    if [ -d "$DEST_PLUGIN" ] &&
       [ "$(cd "$DEST_PLUGIN" && pwd -P)" = "$(cd "$SAGE_ROOT" && pwd -P)" ]; then
      echo -e "    ${CYAN}⊘${RESET} Plugin source is already installed at $DEST_PLUGIN"
    else
      PLUGIN_STAGE="${DEST_PLUGIN}.sage-stage.$$"
      rm -rf "$PLUGIN_STAGE"
      cp -r "$SAGE_ROOT" "$PLUGIN_STAGE"
      rm -rf "$PLUGIN_STAGE/.git" "$PLUGIN_STAGE/.worktrees" "$PLUGIN_STAGE/node_modules" 2>/dev/null || true
      mkdir -p "$DEST_PLUGIN"
      # Copy fresh bytes, then sweep files that no longer exist upstream so
      # skills/gates removed from the framework do not linger across updates
      # (the stale-artifact class the repo's Gate-4 history is about).
      cp -r "$PLUGIN_STAGE"/. "$DEST_PLUGIN"/
      # Walk from inside DEST_PLUGIN so paths are dot-relative — this avoids
      # MSYS path conversion mangling the prefix-strip semantics on Windows.
      while IFS= read -r -d '' rel; do
        if [ "$rel" = "." ] || [ -z "$rel" ]; then continue; fi
        if [ ! -e "$PLUGIN_STAGE/$rel" ]; then
          rm -rf "$DEST_PLUGIN/$rel"
        fi
      done < <(cd "$DEST_PLUGIN" && find . -mindepth 1 -print0)
      rm -rf "$PLUGIN_STAGE"
      echo -e "    ${GREEN}✓${RESET} Plugin refreshed → $DEST_PLUGIN"
    fi
    fi

    # 3. Register hooks in <profile>/config.yaml (idempotent merge).
    # MSYS guard: python3 on Windows needs native paths, not /<drive>/... style.
    CONFIG_YAML="$PROF_ROOT/config.yaml"
    if command -v cygpath >/dev/null 2>&1; then
      CONFIG_YAML_ARG="$(cygpath -w "$CONFIG_YAML")"
      DEST_HOOKS_ARG="$(cygpath -w "$DEST_HOOKS")"
      BINDING_COLLECTION_ARG="$(cygpath -w "$SAGE_HERMES_COLLECTION_ROOT")"
      BINDING_PROFILE_ROOT_ARG="$(cygpath -w "$SAGE_HERMES_PROFILE_ROOT")"
      BINDING_WORKSPACE_ARG="$(cygpath -w "$SAGE_HERMES_WORKSPACE_ROOT")"
      SETUP_DIR_ARG="$(cygpath -w "$SCRIPT_DIR")"
      # Blast-radius (Windows): hermes spawns hook commands via
      # shlex.split + shell=False, so argv[0] must be an executable path
      # CreateProcess can find. A bare `bash` resolves to WSL System32
      # bash (System32 is searched before PATH), which cannot read MSYS-backed
      # drive-letter script paths -> exit 127, hooks fail open. Resolve the bash that
      # is ACTUALLY running this generator to an absolute Windows path at
      # install time. Nothing machine-specific is hardcoded.
      SAGE_BASH_EXE="$(cygpath -w "$(command -v bash)" | tr '\\' '/')"
    else
      CONFIG_YAML_ARG="$CONFIG_YAML"
      DEST_HOOKS_ARG="$DEST_HOOKS"
      BINDING_COLLECTION_ARG="$SAGE_HERMES_COLLECTION_ROOT"
      BINDING_PROFILE_ROOT_ARG="$SAGE_HERMES_PROFILE_ROOT"
      BINDING_WORKSPACE_ARG="$SAGE_HERMES_WORKSPACE_ROOT"
      SETUP_DIR_ARG="$SCRIPT_DIR"
      SAGE_BASH_EXE="bash"
    fi
    # Never emit an empty argv[0].
    [ -z "$SAGE_BASH_EXE" ] && SAGE_BASH_EXE="bash"
    export SAGE_BASH_EXE
    if command -v python3 >/dev/null 2>&1; then
      # Capture the exit code explicitly — under set -e a bare command that
      # fails would abort the script before any error branch could run.
      if python3 - "$CONFIG_YAML_ARG" "$DEST_HOOKS_ARG" "$HOOKS_WANTED" \
          "$BINDING_COLLECTION_ARG" "$SAGE_HERMES_PROFILE" \
          "$BINDING_PROFILE_ROOT_ARG" "$BINDING_WORKSPACE_ARG" "$SETUP_DIR_ARG" << 'PYEOF'
import json, re, sys, os

cfg_path, hooks_dir, wanted_json = sys.argv[1], sys.argv[2], sys.argv[3]
collection_root, profile_id, profile_root, workspace_root = sys.argv[4:8]
setup_dir = sys.argv[8]
sys.path.insert(0, setup_dir)
import hook_config
wanted = json.loads(wanted_json)

try:
    with open(cfg_path, encoding="utf-8") as fh:
        text = fh.read()
except OSError:
    text = ""

adapter = os.path.join(hooks_dir, "sage-hermes-gate.sh").replace("\\", "/")
lines = text.splitlines()

# The selected profile config is one half of the runtime authority pair. Keep
# exactly one machine-readable Sage-owned block; the matching install receipt
# is written by the transactional lifecycle.
state_root = os.path.join(workspace_root, ".sage")
def _canon_path(value):
    # Binding values must round-trip through Hermes config writers, which
    # re-dump JSON-quoted scalars in plain YAML style. Canonicalize to
    # forward slashes so equality checks survive that re-serialization.
    return value.replace("\\", "/")

binding = {
    "profile_id": profile_id,
    "workspace_root": _canon_path(workspace_root),
    "state_root": _canon_path(state_root),
    "memory_root": _canon_path(os.path.join(workspace_root, ".sage-memory")),
    "receipt_path": _canon_path(os.path.join(state_root, "receipts", "install.json")),
}
binding_starts = [
    index for index, line in enumerate(lines)
    if re.match(r"^sage_profile_binding:\s*$", line)
]
if len(binding_starts) > 1:
    raise SystemExit("duplicate sage_profile_binding blocks")
if binding_starts:
    start = binding_starts[0]
    end = start + 1
    current = {}
    while end < len(lines) and (not lines[end] or lines[end][0].isspace()):
        line = lines[end]
        if line.startswith("  ") and not line.startswith("   ") and ":" in line[2:]:
            key, raw = line[2:].split(":", 1)
            if key in current:
                raise SystemExit("duplicate sage_profile_binding field: " + key)
            raw_value = raw.strip()
            try:
                value = json.loads(raw_value)
            except ValueError:
                # Hermes config writers re-dump JSON-quoted binding values as
                # plain YAML scalars; accept the plain form (optionally
                # quoted) so the round-trip stays idempotent.
                value = raw_value
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
            if isinstance(value, str):
                value = value.replace("\\", "/")
            current[key] = value
        elif line.strip() and not line.lstrip().startswith("#"):
            raise SystemExit("malformed sage_profile_binding block")
        end += 1
    if current != binding:
        raise SystemExit("existing Sage profile binding conflicts with the selected profile")
    del lines[start:end]

while lines and not lines[-1].strip():
    lines.pop()
if lines:
    lines.append("")
lines.append("sage_profile_binding:")
for key in ("profile_id", "workspace_root", "state_root", "memory_root", "receipt_path"):
    lines.append("  %s: %s" % (key, json.dumps(binding[key])))
lines.append("")
text = "\n".join(lines) + "\n"

if os.environ.get("SAGE_HERMES_TRANSACTIONAL_INIT") == "1":
    # Transactional init (T26/BD-4): the binding block is the generator's
    # only config contribution. The exact 7+4 hook registry and every
    # profile byte below are committed by profile_installer.install inside
    # one journaled transaction; a merge here would pre-write entries the
    # installer then has to reconcile.
    os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("BINDING_OK transactional=1")
    raise SystemExit(0)

# Commands run via shlex.split + shell=False. The adapter is a bash script,
# so wrap it explicitly — on Windows a bare .sh is not directly executable.
# argv[0] must be an absolute executable path on Windows (bare `bash`
# resolves to WSL System32 bash -> exit 127 on MSYS drive-letter script paths).
# SAGE_BASH_EXE is resolved at install time by the bash wrapper above.
_bash = os.environ.get("SAGE_BASH_EXE", "bash")
def _cmd(event, script):
    # The DECODED command must shlex.split with the full spaced bash path as
    # argv[0]: "<absolute-git-bash.exe>" "<adapter>" <script>.
    # The YAML scalar therefore carries escaped quotes around BOTH paths —
    # an unquoted spaced argv[0] splits to `C:/Program` and dies 127-adjacent.
    if event == "on_session_start":
        # Direct dispatch for the lifecycle session script — matches
        # profile_installer._command_value's branch for sage-session-init.sh:
        # no sage-hermes-gate.sh adapter, just `<bash> "<session-init-path>"`.
        session_init = os.path.join(hooks_dir, "sage-session-init.sh").replace("\\", "/")
        return f'"\\"{_bash}\\" \\"{session_init}\\""'
    return f'"\\"{_bash}\\" \\"{adapter}\\" {script}"'

# Remove the retired blanket-consent scalar before validating the exact
# event/command registry. It is Sage-owned legacy state, not a user hook.
lines = [line for line in lines if not re.match(r"^hooks_auto_accept:\s*", line)]
text = "\n".join(lines) + "\n"

# Locate the top-level hooks: block (or mark end-of-file for append).
hooks_start = None
hooks_end = len(lines)
for i, ln in enumerate(lines):
    if re.match(r"^hooks:\s*$", ln):
        hooks_start = i
        for j in range(i + 1, len(lines)):
            if re.match(r"^\S", lines[j]):
                hooks_end = j
                break
        break

if hooks_start is None:
    lines.append("")
    lines.append("# Sage enforcement hooks (registered by sage init --platform hermes)")
    lines.append("hooks:")
    hooks_start = len(lines) - 1
    hooks_end = len(lines)

def _entry_command(block):
    for index, line in enumerate(block):
        match = re.match(r"^(\s*)(?:-\s*)?command:\s*(.*)$", line)
        if not match:
            continue
        key_indent = len(match.group(1))
        if re.match(r"^\s*-\s*command:", line):
            key_indent += 2
        parts = [match.group(2)]
        for continuation in block[index + 1:]:
            if not continuation.strip():
                break
            indent = len(continuation) - len(continuation.lstrip(" "))
            if indent <= key_indent:
                break
            if not continuation.lstrip().startswith("#"):
                parts.append(continuation.strip())
        return " ".join(parts)
    return None

def _session_entry_blocks():
    blocks = []
    event = None
    index = hooks_start + 1
    while index < hooks_end:
        event_match = re.match(r"^  ([A-Za-z_][\w-]*):\s*$", lines[index])
        if event_match:
            event = event_match.group(1)
            index += 1
            continue
        if not re.match(r"^    -\s+", lines[index]):
            index += 1
            continue
        start = index
        end = start + 1
        while end < hooks_end:
            line = lines[end]
            if re.match(r"^    -\s+", line) or re.match(
                r"^  [A-Za-z_][\w-]*:\s*$", line
            ):
                break
            indent = len(line) - len(line.lstrip(" "))
            if line.strip() and indent <= 4:
                break
            end += 1
        entry_end = end
        while entry_end > start + 1 and not lines[entry_end - 1].strip():
            entry_end -= 1
        command = _entry_command(lines[start:entry_end])
        if command and "sage-session-init.sh" in command:
            blocks.append((start, entry_end, event))
        index = end
    return blocks

session_cmd = _cmd("on_session_start", "sage-session-init.sh")
canonical_session = [
    f"    - command: {session_cmd}",
    "      fail_closed: false",
    "      timeout: 30",
]
session_blocks = _session_entry_blocks()
session_registered = (
    len(session_blocks) == 1
    and session_blocks[0][2] == "on_session_start"
    and lines[session_blocks[0][0]:session_blocks[0][1]] == canonical_session
)
session_updates = 0
if not session_registered and session_blocks:
    for start, end, _event in reversed(session_blocks):
        del lines[start:end]
        hooks_end -= end - start
    session_updates = 1
    text = "\n".join(lines) + "\n"

missing = []
needs_update = []  # (cmd_line_idx, end_idx_inclusive, new_cmd, event)
# Two broken forms need rewrite: the bare `bash` form (WSL System32 -> 127),
# and the unquoted spaced-absolute form (`command: "X:/Path With Spaces/...`),
# whose decoded value shlex-splits argv[0] to `C:/Program`.
broken_bash_re = re.compile(r'^\s*command:\s*(bash(\s|$)|"[A-Za-z]:)')
for event, matcher, script in wanted:
    cmd = _cmd(event, script)
    if event == "on_session_start":
        if session_registered:
            continue  # already registered — idempotent
        missing.append((event, matcher, cmd))
        continue
    # Dedup on the adapter+script pair, tolerant of how the entry lands in
    # the file: the generator writes a double-quoted YAML scalar with
    # backslash-escaped inner quotes (gate.sh\" script), while older/live
    # configs may hold a folded plain scalar split across lines
    # (gate.sh\"\n   script). The needle must allow an optional backslash
    # before the quote or neither form matches and every rerun appends a
    # duplicate set. SEARCH THE WHOLE TEXT: in folded entries the pattern
    # spans two lines, so a per-line search can never match (root cause of
    # the silent updated=0).
    pat = re.compile(r'sage-hermes-gate\.sh\\?"?\s+' + re.escape(script))
    m = pat.search(text)
    if m:
        # Entry already registered. The match lands on the adapter /
        # continuation line; walk back to the `command:` line to find the
        # head of the entry (in folded configs the script name sits on its
        # own line AFTER the adapter path).
        match_line = text[:m.start()].count("\n")
        cmd_line = None
        for bi in range(match_line, -1, -1):
            if re.match(r'\s*command:', lines[bi]):
                cmd_line = bi
                break
        if cmd_line is not None and broken_bash_re.match(lines[cmd_line]):
            # Command uses the bare `bash` form (the WSL System32 -> 127
            # trap). Rewrite the WHOLE folded block in place: continuation
            # lines are strictly deeper-indented than the command line;
            # anything else (blank line, sibling key like `timeout:` at
            # the same indent, new list item) ends the block. A hardcoded
            # shallow threshold would eat `timeout: 30` — derive it from
            # the command line's own indent instead.
            cmd_indent = len(lines[cmd_line]) - len(lines[cmd_line].lstrip(' '))
            end_idx = cmd_line
            for ni in range(cmd_line + 1, len(lines)):
                nl = lines[ni]
                if not nl.strip():
                    break
                n_indent = len(nl) - len(nl.lstrip(' '))
                if n_indent <= cmd_indent:
                    break
                end_idx = ni
            needs_update.append((cmd_line, end_idx, cmd, event, matcher))
        continue  # already registered — idempotent (or queued for rewrite)
    missing.append((event, matcher, cmd))

# Apply in-place folded-block rewrites, reverse order so earlier indexes
# stay valid. Each rewrite normalizes the entry to the exact policy shape:
# one command line plus one fail_closed sibling (a stale fail_closed line
# directly after the block is superseded, never duplicated).
hooks_end_delta = 0
for start_idx, end_idx, new_cmd, event, matcher in sorted(needs_update, key=lambda x: -x[0]):
    fail_value = "true" if event == "pre_tool_call" else "false"
    stop = end_idx + 1  # first line AFTER the folded block
    if stop < len(lines) and re.match(r"\s*fail_closed:", lines[stop]):
        stop += 1  # supersede the stale fail_closed line
    # Normalize the matcher line to canonical: legacy entries keep stale or
    # backslash-wrapped matchers that either never match (decorative) or
    # drift from HOOKS_WANTED (round-trip finding).
    above = start_idx - 1
    if above >= 0:
        m_match = re.match(r'^(\s*- matcher:\s*)(.*?)\s*$', lines[above])
        if m_match:
            lines[above] = "%s'%s'" % (m_match.group(1), matcher)
    lines[start_idx:stop] = [
        f"      command: {new_cmd}",
        f"      fail_closed: {fail_value}",
    ]
    hooks_end_delta -= (stop - start_idx) - 2
hooks_end += hooks_end_delta
text = "\n".join(lines) + "\n"

# Consent is never blanket-enabled: hooks_auto_accept is neither inserted nor
# required. Sage's consent is the exact (event, command) pairs validated by
# hook_config.py; the transactional installer records them (spec 5.3.12).

if missing:
    insert_at = hooks_end
    for event, matcher, cmd in missing:
        # find or create the event subsection inside the hooks block
        ev_idx = None
        for k, ln in enumerate(lines[hooks_start + 1:hooks_end], start=hooks_start + 1):
            if re.match(rf"^  {re.escape(event)}:\s*$", ln):
                ev_idx = k
                break
        if ev_idx is None:
            lines.insert(insert_at, f"  {event}:")
            ev_idx = insert_at
            insert_at += 1
            hooks_end += 1
        # append the entry right after the event key (hooks_end advances so
        # later searches see the inserted lines; duplicate keys never form)
        fail_line = (
            "      fail_closed: true"
            if event == "pre_tool_call"
            else "      fail_closed: false"
        )
        # Matcher as a single-quoted YAML scalar: the previous \"-wrapped form
        # decoded WITH the backslashes in plain style, so appended matchers
        # never matched and the gates were decorative (round-2 finding).
        # Lifecycle session entries (matcher is null) skip the matcher line:
        # the session script is dispatched directly without a tool-name filter.
        new_lines = []
        if matcher is not None:
            new_lines.append(f"    - matcher: '{matcher}'")
            new_lines.append(f"      command: {cmd}")
        else:
            new_lines.append(f"    - command: {cmd}")
        new_lines.append(fail_line)
        new_lines.append("      timeout: 30")
        for offset, line in enumerate(new_lines):
            lines.insert(ev_idx + 1 + offset, line)
        insert_at = hooks_end + len(new_lines)
        hooks_end += len(new_lines)

os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
candidate_text = "\n".join(lines) + "\n"
validation = hook_config.validate_candidate_config(candidate_text)
if not validation["ok"]:
    raise SystemExit(
        "generated hook registry fails canonical policy: "
        + "; ".join(validation["errors"])
    )
with open(cfg_path, "w", encoding="utf-8") as fh:
    fh.write(candidate_text)
print(
    f"MERGED_OK added={len(missing)} "
    f"updated={len(needs_update) + session_updates}"
)
PYEOF
      then
        echo -e "    ${GREEN}✓${RESET} Hooks registered in $CONFIG_YAML"
      else
        echo -e "    ${RED}✗ Hook merge failed; profile installation is incomplete${RESET}" >&2
        exit 1
      fi
    else
      echo -e "    ${YELLOW}⚠ python3 not found — hooks NOT registered; add them to $CONFIG_YAML manually${RESET}"
    fi

    # 4. Enable the plugin for this profile.
    # Transactional init defers enablement to AFTER profile_installer.install
    # commits, so a failed install never leaves an "enabled" plugin whose
    # bytes were never staged. bin/sage performs the enable once install
    # succeeds.
    if [ "${SAGE_HERMES_TRANSACTIONAL_INIT:-0}" = "1" ]; then
      echo -e "    ${CYAN}⊘${RESET} Plugin enablement deferred until after the transactional install"
    elif command -v hermes >/dev/null 2>&1; then
      if hermes --profile "$PROFILE" plugins enable sage >/dev/null 2>&1; then
        echo -e "    ${GREEN}✓${RESET} Plugin enabled (hermes --profile $PROFILE plugins enable sage)"
      else
        echo -e "    ${YELLOW}⚠ Auto-enable failed — run: hermes --profile $PROFILE plugins enable sage${RESET}"
      fi
      if hermes --profile "$PROFILE" plugins list 2>/dev/null | grep -qi "sage"; then
        echo -e "    ${GREEN}✓${RESET} Verified: sage visible in hermes plugins list"
      else
        echo -e "    ${YELLOW}⚠ Not visible yet — restart Hermes for this profile${RESET}"
      fi
    else
      echo -e "    ${YELLOW}⚠ hermes CLI not on PATH — enable manually: hermes --profile $PROFILE plugins enable sage${RESET}"
    fi
    echo ""
  done

  # Report skipped profiles so the operator knows who didn't get provisioned.
  if [ ${#SKIPPED_PROFILES[@]} -gt 0 ]; then
    echo -e "  ${YELLOW}⚠ Skipped profiles (not provisioned):${SKIPPED_PROFILES[*]+" ${SKIPPED_PROFILES[*]+"${SKIPPED_PROFILES[*]}"}"}${RESET}"
    echo "    Update their Git-managed plugin checkouts directly,"
    echo "    then re-run \`sage init --platform hermes --hermes-profile <name>\` for each."
    echo ""
  fi
fi

# ── Summary (claude-code parity) ──
echo ""
echo "═══════════════════════════════════════════════════════════════"
if [ ${#SKIPPED_PROFILES[@]} -gt 0 ]; then
  echo -e "⚠ Sage → Hermes Agent setup incomplete"
  echo ""
  echo "  Workspace surfaces may be present, but every skipped profile received"
  echo "  no Sage hook, config, plugin, or enablement changes. Resolve the"
  echo "  Git-managed checkout listed above before starting Hermes with Sage."
else
  echo -e "✅ Sage → Hermes Agent setup complete"
  echo ""
  echo "  .hermes.md                → project instructions (workspace-owned)"
  echo "  .sage/                    → project state (config, work, gates)"
  echo "  <profile>/hooks/          → gate scripts (canonical, outside plugin)"
  echo "  <profile>/config.yaml     → hooks: registrations (pre/post_tool_call)"
  echo "  <profile>/plugins/sage    → plugin (skills, injection, commands)"
  echo ""
  echo "  Gates only fire in sessions whose cwd is this project and only in"
  echo "  the profiles you selected. To disable: hard_enforcement: false in"
  echo "  .sage/config.yaml."
  echo ""
  echo "Next steps:"
  echo "  1. Start Hermes in this project directory (any selected profile)"
  echo "  2. Type /sage and describe what you want to build"
  echo "  3. Type /sage-status to check project state"
fi
echo ""

# Nonzero exit when any profile was skipped, so automation can detect partial
# installs and the operator gets a non-zero CI signal to investigate.
[ ${#SKIPPED_PROFILES[@]} -eq 0 ] || exit 1
