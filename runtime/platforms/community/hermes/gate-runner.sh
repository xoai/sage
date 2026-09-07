#!/usr/bin/env bash
# Native Windows formal-gate boundary. Canonical gates and their exit contract
# remain unchanged; only the native Python -> Bash text record boundary is LF.
set -uo pipefail

if [ "$#" -lt 2 ] || [ ! -f "$1" ] || [ ! -f "$2" ]; then
  printf '%s\n' 'UNVERIFIABLE — formal gate requires existing Python and gate files' >&2
  exit 2
fi
export SAGE_FORMAL_GATE_PYTHON="$1"
gate_script="$2"
shift 2
export PYTHONUTF8=1
# mktemp and native Python must refer to the same physical temporary directory.
if command -v cygpath >/dev/null 2>&1 && [ -n "${TEMP:-}" ]; then
  export TMPDIR="$(cygpath -m "$TEMP")"
fi

python3() {
  "$SAGE_FORMAL_GATE_PYTHON" "$@" |
    "$SAGE_FORMAL_GATE_PYTHON" -c 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().replace(b"\r\n", b"\n"))'
  local statuses=("${PIPESTATUS[@]}")
  # Neither a native Python failure nor a failed normalizer may become success.
  if [ "${statuses[0]}" -ne 0 ]; then
    return "${statuses[0]}"
  fi
  return "${statuses[1]}"
}
export -f python3
exec "$BASH" "$gate_script" "$@"
