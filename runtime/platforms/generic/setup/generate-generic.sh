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

# ── Inline the system skills (no discovery mechanism to trigger them) ──
#
# On claude-code these are separate files that load when their description
# matches. Here they are appended verbatim, because a skill nothing can trigger
# is a skill that does not exist.
SYS_COUNT=0
if [ -d "$CORE/system-skills" ]; then
  {
    echo ""
    echo "---"
    echo ""
    echo "# Reference"
    echo ""
    echo "On platforms with native skill discovery, everything below is fetched"
    echo "on demand. This platform has no discovery mechanism, so it is inlined."
    echo "Read the section that matches what you are doing; ignore the rest."
  } >> "$OUT"

  for sys_dir in "$CORE/system-skills"/*/; do
    [ -d "$sys_dir" ] || continue
    [ -f "$sys_dir/SKILL.md" ] || continue

    {
      echo ""
      # Strip the YAML frontmatter — it is trigger metadata for a mechanism this
      # platform does not have, and it would read as noise.
      sed '1{/^---$/!q;};1,/^---$/d' "$sys_dir/SKILL.md"
    } >> "$OUT"

    SYS_COUNT=$((SYS_COUNT + 1))
  done
fi

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
