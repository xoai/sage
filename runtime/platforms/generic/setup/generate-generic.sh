#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Generic platform setup
# Generates CLAUDE.md for any tool that reads a project instructions file:
# Cursor, Copilot, Windsurf, and anything else with file-based configuration.
# ═══════════════════════════════════════════════════════════════
#
# WHY THIS EXISTS
#
# Until now there was no generic generator. `runtime/platforms/generic/CLAUDE.md`
# was a hand-written file that nothing emitted and nobody regenerated, and it had
# drifted so far from the real instructions that it still documented "Modes" and
# `.sage/skills/` paths which no longer exist. A platform whose instructions file
# is maintained by hand is a platform whose instructions file is already wrong.
#
# WHAT IS DIFFERENT HERE (ADR-9 / ADR-11)
#
# Delivery is capability-gated. Claude Code has native description-triggered skill
# discovery, so Sage's reference content ships as on-demand skills and its eager
# layer is small. Generic platforms have no discovery mechanism — there is nothing
# to trigger a skill — so the same content must be INLINED into the instructions
# file, and generic's eager layer is correspondingly larger.
#
# That is not a regression. It is the honest cost of a platform that cannot fetch
# on demand, and it is measured in its own budget row rather than hidden inside
# claude-code's number.
#
# NO HOOKS. Generic platforms have no PreToolUse veto, so Rules 3 and 5 are
# enforced by prose alone here. The gate SCRIPTS still run standalone — they need
# only bash and python3 — but nothing invokes them automatically. That degradation
# is stated in the generated file rather than left for the user to discover.

set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"
OUT="$SAGE_ROOT/CLAUDE.md"

echo ""
echo "🚀 Sage → Generic Setup"
echo "═══════════════════════════════"

if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  exit 1
fi

# ── Instructions body (same source as every other platform) ──
echo ""
echo "📝 Generating CLAUDE.md..."
source "$(dirname "$0")/../../_shared/instructions-body.sh"
emit_instructions_body > "$OUT"

# ── Constitution ──
source "$(dirname "$0")/../../_shared/constitution.sh"
CONST_SECTION="$(build_constitution_section "$CORE" "$PROJECT_SAGE")"

# The constitution is passed on stdin rather than interpolated into the script
# body: a project addition containing a quote character would otherwise break the
# python literal, and a project's constitution is exactly the kind of file that
# eventually contains a quote character.
CONST_TMP="$(mktemp)"
printf '%s\n' "$CONST_SECTION" > "$CONST_TMP"

if command -v python3 >/dev/null 2>&1; then
  python3 - "$OUT" "$CONST_TMP" <<'PYEOF'
import sys
out_path, const_path = sys.argv[1], sys.argv[2]
with open(const_path) as f:
    replacement = f.read().rstrip("\n")
with open(out_path) as f:
    content = f.read()
with open(out_path, "w") as f:
    f.write(content.replace("__CONSTITUTION_PLACEHOLDER__", replacement))
PYEOF
else
  # No python3. Fail loudly rather than shipping an instructions file with a
  # placeholder token where the project's principles should be.
  echo "❌ python3 is required to merge the constitution."
  rm -f "$CONST_TMP"
  exit 1
fi
rm -f "$CONST_TMP"

# ── Command table (deleted from the shared body; re-inlined here) ──
#
# claude-code lists the generated .claude/commands/ in its own `/` menu, so a
# hand-written table in the eager layer was nineteen lines duplicating a menu the
# user can already see. Generic platforms have no menu — so the table comes back
# here, GENERATED from core/workflows/ rather than hand-maintained. The old table
# had already drifted (it still listed workflows under their pre-v1.2.0 names),
# which is what a hand-written index of a directory always eventually does.
if [ -d "$CORE/workflows" ]; then
  {
    echo ""
    echo "## Workflows"
    echo ""
    echo "This platform has no slash-command menu. Invoke a workflow by reading"
    echo "and following its file under \`sage/core/workflows/\`."
    echo ""
    echo "| Workflow | File | What it does |"
    echo "|---|---|---|"
    for wf in "$CORE"/workflows/*.workflow.md; do
      [ -f "$wf" ] || continue
      wf_name=$(basename "$wf" .workflow.md)
      wf_desc=$(sed -n '/^---$/,/^---$/{ /^description:/s/^description: *//p; }' "$wf" 2>/dev/null | head -1)
      [ -z "$wf_desc" ] && wf_desc="(no description)"
      echo "| \`/$wf_name\` | \`sage/core/workflows/$wf_name.workflow.md\` | $wf_desc |"
    done
  } >> "$OUT"
fi

# ── Inline the system skills (no discovery mechanism to trigger them) ──
source "$(dirname "$0")/../../_shared/system-skills.sh"
emit_system_skills_inline "$CORE" >> "$OUT"
SYS_COUNT=$(find "$CORE/system-skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')

echo "  ✓ CLAUDE.md generated ($(wc -l < "$OUT" | tr -d ' ') lines, $SYS_COUNT skills inlined)"

# ── .sage/ scaffolding ──
mkdir -p "$PROJECT_SAGE/work" "$PROJECT_SAGE/docs"
[ -f "$PROJECT_SAGE/decisions.md" ] || printf '# Decisions\n\n' > "$PROJECT_SAGE/decisions.md"

# ── Gate scripts (they only need bash + python3, so they work here) ──
if [ -d "$CORE/gates/scripts" ]; then
  mkdir -p "$PROJECT_SAGE/gates"
  cp "$CORE"/gates/scripts/*.sh "$PROJECT_SAGE/gates/" 2>/dev/null || true
  chmod +x "$PROJECT_SAGE"/gates/*.sh 2>/dev/null || true
  echo "  ✓ Gate scripts installed to .sage/gates/ (run them manually — nothing fires them for you)"
fi

echo ""
echo "⚠️  Enforcement is degraded on this platform, and that is not a bug report — it is the contract:"
echo "     • No PreToolUse hooks — nothing BLOCKS an edit that skips the spec or the test."
echo "     • No subagents — reviews run in the same context they are reviewing."
echo "     Rules 3 and 5 are enforced by prose here. On Claude Code they are enforced by scripts."
echo ""
echo "✅ Sage is set up for a generic platform."
echo ""
