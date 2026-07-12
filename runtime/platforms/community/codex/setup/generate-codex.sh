#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Codex (OpenAI) Setup
# Generates AGENTS.md + .codex/agents/ for OpenAI Codex.
# Codex reads AGENTS.md as its system prompt and reads TOML
# agent definitions from .codex/agents/.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
CODEX_DIR="$SAGE_ROOT/.codex"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"

echo ""
echo "🚀 Sage → Codex Setup"
echo "═══════════════════════════════"

# ── Validate ──
if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  echo "   Run this from the project root where sage/ is located."
  exit 1
fi

# ── Create .codex structure ──
echo ""
echo "📁 Creating .codex/ structure..."
mkdir -p "$CODEX_DIR/agents"

# ═══════════════════════════════════════════════════════════════
# AGENTS.md — Generated from shared instructions-body
# Codex reads AGENTS.md as the system prompt (with a 32KiB cap).
# Terminology swaps: "Task tool" → "sub-agent invocation"
#                    ".claude/commands/" → "AGENTS.md routing"
# ═══════════════════════════════════════════════════════════════
echo "📝 Generating AGENTS.md..."

source "$(dirname "$0")/../../../_shared/instructions-body.sh"

emit_instructions_body \
  | sed \
    -e 's|Task tool|sub-agent invocation|g' \
    -e 's|the Task tool|the sub-agent system|g' \
    -e 's|`.claude/commands/\[workflow\].md`|`AGENTS.md` (this file)|g' \
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

  PROJECT_ADDITIONS=$(sed -n '/^## Project Additions/,$ { /^## Project/d; /^$/d; /^(/d; p; }' "$CONST_FILE" 2>/dev/null)
  if [ -n "$PROJECT_ADDITIONS" ]; then
    CONST_SECTION="$CONST_SECTION

Project additions:"
    while IFS= read -r line; do
      if [ -n "$line" ]; then
        PRINCIPLE_NUM=$((PRINCIPLE_NUM + 1))
        CONST_SECTION="$CONST_SECTION
${PRINCIPLE_NUM}. ${line}"
      fi
    done <<< "$PROJECT_ADDITIONS"
  fi
fi

# Replace placeholder in AGENTS.md
python3 -c "
with open('$SAGE_ROOT/AGENTS.md', 'r') as f:
    content = f.read()
replacement = '''$CONST_SECTION'''
content = content.replace('__CONSTITUTION_PLACEHOLDER__', replacement)
with open('$SAGE_ROOT/AGENTS.md', 'w') as f:
    f.write(content)
" 2>/dev/null || {
  sed -i.bak "s|__CONSTITUTION_PLACEHOLDER__|## Engineering Principles\n\nBase (all projects):\n1. Tests before code\n2. No silent failures\n3. Secrets never in code\n4. Dependencies explicit\n5. Changes reversible|" "$SAGE_ROOT/AGENTS.md" 2>/dev/null && rm -f "$SAGE_ROOT/AGENTS.md.bak"
}

# ── Size check (Codex 32 KiB cap) ──
AGENTS_SIZE=$(wc -c < "$SAGE_ROOT/AGENTS.md")
AGENTS_LIMIT=32768
if [ "$AGENTS_SIZE" -gt "$AGENTS_LIMIT" ]; then
  echo "  ⚠ AGENTS.md is $AGENTS_SIZE bytes — Codex default cap is 32 KiB."
  echo "    Set project_doc_max_bytes in ~/.codex/config.toml to allow it."
else
  echo "  ✓ AGENTS.md ($AGENTS_SIZE bytes, under 32 KiB cap)"
fi

# ═══════════════════════════════════════════════════════════════
# Sub-agents — Codex reads .codex/agents/*.toml
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🤖 Generating .codex/agents/ sub-agents..."

# Reviewer sub-agent (used by auto-review, auto-qa, quality-locked)
cat > "$CODEX_DIR/agents/sage-reviewer.toml" << 'AGENT_EOF'
name = "sage-reviewer"
description = "Independent reviewer for Sage artifacts (spec, plan, ADR, root cause, fix plan, QA). READ-ONLY — never modifies files."
sandbox_mode = "read-only"
developer_instructions = """
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
"""
AGENT_EOF
echo "  ✓ sage-reviewer.toml"

# Classifier sub-agent (used by navigator Layer 2 routing)
cat > "$CODEX_DIR/agents/sage-classifier.toml" << 'AGENT_EOF'
name = "sage-classifier"
description = "Routes free-input requests to the right Sage workflow when keyword routing doesn't match."
sandbox_mode = "read-only"
developer_instructions = """
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
"""
AGENT_EOF
echo "  ✓ sage-classifier.toml"

# ═══════════════════════════════════════════════════════════════
# Project state — .sage/ initialization (same logic as Claude Code)
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
echo "✅ Sage → Codex setup complete"
echo ""
echo "Files written:"
echo "  AGENTS.md                  (read by Codex as system prompt)"
echo "  .codex/agents/             (TOML sub-agent definitions)"
echo ""
echo "Next steps:"
echo "  - Run \`codex\` to start a session"
echo "  - The sage-reviewer agent is invoked automatically by Sage workflows"
echo "    that need independent review. Codex will spawn it on request."
echo "  - Sage workflows are described in AGENTS.md routing table"
echo ""
