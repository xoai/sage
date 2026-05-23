#!/usr/bin/env bash
# .sage/scripts/hallucination-check.sh
#
# Cheap, deterministic phantom-import detection. Walks the
# uncommitted diff for files in supported languages (Python,
# TypeScript/JavaScript, Rust, Go), extracts the import lines, and
# resolves each against the language-appropriate manifest *or* the
# project's local file tree. Unresolved imports are reported with
# `path:line`. Designed to run as a precondition for /review-code —
# surfacing phantom imports cheaply, before paying for a codex pass.
#
# Usage:
#   hallucination-check.sh <slug>
#     (slug is informational only — the diff is the working tree's
#     `git diff`, not slug-specific. Slug is accepted for symmetry
#     with the other dispatcher-style scripts and for future use.)
#
# Output: unresolved imports on stdout, one per line:
#     <file>:<line>: <import-statement>
#   Skipped-file `info:` notes go to stderr.
#
# Exit codes:
#   0 — clean (all per-file resolutions succeeded, OR every file in
#       the diff was skipped because its language is unsupported /
#       its language-appropriate manifest is absent).
#   1 — any unresolved import emitted on stdout.
#   2 — no diff at all (no touched files — preserves I1 inert by
#       absence). Also: not a git repo.
#
# Tolerated failures (intentional): `git diff` against a non-repo
# (caught explicitly with exit 2); `grep -P` may be unavailable on
# old macOS — the script uses ERE only; `awk` on Files: matching
# returning nothing (handled).

set -euo pipefail

SLUG="${1:-}"
: "${SLUG:=__no_slug__}"  # unused; kept for API symmetry.

# ── Are we in a git repo? ──
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "info: not a git repository; nothing to check" >&2
  exit 2
fi

# ── Collect the changed files (working-tree diff, no staging area). ──
# Includes both modified and untracked files? No — `git diff` covers
# unstaged modifications; for a fresh /implement cycle the implementer
# leaves edits uncommitted, so `git diff HEAD` is the right reference.
# Falls back to `git diff` (vs the index) if HEAD is missing
# (initial commit case).
CHANGED="$(git diff --name-only HEAD 2>/dev/null || git diff --name-only 2>/dev/null || true)"
if [[ -z "${CHANGED}" ]]; then
  echo "info: no touched files in the working-tree diff" >&2
  exit 2
fi

UNRESOLVED_TOTAL=0

# ── Helper: nearest-ancestor file resolution ──
# Walks up from `start_dir` looking for `filename`. Echoes the path on
# stdout (exit 0) or empty (exit 1) if not found.
find_ancestor() {
  local start_dir="$1" filename="$2"
  local dir="${start_dir}"
  while [[ -n "${dir}" && "${dir}" != "/" ]]; do
    if [[ -f "${dir}/${filename}" ]]; then
      printf '%s' "${dir}/${filename}"
      return 0
    fi
    [[ "${dir}" == "." ]] && return 1
    dir="$(dirname "${dir}")"
  done
  return 1
}

# ── Helper: report an unresolved import ──
report() {
  printf '%s\n' "$1"
  UNRESOLVED_TOTAL=$((UNRESOLVED_TOTAL + 1))
}

# ── Per-language resolvers ──────────────────────────────────────────────

check_python() {
  local file="$1"
  local file_dir; file_dir="$(dirname "${file}")"

  # Find manifest — pyproject.toml, then setup.cfg, then requirements.txt
  local manifest=""
  for m in pyproject.toml setup.cfg requirements.txt; do
    manifest="$(find_ancestor "${file_dir}" "${m}" 2>/dev/null || true)"
    [[ -n "${manifest}" ]] && break
  done
  if [[ -z "${manifest}" ]]; then
    echo "info: ${file}: no Python manifest found in ancestors; skipping" >&2
    return 0
  fi

  # Walk import lines added in the diff (lines starting with `+import` /
  # `+from`, but we also want their line numbers — easier to grep the
  # current file content for now, since the diff line numbers would
  # require a more complex diff-parse).
  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    local lineno mod
    lineno="$(printf '%s' "${line}" | cut -d: -f1)"
    mod="$(printf '%s' "${line}" | sed -nE 's/^[0-9]+:[[:space:]]*(from|import)[[:space:]]+([a-zA-Z0-9_.]+).*/\2/p')"
    [[ -z "${mod}" ]] && continue

    # Top-level package.
    local top="${mod%%.*}"

    # Relative import (starts with `.`) → file-tree resolution only.
    if [[ "${mod}" == .* ]]; then
      # Strip leading dots; resolve against file_dir/{mod_without_dots}.py
      local stripped="${mod#.}"
      local rel="${file_dir}/${stripped//./\/}.py"
      [[ -f "${rel}" || -d "${file_dir}/${stripped//./\/}" ]] && continue
      report "${file}:${lineno}: ${line#*:}"
      continue
    fi

    # Stdlib heuristic: presence in a tiny built-in allowlist plus the
    # current language's stdlib via `python3 -c` is too slow for a
    # bash precondition. Use a static list of common stdlib modules.
    case "${top}" in
      sys|os|re|io|json|csv|math|typing|pathlib|datetime|time|argparse|subprocess|tempfile|shutil|collections|functools|itertools|contextlib|unittest|abc|enum|dataclasses|asyncio|logging|threading|multiprocessing|http|urllib|base64|hashlib|hmac|secrets|random|string|textwrap|warnings|tomllib|copy|operator|inspect|pickle)
        continue ;;
    esac

    # In-repo module (file or package at the top level).
    if [[ -f "${top}.py" || -d "${top}" ]]; then continue; fi

    # Look in the manifest's dependency lists. Match the package name
    # as a whole token — preceded and followed by a non-name char (or
    # line boundary). The negated bracket-expression form is portable
    # across grep flavors (GNU grep, BSD grep, ugrep) where the
    # `["'\[ ]`-style classes parse subtly differently. Conservative
    # by design (spec acknowledges false-positive avoidance over
    # false-negative pickup).
    if grep -qE "(^|[^a-zA-Z0-9_-])${top}([^a-zA-Z0-9_-]|\$)" "${manifest}" 2>/dev/null; then
      continue
    fi

    report "${file}:${lineno}: ${line#*:}"
  done < <(grep -nE '^(import|from)[[:space:]]' "${file}" 2>/dev/null || true)
}

check_typescript() {
  local file="$1"
  local file_dir; file_dir="$(dirname "${file}")"

  local manifest
  manifest="$(find_ancestor "${file_dir}" "package.json" 2>/dev/null || true)"
  if [[ -z "${manifest}" ]]; then
    echo "info: ${file}: no package.json found in ancestors; skipping" >&2
    return 0
  fi

  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    local lineno spec
    lineno="$(printf '%s' "${line}" | cut -d: -f1)"
    # Match `import … from "x"` / `from "x"` / `require("x")`.
    spec="$(printf '%s' "${line}" | sed -nE 's/.*(from|require)[[:space:]]*\(?[[:space:]]*["'\''"]([^"'\''"]+)["'\''"].*/\2/p')"
    [[ -z "${spec}" ]] && continue

    # Relative / absolute path import → file-tree resolution.
    if [[ "${spec}" == .* || "${spec}" == /* ]]; then
      local base="${file_dir}/${spec}"
      [[ "${spec}" == /* ]] && base="${spec}"
      # Try common extensions and index files.
      for ext in "" .ts .tsx .js .jsx .mjs .cjs /index.ts /index.tsx /index.js /index.jsx /index.mjs; do
        [[ -e "${base}${ext}" ]] && { spec=""; break; }
      done
      [[ -z "${spec}" ]] && continue
      report "${file}:${lineno}: ${line#*:}"
      continue
    fi

    # Scoped (`@scope/pkg`) or normal package (`pkg`): match by name.
    # Extract the package name (first segment of scoped, full of normal).
    local pkg_name="${spec}"
    case "${spec}" in
      @*/*)  pkg_name="${spec%%/*}/${spec#*/}"; pkg_name="${pkg_name%%/*}/${pkg_name#*/}"
             # ^ keep `@scope/pkg`, drop deeper paths.
             pkg_name="$(printf '%s' "${spec}" | awk -F/ '{print $1 "/" $2}')"
             ;;
      */*)   pkg_name="${spec%%/*}" ;;
    esac

    # Node built-ins are always resolved.
    case "${pkg_name}" in
      fs|path|os|url|util|crypto|stream|events|http|https|net|child_process|process|buffer|querystring|assert|zlib|tls|dgram|cluster|module|vm|worker_threads|perf_hooks)
        continue ;;
      node:*) continue ;;
    esac

    # Search the manifest's dependency-style fields.
    if grep -qE "\"${pkg_name}\"[[:space:]]*:" "${manifest}" 2>/dev/null; then
      continue
    fi

    report "${file}:${lineno}: ${line#*:}"
  done < <(grep -nE '^(import|export)[[:space:]]|from[[:space:]]+["'\'']|require[[:space:]]*\(' "${file}" 2>/dev/null || true)
}

check_rust() {
  local file="$1"
  local file_dir; file_dir="$(dirname "${file}")"

  local manifest
  manifest="$(find_ancestor "${file_dir}" "Cargo.toml" 2>/dev/null || true)"
  if [[ -z "${manifest}" ]]; then
    echo "info: ${file}: no Cargo.toml found in ancestors; skipping" >&2
    return 0
  fi

  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    local lineno crate
    lineno="$(printf '%s' "${line}" | cut -d: -f1)"
    crate="$(printf '%s' "${line}" | sed -nE 's/^[0-9]+:[[:space:]]*use[[:space:]]+([a-zA-Z0-9_]+)::.*/\1/p; s/^[0-9]+:[[:space:]]*use[[:space:]]+([a-zA-Z0-9_]+);.*/\1/p; s/^[0-9]+:[[:space:]]*extern crate[[:space:]]+([a-zA-Z0-9_]+).*/\1/p')"
    [[ -z "${crate}" ]] && continue

    # `crate`, `self`, `super` are language constructs.
    case "${crate}" in crate|self|super|std|core|alloc) continue ;; esac

    # Look in Cargo.toml dependencies — same robust token-boundary
    # pattern as the Python check.
    if grep -qE "(^|[^a-zA-Z0-9_-])${crate}([^a-zA-Z0-9_-]|\$)" "${manifest}" 2>/dev/null; then
      continue
    fi

    report "${file}:${lineno}: ${line#*:}"
  done < <(grep -nE '^(use|extern crate)[[:space:]]' "${file}" 2>/dev/null || true)
}

check_go() {
  local file="$1"
  local file_dir; file_dir="$(dirname "${file}")"

  local manifest
  manifest="$(find_ancestor "${file_dir}" "go.mod" 2>/dev/null || true)"
  if [[ -z "${manifest}" ]]; then
    echo "info: ${file}: no go.mod found in ancestors; skipping" >&2
    return 0
  fi

  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    local lineno pkg
    lineno="$(printf '%s' "${line}" | cut -d: -f1)"
    pkg="$(printf '%s' "${line}" | sed -nE 's/^[0-9]+:[[:space:]]*"([^"]+)".*/\1/p')"
    [[ -z "${pkg}" ]] && continue

    # Go stdlib heuristic — packages with no dot are typically stdlib.
    case "${pkg}" in
      *.*) ;;   # third-party or self
      *)   continue ;;
    esac

    # In-repo: extract module path from go.mod and check if pkg starts with it.
    local mod_path
    mod_path="$(grep -E '^module ' "${manifest}" | awk '{print $2}' || true)"
    if [[ -n "${mod_path}" && "${pkg}" == "${mod_path}"/* ]]; then continue; fi

    # Look in go.mod's require block.
    if grep -qE "^[[:space:]]*${pkg//\//\\/}[[:space:]]" "${manifest}" 2>/dev/null; then
      continue
    fi

    report "${file}:${lineno}: ${line#*:}"
  done < <(grep -nE '^[[:space:]]*"[^"]+"[[:space:]]*$' "${file}" 2>/dev/null || true)
}

# ── Walk the diff ──
while IFS= read -r file; do
  [[ -z "${file}" ]] && continue
  [[ -f "${file}" ]] || continue   # deleted files — skip

  case "${file}" in
    *.py)                                                 check_python    "${file}" ;;
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs)                    check_typescript "${file}" ;;
    *.rs)                                                 check_rust      "${file}" ;;
    *.go)                                                 check_go        "${file}" ;;
    *) ;;  # unsupported language — silent skip
  esac
done <<EOF
${CHANGED}
EOF

if [[ "${UNRESOLVED_TOTAL}" -eq 0 ]]; then
  exit 0
else
  exit 1
fi
