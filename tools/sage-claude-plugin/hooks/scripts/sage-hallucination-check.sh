#!/usr/bin/env bash
# sage-hallucination-check.sh — Deterministic checks for Gate 4
# Verifies imports resolve, referenced files exist, and no phantom APIs are used.
# Usage: bash sage/core/gates/scripts/sage-hallucination-check.sh [file-or-dir] [project-root]

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

# ── Step 1: Check file references exist ──
log "── File reference check ──"

# Find import/require statements in changed files
find_files() {
  if [ -d "$TARGET" ]; then
    find "$TARGET" -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -o -name "*.py" -o -name "*.dart" 2>/dev/null
  elif [ -f "$TARGET" ]; then
    echo "$TARGET"
  fi
}

CHECKED=0
MISSING=0

for file in $(find_files); do
  # Check relative imports (JS/TS)
  grep -oP "from ['\"](\./[^'\"]+)['\"]" "$file" 2>/dev/null | while read -r line; do
    import_path=$(echo "$line" | grep -oP "(?<=from ['\"])\./[^'\"]+")
    # Resolve relative to file's directory
    file_dir=$(dirname "$file")
    full_path="$file_dir/$import_path"
    
    # Try common extensions
    found=false
    for ext in "" ".ts" ".tsx" ".js" ".jsx" "/index.ts" "/index.tsx" "/index.js"; do
      if [ -f "${full_path}${ext}" ]; then
        found=true
        break
      fi
    done
    
    if [ "$found" = false ]; then
      fail "Import not found: '$import_path' in $file"
      MISSING=$((MISSING + 1))
    fi
    CHECKED=$((CHECKED + 1))
  done
done

if [ $CHECKED -eq 0 ]; then
  log "  No relative imports to check"
else
  log "  Checked $CHECKED imports, $MISSING missing"
fi

log ""

# ── Step 2: Check for known phantom packages ──
log "── Package existence check ──"

if [ -f "$ROOT/package.json" ]; then
  # Check that imported packages exist in package.json or node_modules
  DEPS=$(cat "$ROOT/package.json" | grep -oP '"[^"]+"\s*:' | tr -d '":' | tr -d ' ')
  
  for file in $(find_files); do
    # Find package imports (not relative)
    grep -oP "from ['\"]([^./][^'\"]*)['\"]" "$file" 2>/dev/null | while read -r line; do
      pkg=$(echo "$line" | grep -oP "(?<=from ['\"])[^./][^'\"]*" | sed 's|/.*||')
      
      # Skip node builtins
      case "$pkg" in
        react|react-dom|next|fs|path|crypto|http|https|url|util|stream|os|child_process) continue ;;
      esac
      
      # Check in package.json deps
      if ! echo "$DEPS" | grep -q "^${pkg}$" 2>/dev/null; then
        # Check node_modules as fallback (might be a transitive dep)
        if [ ! -d "$ROOT/node_modules/$pkg" ]; then
          warn "Package '$pkg' imported in $file but not in package.json"
        fi
      fi
    done
  done
fi

log ""

# ── Step 3: TypeScript compilation check ──
log "── Type check ──"

if [ -f "$ROOT/tsconfig.json" ]; then
  if command -v npx &>/dev/null; then
    TYPE_OUTPUT=$(cd "$ROOT" && npx tsc --noEmit 2>&1) || {
      ERRORS=$(echo "$TYPE_OUTPUT" | grep -c "error TS" 2>/dev/null || echo "?")
      fail "TypeScript errors: $ERRORS"
      echo "$TYPE_OUTPUT" | grep "error TS" | head -5
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

for file in $(find_files); do
  # Check for non-existent React hooks (common hallucination)
  if grep -q "useServer\b" "$file" 2>/dev/null; then
    fail "Hallucinated API: 'useServer' does not exist (in $file)"
  fi
  if grep -q "useClient\b" "$file" 2>/dev/null; then
    fail "Hallucinated API: 'useClient' does not exist — use 'use client' directive (in $file)"
  fi
  
  # Check for deprecated/removed APIs used as if current
  if grep -q "getServerSideProps\|getStaticProps\|getInitialProps" "$file" 2>/dev/null; then
    if grep -q "app/" <<< "$file" 2>/dev/null; then
      warn "Pages Router API in App Router file: $file"
    fi
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
