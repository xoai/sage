#!/usr/bin/env bash
# Validate all constitutions against constitution.contract.md
set -uo pipefail
SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-constitutions"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"
pass() { PASS=$((PASS + 1)); echo "  $(echo -e '\033[32m✓\033[0m') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(echo -e '\033[31m✗\033[0m') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(echo -e '\033[33m⚠\033[0m') $1"; }

echo ""
echo -e "\033[1m── Constitution Contract Validation ──\033[0m"

FILES=$(find "$SAGE_ROOT/constitution" -name "*.constitution.md" 2>/dev/null | sort)
COUNT=$(echo "$FILES" | grep -c "constitution" || echo "0")
echo "  Found $COUNT constitutions"
echo ""

for f in $FILES; do
  name=$(basename "$f" .constitution.md)
  echo "  Checking: $name"

  if ! head -1 "$f" | grep -q "^---$"; then
    fail "$name: missing YAML frontmatter"; continue
  fi

  fm=$(sed -n '/^---$/,/^---$/p' "$f" | sed '1d;$d')

  # name field
  [ -n "$(echo "$fm" | grep '^name:')" ] && pass "$name: has name" || fail "$name: missing name"

  # tier field
  tier=$(echo "$fm" | grep -oP '^tier:\s*\K\d+' | head -1)
  if [ -n "$tier" ]; then
    pass "$name: has tier ($tier)"
  else
    fail "$name: missing tier field"
  fi

  # version
  echo "$fm" | grep -qP '^version:' && pass "$name: has version" || fail "$name: missing version"

  # Check for numbered principles
  body=$(sed -n '/^---$/,/^---$/!p' "$f" | tail -n +2)
  principle_count=$(echo "$body" | grep -cP '^\d+\.' || echo "0")
  if [ "$principle_count" -gt 0 ]; then
    pass "$name: has $principle_count numbered principles"
  else
    warn "$name: no numbered principles found"
  fi

  # Starters should have extends
  if echo "$f" | grep -q "presets"; then
    if echo "$fm" | grep -q "^extends:"; then
      pass "$name: starter has extends field"
    else
      warn "$name: preset constitution should have 'extends' field"
    fi
  fi

  echo ""
done

echo "  Constitutions: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
