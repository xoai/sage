#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Gemini CLI Setup
# Generates GEMINI.md + .gemini/commands/*.toml for Gemini CLI.
# Gemini CLI reads GEMINI.md as project context and supports TOML
# slash commands in .gemini/commands/. Uses {{args}} for user input.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
GEMINI_DIR="$SAGE_ROOT/.gemini"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"

echo ""
echo "🚀 Sage → Gemini CLI Setup"
echo "═══════════════════════════════"

# ── Validate ──
if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  echo "   Run this from the project root where sage/ is located."
  exit 1
fi

# ── Read prefix config ──
PREFIX=""
if [ -f "$PROJECT_SAGE/config.yaml" ]; then
  if grep -q 'command_prefix: true' "$PROJECT_SAGE/config.yaml" 2>/dev/null; then
    PREFIX="sage:"
  fi
fi

# ── Create .gemini structure ──
echo ""
echo "📁 Creating .gemini/ structure..."
mkdir -p "$GEMINI_DIR/commands"

# ═══════════════════════════════════════════════════════════════
# GEMINI.md — Generated from shared instructions-body
# Gemini CLI reads GEMINI.md as project context (concatenated from
# global, workspace, and JIT scans). If Antigravity is also installed,
# both platforms read the same file.
# ═══════════════════════════════════════════════════════════════
echo "📝 Generating GEMINI.md..."

# Only write GEMINI.md if it doesn't exist OR is Sage-generated.
SKIP_GEMINI_MD=false
if [ -f "$SAGE_ROOT/GEMINI.md" ]; then
  if head -1 "$SAGE_ROOT/GEMINI.md" 2>/dev/null | grep -q "Sage"; then
    SKIP_GEMINI_MD=false
  else
    SKIP_GEMINI_MD=true
    echo "  ⚠ GEMINI.md exists and is not Sage-generated — skipping write."
  fi
fi

if [ "$SKIP_GEMINI_MD" = false ]; then
  source "$(dirname "$0")/../../../_shared/instructions-body.sh"
  emit_instructions_body \
    | sed \
      -e 's|Task tool|sub-agent invocation|g' \
      -e 's|the Task tool|the sub-agent system|g' \
      -e 's|`.claude/commands/\[workflow\].md`|`.gemini/commands/[workflow].toml`|g' \
      -e 's|\$ARGUMENTS|{{args}}|g' \
    > "$SAGE_ROOT/GEMINI.md"
  echo "  ✓ GEMINI.md"
fi

# ── Dynamic constitution merging ──
CONST_SECTION="## Engineering Principles

Base (all projects):
1. Tests before code — every behavior has a test before implementation
2. No silent failures — errors handled, logged, or propagated
3. Secrets never in code — use env vars or secret managers
4. Dependencies explicit — declared with pinned versions
5. Changes reversible — migrations reversible, deployments rollbackable"

PRINCIPLE_NUM=5
CONST_FILE="$PROJECT_SAGE/constitution.md"
if [ -f "$CONST_FILE" ]; then
  PRESET=$(sed -n '/^extends:/s/^extends: *//p' "$CONST_FILE" 2>/dev/null)
  if [ -n "$PRESET" ] && [ "$PRESET" != "base" ] && [ "$PRESET" != "none" ]; then
    PRESET_FILE="$CORE/constitution/presets/${PRESET}.constitution.md"
    if [ -f "$PRESET_FILE" ]; then
      PRESET_PRINCIPLES=$(awk '/^[0-9]+\./{print}' "$PRESET_FILE" 2>/dev/null)
      if [ -n "$PRESET_PRINCIPLES" ]; then
        CONST_SECTION="$CONST_SECTION

Preset ($PRESET):"
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          NEW_PRINCIPLE=$(echo "$line" | sed "s/^[0-9]\+\./$((++PRINCIPLE_NUM))./")
          CONST_SECTION="$CONST_SECTION
$NEW_PRINCIPLE"
        done <<< "$PRESET_PRINCIPLES"
      fi
    fi
  fi
fi

if [ "$SKIP_GEMINI_MD" = false ]; then
  python3 -c "
with open('$SAGE_ROOT/GEMINI.md', 'r') as f:
    content = f.read()
replacement = '''$CONST_SECTION'''
content = content.replace('__CONSTITUTION_PLACEHOLDER__', replacement)
with open('$SAGE_ROOT/GEMINI.md', 'w') as f:
    f.write(content)
" 2>/dev/null || true
fi

# ═══════════════════════════════════════════════════════════════
# Per-workflow TOML commands in .gemini/commands/
# Format per Gemini CLI docs:
#   description = "one-line help text"
#   prompt = """multi-line prompt with {{args}} placeholder"""
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📎 Generating .gemini/commands/ from core workflows..."

source "$(dirname "$0")/../../../_shared/preambles.sh"

for wf in "$CORE"/workflows/*.workflow.md; do
  [ -f "$wf" ] || continue
  basename_wf=$(basename "$wf" .workflow.md)

  # Get preamble (preserve trailing newlines)
  PREAMBLE=$({ emit_preamble "$basename_wf"; printf x; })
  PREAMBLE="${PREAMBLE%x}"

  # Workflow description for TOML
  WF_DESC=$(sed -n '/^---$/,/^---$/{ /^produces:/s/^produces: *//p; }' "$wf" \
    | head -1 | sed 's/\[//g;s/\]//g;s/"//g' | cut -c1-100)
  [ -z "$WF_DESC" ] && WF_DESC="Sage $basename_wf workflow"
  # Escape any double quotes in description for TOML
  WF_DESC=$(echo "$WF_DESC" | sed 's/"/\\"/g')

  # /sage stays unprefixed; everything else gets PREFIX
  cmd_name="$basename_wf"
  [ "$basename_wf" != "sage" ] && cmd_name="${PREFIX}${basename_wf}"

  # Build the TOML file
  # Gemini CLI uses subdirectories for namespaced commands: sage/<name>.toml → /sage:<name>
  if [ -n "$PREFIX" ] && [ "$basename_wf" != "sage" ]; then
    mkdir -p "$GEMINI_DIR/commands/sage"
    out="$GEMINI_DIR/commands/sage/${basename_wf}.toml"
    cmd_display="sage:${basename_wf}"
  else
    out="$GEMINI_DIR/commands/${basename_wf}.toml"
    cmd_display="${basename_wf}"
  fi

  {
    printf 'description = "%s"\n' "$WF_DESC"
    printf 'prompt = """\n'
    # Preamble (terminology swap + replace $ARGUMENTS with {{args}})
    printf "%s" "$PREAMBLE" | sed \
      -e 's|Task tool|sub-agent invocation|g' \
      -e 's|the Task tool|the sub-agent system|g' \
      -e 's|\$ARGUMENTS|{{args}}|g'
    # Workflow body (strip frontmatter, substitute paths, replace $ARGUMENTS)
    sed '/^---$/,/^---$/d' "$wf" \
      | sed 's|\*\*sage-navigator\*\* skill|**sage-navigator** skill at `sage/core/capabilities/orchestration/sage-navigator/SKILL.md`|g' \
      | sed "s|sage-navigator's intelligence layer|sage-navigator's intelligence layer (\`sage/core/capabilities/orchestration/sage-navigator/SKILL.md\`, section 2)|g" \
      | sed 's|If relevant Sage skills exist, read and follow them.|If relevant Sage skills exist in `sage/skills/`, read and follow them.|g' \
      | sed 's|\$ARGUMENTS|{{args}}|g' \
      | sed '/^$/N;/^\n$/d'
    printf '\n{{args}}\n"""\n'
  } > "$out"

  echo "  ✓ ${cmd_display}.toml → /${cmd_display}"
done

# ═══════════════════════════════════════════════════════════════
# Project state — .sage/ initialization
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📊 Checking project state..."
if [ -d "$PROJECT_SAGE" ]; then
  echo "  ✓ .sage/ already exists"
else
  mkdir -p "$PROJECT_SAGE/work" "$PROJECT_SAGE/docs"
  echo "  ✓ .sage/ initialized"
fi

# ── Report ──
echo ""
echo "═══════════════════════════════"
echo "✅ Sage → Gemini CLI setup complete"
echo ""
echo "Files written:"
echo "  GEMINI.md                    (read by Gemini CLI as context)"
echo "  .gemini/commands/*.toml      (TOML slash command definitions)"
echo ""
echo "Next steps:"
echo "  - Run \`gemini\` to start a session"
echo "  - Type /sage or describe what you want to build"
echo "  - Sub-agent support depends on Gemini CLI version — if unavailable,"
echo "    Sage reviews degrade to single-pass with a session notice."
echo ""
