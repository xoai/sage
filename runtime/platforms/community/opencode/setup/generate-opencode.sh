#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Opencode Setup
# Generates AGENTS.md + .opencode/{commands,agents}/ for Opencode.
# Opencode reads AGENTS.md as the project instructions and supports
# markdown commands with YAML frontmatter in .opencode/commands/,
# plus sub-agents in .opencode/agents/.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
OC_DIR="$SAGE_ROOT/.opencode"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"

echo ""
echo "🚀 Sage → Opencode Setup"
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

# ── Create .opencode structure ──
echo ""
echo "📁 Creating .opencode/ structure..."
mkdir -p "$OC_DIR/commands" "$OC_DIR/agents"

# ═══════════════════════════════════════════════════════════════
# AGENTS.md — Generated from shared instructions-body
# Opencode reads AGENTS.md at project root as system context.
# Same content as Codex's AGENTS.md; if Codex is also installed,
# both platforms read the same file.
# ═══════════════════════════════════════════════════════════════
echo "📝 Generating AGENTS.md..."

# Only write AGENTS.md if it doesn't exist OR is Sage-generated.
# This avoids clobbering a user's manual AGENTS.md.
SKIP_AGENTS_MD=false
if [ -f "$SAGE_ROOT/AGENTS.md" ]; then
  if head -1 "$SAGE_ROOT/AGENTS.md" 2>/dev/null | grep -q "Sage"; then
    SKIP_AGENTS_MD=false  # Sage-generated, safe to overwrite
  else
    SKIP_AGENTS_MD=true
    echo "  ⚠ AGENTS.md exists and is not Sage-generated — skipping write."
    echo "    Move or rename it if you want Sage to manage it."
  fi
fi

if [ "$SKIP_AGENTS_MD" = false ]; then
  source "$(dirname "$0")/../../../_shared/instructions-body.sh"
  emit_instructions_body \
    | sed \
      -e 's|Task tool|sub-agent invocation|g' \
      -e 's|the Task tool|the sub-agent system|g' \
      -e 's|`.claude/commands/\[workflow\].md`|`.opencode/commands/[workflow].md`|g' \
    > "$SAGE_ROOT/AGENTS.md"

# ── Inline the system skills (ADR-9: no discovery on this platform) ──
#
# The eager body no longer carries the routing chain, memory guide, gates
# explainer, checkpoint protocol, tiers, constitution text or decision protocol —
# ADR-9 moved them into skills. Claude Code fetches those on demand. This platform
# has no discovery mechanism, so they must be INLINED, or its users lose the
# content entirely while their instructions file still points at it ("→ sage-gates
# skill") as though it were reachable.
#
# The conformance suite caught exactly that regression here (P4-T4): "declared
# false, and nothing is inlined — the content is unreachable on this platform".
source "$(dirname "$0")/../../../_shared/system-skills.sh"
emit_system_skills_inline "$CORE" >> ""$SAGE_ROOT/AGENTS.md""
  echo "  ✓ AGENTS.md"
fi

# ── Dynamic constitution merging (same as Claude Code) ──
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

if [ "$SKIP_AGENTS_MD" = false ]; then
  python3 -c "
with open('$SAGE_ROOT/AGENTS.md', 'r') as f:
    content = f.read()
replacement = '''$CONST_SECTION'''
content = content.replace('__CONSTITUTION_PLACEHOLDER__', replacement)
with open('$SAGE_ROOT/AGENTS.md', 'w') as f:
    f.write(content)
" 2>/dev/null || true
fi

# ═══════════════════════════════════════════════════════════════
# Per-workflow command files in .opencode/commands/
# Format: markdown with YAML frontmatter
# Filename = command name (e.g., build.md → /build)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📎 Generating .opencode/commands/ from core workflows..."

# Source the shared preambles emitter
source "$(dirname "$0")/../../../_shared/preambles.sh"

for wf in "$CORE"/workflows/*.workflow.md; do
  [ -f "$wf" ] || continue
  basename_wf=$(basename "$wf" .workflow.md)

  # Get preamble (preserve trailing newlines)
  PREAMBLE=$({ emit_preamble "$basename_wf"; printf x; })
  PREAMBLE="${PREAMBLE%x}"

  # Get workflow description from frontmatter for the YAML `description:` field
  WF_DESC=$(sed -n '/^---$/,/^---$/{ /^produces:/s/^produces: *//p; }' "$wf" \
    | head -1 | sed 's/\[//g;s/\]//g;s/"//g' | cut -c1-100)
  [ -z "$WF_DESC" ] && WF_DESC="Sage $basename_wf workflow"

  # /sage stays unprefixed; everything else gets PREFIX
  cmd_name="$basename_wf"
  [ "$basename_wf" != "sage" ] && cmd_name="${PREFIX}${basename_wf}"

  # Build the command file — YAML frontmatter + preamble + workflow body
  {
    echo "---"
    echo "description: ${WF_DESC}"
    echo "---"
    echo ""
    # Preamble translated for Opencode terminology
    printf "%s" "$PREAMBLE" | sed \
      -e 's|Task tool|sub-agent invocation|g' \
      -e 's|the Task tool|the sub-agent system|g'
    # Workflow body (strip frontmatter, substitute paths)
    sed '/^---$/,/^---$/d' "$wf" \
      | sed 's|\*\*sage-navigator\*\* skill|**sage-navigator** skill at `sage/core/capabilities/orchestration/sage-navigator/SKILL.md`|g' \
      | sed "s|sage-navigator's intelligence layer|sage-navigator's intelligence layer (\`sage/core/capabilities/orchestration/sage-navigator/SKILL.md\`, section 2)|g" \
      | sed 's|If relevant Sage skills exist, read and follow them.|If relevant Sage skills exist in `sage/skills/`, read and follow them.|g' \
      | sed '/^$/N;/^\n$/d'
    echo ""
    echo '$ARGUMENTS'
  } > "$OC_DIR/commands/${cmd_name}.md"

  echo "  ✓ ${cmd_name}.md → /${cmd_name}"
done

# ═══════════════════════════════════════════════════════════════
# Sub-agents in .opencode/agents/
# Format: markdown with YAML frontmatter (mode: subagent)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🤖 Generating .opencode/agents/ sub-agents..."

cat > "$OC_DIR/agents/sage-reviewer.md" << 'AGENT_EOF'
---
description: Independent reviewer for Sage artifacts (spec, plan, ADR, root cause, fix plan, QA). READ-ONLY — never modifies files.
mode: subagent
permission:
  edit: deny
  bash: deny
---

You are a review sub-agent for the Sage framework. You were NOT
involved in writing the artifact under review. Evaluate it with fresh
eyes. Be specific. Be brief.

CRITICAL: You are READ-ONLY. Do NOT modify any files. Do NOT use
Edit or Write tools. Your job is to REPORT findings, not fix them.

You will be invoked with a specific review prompt (spec review, plan
review, ADR review, root cause review, fix plan review, or QA review).
The invocation will tell you which artifact to read and which checks
to run. Follow the prompt's CHECK list precisely.

Classify each finding:
- CRITICAL: Must fix. Blocks the next phase.
- MAJOR: Should fix. Significant gap or risk.
- MINOR-substantive: Improvement opportunity affecting readability,
  maintainability, or future behavior.
- MINOR-cosmetic: Style/naming/formatting with equally valid alternatives.
  No behavior change.

Output format (strict):
VERDICT: PASS | NEEDS REVISION | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. No generic praise. No padding. Just findings.
AGENT_EOF
echo "  ✓ sage-reviewer.md"

cat > "$OC_DIR/agents/sage-classifier.md" << 'AGENT_EOF'
---
description: Routes free-input requests to the right Sage workflow when keyword routing doesn't match.
mode: subagent
permission:
  edit: deny
  bash: deny
---

You are a routing classifier for the Sage framework. Your only job is
to classify a request into one of three phases of work:

- UNDERSTAND: research, analyze, learn, investigate
- ENVISION: design, architect, plan
- DELIVER: build, fix, ship

Read the user's request. Pick ONE phase. Respond with just the phase
name (UNDERSTAND, ENVISION, or DELIVER) and one short sentence of
reasoning.

Do not ask questions. Do not produce code. Do not propose workflows.
Classification only.
AGENT_EOF
echo "  ✓ sage-classifier.md"

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
echo "✅ Sage → Opencode setup complete"
echo ""
echo "Files written:"
echo "  AGENTS.md                    (read by Opencode as system context)"
echo "  .opencode/commands/          (markdown command definitions)"
echo "  .opencode/agents/            (markdown sub-agent definitions)"
echo ""
echo "Next steps:"
echo "  - Run \`opencode\` to start a session"
echo "  - Type /sage or describe what you want to build"
echo "  - Sub-agent reviews use @sage-reviewer (invoked automatically by workflows)"
echo ""
