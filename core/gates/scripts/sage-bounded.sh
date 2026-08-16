#!/usr/bin/env bash
# sage-bounded.sh — portable bounded execution for gate scripts (sourced).
#
# Field lesson (loop-field-economics, 2026-08-16): after a subagent
# returned, the orchestrator ran an unbounded suite — `go test -race`
# with no -timeout behind an SPA build — and ground for hours while
# every subagent box read "completed". A hanging suite is a defect
# being surfaced; the gate's job is to surface it AS A FAIL WITH
# EVIDENCE, never to inherit the hang.
#
# Portability constraints this file exists to encode (bash 3.2, macOS):
#   - no GNU `timeout`, no `setsid`;
#   - no `wait -n` (bash 4.3+): ONE `wait` on the runner pid only;
#   - background jobs share a non-interactive script's process group, so
#     `kill -- -$pid` would kill the SCRIPT — kill the pid, then sweep
#     children with `pkill -P` where pkill exists;
#   - output goes to a FILE, not command substitution: an orphaned child
#     holding the pipe would hang `$( ... )` even after the runner died.
#
# Timeout detection: the watcher writes a SENTINEL before killing.
# Timeout = sentinel exists AND rc != 0 — rc 0 wins regardless (the
# runner may pass in the instant the watcher expires, and a passing
# suite must never grade as a timeout); a suite dying with 143 on its
# own, no sentinel, is a plain FAIL.
#
# Usage (from a gate script in the same directory):
#   . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sage-bounded.sh"
#   LIMIT=$(sage_bounded_timeout "$ROOT")      # env > config > 600
#   sage_bounded_run OUT_FILE SENTINEL_FILE "$LIMIT" "$ROOT" cmd [args...]
#   rc=$?   # timeout iff SENTINEL exists and rc != 0

sage_bounded_timeout() {
  # Precedence: SAGE_VERIFY_TIMEOUT env > top-level `verify_timeout:` in
  # .sage/config.yaml > 600. Non-numeric config values are ignored.
  if [ -n "${SAGE_VERIFY_TIMEOUT:-}" ]; then
    printf '%s\n' "$SAGE_VERIFY_TIMEOUT"
    return 0
  fi
  _sb_cfg="$1/.sage/config.yaml"
  if [ -f "$_sb_cfg" ]; then
    _sb_t=$(grep -E '^verify_timeout[[:space:]]*:' "$_sb_cfg" 2>/dev/null \
            | head -1 \
            | sed -e 's/^verify_timeout[[:space:]]*:[[:space:]]*//' \
                  -e 's/[[:space:]]*#.*$//' -e 's/[[:space:]]*$//')
    case "$_sb_t" in
      ''|*[!0-9]*) : ;;
      *) printf '%s\n' "$_sb_t"; return 0 ;;
    esac
  fi
  printf '600\n'
}

sage_bounded_run() {
  # $1 out-file  $2 sentinel  $3 limit-seconds  $4 workdir  $5.. argv
  _sb_out="$1"; _sb_sentinel="$2"; _sb_limit="$3"; _sb_root="$4"
  shift 4
  rm -f "$_sb_sentinel"
  ( cd "$_sb_root" 2>/dev/null && exec "$@" ) >"$_sb_out" 2>&1 &
  _sb_pid=$!
  # The watcher's stdout/stderr MUST be /dev/null: its `sleep` child
  # inherits every open fd, and a caller capturing this script through
  # `$( ... )` would wait for that pipe's EOF long after we exit — the
  # exact hang this helper exists to prevent.
  (
    sleep "$_sb_limit"
    : > "$_sb_sentinel"
    kill -TERM "$_sb_pid" 2>/dev/null
    if command -v pkill >/dev/null 2>&1; then
      pkill -TERM -P "$_sb_pid" 2>/dev/null
    fi
    sleep 5
    kill -KILL "$_sb_pid" 2>/dev/null
    if command -v pkill >/dev/null 2>&1; then
      pkill -KILL -P "$_sb_pid" 2>/dev/null
    fi
  ) >/dev/null 2>&1 &
  _sb_watcher=$!
  wait "$_sb_pid"
  _sb_rc=$?
  # Sweep the watcher's children BEFORE killing it — kill the parent
  # first and its sleep reparents to init, where pkill -P finds nothing.
  if command -v pkill >/dev/null 2>&1; then
    pkill -P "$_sb_watcher" 2>/dev/null
  fi
  kill "$_sb_watcher" 2>/dev/null
  wait "$_sb_watcher" 2>/dev/null
  return "$_sb_rc"
}
