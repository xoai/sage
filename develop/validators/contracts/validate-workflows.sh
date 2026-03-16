#!/usr/bin/env bash
# Validate all workflows against workflow.contract.md
set -uo pipefail

SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
RESULTS="/tmp/sage-test-results-workflows"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"

green()  { echo -e "\033[32m$1\033[0m"; }
red()    { echo -e "\033[31m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
pass() { PASS=$((PASS + 1)); echo "  $(green '✓') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(red '✗') $1"; echo "ERR:$1" >> "$RESULTS"; }
warn() { WARN=$((WARN + 1)); echo "  $(yellow '⚠') $1"; }

echo ""
echo -e "\033[1m── Workflow Contract Validation ──\033[0m"

WF_FILES=$(find "$SAGE_ROOT/core/workflows" -name "*.workflow.md" 2>/dev/null | sort)
WF_COUNT=$(echo "$WF_FILES" | grep -c "workflow.md" || echo "0")
echo "  Found $WF_COUNT workflows to validate"
echo ""

for wf_file in $WF_FILES; do
  wf_name=$(basename "$wf_file" .workflow.md)
  echo "  Checking: $wf_name"

  if ! head -1 "$wf_file" | grep -q "^---$"; then
    fail "$wf_name: missing YAML frontmatter"
    continue
  fi

  frontmatter=$(sed -n '/^---$/,/^---$/p' "$wf_file" | sed '1d;$d')

  # Required: name
  if echo "$frontmatter" | grep -q "^name:"; then
    pass "$wf_name: has name"
  else
    fail "$wf_name: missing 'name' field"
  fi

  # Required: version
  if echo "$frontmatter" | grep -qP '^version:'; then
    pass "$wf_name: has version"
  else
    fail "$wf_name: missing 'version' field"
  fi

  # Required for main workflows: mode
  if echo "$wf_name" | grep -qP '^(fix|build|architect)$'; then
    mode=$(echo "$frontmatter" | grep -oP '^mode:\s*\K\S+' | head -1)
    if [ -n "$mode" ]; then
      pass "$wf_name: has mode ($mode)"
      if [ "$wf_name" = "$mode" ]; then
        pass "$wf_name: mode matches filename"
      else
        warn "$wf_name: mode '$mode' doesn't match filename '$wf_name'"
      fi
    else
      fail "$wf_name: missing 'mode' field (required for main workflows)"
    fi
  fi

  body=$(sed -n '/^---$/,/^---$/!p' "$wf_file" | tail -n +2)

  # Required: Sequence section
  if echo "$body" | grep -qiE "^## (Sequence|Process|Step)"; then
    pass "$wf_name: has process/sequence section"

    # Check that sequence references skill names with backtick syntax
    skill_refs=$(echo "$body" | grep -oP '`[\w-]+`' | sort -u)
    ref_count=$(echo "$skill_refs" | grep -c '`' || echo "0")
    if [ "$ref_count" -gt 0 ]; then
      pass "$wf_name: references $ref_count skills by name"
    else
      warn "$wf_name: no skill references found in sequence (expected \`skill-name\` syntax)"
    fi
  else
    fail "$wf_name: missing 'Sequence' or 'Process' or 'Step' section"
  fi

  # Required: Fallbacks section
  if echo "$body" | grep -qiE "^## (Fallback|Rules)"; then
    pass "$wf_name: has fallbacks/rules section"
  else
    fail "$wf_name: missing 'Fallbacks' or 'Rules' section"
  fi

  # Check for human checkpoints in BUILD and ARCHITECT
  if echo "$wf_name" | grep -qP '^(build|architect)$'; then
    checkpoint_count=$(echo "$body" | grep -ci "CHECKPOINT" || echo "0")
    if [ "$checkpoint_count" -gt 0 ]; then
      pass "$wf_name: has $checkpoint_count human checkpoint(s)"
    else
      fail "$wf_name: BUILD/ARCHITECT workflows must have at least one human checkpoint"
    fi
  fi

  echo ""
done

echo "  Workflows: $PASS passed, $FAIL failed, $WARN warnings"
echo "PASS:$PASS" >> "$RESULTS"
echo "FAIL:$FAIL" >> "$RESULTS"
echo "WARN:$WARN" >> "$RESULTS"
