#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Hermes Setup
# Generates AGENTS.md + Hermes SKILLs (skills/<name>/SKILL.md) for a
# Hermes Agent home/profile.
#
# Hermes reads AGENTS.md as the agent constitution, discovers skills by
# their `name:` frontmatter (category folder is cosmetic), and surfaces
# skills as slash commands (/build, /fix, ...). Hermes normalizes the
# `name:` to the command slug by lowercasing + mapping space/underscore
# to '-' and STRIPPING any char not in [a-z0-9-] — so the prefix
# separator here is '-' (not ':'), or the colon would be stripped and
# /sage:build would resolve as /sagebuild.
#
# Independent reviews use Hermes' delegate_task with a restricted
# toolsets=["file"] (drops terminal/code_execution) plus a strong
# read-only prompt — best-effort enforcement, NOT permission-denial
# (Hermes has no opencode-style permission:{edit:deny,bash:deny}).
#
# Cloned from generate-opencode.sh with these changes:
#   1. workflow  -> Hermes SKILL.md (name/description/metadata.hermes)
#   2. "Task tool" -> "delegate_task"; $ARGUMENTS -> a prose phrase
#      (Hermes does NOT interpolate $ARGUMENTS — user args arrive as a
#      separate appended instruction line)
#   3. prefix separator ':' -> '-' (Hermes name-slug rules)
#   (registration of 'hermes' lives in bin/sage, not here)
#
# NOTE on AGENTS.md co-ownership: Hermes writes AGENTS.md (like codex +
# opencode). Do NOT run this generator alongside codex/opencode in one
# pass (the second writer clobbers the first's terminology). This is why
# bin/sage intentionally excludes 'hermes' from the `all` expansion.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
# Target Hermes home. Defaults to SAGE_ROOT for project-local generation
# (the path bin/sage uses — run_generators passes only one positional
# arg). Pass a profile dir (e.g. ~/.hermes or a Hermes profile) as $2 to
# generate INTO that profile — manual-invocation only.
HERMES_HOME="${2:-$SAGE_ROOT}"
SAGE_DIR="$SAGE_ROOT/sage"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"
SKILLS_DIR="$HERMES_HOME/skills"

# Phrase substituted for the literal $ARGUMENTS token: Hermes delivers
# user input typed after a slash command as a SEPARATE appended line
# ("The user has provided the following instruction alongside the skill
# invocation: <text>"), so $ARGUMENTS would otherwise reach the model
# verbatim. The flag-parser commands must operate on this, not the token.
ARGS_PHRASE='the arguments the user provided alongside this skill invocation (delivered as a separate instruction line, NOT a literal token)'

echo ""
echo "🚀 Sage → Hermes Setup"
echo "═══════════════════════════════"
echo "   Sage root:    $SAGE_ROOT"
echo "   Hermes home:  $HERMES_HOME"

# ── Validate ──
if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  echo "   Run this from the project root where sage/ is located."
  exit 1
fi

# ── Read prefix config ── (Hermes name-slug rule → '-' separator, not ':')
PREFIX=""
if [ -f "$PROJECT_SAGE/config.yaml" ]; then
  if grep -q 'command_prefix: true' "$PROJECT_SAGE/config.yaml" 2>/dev/null; then
    PREFIX="sage-"
  fi
fi

# ── Create skills dir ──
# SKILLs are written here directly by the host shell (mkdir + heredoc),
# which BYPASSES Hermes' skills.write_approval staging (that only gates
# agent-side skill_manage writes) — so they apply immediately, no
# `/skills approve` needed. A re-run overwrites prior generated SKILLs.
echo ""
echo "📁 Ensuring Hermes skills dir: $SKILLS_DIR"
mkdir -p "$SKILLS_DIR"

# ═══════════════════════════════════════════════════════════════
# AGENTS.md — Hermes reads AGENTS.md as the constitution.
# Reuse opencode's emit + clobber-guard (don't overwrite a non-Sage
# AGENTS.md). Co-owned with codex/opencode — see header note.
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📝 Generating AGENTS.md..."

SKIP_AGENTS_MD=false
if [ -f "$HERMES_HOME/AGENTS.md" ]; then
  if head -1 "$HERMES_HOME/AGENTS.md" 2>/dev/null | grep -q "Sage"; then
    SKIP_AGENTS_MD=false  # Sage-generated, safe to overwrite
  else
    SKIP_AGENTS_MD=true
    echo "  ⚠ AGENTS.md exists and is not Sage-generated — skipping write."
    echo "    Move or rename it if you want Sage to manage it."
  fi
fi

if [ "$SKIP_AGENTS_MD" = false ]; then
  source "$(dirname "$0")/../../_shared/instructions-body.sh"
  emit_instructions_body \
    | sed \
      -e 's|the Task tool|the delegate_task tool|g' \
      -e 's|Task tool|delegate_task|g' \
      -e "s|\$ARGUMENTS|${ARGS_PHRASE}|g" \
      -e 's|`.claude/commands/\[workflow\].md`|the Hermes skill `/[workflow]`|g' \
    > "$HERMES_HOME/AGENTS.md"
  echo "  ✓ AGENTS.md"
fi

# ── Dynamic constitution merging (identical to opencode/claude-code) ──
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

# Placeholder swap — pass file path + content via ENV (no source
# interpolation: a quote/apostrophe in HERMES_HOME or a preset line can't
# break it), and FAIL LOUDLY rather than silently leaving the token.
if [ "$SKIP_AGENTS_MD" = false ]; then
  if command -v python3 >/dev/null 2>&1; then
    SAGE_AGENTS_FILE="$HERMES_HOME/AGENTS.md" SAGE_CONST="$CONST_SECTION" python3 - <<'PY' || echo "  ⚠ constitution merge step failed — check AGENTS.md for __CONSTITUTION_PLACEHOLDER__"
import os
p = os.environ["SAGE_AGENTS_FILE"]
with open(p, "r", encoding="utf-8") as f:
    content = f.read()
content = content.replace("__CONSTITUTION_PLACEHOLDER__", os.environ["SAGE_CONST"])
with open(p, "w", encoding="utf-8") as f:
    f.write(content)
PY
    if grep -q '__CONSTITUTION_PLACEHOLDER__' "$HERMES_HOME/AGENTS.md" 2>/dev/null; then
      echo "  ⚠ __CONSTITUTION_PLACEHOLDER__ still present in AGENTS.md — constitution NOT merged"
    fi
  else
    echo "  ⚠ python3 not found — constitution placeholder NOT merged into AGENTS.md"
  fi
fi

# ═══════════════════════════════════════════════════════════════
# Per-workflow Hermes SKILLs: skills/<name>/SKILL.md
# Hermes frontmatter: name (identity, = slash command), description,
# metadata.hermes.tags. Body = When-to-Use + preamble + workflow.
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📎 Generating Hermes SKILLs from core workflows..."

source "$(dirname "$0")/../../_shared/preambles.sh"

for wf in "$CORE"/workflows/*.workflow.md; do
  [ -f "$wf" ] || continue
  name=$(basename "$wf" .workflow.md)

  PREAMBLE=$({ emit_preamble "$name"; printf x; })
  PREAMBLE="${PREAMBLE%x}"

  WF_DESC=$(sed -n '/^---$/,/^---$/{ /^produces:/s/^produces: *//p; }' "$wf" \
    | head -1 | sed 's/\[//g;s/\]//g;s/"//g' | cut -c1-100)
  [ -z "$WF_DESC" ] && WF_DESC="Sage $name workflow"
  # Quote the description + escape internal quotes so a value containing
  # ': ' or a YAML indicator char can't break frontmatter parsing.
  WF_DESC_ESC=$(printf '%s' "$WF_DESC" | sed 's/"/\\"/g')

  # /sage stays unprefixed; everything else gets PREFIX (sage-).
  # name: IS the slash command after Hermes normalization, so it must be
  # a valid slug ([a-z0-9-]); the '-' prefix keeps it valid.
  skill_name="$name"
  [ "$name" != "sage" ] && skill_name="${PREFIX}${name}"
  dir_name="$skill_name"

  mkdir -p "$SKILLS_DIR/$dir_name"
  {
    echo "---"
    echo "name: ${skill_name}"
    echo "description: \"${WF_DESC_ESC}\""
    echo "version: 1.0.0"
    echo "author: Sage"
    echo "metadata:"
    echo "  hermes:"
    echo "    tags: [Sage, Workflow, ${name}]"
    echo "---"
    echo ""
    echo "## When to Use"
    echo "Load this skill when the user runs \`/${skill_name}\` or asks to ${name} something (the Sage ${name} workflow)."
    echo ""
    echo "## Arguments"
    echo "Hermes does NOT interpolate an in-body argument token. The user's arguments/flags arrive as a SEPARATE instruction line appended to this skill invocation. Wherever the steps below refer to \"the user's arguments\", use the text of that appended instruction line."
    echo ""
    echo "## Independent review (delegate_task)"
    echo "When a step calls for an independent review, invoke \`delegate_task\` with a restricted \`toolsets=[\"file\"]\` (drops terminal/code_execution) against the \`sage-reviewer\` skill. This is best-effort read-only (restricted toolset + prompt), NOT permission-denied — verify the reviewer never edits a file during the run."
    echo ""
    # Preamble, translated for Hermes (delegate_task; $ARGUMENTS -> phrase)
    printf "%s" "$PREAMBLE" | sed \
      -e 's|the Task tool|the delegate_task tool|g' \
      -e 's|Task tool|delegate_task|g' \
      -e "s|\$ARGUMENTS|${ARGS_PHRASE}|g"
    # Workflow body (strip frontmatter, point sage-navigator + skills at sage/)
    sed '/^---$/,/^---$/d' "$wf" \
      | sed 's|\*\*sage-navigator\*\* skill|**sage-navigator** skill at `sage/core/capabilities/orchestration/sage-navigator/SKILL.md`|g' \
      | sed "s|sage-navigator's intelligence layer|sage-navigator's intelligence layer (\`sage/core/capabilities/orchestration/sage-navigator/SKILL.md\`, section 2)|g" \
      | sed 's|If relevant Sage skills exist, read and follow them.|If relevant Sage skills exist in `sage/skills/`, read and follow them.|g' \
      | sed -e 's|the Task tool|the delegate_task tool|g' -e 's|Task tool|delegate_task|g' \
      | sed "s|\$ARGUMENTS|${ARGS_PHRASE}|g" \
      | sed '/^$/N;/^\n$/d'
  } > "$SKILLS_DIR/$dir_name/SKILL.md"

  echo "  ✓ ${skill_name} → /${skill_name}"
done

# ═══════════════════════════════════════════════════════════════
# Reviewer + classifier as Hermes SKILLs
# READ-ONLY is best-effort: invoke via delegate_task with
# toolsets=["file"] (no terminal/code_execution) + the prompt below.
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🤖 Generating sage-reviewer + sage-classifier SKILLs..."

mkdir -p "$SKILLS_DIR/sage-reviewer"
cat > "$SKILLS_DIR/sage-reviewer/SKILL.md" << 'AGENT_EOF'
---
name: sage-reviewer
description: "Independent READ-ONLY reviewer for Sage artifacts (spec, plan, ADR, root cause, fix plan, QA). Invoke via delegate_task with toolsets=[\"file\"]."
version: 1.0.0
author: Sage
metadata:
  hermes:
    tags: [Sage, Review]
---

# Sage Reviewer

You are a review sub-agent for the Sage framework, invoked via
`delegate_task`. You were NOT involved in writing the artifact under
review. Evaluate it with fresh eyes. Be specific. Be brief.

## Invocation
The parent should invoke you with `toolsets=["file"]` so you have no
terminal/code_execution (best-effort read-only). Even so:

## CRITICAL: READ-ONLY
Do NOT modify, create, or delete any file. Do NOT run any command that
writes to disk or mutates state. If you modify anything, THE REVIEW IS
INVALID and must be discarded. Your job is to REPORT findings, not fix them.

## Procedure
You will be invoked with a specific review prompt (spec review, plan
review, ADR review, root cause review, fix plan review, or QA review).
It tells you which artifact to read and which checks to run. Follow the
prompt's CHECK list precisely. Read only the artifact + the cited context.

Classify each finding:
- CRITICAL: Must fix. Blocks the next phase.
- MAJOR: Should fix. Significant gap or risk.
- MINOR-substantive: Improvement affecting readability/maintainability/behavior.
- MINOR-cosmetic: Style/naming with equally valid alternatives. No behavior change.

## Output (strict)
VERDICT: PASS | NEEDS REVISION | FAIL
CRITICAL: [list or "None"]
MAJOR: [list or "None"]
MINOR-substantive: [list or "None"]
MINOR-cosmetic: [list or "None"]

Be concise. No generic praise. No padding. Just findings.
AGENT_EOF
echo "  ✓ sage-reviewer"

mkdir -p "$SKILLS_DIR/sage-classifier"
cat > "$SKILLS_DIR/sage-classifier/SKILL.md" << 'AGENT_EOF'
---
name: sage-classifier
description: "Routes free-input requests to the right Sage workflow phase when keyword routing doesn't match. Invoke via delegate_task with toolsets=[\"file\"]."
version: 1.0.0
author: Sage
metadata:
  hermes:
    tags: [Sage, Routing]
---

# Sage Classifier

You are a routing classifier for the Sage framework, invoked via
`delegate_task`. Your only job is to classify a request into one of
three phases of work:

- UNDERSTAND: research, analyze, learn, investigate
- ENVISION: design, architect, plan
- DELIVER: build, fix, ship

Read the user's request. Pick ONE phase. Respond with just the phase
name (UNDERSTAND, ENVISION, or DELIVER) and one short sentence of
reasoning. Do not ask questions. Do not produce code. Do not propose
workflows. Classification only. READ-ONLY: do not modify any file.
AGENT_EOF
echo "  ✓ sage-classifier"

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
echo "✅ Sage → Hermes setup complete"
echo ""
echo "Files written:"
echo "  $HERMES_HOME/AGENTS.md            (Hermes constitution)"
echo "  $SKILLS_DIR/<name>/SKILL.md       (workflow skills → /build, /fix, ...)"
echo "  $SKILLS_DIR/sage-reviewer/        (read-only reviewer, via delegate_task toolsets=[file])"
echo "  $SKILLS_DIR/sage-classifier/      (router, via delegate_task)"
echo ""
echo "Next steps:"
echo "  - hermes skills reload   (or restart the gateway) to index the new SKILLs"
echo "  - /sage or /build etc. should now resolve to the Sage workflows"
echo ""
