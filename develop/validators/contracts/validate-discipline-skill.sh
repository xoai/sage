#!/usr/bin/env bash
# Validate DISCIPLINE skills against the skill.contract.md discipline clause.
# Usage: bash develop/validators/contracts/validate-discipline-skill.sh [sage-root]
#
# A skill is a discipline skill iff its SKILL.md frontmatter declares
# `skill_type: discipline`. Such a skill MUST:
#   (a) declare a non-empty `compliance_marker`,
#   (b) have a sibling TESTS.md whose latest `green_verdict:` is PASS,
#   (c) contain a `## Rationalization table` section.
# Skills without `skill_type: discipline` are EXEMPT (untouched by this check).
#
# Results are appended to /tmp/sage-test-results-discipline in the same
# PASS:/FAIL:/WARN:/ERR: format the other validators use, so validate-all.sh
# folds them into the global tally.

set -uo pipefail

SAGE_ROOT="${1:-$(cd "$(dirname "$0")/../../.." && pwd)}"
RESULTS="/tmp/sage-test-results-discipline"
PASS=0; FAIL=0; WARN=0
> "$RESULTS"

green() { echo -e "\033[32m$1\033[0m"; }
red()   { echo -e "\033[31m$1\033[0m"; }
pass() { PASS=$((PASS + 1)); echo "  $(green '✓') $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  $(red '✗') $1"; echo "ERR:$1" >> "$RESULTS"; }

echo ""
echo -e "\033[1m── Discipline-Skill Contract Validation ──\033[0m"

CAP_DIR="$SAGE_ROOT/core/capabilities"
if [ ! -d "$CAP_DIR" ]; then
  echo "  (no core/capabilities under $SAGE_ROOT — nothing to check)"
  echo "PASS:$PASS" >> "$RESULTS"; echo "FAIL:$FAIL" >> "$RESULTS"; echo "WARN:$WARN" >> "$RESULTS"
  exit 0
fi

# Read a frontmatter field's raw value (first --- … --- block).
fm_value() { # fm_value <file> <field>
  awk -v field="$2" '
    NR==1 && $0=="---" { infm=1; next }
    infm && $0=="---" { exit }
    infm && index($0, field":")==1 {
      sub("^"field":[[:space:]]*", ""); print; exit
    }
  ' "$1"
}

strip_quotes() { # echo value with one layer of surrounding quotes removed
  local v="$1"; v="${v%$'\r'}"
  case "$v" in \"*\") v="${v#\"}"; v="${v%\"}" ;; \'*\') v="${v#\'}"; v="${v%\'}" ;; esac
  printf '%s' "$v"
}

DISC_COUNT=0
while IFS= read -r skill_file; do
  [ -z "$skill_file" ] && continue
  stype="$(strip_quotes "$(fm_value "$skill_file" skill_type)")"
  [ "$stype" = "discipline" ] || continue   # exempt: not a discipline skill

  DISC_COUNT=$((DISC_COUNT + 1))
  skill_dir="$(dirname "$skill_file")"
  name="$(basename "$skill_dir")"
  tests_file="$skill_dir/TESTS.md"
  problems=""

  # (a) compliance_marker present and non-empty.
  marker="$(strip_quotes "$(fm_value "$skill_file" compliance_marker)")"
  [ -n "$marker" ] || problems+="; missing compliance_marker"

  # (b) sibling TESTS.md with a latest green_verdict of PASS.
  if [ ! -f "$tests_file" ]; then
    problems+="; missing sibling TESTS.md"
  else
    verdict="$(strip_quotes "$(fm_value "$tests_file" green_verdict)")"
    if [ -z "$verdict" ]; then
      problems+="; TESTS.md has no green_verdict line"
    elif [ "$verdict" != "PASS" ]; then
      problems+="; TESTS.md green_verdict is '$verdict' (not PASS)"
    fi
  fi

  # (c) ## Rationalization table section.
  grep -qE '^##[[:space:]]+Rationalization table' "$skill_file" \
    || problems+="; missing '## Rationalization table' section"

  if [ -z "$problems" ]; then
    pass "$name: discipline-skill contract satisfied"
  else
    fail "$name: discipline-skill contract violated${problems}"
  fi
done <<EOF
$(find "$CAP_DIR" -name SKILL.md -not -path '*/\{*' 2>/dev/null | sort)
EOF

echo "  Discipline skills: $DISC_COUNT checked, $PASS passed, $FAIL failed"
echo "PASS:$PASS" >> "$RESULTS"
echo "FAIL:$FAIL" >> "$RESULTS"
echo "WARN:$WARN" >> "$RESULTS"
