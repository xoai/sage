#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# generate-plugin.sh — Sage Plugin Generator for Claude Code
#
# Reads the Sage framework and produces a valid Claude Code plugin.
# The framework is the source of truth; the plugin is a distribution format.
#
# Usage: bash generate-plugin.sh [sage-root] [output-dir]
# ═══════════════════════════════════════════════════════════════

SAGE_ROOT="${1:-.}"
OUTPUT="${2:-$SAGE_ROOT/sage-plugin}"

CORE="$SAGE_ROOT/core"
SKILLS_DIR="$SAGE_ROOT/skills"
WORKFLOWS="$CORE/workflows"
AGENTS_SRC="$CORE/agents"
CONSTITUTION="$CORE/constitution"
TEMPLATES="$SAGE_ROOT/develop/templates"
REFERENCES="$CORE/references"
GUIDES="$SAGE_ROOT/develop/guides"
CC_GEN="$SAGE_ROOT/runtime/platforms/claude-code/setup/generate-claude-code.sh"
HOOKS_SRC="$SAGE_ROOT/runtime/platforms/claude-code/hooks"
GATES_SRC="$CORE/gates/scripts"

echo "═══ Sage Plugin Generator ═══"
echo ""

# ─── Validate source ───
if [ ! -f "$CC_GEN" ]; then
  echo "ERROR: Cannot find $CC_GEN"
  echo "Run from the Sage framework root, or pass the path as first argument."
  exit 1
fi

# ─── Clean + create output structure ───
rm -rf "$OUTPUT"
mkdir -p "$OUTPUT/.claude-plugin"
mkdir -p "$OUTPUT/skills"
mkdir -p "$OUTPUT/agents"
mkdir -p "$OUTPUT/hooks/scripts"
mkdir -p "$OUTPUT/scripts"
mkdir -p "$OUTPUT/references"

# ═══════════════════════════════════════════════════════════════
# Task 1: Generate plugin.json
# ═══════════════════════════════════════════════════════════════
echo "📦 Generating plugin.json..."

VERSION=$(grep -m1 '^\#\# \[' "$SAGE_ROOT/CHANGELOG.md" | sed 's/.*\[\(.*\)\].*/\1/')
[ -z "$VERSION" ] && VERSION="0.0.0"

cat > "$OUTPUT/.claude-plugin/plugin.json" << PJEOF
{
  "name": "sage",
  "version": "$VERSION",
  "description": "AI skills framework: UNDERSTAND → ENVISION → DELIVER → REFLECT. Process enforcement, 14 workflows, 37 skills, 5 agent personas.",
  "author": {
    "name": "xoai",
    "url": "https://github.com/xoai"
  },
  "repository": "https://github.com/xoai/sage",
  "license": "MIT",
  "keywords": ["framework", "process", "skills", "workflows", "product", "engineering", "design", "ux", "research"]
}
PJEOF

echo "  ✓ plugin.json (v$VERSION)"

# ═══════════════════════════════════════════════════════════════
# Task 2: Generate sage-navigator skill
# ═══════════════════════════════════════════════════════════════
echo "🧭 Generating sage-navigator skill..."

mkdir -p "$OUTPUT/skills/sage-navigator"

# Extract CLAUDE.md content from CC generator (between CLAUDEEOF markers)
CLAUDEMD_CONTENT=$(sed -n "/^cat > \"\$SAGE_ROOT\/CLAUDE.md\" << 'CLAUDEEOF'$/,/^CLAUDEEOF$/{ /CLAUDEEOF/d; /^cat /d; p; }" "$CC_GEN")

cat > "$OUTPUT/skills/sage-navigator/SKILL.md" << 'NAVHEAD'
---
name: sage-navigator
description: >
  Sage process framework — constitution, routing, interaction zones,
  enforcement rules. Auto-loads to provide process enforcement, keyword
  routing, and structured interaction patterns for all Sage workflows.
  This is the always-on layer that ensures quality even when specific
  workflow skills are not loaded.
user-invocable: false
---

NAVHEAD

# Write the CLAUDE.md content (minus the auto-generated header line)
echo "$CLAUDEMD_CONTENT" | sed '1,3d' >> "$OUTPUT/skills/sage-navigator/SKILL.md"

# Append constitution merge note
cat >> "$OUTPUT/skills/sage-navigator/SKILL.md" << 'NAVFOOT'

## Constitution Presets

The default preset is **base** (TDD, no silent failures, simple first,
document decisions, work in the open). To switch presets, type
`/sage:configure`.

Presets add constraints on top of base — they never remove inherited
principles. Available: base, startup, enterprise, opensource.

If `.sage/config.yaml` specifies a preset, load the additional rules
from this skill's preset sections below on session start.
NAVFOOT

# Append preset contents inline
for preset_file in "$CONSTITUTION/presets/"*.constitution.md; do
  [ -f "$preset_file" ] || continue
  preset_name=$(basename "$preset_file" .constitution.md)
  echo "" >> "$OUTPUT/skills/sage-navigator/SKILL.md"
  echo "### Preset: $preset_name" >> "$OUTPUT/skills/sage-navigator/SKILL.md"
  echo "" >> "$OUTPUT/skills/sage-navigator/SKILL.md"
  # Strip frontmatter if present
  sed '/^---$/,/^---$/d' "$preset_file" >> "$OUTPUT/skills/sage-navigator/SKILL.md"
done

NAV_LINES=$(wc -l < "$OUTPUT/skills/sage-navigator/SKILL.md")
echo "  ✓ sage-navigator ($NAV_LINES lines)"

# ═══════════════════════════════════════════════════════════════
# Task 3: Generate workflow skills (14)
# ═══════════════════════════════════════════════════════════════
echo "⚡ Generating workflow skills..."

WF_COUNT=0

# Extract preambles from CC generator into a temp lookup
PREAMBLE_CACHE=$(mktemp)
# Parse the case statement: extract workflow name and preamble content
awk '
  /^    [a-z_-]+\)$/ { name = $1; sub(/\)/, "", name); next }
  /PREAMBLE='"'"'/ { capture=1; preamble=""; next }
  capture && /^'"'"'$/ { capture=0; print name "|||" preamble; next }
  capture { preamble = preamble $0 "\n" }
' "$CC_GEN" > "$PREAMBLE_CACHE"

# Special case: extract sage command (self-contained SAGEEOF block)
SAGE_CMD=$(sed -n "/^    cat > \"\$CLAUDE_DIR\/commands\/sage.md\" << 'SAGEEOF'$/,/^SAGEEOF$/{ /SAGEEOF/d; /^    cat /d; p; }" "$CC_GEN")

# Special case: extract review command (REVIEWEOF block)
REVIEW_CMD=$(sed -n "/^    cat > \"\$CLAUDE_DIR\/commands\/review.md\" << 'REVIEWEOF'$/,/^REVIEWEOF$/{ /REVIEWEOF/d; /^    cat /d; p; }" "$CC_GEN")

for wf_file in "$WORKFLOWS"/*.workflow.md; do
  [ -f "$wf_file" ] || continue
  wf_name=$(basename "$wf_file" .workflow.md)

  mkdir -p "$OUTPUT/skills/$wf_name"

  # Get description from workflow frontmatter — clean it up
  wf_desc=$(sed -n '/^---$/,/^---$/{ /^produces:/s/^produces: *//p; }' "$wf_file" | head -1 | sed 's/\[//g;s/\]//g;s/"//g')
  [ -z "$wf_desc" ] && wf_desc="Sage $wf_name workflow"
  # Truncate to 120 chars
  wf_desc=$(echo "$wf_desc" | cut -c1-120)

  # Get preamble for this workflow
  preamble=$(grep "^${wf_name}|||" "$PREAMBLE_CACHE" | sed "s/^${wf_name}|||//" || true)

  # Strip YAML frontmatter from workflow
  wf_body=$(sed '/^---$/,/^---$/d' "$wf_file")

  # Handle special cases
  if [ "$wf_name" = "sage" ] && [ -n "$SAGE_CMD" ]; then
    cat > "$OUTPUT/skills/$wf_name/SKILL.md" << WFEOF
---
name: $wf_name
description: >
  Start here. Sage reads project state, routes via keywords, classifies
  intent, and guides you to the right workflow.
disable-model-invocation: true
---

$SAGE_CMD
WFEOF
  elif [ "$wf_name" = "review" ] && [ -n "$REVIEW_CMD" ]; then
    cat > "$OUTPUT/skills/$wf_name/SKILL.md" << WFEOF
---
name: $wf_name
description: >
  Independent artifact review via sub-agent delegation. Evaluates
  completeness, consistency, and quality with severity classification.
disable-model-invocation: true
---

$REVIEW_CMD
WFEOF
  else
    # Standard workflow: frontmatter + preamble + body
    {
      echo "---"
      echo "name: $wf_name"
      echo "description: >-"
      echo "  $wf_desc"
      echo "disable-model-invocation: true"
      echo "---"
      echo ""
      if [ -n "$preamble" ]; then
        printf "%b" "$preamble"
        echo ""
      fi
      echo "$wf_body"
    } > "$OUTPUT/skills/$wf_name/SKILL.md"
  fi

  WF_COUNT=$((WF_COUNT + 1))
done

rm -f "$PREAMBLE_CACHE"
echo "  ✓ $WF_COUNT workflow skills"

# ═══════════════════════════════════════════════════════════════
# Task 4: Copy direct skills (37)
# ═══════════════════════════════════════════════════════════════
echo "📚 Copying direct skills..."

SK_COUNT=0
for skill_dir in "$SKILLS_DIR"/*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "$skill_dir")
  [ -f "$skill_dir/SKILL.md" ] || continue

  # Skip if a workflow skill already exists with this name
  [ -d "$OUTPUT/skills/$skill_name" ] && continue

  mkdir -p "$OUTPUT/skills/$skill_name"
  cp "$skill_dir/SKILL.md" "$OUTPUT/skills/$skill_name/SKILL.md"

  # Copy references/ and scripts/ if they exist
  [ -d "$skill_dir/references" ] && cp -r "$skill_dir/references" "$OUTPUT/skills/$skill_name/"
  [ -d "$skill_dir/scripts" ] && cp -r "$skill_dir/scripts" "$OUTPUT/skills/$skill_name/"

  SK_COUNT=$((SK_COUNT + 1))
done

echo "  ✓ $SK_COUNT direct skills"

# ═══════════════════════════════════════════════════════════════
# Task 5: Generate agent definitions (5)
# ═══════════════════════════════════════════════════════════════
echo "🤖 Generating agent definitions..."

AG_COUNT=0
for persona_file in "$AGENTS_SRC"/*.persona.md; do
  [ -f "$persona_file" ] || continue
  agent_name=$(basename "$persona_file" .persona.md)

  # Read persona content (strip frontmatter if any)
  persona_content=$(sed '/^---$/,/^---$/d' "$persona_file")

  # Extract description from persona frontmatter
  first_line=$(sed -n '/^---$/,/^---$/{ /^description:/s/^description: *//p; }' "$persona_file" | head -1)
  [ -z "$first_line" ] && first_line="Sage $agent_name persona"

  # Extract activates-in for capabilities
  activates=$(sed -n '/^---$/,/^---$/{ /^activates-in:/s/^activates-in: *//p; }' "$persona_file" | head -1 | sed 's/\[//g;s/\]//g')

  cat > "$OUTPUT/agents/$agent_name.md" << AGEOF
---
description: >-
  $first_line
capabilities:
  - Activates in: $activates
---

$persona_content
AGEOF

  AG_COUNT=$((AG_COUNT + 1))
done

echo "  ✓ $AG_COUNT agent definitions"

# ═══════════════════════════════════════════════════════════════
# Task 6: Generate hooks.json + copy scripts
# ═══════════════════════════════════════════════════════════════
echo "🔗 Generating hooks and scripts..."

cat > "$OUTPUT/hooks/hooks.json" << 'HOOKEOF'
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/sage-session-init.sh",
        "timeout": 10
      }]
    }],
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/sage-verify.sh ${CLAUDE_PROJECT_DIR}",
        "timeout": 30
      }]
    }]
  }
}
HOOKEOF

# Copy hook scripts
SCRIPT_COUNT=0

if [ -f "$HOOKS_SRC/sage-session-init.sh" ]; then
  cp "$HOOKS_SRC/sage-session-init.sh" "$OUTPUT/hooks/scripts/"
  chmod +x "$OUTPUT/hooks/scripts/sage-session-init.sh"
  SCRIPT_COUNT=$((SCRIPT_COUNT + 1))
fi

# Copy gate scripts
for gate_script in "$GATES_SRC"/*.sh; do
  [ -f "$gate_script" ] || continue
  cp "$gate_script" "$OUTPUT/hooks/scripts/"
  chmod +x "$OUTPUT/hooks/scripts/$(basename "$gate_script")"
  SCRIPT_COUNT=$((SCRIPT_COUNT + 1))
done

# Copy sage CLI tool
if [ -f "$SAGE_ROOT/bin/sage" ]; then
  cp "$SAGE_ROOT/bin/sage" "$OUTPUT/scripts/sage"
  chmod +x "$OUTPUT/scripts/sage"
fi

echo "  ✓ hooks.json + $SCRIPT_COUNT scripts"

# ═══════════════════════════════════════════════════════════════
# Task 7: Copy references and templates
# ═══════════════════════════════════════════════════════════════
echo "📄 Copying references and templates..."

REF_COUNT=0

# Lightpanda setup
if [ -f "$REFERENCES/lightpanda-setup.md" ]; then
  cp "$REFERENCES/lightpanda-setup.md" "$OUTPUT/references/"
  REF_COUNT=$((REF_COUNT + 1))
fi

# Skill authoring guide
if [ -f "$GUIDES/skill-authoring-guide.md" ]; then
  cp "$GUIDES/skill-authoring-guide.md" "$OUTPUT/references/"
  REF_COUNT=$((REF_COUNT + 1))
fi

# Templates (flattened into references/)
for tmpl in \
  "$TEMPLATES/spec/minimal.spec-template.md:spec-template.md" \
  "$TEMPLATES/spec/full.spec-template.md:full-spec-template.md" \
  "$TEMPLATES/plan/standard.plan-template.md:plan-template.md" \
  "$TEMPLATES/manifest-template.md:manifest-template.md" \
  "$TEMPLATES/qa-report-template.md:qa-report-template.md" \
  "$TEMPLATES/design-review-template.md:design-review-template.md" \
  "$TEMPLATES/architecture/decision-template.md:decision-template.md" \
  "$TEMPLATES/journal-template.md:journal-template.md"; do

  src="${tmpl%%:*}"
  dst="${tmpl##*:}"
  if [ -f "$src" ]; then
    cp "$src" "$OUTPUT/references/$dst"
    REF_COUNT=$((REF_COUNT + 1))
  fi
done

echo "  ✓ $REF_COUNT references"

# Copy key capabilities that workflows reference
CAP_COUNT=0
CAPS_DIR="$CORE/capabilities"
for cap_file in \
  "$CAPS_DIR/review/auto-review/SKILL.md:auto-review.md" \
  "$CAPS_DIR/review/auto-qa/SKILL.md:auto-qa.md" \
  "$CAPS_DIR/execution/coding-principles/SKILL.md:coding-principles.md" \
  "$CAPS_DIR/verification/browser-check/SKILL.md:browser-check.md" \
  "$CAPS_DIR/verification/design-check/SKILL.md:design-check.md"; do

  src="${cap_file%%:*}"
  dst="${cap_file##*:}"
  if [ -f "$src" ]; then
    cp "$src" "$OUTPUT/references/$dst"
    CAP_COUNT=$((CAP_COUNT + 1))
  fi
done
[ "$CAP_COUNT" -gt 0 ] && echo "  ✓ $CAP_COUNT capabilities copied to references"

# ═══════════════════════════════════════════════════════════════
# Task 8: Create /sage:configure skill
# ═══════════════════════════════════════════════════════════════
echo "⚙️  Generating configure skill..."

mkdir -p "$OUTPUT/skills/configure"

cat > "$OUTPUT/skills/configure/SKILL.md" << 'CFGEOF'
---
name: configure
description: >
  Configure Sage preset and project settings. Switch between base,
  startup, enterprise, or opensource constitution presets. Use when
  the user says "configure sage", "change preset", or "sage settings".
disable-model-invocation: true
---

# Configure Sage

Set up project-level Sage configuration.

## Step 1: Read Current Config

Read `.sage/config.yaml` if it exists. If not, note: "No project
config found. Using base preset (default)."

## Step 2: Present Options (Zone 1)

Sage: Current preset: {current or "base (default)"}

[1] Base — TDD, no silent failures, simple first, document decisions
[2] Startup — velocity-focused, lighter process, ship fast
[3] Enterprise — compliance, audit trails, security-first
[4] Open Source — contributor-friendly, RFC process, public decisions

Pick 1-4, or describe what you need.

## Step 3: Apply Preset

Write the choice to `.sage/config.yaml`:

```yaml
preset: {chosen-preset}
```

If `.sage/` doesn't exist, create it with:
- config.yaml (with preset)
- decisions.md (empty template)

## Step 4: Confirm

Sage: Preset updated to {preset}. Start a new session or reload
the plugin to apply the new rules.

The {preset} preset adds these principles on top of base:
{list key additions from the chosen preset}

Type a command, or describe what you want to do next.

## Preset Summaries

**Base** (default): TDD first, no silent failures, simplest solution
first, document decisions, work in the open. Applied to all projects.

**Startup**: Bias toward shipping. Reduce ceremony for small changes.
Speed > perfection for v1. But: never skip tests, never skip root
cause analysis. Fast doesn't mean reckless.

**Enterprise**: Every change auditable. Security review on auth/data
changes. Compliance evidence in artifacts. Approval chains documented.
Change management discipline.

**Open Source**: Changes proposed as RFCs. Public decision log.
Contributor-friendly: explain WHY in every decision. Breaking changes
get migration guides. Backward compatibility by default.
CFGEOF

echo "  ✓ configure skill"

# ═══════════════════════════════════════════════════════════════
# Task 9: Validation + report
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🔍 Validating..."

# Validate plugin.json
if python3 -c "import json; json.load(open('$OUTPUT/.claude-plugin/plugin.json'))" 2>/dev/null; then
  echo "  ✓ plugin.json valid JSON"
else
  echo "  ✗ plugin.json invalid JSON!"
  exit 1
fi

# Count everything
TOTAL_SKILLS=$(find "$OUTPUT/skills" -name SKILL.md | wc -l)
TOTAL_AGENTS=$(find "$OUTPUT/agents" -name "*.md" | wc -l)
TOTAL_HOOKS=$(python3 -c "
import json
h = json.load(open('$OUTPUT/hooks/hooks.json'))
events = list(h.get('hooks', {}).keys())
print(len(events))
" 2>/dev/null || echo "0")
TOTAL_REFS=$(find "$OUTPUT/references" -name "*.md" | wc -l)
TOTAL_SCRIPTS=$(find "$OUTPUT/hooks/scripts" -name "*.sh" | wc -l)
TOTAL_SIZE=$(du -sh "$OUTPUT" | cut -f1)

# Verify key files
MISSING=""
[ -f "$OUTPUT/skills/sage-navigator/SKILL.md" ] || MISSING="$MISSING navigator"
[ -f "$OUTPUT/skills/build/SKILL.md" ] || MISSING="$MISSING build"
[ -f "$OUTPUT/skills/fix/SKILL.md" ] || MISSING="$MISSING fix"
[ -f "$OUTPUT/skills/configure/SKILL.md" ] || MISSING="$MISSING configure"
[ -f "$OUTPUT/hooks/hooks.json" ] || MISSING="$MISSING hooks.json"

if [ -n "$MISSING" ]; then
  echo "  ✗ Missing:$MISSING"
  exit 1
fi
echo "  ✓ All key files present"

# Report
echo ""
echo "═══════════════════════════════════════════════"
echo "  ✓ Sage plugin generated: $OUTPUT/"
echo ""
echo "  plugin.json:  v$VERSION"
echo "  Skills:       $TOTAL_SKILLS ($WF_COUNT workflows + $SK_COUNT direct + navigator + configure)"
echo "  Agents:       $TOTAL_AGENTS"
echo "  Hooks:        $TOTAL_HOOKS events (SessionStart + PostToolUse)"
echo "  References:   $TOTAL_REFS templates"
echo "  Scripts:      $TOTAL_SCRIPTS"
echo "  Size:         $TOTAL_SIZE"
echo ""
echo "  To test locally:"
echo "    claude --plugin-dir $OUTPUT"
echo ""
echo "  To distribute via marketplace:"
echo "    Push to GitHub, then users run:"
echo "    /plugin marketplace add xoai/sage"
echo "    /plugin install sage@xoai"
echo "═══════════════════════════════════════════════"
