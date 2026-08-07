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
#   2. Writes SOUL.md from the canonical shared instructions body
#      (Hermes reads SOUL.md as system prompt slot #1 — same role
#      CLAUDE.md plays on Claude Code)
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

# ── Write SOUL.md from the canonical shared instructions body ──
# Claude Code parity: generate-claude-code.sh emits the same body into
# CLAUDE.md via emit_instructions_body, then merges the constitution
# section. SOUL.md is Hermes's equivalent (system prompt slot #1).
SOUL="$PROJECT_ROOT/SOUL.md"
if [ ! -f "$SOUL" ]; then
  if [ -f "$SHARED/instructions-body.sh" ] && [ -f "$SHARED/constitution.sh" ]; then
    # shellcheck source=../../../_shared/instructions-body.sh
    source "$SHARED/instructions-body.sh"
    # shellcheck source=../../../_shared/constitution.sh
    source "$SHARED/constitution.sh"
    emit_instructions_body > "$SOUL"
    CONST_SECTION="$(build_constitution_section "$CORE" "$PROJECT_ROOT/.sage")"
    if [ -n "$CONST_SECTION" ]; then
      # MSYS guard: python3 on Windows needs a native path for the file.
      if command -v cygpath >/dev/null 2>&1; then
        SOUL_ARG="$(cygpath -w "$SOUL")"
      else
        SOUL_ARG="$SOUL"
      fi
      python3 - "$SOUL_ARG" "$CONST_SECTION" << 'PYEOF'
import sys
path, section = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    content = fh.read()
content = content.replace("__CONSTITUTION_PLACEHOLDER__", section)
with open(path, "w", encoding="utf-8") as fh:
    fh.write(content)
PYEOF
    fi
    echo -e "  ${GREEN}✓${RESET} Wrote SOUL.md (canonical instructions + constitution)"
  else
    echo -e "  ${YELLOW}⚠ Shared emitters not found — SOUL.md not generated (run from a full sage checkout)${RESET}"
  fi
else
  echo -e "  ${CYAN}⊘${RESET} SOUL.md already exists, skipping"
fi

# ═══════════════════════════════════════════════════════════════
# Enforcement hooks — canonical registration (claude-code parity)
# ═══════════════════════════════════════════════════════════════
# On Claude Code, generate-claude-code.sh copies the gate scripts into
# .claude/hooks/ and registers them in settings.json OUTSIDE the plugin.
# On Hermes the canonical equivalent (docs: user-guide/features/hooks) is:
#   1. scripts live in the profile's agent-hooks dir (always-on, per profile)
#   2. registration via the hooks: block in the profile's config.yaml
#   3. JSON wire protocol: {"decision":"block","reason":...} on stdout
#
# The claude-code gate scripts speak their own wire format (exit 2 +
# stderr, tool_input.file_path), so we ship ONE adapter
# (sage-hermes-gate.sh) that translates Hermes payloads and decisions.
# The gate scripts stay the single source of decision logic.
#
# Registration is PER PROFILE — Hermes plugins and hooks both live under
# each profile, so the installer enumerates every profile and lets the
# user pick which agents get Sage (multi-select).

CC_HOOKS_SRC="$SAGE_ROOT/runtime/platforms/claude-code/hooks"
HERMES_HOOKS_SRC="$HERMES_PLATFORM_ROOT/hooks"
ADAPTER_SRC="$HERMES_HOOKS_SRC/sage-hermes-gate.sh"

# (event, matcher, script) — mirrors the claude-code WANTED table so
# enforcement behavior is identical across platforms. Matchers use
# Hermes tool names: write_file|patch (file edits), terminal (shell).
HOOKS_WANTED='[
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
  HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
  PROFILES_DIR="$HERMES_HOME/profiles"

  # ── Enumerate profiles ──
  ALL_PROFILES=()
  if [ -d "$PROFILES_DIR" ]; then
    for d in "$PROFILES_DIR"/*/; do
      [ -d "$d" ] && ALL_PROFILES+=("$(basename "$d")")
    done
  fi
  if [ ${#ALL_PROFILES[@]} -eq 0 ]; then
    ALL_PROFILES=("default")
  fi

  # ── Multi-select: which profiles get Sage? ──
  # (portable multi-select: numbered list, enter numbers or 'all';
  # a true spacebar-toggle needs a TUI — this is the bash equivalent)
  SELECTED_PROFILES=()
  if [ -t 0 ]; then
    echo ""
    echo -e "  ${BOLD}Hermes profiles found — which ones should get Sage?${RESET}"
    echo ""
    for i in "${!ALL_PROFILES[@]}"; do
      echo "    $((i + 1))) ${ALL_PROFILES[$i]}"
    done
    echo ""
    printf "  Enter numbers separated by spaces (or 'all'): "
    read -r selection
    if [ "$selection" = "all" ] || [ -z "${selection// /}" ]; then
      SELECTED_PROFILES=("${ALL_PROFILES[@]}")
    else
      for tok in $selection; do
        if [[ "$tok" =~ ^[0-9]+$ ]] && [ "$tok" -ge 1 ] && [ "$tok" -le ${#ALL_PROFILES[@]} ]; then
          SELECTED_PROFILES+=("${ALL_PROFILES[$((tok - 1))]}")
        fi
      done
      [ ${#SELECTED_PROFILES[@]} -eq 0 ] && SELECTED_PROFILES=("${ALL_PROFILES[@]}")
    fi
  else
    # Non-interactive: install into every profile.
    SELECTED_PROFILES=("${ALL_PROFILES[@]}")
  fi

  echo ""
  echo -e "  Installing Sage for profiles: ${SELECTED_PROFILES[*]}"
  echo ""

  for PROFILE in "${SELECTED_PROFILES[@]}"; do
    echo -e "  ${BOLD}── Profile: $PROFILE${RESET}"
    if [ "$PROFILE" = "default" ] && [ ! -d "$PROFILES_DIR/default" ]; then
      PROF_ROOT="$HERMES_HOME"
    else
      PROF_ROOT="$PROFILES_DIR/$PROFILE"
    fi

    # 1. Gate scripts + adapter → <profile>/agent-hooks/sage/
    DEST_HOOKS="$PROF_ROOT/agent-hooks/sage"
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
    DEST_PLUGIN="$PROF_ROOT/plugins/sage"
    if [ -d "$DEST_PLUGIN" ]; then
      echo -e "    ${CYAN}⊘${RESET} Plugin already installed at $DEST_PLUGIN"
    else
      mkdir -p "$(dirname "$DEST_PLUGIN")"
      cp -r "$SAGE_ROOT" "$DEST_PLUGIN"
      rm -rf "$DEST_PLUGIN/.git" "$DEST_PLUGIN/.worktrees" "$DEST_PLUGIN/node_modules" 2>/dev/null || true
      echo -e "    ${GREEN}✓${RESET} Plugin → $DEST_PLUGIN"
    fi

    # 3. Register hooks in <profile>/config.yaml (idempotent merge).
    # MSYS guard: python3 on Windows needs native paths, not /g/... style.
    CONFIG_YAML="$PROF_ROOT/config.yaml"
    if command -v cygpath >/dev/null 2>&1; then
      CONFIG_YAML_ARG="$(cygpath -w "$CONFIG_YAML")"
      DEST_HOOKS_ARG="$(cygpath -w "$DEST_HOOKS")"
      # Blast-radius (Windows): hermes spawns hook commands via
      # shlex.split + shell=False, so argv[0] must be an executable path
      # CreateProcess can find. A bare `bash` resolves to WSL System32
      # bash (System32 is searched before PATH), which cannot read G:/
      # script paths -> exit 127, hooks fail open. Resolve the bash that
      # is ACTUALLY running this generator to an absolute Windows path at
      # install time. Nothing machine-specific is hardcoded.
      SAGE_BASH_EXE="$(cygpath -w "$(command -v bash)" | tr '\\' '/')"
    else
      CONFIG_YAML_ARG="$CONFIG_YAML"
      DEST_HOOKS_ARG="$DEST_HOOKS"
      SAGE_BASH_EXE="bash"
    fi
    # Never emit an empty argv[0].
    [ -z "$SAGE_BASH_EXE" ] && SAGE_BASH_EXE="bash"
    export SAGE_BASH_EXE
    if command -v python3 >/dev/null 2>&1; then
      # Capture the exit code explicitly — under set -e a bare command that
      # fails would abort the script before any error branch could run.
      if python3 - "$CONFIG_YAML_ARG" "$DEST_HOOKS_ARG" "$HOOKS_WANTED" << 'PYEOF'
import json, re, sys, os

cfg_path, hooks_dir, wanted_json = sys.argv[1], sys.argv[2], sys.argv[3]
wanted = json.loads(wanted_json)

try:
    with open(cfg_path, encoding="utf-8") as fh:
        text = fh.read()
except OSError:
    text = ""

adapter = os.path.join(hooks_dir, "sage-hermes-gate.sh").replace("\\", "/")
lines = text.splitlines()

# Commands run via shlex.split + shell=False. The adapter is a bash script,
# so wrap it explicitly — on Windows a bare .sh is not directly executable.
# argv[0] must be an absolute executable path on Windows (bare `bash`
# resolves to WSL System32 bash -> exit 127 on G:/ script paths).
# SAGE_BASH_EXE is resolved at install time by the bash wrapper above.
_bash = os.environ.get("SAGE_BASH_EXE", "bash")
def _cmd(script):
    return f'"{_bash} \\"{adapter}\\" {script}"'

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

missing = []
needs_update = []  # (cmd_line_idx, end_idx_inclusive, new_cmd)
broken_bash_re = re.compile(r'^\s*command:\s*bash(\s|$)')
for event, matcher, script in wanted:
    cmd = _cmd(script)
    # Dedup on the adapter+script pair, tolerant of how the entry lands in
    # the file: the generator writes a double-quoted YAML scalar with
    # backslash-escaped inner quotes (gate.sh\" script), while older/live
    # configs may hold a folded plain scalar split across lines
    # (gate.sh"\n   script). The needle must allow an optional backslash
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
            needs_update.append((cmd_line, end_idx, cmd))
        continue  # already registered — idempotent (or queued for rewrite)
    missing.append((event, matcher, cmd))

# Apply in-place folded-block rewrites, reverse order so earlier indexes
# stay valid. Each 3-line folded block collapses to 1 line; shift hooks_end
# by the net delta so later inserts land in the right place.
hooks_end_delta = 0
for start_idx, end_idx, new_cmd in sorted(needs_update, key=lambda x: -x[0]):
    removed = end_idx - start_idx  # continuation lines dropped
    lines[start_idx:end_idx + 1] = [f"      command: {new_cmd}"]
    hooks_end_delta -= removed
hooks_end += hooks_end_delta
text = "\n".join(lines) + "\n"

# Ensure hooks_auto_accept so the consent prompt doesn't ambush the user.
# Insert ABOVE the hooks: block (top-level key) and shift hooks_start so
# later appends land in the right place.
if "hooks_auto_accept" not in text:
    lines.insert(hooks_start, "# Auto-accept Sage hook consent (registered by sage init)")
    lines.insert(hooks_start + 1, "hooks_auto_accept: true")
    hooks_start += 2
    hooks_end += 2

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
        lines.insert(ev_idx + 1, f"    - matcher: \"{matcher}\"")
        lines.insert(ev_idx + 2, f"      command: {cmd}")
        lines.insert(ev_idx + 3, "      timeout: 30")
        insert_at = hooks_end + 3
        hooks_end += 3

os.makedirs(os.path.dirname(os.path.abspath(cfg_path)), exist_ok=True)
with open(cfg_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(f"MERGED_OK added={len(missing)} updated={len(needs_update)}")
PYEOF
      then
        echo -e "    ${GREEN}✓${RESET} Hooks registered in $CONFIG_YAML"
      else
        echo -e "    ${YELLOW}⚠ Hook merge failed — add them manually (see docs/user-guide/features/hooks)${RESET}"
      fi
    else
      echo -e "    ${YELLOW}⚠ python3 not found — hooks NOT registered; add them to $CONFIG_YAML manually${RESET}"
    fi

    # 4. Enable the plugin for this profile
    if command -v hermes >/dev/null 2>&1; then
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
fi

# ── Summary (claude-code parity) ──
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "✅ Sage → Hermes Agent setup complete"
echo ""
echo "  SOUL.md                   → always-on project instructions (slot #1)"
echo "  .sage/                    → project state (config, work, gates)"
echo "  <profile>/agent-hooks/sage/ → gate scripts (canonical, outside plugin)"
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
echo ""
