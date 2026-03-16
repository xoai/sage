#!/usr/bin/env bash
# Validate all skills against skill.contract.md
# Usage: bash develop/validators/contracts/validate-skills.sh [sage-root]

set -uo pipefail

SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-skills"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"

green()  { echo -e "\033[32m$1\033[0m"; }
red()    { echo -e "\033[31m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
pass() { PASS=$((PASS + 1)); echo "  $(green '✓') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(red '✗') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(yellow '⚠') $1"; }

echo ""
echo -e "\033[1m── Skill Contract Validation ──\033[0m"

# Find all SKILL.md files
SKILL_FILES=$(find "$SAGE_ROOT/core/capabilities" -name "SKILL.md" -not -path "*/\{*" 2>/dev/null | sort)
SKILL_COUNT=$(echo "$SKILL_FILES" | grep -c "SKILL.md" || echo "0")
echo "  Found $SKILL_COUNT skills to validate"
echo ""

if [ "$SKILL_COUNT" -eq 0 ]; then
  fail "No SKILL.md files found in $SAGE_ROOT/core/capabilities/"
  echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
  exit 0
fi

for skill_file in $SKILL_FILES; do
  skill_dir=$(dirname "$skill_file")
  skill_name=$(basename "$skill_dir")
  echo "  Checking: $skill_name"

  # ── Check 1: YAML frontmatter exists ──
  if head -1 "$skill_file" | grep -q "^---$"; then
    pass "$skill_name: has YAML frontmatter"
  else
    fail "$skill_name: missing YAML frontmatter (must start with ---)"
    continue
  fi

  # Extract frontmatter
  frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill_file" | sed '1d;$d')

  # ── Check 2: Required field — name ──
  fm_name=$(echo "$frontmatter" | grep -oP '^name:\s*\K\S+' | head -1)
  if [ -n "$fm_name" ]; then
    pass "$skill_name: has 'name' field ($fm_name)"
    # Check kebab-case
    if echo "$fm_name" | grep -qP '^[a-z][a-z0-9]*(-[a-z0-9]+)*$'; then
      pass "$skill_name: name is kebab-case"
    else
      fail "$skill_name: name '$fm_name' is not kebab-case (must be lowercase-with-hyphens)"
    fi
    # Check name matches directory
    if [ "$fm_name" = "$skill_name" ]; then
      pass "$skill_name: name matches directory name"
    else
      warn "$skill_name: name '$fm_name' doesn't match directory '$skill_name'"
    fi
  else
    fail "$skill_name: missing required 'name' field in frontmatter"
  fi

  # ── Check 3: Required field — description ──
  if echo "$frontmatter" | grep -q "^description:"; then
    desc=$(echo "$frontmatter" | sed -n '/^description:/,/^[a-z]/p' | head -5)
    desc_len=${#desc}
    if [ "$desc_len" -gt 50 ]; then
      pass "$skill_name: has description (${desc_len} chars)"
    else
      warn "$skill_name: description is short ($desc_len chars) — may not trigger reliably"
    fi
  else
    fail "$skill_name: missing required 'description' field"
  fi

  # ── Check 4: Required field — version ──
  if echo "$frontmatter" | grep -qP '^version:\s*"?\d+\.\d+\.\d+"?'; then
    pass "$skill_name: has valid semver version"
  else
    fail "$skill_name: missing or invalid 'version' field (must be semver: X.Y.Z)"
  fi

  # ── Check 5: Required field — modes ──
  if echo "$frontmatter" | grep -q "^modes:"; then
    modes=$(echo "$frontmatter" | grep -oP '^modes:\s*\[?\K[^\]]+')
    if echo "$modes" | grep -qP '(fix|build|architect)'; then
      pass "$skill_name: has valid modes ($modes)"
    else
      fail "$skill_name: modes must contain at least one of: fix, build, architect"
    fi
  else
    fail "$skill_name: missing required 'modes' field"
  fi

  # ── Check 6: Body structure — has ## sections ──
  body=$(sed -n '/^---$/,/^---$/!p' "$skill_file" | tail -n +2)
  section_count=$(echo "$body" | grep -c "^## " || echo "0")
  if [ "$section_count" -ge 2 ]; then
    pass "$skill_name: has $section_count sections"
  else
    warn "$skill_name: only $section_count sections — consider adding more structure"
  fi

  # ── Check 7: Has "When to Use" or "Process" section ──
  if echo "$body" | grep -qi "^## \(When to Use\|Process\|Rules\)"; then
    pass "$skill_name: has actionable sections (When to Use / Process / Rules)"
  else
    warn "$skill_name: missing 'When to Use', 'Process', or 'Rules' section"
  fi

  # ── Check 8: Has failure modes ──
  if echo "$body" | grep -qi "^## Failure"; then
    pass "$skill_name: has Failure Modes section"
  else
    warn "$skill_name: missing Failure Modes section (recommended by contract)"
  fi

  # ── Check 9: Reasonable length ──
  line_count=$(wc -l < "$skill_file")
  if [ "$line_count" -gt 500 ]; then
    warn "$skill_name: $line_count lines — consider splitting into SKILL.md + references/"
  elif [ "$line_count" -lt 20 ]; then
    warn "$skill_name: only $line_count lines — may be too brief to be useful"
  else
    pass "$skill_name: reasonable length ($line_count lines)"
  fi

  echo ""
done

echo "  Skills: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"
echo "FAIL:$FAIL" >> "$RESULTS"
echo "WARN:$WARN" >> "$RESULTS"
