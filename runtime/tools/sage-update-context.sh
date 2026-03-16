#!/usr/bin/env bash
# sage-update-context.sh — Generate CLAUDE.md from template + active packs + constitution
# Usage: bash sage/runtime/tools/sage-update-context.sh [project-root]

set -euo pipefail

ROOT="${1:-.}"
SAGE_DIR="$ROOT/.sage"
SAGE_SRC="${SAGE_SRC:-sage}"
TEMPLATE="$SAGE_SRC/core/context-loader/CLAUDE.md.template"
OUTPUT="$ROOT/CLAUDE.md"

if [ ! -f "$SAGE_DIR/config.yaml" ]; then
  echo "❌ No .sage/config.yaml found. Run onboard first."
  exit 1
fi

echo "── Generating CLAUDE.md ──"

# Read enabled packs
PACKS=$(grep -A 50 'enabled:' "$SAGE_DIR/config.yaml" | grep '^\s*-' | sed 's/.*- //' | head -20)

# Start with template
cp "$TEMPLATE" "$OUTPUT"

# Build pack section
PACK_SECTION=""
for pack in $PACKS; do
  pack_dir="$SAGE_SRC/skills/@sage/$pack"
  [ -d "$pack_dir" ] || continue
  layer=$(grep '^layer:' "$pack_dir/SKILL.md manifest" 2>/dev/null | head -1 | sed 's/layer:\s*//')
  PACK_SECTION="$PACK_SECTION\n### @sage/$pack (L$layer)\n"
  # Append patterns summary (first line of each pattern)
  for pf in "$pack_dir"/patterns/*.md; do
    [ -f "$pf" ] || continue
    grep '^# ' "$pf" | while read -r line; do
      PACK_SECTION="$PACK_SECTION- $line\n"
    done
  done
  # Append constitution additions
  for cf in "$pack_dir"/constitution/*.md; do
    [ -f "$cf" ] || continue
    PACK_SECTION="$PACK_SECTION\n$(cat "$cf")\n"
  done
done

# Build constitution from base + preset
CONST=""
preset=$(grep 'preset:' "$SAGE_DIR/config.yaml" 2>/dev/null | head -1 | sed 's/.*preset:\s*//' | tr -d ' ')
[ -f "$SAGE_SRC/core/constitution/base.constitution.md" ] && CONST="$(cat "$SAGE_SRC/constitution/base.constitution.md")"
[ -f "$SAGE_SRC/core/constitution/presets/${preset}.constitution.md" ] && CONST="$CONST
$(cat "$SAGE_SRC/core/constitution/presets/${preset}.constitution.md")"

# Conventions
CONV="No conventions established yet. They'll be discovered during first codebase scan."
[ -f "$SAGE_DIR/conventions.md" ] && CONV="$(cat "$SAGE_DIR/conventions.md")"

# Replace placeholders using python (handles multiline)
python3 << PYEOF
t = open("$OUTPUT").read()
t = t.replace("{{CONSTITUTION_PRINCIPLES}}", """$CONST""")
t = t.replace("{{LOADED_PACKS}}", """$(echo -e "$PACK_SECTION")""")
t = t.replace("{{CONVENTIONS}}", """$CONV""")
open("$OUTPUT","w").write(t)
PYEOF

# Append skill reference
cat >> "$OUTPUT" << 'SKILLS'

## Skills Quick Reference

| Skill | When | What It Does |
|-------|------|-------------|
| `sage-help` | Anytime | Shows what to do next based on current state |
| `onboard` | First run | Detects stack, selects packs, generates .sage/ |
| `codebase-scan` | Before planning | Understands existing patterns and conventions |
| `quick-elicit` | BUILD mode | 3-round guided specification (~2 min) |
| `plan` | After spec approved | Breaks spec into 2-5 min tasks with file paths |
| `build-loop` | After plan approved | Executes tasks with quality gates between each |
| `implement` | Per task | TDD: test → code → refactor → commit |
| `systematic-debug` | FIX mode | 4-phase root cause analysis |
| `session-bridge` | Session boundaries | Preserves context across sessions |
SKILLS

echo "  ✅ Generated $OUTPUT ($(wc -l < "$OUTPUT") lines)"
echo "  Packs: $(echo $PACKS | tr '\n' ' ')"
