#!/usr/bin/env bash
# Validate cross-references between modules
# Checks: workflows reference real skills, personas bind to real skills,
# gate-modes reference real gates, etc.
set -uo pipefail
SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-xrefs"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"
pass() { PASS=$((PASS + 1)); echo "  $(echo -e '\033[32m✓\033[0m') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(echo -e '\033[31m✗\033[0m') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(echo -e '\033[33m⚠\033[0m') $1"; }

echo ""
echo -e "\033[1m── Cross-Reference Validation ──\033[0m"

# Build list of known skill names
KNOWN_SKILLS=""
for sf in $(find "$SAGE_ROOT/skills" -name "SKILL.md" -not -path "*/\{*" 2>/dev/null); do
  sn=$(sed -n '/^---$/,/^---$/p' "$sf" | grep -oP '^name:\s*\K\S+' | head -1)
  [ -n "$sn" ] && KNOWN_SKILLS+=" $sn"
done
echo "  Known skills:$KNOWN_SKILLS"
echo ""

# ── Check 1: Workflow skill references ──
echo "  Checking workflow → skill references..."
for wf in $(find "$SAGE_ROOT/workflows" -name "*.workflow.md" 2>/dev/null); do
  wf_name=$(basename "$wf" .workflow.md)
  # Extract backtick-quoted skill references from workflow body
  refs=$(sed -n '/^---$/,/^---$/!p' "$wf" | grep -oP '`([\w-]+)`' | tr -d '`' | sort -u)
  for ref in $refs; do
    # Skip known non-skill references (sub-workflow names, generic terms)
    if echo "$ref" | grep -qP '^(quality-gates|sub-workflow|session-start)$'; then
      continue
    fi
    if echo "$KNOWN_SKILLS" | grep -qw "$ref"; then
      pass "workflow/$wf_name → skill '$ref' exists"
    else
      warn "workflow/$wf_name references '$ref' — not found as a skill name (may be a workflow concept)"
    fi
  done
done
echo ""

# ── Check 2: Persona → skill bindings ──
echo "  Checking persona → skill bindings..."
for pf in $(find "$SAGE_ROOT/agents" -name "*.persona.md" 2>/dev/null); do
  p_name=$(basename "$pf" .persona.md)
  fm=$(sed -n '/^---$/,/^---$/p' "$pf" | sed '1d;$d')
  bindings=$(echo "$fm" | grep -oP 'applies-to-skills:\s*\[\K[^\]]+' | tr ',' '\n' | sed 's/^ *//;s/ *$//')
  for binding in $bindings; do
    if echo "$KNOWN_SKILLS" | grep -qw "$binding"; then
      pass "persona/$p_name → skill '$binding' exists"
    else
      fail "persona/$p_name binds to skill '$binding' which doesn't exist"
    fi
  done
done
echo ""

# ── Check 3: Skill requires → skill exists ──
echo "  Checking skill → skill dependencies..."
for sf in $(find "$SAGE_ROOT/skills" -name "SKILL.md" -not -path "*/\{*" 2>/dev/null); do
  s_name=$(sed -n '/^---$/,/^---$/p' "$sf" | grep -oP '^name:\s*\K\S+' | head -1)
  requires=$(sed -n '/^---$/,/^---$/p' "$sf" | grep -oP '^requires:\s*\[\K[^\]]+' | tr ',' '\n' | sed 's/^ *//;s/ *$//')
  for req in $requires; do
    if echo "$KNOWN_SKILLS" | grep -qw "$req"; then
      pass "skill/$s_name requires '$req' — exists"
    else
      fail "skill/$s_name requires '$req' — not found"
    fi
  done
done
echo ""

# ── Check 4: Every README exists ──
echo "  Checking README coverage..."
for dir in skills workflows gates constitution agents templates platforms packs core tools; do
  dir_path="$SAGE_ROOT/$dir"
  if [ -d "$dir_path" ]; then
    if [ -f "$dir_path/README.md" ]; then
      pass "$dir/README.md exists"
    else
      fail "$dir/README.md missing"
    fi
  fi
done

echo ""
echo "  Cross-refs: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
