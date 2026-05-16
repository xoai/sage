#!/usr/bin/env bash
# Bash fallback for the Sage workflow flag parser.
#
# Usage:
#   bash parse.sh "<arguments>" [--config-path PATH]
#
# Output: JSON to stdout matching the Python parser's contract:
#   {"quality_locked": bool, "autonomous": bool, "goal": "...",
#    "error": null | "...", "quality_locked_source": "flag"|"config"|null,
#    "autonomous_source": "flag"|"config"|null}
#
# Exit code: 0 on clean parse, 1 on unknown flag or conflict.
#
# Recognized flags (boolean, no value):
#   --quality-locked     turn quality-locked mode on (source: "flag")
#   --no-quality-locked  turn it off, overriding config (source: "flag")
#   --autonomous         turn autonomous mode on (source: "flag")
#   --no-autonomous      turn it off, overriding config (source: "flag")
#
# Config defaults: read .sage/config.yaml (path passed via --config-path).
# Strict-match contract: only `<key>: true` exactly (one space, lowercase)
# is honored. All other variants → no default. See Python config_loader.py
# for the full rationale; both runtimes must agree byte-for-byte.

set -u

# ── JSON helpers ─────────────────────────────────────────────────────

json_escape() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\r'/\\r}
  s=${s//$'\t'/\\t}
  printf '%s' "$s"
}

# Emit a quoted source value or null. Input is "flag", "config", or "" (=null).
src_field() {
  if [ -z "$1" ]; then
    printf 'null'
  else
    printf '"%s"' "$1"
  fi
}

emit() {
  local quality_locked=$1 autonomous=$2 goal=$3 error=$4
  local ql_source=$5 auto_source=$6
  local error_field='null'
  if [ -n "$error" ]; then
    error_field='"'"$(json_escape "$error")"'"'
  fi
  printf '{"quality_locked": %s, "autonomous": %s, "goal": "%s", "error": %s, "quality_locked_source": %s, "autonomous_source": %s}\n' \
    "$quality_locked" "$autonomous" "$(json_escape "$goal")" "$error_field" \
    "$(src_field "$ql_source")" "$(src_field "$auto_source")"
}

# ── Parse positional + --config-path ─────────────────────────────────

config_path=''
positional=()
while [ $# -gt 0 ]; do
  case "$1" in
    --config-path)
      config_path="${2:-}"
      shift 2
      ;;
    --config-path=*)
      config_path="${1#--config-path=}"
      shift
      ;;
    *)
      positional+=("$1")
      shift
      ;;
  esac
done

# Reconstitute the arguments string from positional (joined with single spaces).
input=""
if [ ${#positional[@]} -gt 0 ]; then
  input="${positional[*]}"
fi

# ── Read config defaults (strict-match contract) ─────────────────────

ql_default='false'
auto_default='false'
if [ -n "$config_path" ] && [ -f "$config_path" ]; then
  # Match exactly: `<key>: true` at start of line, one space, lowercase true.
  # grep -E so we can use the alternation. -q would suppress output and
  # -F doesn't help (we need anchors).
  if grep -Eq '^quality_locked: true$' "$config_path" 2>/dev/null; then
    ql_default='true'
  fi
  if grep -Eq '^autonomous: true$' "$config_path" 2>/dev/null; then
    auto_default='true'
  fi
fi

# Trim leading/trailing whitespace from input
input="${input#"${input%%[![:space:]]*}"}"
input="${input%"${input##*[![:space:]]}"}"

# ── Parse flags ──────────────────────────────────────────────────────
# Track each key's per-flag state separately so we can detect conflicts.
# State values: "" (no flag), "positive", "negative"
ql_flag_state=''
auto_flag_state=''

while [[ "$input" == --* ]]; do
  flag="${input%% *}"
  if [[ "$input" == *' '* ]]; then
    rest="${input#* }"
  else
    rest=''
  fi

  case "$flag" in
    --quality-locked)
      if [ "$ql_flag_state" = 'negative' ]; then
        emit 'false' 'false' '' \
          "Conflicting flags for quality_locked: both --quality-locked and --no-quality-locked passed." \
          '' ''
        exit 1
      fi
      ql_flag_state='positive'
      ;;
    --no-quality-locked)
      if [ "$ql_flag_state" = 'positive' ]; then
        emit 'false' 'false' '' \
          "Conflicting flags for quality_locked: both --quality-locked and --no-quality-locked passed." \
          '' ''
        exit 1
      fi
      ql_flag_state='negative'
      ;;
    --autonomous)
      if [ "$auto_flag_state" = 'negative' ]; then
        emit 'false' 'false' '' \
          "Conflicting flags for autonomous: both --autonomous and --no-autonomous passed." \
          '' ''
        exit 1
      fi
      auto_flag_state='positive'
      ;;
    --no-autonomous)
      if [ "$auto_flag_state" = 'positive' ]; then
        emit 'false' 'false' '' \
          "Conflicting flags for autonomous: both --autonomous and --no-autonomous passed." \
          '' ''
        exit 1
      fi
      auto_flag_state='negative'
      ;;
    *)
      emit 'false' 'false' '' \
        "Unknown flag '$flag'. Supported flags: --autonomous, --no-autonomous, --no-quality-locked, --quality-locked." \
        '' ''
      exit 1
      ;;
  esac

  input="${rest#"${rest%%[![:space:]]*}"}"
done

# ── Resolve precedence: flag > config > default off ──────────────────

ql_value='false'
ql_source=''
case "$ql_flag_state" in
  positive) ql_value='true';  ql_source='flag' ;;
  negative) ql_value='false'; ql_source='flag' ;;
  '')       if [ "$ql_default" = 'true' ]; then ql_value='true'; ql_source='config'; fi ;;
esac

auto_value='false'
auto_source=''
case "$auto_flag_state" in
  positive) auto_value='true';  auto_source='flag' ;;
  negative) auto_value='false'; auto_source='flag' ;;
  '')       if [ "$auto_default" = 'true' ]; then auto_value='true'; auto_source='config'; fi ;;
esac

emit "$ql_value" "$auto_value" "$input" '' "$ql_source" "$auto_source"
exit 0
