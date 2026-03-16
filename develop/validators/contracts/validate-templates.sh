#!/usr/bin/env bash
# Validate all templates against template.contract.md
set -uo pipefail
SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-templates"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"
pass() { PASS=$((PASS + 1)); echo "  $(echo -e '\033[32m✓\033[0m') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(echo -e '\033[31m✗\033[0m') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(echo -e '\033[33m⚠\033[0m') $1"; }

echo ""
echo -e "\033[1m── Template Contract Validation ──\033[0m"

FILES=$(find "$SAGE_ROOT/templates" -type f -name "*template*" -not -name "README*" 2>/dev/null | sort)
COUNT=$(echo "$FILES" | grep -c "template" || echo "0")
echo "  Found $COUNT templates"
echo ""

for f in $FILES; do
  name=$(basename "$f" .md)
  echo "  Checking: $name"

  if ! head -1 "$f" | grep -q "^---$"; then
    fail "$name: missing frontmatter"; continue
  fi

  fm=$(sed -n '/^---$/,/^---$/p' "$f" | sed '1d;$d')

  echo "$fm" | grep -q "^name:" && pass "$name: has name" || fail "$name: missing name"
  echo "$fm" | grep -q "^type:" && pass "$name: has type" || fail "$name: missing type"
  echo "$fm" | grep -q "^variant:" && pass "$name: has variant" || fail "$name: missing variant"
  echo "$fm" | grep -q "^version:" && pass "$name: has version" || fail "$name: missing version"

  # Check for placeholder syntax
  body=$(sed -n '/^---$/,/^---$/!p' "$f" | tail -n +2)
  placeholder_count=$(echo "$body" | grep -coP '\{[a-z_]+\}' || echo "0")
  if [ "$placeholder_count" -gt 0 ]; then
    pass "$name: has $placeholder_count placeholders"
  else
    warn "$name: no {placeholder} syntax found"
  fi

  # Check for SECTION markers
  section_count=$(echo "$body" | grep -c '\[SECTION:' || echo "0")
  if [ "$section_count" -gt 0 ]; then
    pass "$name: has $section_count named sections"
    # Verify sections are closed
    close_count=$(echo "$body" | grep -c '\[/SECTION\]' || echo "0")
    if [ "$section_count" -eq "$close_count" ]; then
      pass "$name: all sections properly closed"
    else
      fail "$name: $section_count sections opened but $close_count closed"
    fi
  else
    warn "$name: no [SECTION:] markers (optional but enables partial loading)"
  fi

  echo ""
done

echo "  Templates: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
