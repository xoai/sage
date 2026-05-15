#!/usr/bin/env bash
# Bash fallback for the Sage workflow flag parser.
#
# Usage: bash parse.sh "<arguments>"
# Output: JSON to stdout matching the Python parser's contract.
# Exit code: 0 on clean parse, 1 on unknown flag.
#
# Recognized flags: --quality-locked, --autonomous (boolean, no value).
# Rules match parser.py:
#   - Flags must be at the start
#   - Flag order doesn't matter
#   - Unknown flags produce an error
#   - Goal is everything after the flags

set -u

# JSON-escape a string for embedding inside double quotes.
# Handles backslashes, double quotes, and control chars.
json_escape() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//$'\t'/\\t}
  printf '%s' "$s"
}

emit() {
  local quality_locked=$1 autonomous=$2 goal=$3 error=$4
  local error_field='null'
  if [ -n "$error" ]; then
    error_field='"'"$(json_escape "$error")"'"'
  fi
  printf '{"quality_locked": %s, "autonomous": %s, "goal": "%s", "error": %s}\n' \
    "$quality_locked" "$autonomous" "$(json_escape "$goal")" "$error_field"
}

# Read input — concatenate all args (handles unquoted invocations).
input="${*:-}"

# Trim leading whitespace
input="${input#"${input%%[![:space:]]*}"}"
# Trim trailing whitespace
input="${input%"${input##*[![:space:]]}"}"

quality_locked='false'
autonomous='false'

while [[ "$input" == --* ]]; do
  # Extract first word (flag)
  flag="${input%% *}"
  # Compute the rest (everything after the first whitespace, or empty)
  if [[ "$input" == *' '* ]]; then
    rest="${input#* }"
  else
    rest=''
  fi

  case "$flag" in
    --quality-locked)
      quality_locked='true'
      ;;
    --autonomous)
      autonomous='true'
      ;;
    *)
      emit 'false' 'false' '' \
        "Unknown flag '$flag'. Supported flags: --quality-locked, --autonomous."
      exit 1
      ;;
  esac

  # Strip leading whitespace from the remainder before re-checking
  input="${rest#"${rest%%[![:space:]]*}"}"
done

emit "$quality_locked" "$autonomous" "$input" ''
exit 0
