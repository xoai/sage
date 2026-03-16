#!/usr/bin/env bash
# Validate all gates against gate.contract.md
set -uo pipefail

SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-gates"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"

green()  { echo -e "\033[32m$1\033[0m"; }
red()    { echo -e "\033[31m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
pass() { PASS=$((PASS + 1)); echo "  $(green '✓') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(red '✗') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(yellow '⚠') $1"; }

echo ""
echo -e "\033[1m── Gate Contract Validation ──\033[0m"

GATE_FILES=$(find "$SAGE_ROOT/core/gates" -name "*.gate.md" -not -path "*optional*" 2>/dev/null | sort)
GATE_COUNT=$(echo "$GATE_FILES" | grep -c "gate.md" || echo "0")
echo "  Found $GATE_COUNT gates to validate"
echo ""

for gate_file in $GATE_FILES; do
  gate_name=$(basename "$gate_file" .gate.md)
  echo "  Checking: $gate_name"

  # Check YAML frontmatter
  if ! head -1 "$gate_file" | grep -q "^---$"; then
    fail "$gate_name: missing YAML frontmatter"
    continue
  fi

  frontmatter=$(sed -n '/^---$/,/^---$/p' "$gate_file" | sed '1d;$d')

  # Required: name
  if echo "$frontmatter" | grep -q "^name:"; then
    pass "$gate_name: has name field"
  else
    fail "$gate_name: missing 'name' field"
  fi

  # Required: order (integer)
  order=$(echo "$frontmatter" | grep -oP '^order:\s*\K\d+' | head -1)
  if [ -n "$order" ]; then
    pass "$gate_name: has order ($order)"
    # Check filename matches order
    file_order=$(echo "$gate_name" | grep -oP '^\d+')
    if [ "$file_order" = "$order" ] || [ "$file_order" = "0$order" ]; then
      pass "$gate_name: filename prefix matches order"
    else
      warn "$gate_name: filename prefix '$file_order' doesn't match order '$order'"
    fi
  else
    fail "$gate_name: missing 'order' field (must be integer 01-99)"
  fi

  # Required: version
  if echo "$frontmatter" | grep -qP '^version:\s*"?\d+\.\d+\.\d+"?'; then
    pass "$gate_name: has valid version"
  else
    fail "$gate_name: missing or invalid version"
  fi

  # Required: category
  category=$(echo "$frontmatter" | grep -oP '^category:\s*\K\S+' | head -1)
  if echo "$category" | grep -qP '^(compliance|quality|safety|verification)$'; then
    pass "$gate_name: valid category ($category)"
  else
    fail "$gate_name: category must be one of: compliance, quality, safety, verification (got: '$category')"
  fi

  # Body: Check Criteria section
  body=$(sed -n '/^---$/,/^---$/!p' "$gate_file" | tail -n +2)
  if echo "$body" | grep -qi "^## Check Criteria"; then
    pass "$gate_name: has Check Criteria section"
  else
    fail "$gate_name: missing 'Check Criteria' section (required by contract)"
  fi

  # Body: Failure Response section
  if echo "$body" | grep -qi "^## Failure Response"; then
    pass "$gate_name: has Failure Response section"
  else
    fail "$gate_name: missing 'Failure Response' section"
  fi

  # Body: Adversarial Guidance section
  if echo "$body" | grep -qi "^## Adversarial"; then
    pass "$gate_name: has Adversarial Guidance section"
  else
    warn "$gate_name: missing Adversarial Guidance section (recommended)"
  fi

  echo ""
done

# Validate gate-modes.yaml
echo "  Checking: gate-modes.yaml"
MODES_FILE="$SAGE_ROOT/core/gates/_config/gate-modes.yaml"
if [ -f "$MODES_FILE" ]; then
  pass "gate-modes.yaml: exists"
  for mode in fix build architect; do
    if grep -q "^${mode}:" "$MODES_FILE"; then
      pass "gate-modes.yaml: has $mode configuration"
    else
      fail "gate-modes.yaml: missing $mode mode configuration"
    fi
  done
  # Check all gate names in modes file reference actual gate files
  gate_names_in_config=$(grep -oP '- \K[\w-]+' "$MODES_FILE" | sort -u)
  for gn in $gate_names_in_config; do
    if find "$SAGE_ROOT/core/gates" -name "*${gn}*" -type f 2>/dev/null | grep -q .; then
      pass "gate-modes.yaml: '$gn' references an existing gate"
    else
      fail "gate-modes.yaml: '$gn' references non-existent gate"
    fi
  done
else
  fail "gate-modes.yaml: not found at $MODES_FILE"
fi

echo ""
echo "  Gates: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"
echo "FAIL:$FAIL" >> "$RESULTS"
echo "WARN:$WARN" >> "$RESULTS"
