#!/usr/bin/env bash
# .sage/scripts/validate-review.sh
#
# Validate a reviewer's output matches the required schema. Exits 0 on
# success; non-zero with a reason on stderr on failure. The dispatcher
# calls this after every reviewer run.
#
# Usage:
#   validate-review.sh <path-to-review-file>

set -euo pipefail
FILE="${1:?review file path required}"
[[ -f "${FILE}" ]] || { echo "Missing: ${FILE}" >&2; exit 2; }

fail() { echo "INVALID: $1" >&2; exit 1; }

# ─── 1. Last non-empty line must be a valid verdict ────────────────────────
LAST="$(grep -v '^[[:space:]]*$' "${FILE}" | tail -1 | tr -d '[:space:]')"
case "${LAST}" in
  APPROVE|REVISE|REJECT|FIX_BEFORE_MERGE|REWORK) ;;
  *) fail "Last line is not a valid verdict (got: '${LAST}')" ;;
esac

# ─── 2. Must have a Findings section ──────────────────────────────────────
grep -q '^## Findings' "${FILE}" || fail "Missing '## Findings' section"

# ─── 3. Every ### header inside Findings must declare a valid severity ───
awk '
  /^## Findings/      { in_findings = 1; next }
  /^## / && in_findings { in_findings = 0 }
  in_findings && /^### / {
    if ($0 !~ /^### \[(BLOCKER|MAJOR|MINOR)\] /) {
      print "Finding header without valid severity tag: " $0 > "/dev/stderr"; exit 1
    }
  }
' "${FILE}" || exit 1

# ─── 4. Every finding must have Where + Quote lines ───────────────────────
awk '
  /^### \[(BLOCKER|MAJOR|MINOR)\]/ {
    if (in_finding && (!has_where || !has_quote)) {
      print "Finding missing Where/Quote: " title > "/dev/stderr"; exit 1
    }
    in_finding = 1; has_where = 0; has_quote = 0; title = $0; next
  }
  /^- \*\*Where:\*\*/  { has_where = 1 }
  /^- \*\*Quote:\*\*/  { has_quote = 1 }
  END {
    if (in_finding && (!has_where || !has_quote)) {
      print "Final finding missing Where/Quote: " title > "/dev/stderr"; exit 1
    }
  }
' "${FILE}" || exit 1

echo "OK"
