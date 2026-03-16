#!/usr/bin/env bash
# Validate all personas against agent.contract.md
set -uo pipefail
SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-personas"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"
pass() { PASS=$((PASS + 1)); echo "  $(echo -e '\033[32m✓\033[0m') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(echo -e '\033[31m✗\033[0m') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(echo -e '\033[33m⚠\033[0m') $1"; }

echo ""
echo -e "\033[1m── Persona Contract Validation ──\033[0m"

FILES=$(find "$SAGE_ROOT/agents" -name "*.persona.md" 2>/dev/null | sort)
COUNT=$(echo "$FILES" | grep -c "persona" || echo "0")
echo "  Found $COUNT personas"
echo ""

for f in $FILES; do
  name=$(basename "$f" .persona.md)
  echo "  Checking: $name"

  if ! head -1 "$f" | grep -q "^---$"; then
    fail "$name: missing frontmatter"; continue
  fi

  fm=$(sed -n '/^---$/,/^---$/p' "$f" | sed '1d;$d')

  echo "$fm" | grep -q "^name:" && pass "$name: has name" || fail "$name: missing name"
  echo "$fm" | grep -q "^version:" && pass "$name: has version" || fail "$name: missing version"
  echo "$fm" | grep -q "^activates-in:" && pass "$name: has activates-in" || fail "$name: missing activates-in"
  echo "$fm" | grep -q "^applies-to-skills:" && pass "$name: has applies-to-skills" || fail "$name: missing applies-to-skills"

  # Check token budget — personas should be lightweight
  line_count=$(wc -l < "$f")
  if [ "$line_count" -gt 60 ]; then
    warn "$name: $line_count lines — personas should be under ~40 lines (500 tokens)"
  else
    pass "$name: lightweight ($line_count lines)"
  fi

  # Check for required sections
  body=$(sed -n '/^---$/,/^---$/!p' "$f" | tail -n +2)
  echo "$body" | grep -qi "^## Identity" && pass "$name: has Identity section" || warn "$name: missing Identity section"
  echo "$body" | grep -qi "^## Principles" && pass "$name: has Principles section" || warn "$name: missing Principles section"
  echo "$body" | grep -qi "^## Anti-Patterns" && pass "$name: has Anti-Patterns section" || warn "$name: missing Anti-Patterns"

  echo ""
done

echo "  Personas: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
