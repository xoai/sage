#!/usr/bin/env bash
# Validate overall framework structure (ring layout)
set -uo pipefail
SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-structure"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"
pass() { PASS=$((PASS + 1)); echo "  $(echo -e '\033[32m✓\033[0m') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(echo -e '\033[31m✗\033[0m') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(echo -e '\033[33m⚠\033[0m') $1"; }

echo ""
echo -e "\033[1m── Framework Structure Validation ──\033[0m"

echo "  Checking required directories..."
for dir in core core/capabilities core/workflows core/gates core/constitution \
           core/agents core/capabilities/context/context-loader \
           skills \
           runtime runtime/tools runtime/platforms runtime/cli \
           develop develop/contracts develop/guides develop/templates develop/validators; do
  [ -d "$SAGE_ROOT/$dir" ] && pass "Directory: $dir/" || fail "Missing directory: $dir/"
done
echo ""

echo "  Checking contract files..."
for contract in skill workflow gate constitution agent knowledge-skill platform template bundle-skill; do
  f="$SAGE_ROOT/develop/contracts/${contract}.contract.md"
  [ -f "$f" ] && pass "Contract: ${contract}.contract.md" || fail "Missing contract: ${contract}.contract.md"
done
echo ""

echo "  Checking context loader..."
[ -f "$SAGE_ROOT/core/capabilities/context/context-loader/loading-rules.md" ] && pass "loading-rules.md exists" || fail "loading-rules.md missing"
[ -f "$SAGE_ROOT/core/capabilities/context/context-loader/templates/main-instructions.template.md" ] && pass "main-instructions template exists" || fail "main-instructions template missing"
echo ""

echo "  Checking one workflow per mode..."
for mode in fix build architect; do
  [ -f "$SAGE_ROOT/core/workflows/${mode}.workflow.md" ] && pass "Workflow for $mode" || fail "Missing: ${mode}.workflow.md"
done
echo ""

echo "  Checking root README..."
[ -f "$SAGE_ROOT/README.md" ] && pass "Root README.md exists" || fail "Root README.md missing"
echo ""

echo "  Checking CLI..."
[ -f "$SAGE_ROOT/runtime/cli/src/cli.mjs" ] && pass "CLI entry point exists" || fail "CLI entry point missing"
[ -f "$SAGE_ROOT/runtime/cli/package.json" ] && pass "CLI package.json exists" || fail "CLI package.json missing"
echo ""

echo "  Checking platforms..."
PLATFORM_COUNT=$(find "$SAGE_ROOT/runtime/platforms" -name "platform.yaml" 2>/dev/null | wc -l)
[ "$PLATFORM_COUNT" -gt 0 ] && pass "Found $PLATFORM_COUNT platform(s)" || fail "No platforms found (need at least one platform.yaml)"
echo ""

echo "  Checking for empty capability directories..."
find "$SAGE_ROOT/core/capabilities" -type d 2>/dev/null | while read -r dir; do
  bn=$(basename "$dir")
  case "$bn" in capabilities|references|prompts|orchestration|elicitation|planning|execution|review|debugging|context|templates) continue ;; esac
  if [ ! -f "$dir/SKILL.md" ]; then
    subdir_count=$(find "$dir" -maxdepth 1 -type d | wc -l)
    [ "$subdir_count" -le 1 ] && warn "Empty capability directory: $dir (no SKILL.md)"
  fi
done

echo ""
echo "  Structure: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
