#!/usr/bin/env bash
# Validate all templates against template.contract.md
set -uo pipefail
SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS="/tmp/sage-test-results-templates"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"
pass() { PASS=$((PASS + 1)); echo "  $(echo -e '\033[32m✓\033[0m') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(echo -e '\033[31m✗\033[0m') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(echo -e '\033[33m⚠\033[0m') $1"; }

echo ""
echo -e "\033[1m── Template Contract Validation ──\033[0m"

# Templates live under core/templates (moved from develop/templates in Phase 3).
# Fall back to the older locations for pre-move trees.
TEMPLATES_DIR="$SAGE_ROOT/core/templates"
[ -d "$TEMPLATES_DIR" ] || TEMPLATES_DIR="$SAGE_ROOT/develop/templates"
[ -d "$TEMPLATES_DIR" ] || TEMPLATES_DIR="$SAGE_ROOT/templates"
# Every .md under core/templates/ is a template and gets checked. The old glob
# was `*template*` — a filename convention, not a location — so the four subagent
# prompts (context-packet.md, implementer-prompt.md, …) would have sat in the
# templates directory, unchecked, forever, because of how they are spelled.
FILES=$(find "$TEMPLATES_DIR" -type f -name "*.md" -not -name "README*" 2>/dev/null | sort)
# `grep -c` prints 0 AND exits 1 when it matches nothing, so the old
# `grep -c ... || echo "0"` appended a SECOND zero and COUNT became "0\n0" —
# which then blew up `[ "$COUNT" -eq 0 ]` with "integer expression expected".
# Count the lines instead; an empty FILES is the only zero case.
if [ -z "$FILES" ]; then
  COUNT=0
else
  COUNT=$(printf '%s\n' "$FILES" | wc -l | tr -d ' ')
fi
echo "  Found $COUNT templates"

# Zero is not a pass. It means the search was wrong, not that the tree is clean.
if [ "$COUNT" -eq 0 ]; then
  echo ""
  echo "  ⚠️  UNVERIFIABLE — no templates found under $TEMPLATES_DIR."
  echo "     Nothing was checked. This is exit 2, not exit 0: 'everything passed'"
  echo "     and 'nothing was examined' are different claims."
  exit 2
fi
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
  placeholder_count=$(echo "$body" | grep -cE '[{][a-z_]+[}]' || echo "0")
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
