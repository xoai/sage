#!/usr/bin/env bash
# sage-hallucination-check.sh — Deterministic checks for Gate 4
# Verifies imports resolve, referenced files exist, and no phantom APIs are used.
# Usage: bash sage/core/gates/scripts/sage-hallucination-check.sh [file-or-dir] [project-root]
#
# Exit contract (ADR-1):
#   0 = verified pass   1 = verified fail   2 = unverifiable (nothing to check)
#
# Source analysis runs in one embedded python3 block rather than in a
# `grep -oP … | while read` pipeline. Two reasons, both of which produced
# silent fail-open behavior before:
#   1. A `while` loop on the right of a pipe runs in a subshell, so the
#      failure state and counters it set never reached the final verdict.
#   2. `grep -P` is GNU-only. BSD grep (macOS) and BusyBox grep (Alpine) do
#      not have it, so on those platforms the checks examined nothing at all.

set -uo pipefail

TARGET="${1:-.}"
ROOT="${2:-.}"
PASS=true
WARNINGS=0

log() { echo "$1"; }
warn() { log "⚠️  $1"; WARNINGS=$((WARNINGS + 1)); }
fail() { log "❌ $1"; PASS=false; }

log "═══ Sage Gate 4: Hallucination Check ═══"
log "Target: $TARGET"
log ""

if ! command -v python3 >/dev/null 2>&1; then
  log "═══ Gate 4 Result ═══"
  log "⚠️ UNVERIFIABLE — python3 is required to analyze source files"
  exit 2
fi

# ── Static analysis (single pass, emitted as tab-separated records) ──
#
# Protocol:
#   FILE            <path>
#   CHECKED_IMPORTS <n>
#   MISSING_IMPORT  <file>  <specifier>
#   PKG_MANIFEST    <path|->
#   CHECKED_PKGS    <n>
#   PHANTOM_PKG     <file>  <package>
#
# The analyzer is written to a temp file rather than piped straight into
# `$(python3 - <<'PYEOF' … )`. bash 3.2 scans for the closing paren of a
# command substitution without understanding the heredoc inside it, so an
# unbalanced quote in the heredoc body — this analyzer's `['"]` regex has an
# odd number of double quotes — makes it mis-parse code much further down the
# file. bash 4+ and every other shell handle it; bash 3.2 (macOS /bin/bash)
# does not. Keep the heredoc at statement level.
PY_ANALYZER=$(mktemp "${TMPDIR:-/tmp}/sage-gate4-XXXXXX") || {
  log "═══ Gate 4 Result ═══"
  log "⚠️ UNVERIFIABLE — could not create a temporary file"
  exit 2
}
trap 'rm -f "$PY_ANALYZER"' EXIT

cat > "$PY_ANALYZER" <<'PYEOF'
import json
import os
import re
import sys

target, root = sys.argv[1], sys.argv[2]

SRC_EXT = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.dart'}
JS_EXT = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', '.next', 'out',
             'venv', '.venv', '__pycache__', '.dart_tool', 'coverage'}

# Resolution order mirrors bundler/tsc behavior closely enough for a gate.
CAND_EXT = ['', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.d.ts']
INDEX_FILES = ['index.ts', 'index.tsx', 'index.js', 'index.jsx']

NODE_BUILTINS = {
    'assert', 'async_hooks', 'buffer', 'child_process', 'cluster', 'console',
    'constants', 'crypto', 'dgram', 'diagnostics_channel', 'dns', 'domain',
    'events', 'fs', 'http', 'http2', 'https', 'inspector', 'module', 'net',
    'os', 'path', 'perf_hooks', 'process', 'punycode', 'querystring',
    'readline', 'repl', 'stream', 'string_decoder', 'sys', 'timers', 'tls',
    'trace_events', 'tty', 'url', 'util', 'v8', 'vm', 'wasi', 'worker_threads',
    'zlib',
}

SPEC = r"""['"]([^'"\n]+)['"]"""
IMPORT_PATTERNS = [
    re.compile(r'\bfrom\s+' + SPEC),          # import x from 'y' / export … from 'y'
    re.compile(r'\bimport\s+' + SPEC),        # import 'y'  (side-effect)
    re.compile(r'\brequire\s*\(\s*' + SPEC),  # require('y')
    re.compile(r'\bimport\s*\(\s*' + SPEC),   # import('y') (dynamic)
]

out = []


def emit(*fields):
    out.append('\t'.join(str(f) for f in fields))


def discover(t):
    if os.path.isfile(t):
        return [t]
    if not os.path.isdir(t):
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(t):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] in SRC_EXT:
                found.append(os.path.join(dirpath, fn))
    return sorted(found)


def strip_jsonc(text):
    """tsconfig.json is JSON-with-comments; tolerate // and /* */ plus trailing commas."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'(^|\s)//[^\n]*', r'\1', text)
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def load_json(path, tolerant=False):
    try:
        with open(path, encoding='utf-8') as fh:
            raw = fh.read()
        return json.loads(strip_jsonc(raw) if tolerant else raw)
    except Exception:
        return None


def specifiers(path):
    """Unique import specifiers, in source order."""
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            src = fh.read()
    except OSError:
        return []
    seen, found = set(), []
    for pat in IMPORT_PATTERNS:
        for m in pat.finditer(src):
            spec = m.group(1)
            if spec not in seen:
                seen.add(spec)
                found.append(spec)
    return found


def resolves(base_dir, spec):
    p = os.path.normpath(os.path.join(base_dir, spec))
    for ext in CAND_EXT:
        if os.path.isfile(p + ext):
            return True
    if os.path.isdir(p):
        for idx in INDEX_FILES:
            if os.path.isfile(os.path.join(p, idx)):
                return True
    return False


def ancestors(start):
    """`start` and its parents, stopping at a repo boundary (inclusive)."""
    cur = os.path.abspath(start)
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        yield cur
        if os.path.isdir(os.path.join(cur, '.git')):
            return
        parent = os.path.dirname(cur)
        if parent == cur:
            return
        cur = parent


def package_name(spec):
    if spec.startswith('@'):
        parts = spec.split('/')
        return '/'.join(parts[:2]) if len(parts) >= 2 else spec
    return spec.split('/')[0]


files = discover(target)
for f in files:
    emit('FILE', f)

# ── relative imports ──
checked_imports = 0
for f in files:
    if os.path.splitext(f)[1] not in JS_EXT:
        continue
    base = os.path.dirname(f) or '.'
    for spec in specifiers(f):
        if not (spec.startswith('./') or spec.startswith('../')):
            continue
        checked_imports += 1
        if not resolves(base, spec):
            emit('MISSING_IMPORT', f, spec)
emit('CHECKED_IMPORTS', checked_imports)

# ── package imports ──
# Declared dependencies are collected from the nearest package.json and its
# ancestors (monorepos declare deps in the workspace package). node_modules is
# consulted along the same chain, matching Node's own resolution.
manifest = None
declared = set()
node_modules_dirs = []
for d in ancestors(root):
    pj = os.path.join(d, 'package.json')
    if os.path.isfile(pj):
        if manifest is None:
            manifest = pj
        data = load_json(pj) or {}
        for field in ('dependencies', 'devDependencies', 'peerDependencies',
                      'optionalDependencies'):
            declared.update((data.get(field) or {}).keys())
    nm = os.path.join(d, 'node_modules')
    if os.path.isdir(nm):
        node_modules_dirs.append(nm)

# tsconfig `paths` keys are aliases, not packages.
aliases = set()
ts = load_json(os.path.join(root, 'tsconfig.json'), tolerant=True)
if isinstance(ts, dict):
    paths = ((ts.get('compilerOptions') or {}).get('paths') or {})
    for key in paths:
        aliases.add(key.rstrip('*').rstrip('/'))

emit('PKG_MANIFEST', manifest or '-')

checked_pkgs = 0
if manifest:
    for f in files:
        if os.path.splitext(f)[1] not in JS_EXT:
            continue
        for spec in specifiers(f):
            if spec.startswith(('.', '/')):
                continue
            if spec.startswith(('@/', '~/', '#')):
                continue          # conventional path aliases
            if any(spec == a or spec.startswith(a + '/') for a in aliases):
                continue
            if spec.startswith('node:'):
                continue
            pkg = package_name(spec)
            if pkg in NODE_BUILTINS:
                continue
            checked_pkgs += 1
            if pkg in declared:
                continue
            if any(os.path.isdir(os.path.join(nm, pkg)) for nm in node_modules_dirs):
                continue
            emit('PHANTOM_PKG', f, pkg)
emit('CHECKED_PKGS', checked_pkgs)

sys.stdout.write('\n'.join(out) + ('\n' if out else ''))
PYEOF

ANALYSIS=$(python3 "$PY_ANALYZER" "$TARGET" "$ROOT")
ANALYSIS_RC=$?

if [ "$ANALYSIS_RC" -ne 0 ]; then
  log "═══ Gate 4 Result ═══"
  log "⚠️ UNVERIFIABLE — source analysis failed (python3 exited $ANALYSIS_RC)"
  exit 2
fi

# ── Parse the analysis into shell state (here-string: no subshell) ──
FILE_COUNT=0
CHECKED_IMPORTS=0
MISSING_IMPORTS=0
CHECKED_PKGS=0
PHANTOM_PKGS=0
PKG_MANIFEST="-"
MISSING_LINES=""
PHANTOM_LINES=""
FILES_LIST=()

while IFS=$'\t' read -r kind a b; do
  case "$kind" in
    FILE)            FILES_LIST+=("$a"); FILE_COUNT=$((FILE_COUNT + 1)) ;;
    CHECKED_IMPORTS) CHECKED_IMPORTS="$a" ;;
    CHECKED_PKGS)    CHECKED_PKGS="$a" ;;
    PKG_MANIFEST)    PKG_MANIFEST="$a" ;;
    MISSING_IMPORT)  MISSING_IMPORTS=$((MISSING_IMPORTS + 1))
                     MISSING_LINES="${MISSING_LINES}${b}|${a}"$'\n' ;;
    PHANTOM_PKG)     PHANTOM_PKGS=$((PHANTOM_PKGS + 1))
                     PHANTOM_LINES="${PHANTOM_LINES}${b}|${a}"$'\n' ;;
  esac
done <<< "$ANALYSIS"

# ── Step 1: Check file references exist ──
log "── File reference check ──"

if [ -n "$MISSING_LINES" ]; then
  while IFS='|' read -r spec file; do
    [ -z "$spec" ] && continue
    fail "Import not found: '$spec' in $file"
  done <<< "$MISSING_LINES"
fi

if [ "$CHECKED_IMPORTS" -eq 0 ]; then
  log "  No relative imports to check"
else
  log "  Checked $CHECKED_IMPORTS imports, $MISSING_IMPORTS missing"
fi

log ""

# ── Step 2: Check for phantom packages ──
log "── Package existence check ──"

if [ "$PKG_MANIFEST" = "-" ]; then
  log "  No package.json — skipping package check"
else
  if [ -n "$PHANTOM_LINES" ]; then
    while IFS='|' read -r pkg file; do
      [ -z "$pkg" ] && continue
      fail "Package '$pkg' imported in $file but not declared in package.json or installed"
    done <<< "$PHANTOM_LINES"
  fi
  if [ "$CHECKED_PKGS" -eq 0 ]; then
    log "  No package imports to check"
  else
    log "  Checked $CHECKED_PKGS package imports, $PHANTOM_PKGS undeclared"
  fi
fi

log ""

# ── Step 3: TypeScript compilation check ──
log "── Type check ──"

if [ -f "$ROOT/tsconfig.json" ]; then
  if command -v npx >/dev/null 2>&1; then
    TYPE_OUTPUT=$(cd "$ROOT" && npx tsc --noEmit 2>&1) || {
      ERRORS=$(printf '%s\n' "$TYPE_OUTPUT" | grep -c "error TS")
      fail "TypeScript errors: $ERRORS"
      printf '%s\n' "$TYPE_OUTPUT" | grep "error TS" | head -5
    }
    [ "$PASS" = true ] && log "  ✅ TypeScript compiles with no errors"
  else
    warn "npx not available, skipping TypeScript check"
  fi
else
  log "  No tsconfig.json — skipping type check"
fi

log ""

# ── Step 4: Check for common hallucination patterns ──
log "── Common hallucination patterns ──"

for file in ${FILES_LIST[@]+"${FILES_LIST[@]}"}; do
  # Check for non-existent React hooks (common hallucination)
  if grep -q "useServer" "$file"; then
    fail "Hallucinated API: 'useServer' does not exist (in $file)"
  fi
  if grep -q "useClient" "$file"; then
    fail "Hallucinated API: 'useClient' does not exist — use 'use client' directive (in $file)"
  fi

  # Check for deprecated/removed APIs used as if current
  if grep -q "getServerSideProps\|getStaticProps\|getInitialProps" "$file"; then
    case "$file" in
      */app/*) warn "Pages Router API in App Router file: $file" ;;
    esac
  fi
done

log ""

# ── Result ──
log "═══ Gate 4 Result ═══"
if [ "$PASS" = true ] && [ $WARNINGS -eq 0 ]; then
  log "✅ PASS — No hallucinations detected"
  exit 0
elif [ "$PASS" = true ]; then
  log "⚠️  PASS WITH WARNINGS — $WARNINGS warning(s), review recommended"
  exit 0
else
  log "❌ FAIL — Hallucinated imports or APIs detected"
  exit 1
fi
