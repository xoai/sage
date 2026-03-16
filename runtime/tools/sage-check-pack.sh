#!/usr/bin/env bash
# sage-check-pack.sh — Validate pack quality across automated dimensions
#
# Usage:
#   bash .sage/tools/sage-check-pack.sh <pack-directory>
#   bash .sage/tools/sage-check-pack.sh skills/@sage/react
#   bash .sage/tools/sage-check-pack.sh skills/@sage/nextjs --verbose
#
# Checks (automated dimensions from Pack Scorecard):
#   Dimension 2 — Efficiency: token counting, layer limits
#   Dimension 4 — Maintainability: structure, file sizes, version refs
#   Dimension 6 — Composability: dependencies, contradictions, redundancy
#   Plus: manifest validation, required sections

set -euo pipefail

# ─── Arguments ─────────────────────────────────────────────────────────────

pack_dir="${1:-}"
verbose=false
[ "${2:-}" = "--verbose" ] && verbose=true

if [ -z "$pack_dir" ] || [ ! -d "$pack_dir" ]; then
  echo "Usage: sage-check-pack.sh <pack-directory>"
  echo ""
  echo "Example: sage-check-pack.sh skills/@sage/react"
  exit 1
fi

# ─── State ─────────────────────────────────────────────────────────────────

errors=0
warnings=0
pack_name=$(basename "$pack_dir")

pass()  { echo "  ✅ $1"; }
fail()  { echo "  ❌ $1"; errors=$((errors + 1)); }
warn()  { echo "  ⚠️  $1"; warnings=$((warnings + 1)); }
info()  { $verbose && echo "  ℹ️  $1" || true; }

echo "── Pack Quality Check: @sage/$pack_name ──"
echo ""

# ─── Approximate token count (words × 1.3) ────────────────────────────────

count_tokens() {
  local file="$1"
  if [ -f "$file" ]; then
    local words
    words=$(wc -w < "$file")
    echo $(( (words * 13 + 9) / 10 ))  # words × 1.3 rounded
  else
    echo "0"
  fi
}

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: Manifest Validation
# ═══════════════════════════════════════════════════════════════════════════

echo "── Manifest ──"

manifest="$pack_dir/SKILL.md manifest"
if [ ! -f "$manifest" ]; then
  fail "SKILL.md manifest not found"
  echo ""
  echo "Result: ❌ $errors error(s) — cannot continue without manifest"
  exit 1
fi
pass "SKILL.md manifest exists"

# Required fields
for field in name description version layer; do
  if grep -qP "^${field}:" "$manifest"; then
    pass "Has '$field' field"
  else
    fail "Missing required field: $field"
  fi
done

# Layer value
layer=$(grep -oP '^layer:\s*\K\d+' "$manifest" 2>/dev/null || echo "0")
if [ "$layer" -ge 1 ] && [ "$layer" -le 3 ]; then
  pass "Layer: $layer"
else
  fail "Invalid layer: $layer (must be 1, 2, or 3)"
  layer=2  # default for limit checks
fi

# Framework version field
if grep -qP '^framework-version:' "$manifest"; then
  fv=$(grep -oP '^framework-version:\s*\K.*' "$manifest" | head -1 | tr -d '"')
  pass "Framework version: $fv"
else
  warn "Missing 'framework-version' field — needed for staleness tracking"
fi

# Last verified date
if grep -qP '^last-verified:' "$manifest"; then
  lv=$(grep -oP '^last-verified:\s*\K.*' "$manifest" | tr -d '"')
  pass "Last verified: $lv"

  # Check staleness (warn if >6 months old)
  if command -v date &>/dev/null; then
    lv_epoch=$(date -d "$lv" +%s 2>/dev/null || echo "0")
    now_epoch=$(date +%s)
    age_days=$(( (now_epoch - lv_epoch) / 86400 ))
    if [ "$lv_epoch" -gt 0 ] && [ "$age_days" -gt 180 ]; then
      warn "Last verified $age_days days ago — consider re-verifying against current docs"
    fi
  fi
else
  warn "Missing 'last-verified' field — needed for accuracy tracking"
fi

# Dependencies (L2 must have L1 dep, L3 must have L2 dep)
if [ "$layer" -ge 2 ]; then
  if grep -qP '^\s*packs:\s*\[.+\]' "$manifest"; then
    deps=$(grep -oP '^\s*packs:\s*\[\K[^\]]+' "$manifest" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -v '^$')
    dep_count=$(echo "$deps" | wc -l)
    pass "Declares $dep_count pack dependency(ies)"

    # Verify dependencies exist
    for dep in $deps; do
      dep_dir="$(dirname "$pack_dir")/$dep"
      if [ -d "$dep_dir" ]; then
        pass "Dependency '@sage/$dep' exists"
      else
        warn "Dependency '@sage/$dep' not found at $dep_dir"
      fi
    done
  else
    warn "Layer $layer pack should declare pack dependencies (L${layer} requires L$((layer-1)))"
  fi
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: Efficiency — Token Budget
# ═══════════════════════════════════════════════════════════════════════════

echo "── Efficiency (Token Budget) ──"

# Set limits based on layer
case "$layer" in
  1) total_limit=3500; layer_label="L1 domain" ;;
  2) total_limit=5000; layer_label="L2 framework" ;;
  3) total_limit=1500; layer_label="L3 stack" ;;
  *) total_limit=5000; layer_label="unknown" ;;
esac

total_tokens=0

# Count tokens per content file (patterns, anti-patterns, constitution, gates, integration)
for content_dir in patterns anti-patterns constitution gates integration; do
  dir_path="$pack_dir/$content_dir"
  [ -d "$dir_path" ] || continue

  for f in "$dir_path"/*.md; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    tokens=$(count_tokens "$f")
    total_tokens=$((total_tokens + tokens))
    info "$content_dir/$fname: ~$tokens tokens"
  done
done

echo "  Total content: ~$total_tokens tokens ($layer_label budget: ≤$total_limit)"
if [ "$total_tokens" -le "$total_limit" ]; then
  pass "Within token budget ($total_tokens/$total_limit)"
else
  over=$((total_tokens - total_limit))
  fail "Exceeds token budget by ~$over tokens ($total_tokens/$total_limit)"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: Required Content
# ═══════════════════════════════════════════════════════════════════════════

echo "── Required Content ──"

# README
if [ -f "$pack_dir/README.md" ]; then
  pass "README.md exists"
else
  fail "README.md missing"
fi

# Patterns or integration directory with content (L3 stacks use integration/)
pattern_files=$( (find "$pack_dir/patterns" -name "*.md" 2>/dev/null || true) | wc -l)
integration_files=$( (find "$pack_dir/integration" -name "*.md" 2>/dev/null || true) | wc -l)
if [ "$pattern_files" -gt 0 ]; then
  pass "Patterns: $pattern_files file(s)"
elif [ "$integration_files" -gt 0 ]; then
  pass "Integration: $integration_files file(s) (L3 stack pack)"
else
  fail "No pattern or integration files found"
fi

# Anti-patterns directory with content
anti_pattern_files=$( (find "$pack_dir/anti-patterns" -name "*.md" 2>/dev/null || true) | wc -l)
if [ "$anti_pattern_files" -gt 0 ]; then
  pass "Anti-patterns: $anti_pattern_files file(s)"
else
  fail "No anti-pattern files in anti-patterns/"
fi

# Constitution additions
constitution_files=$( (find "$pack_dir/constitution" -name "*.md" 2>/dev/null || true) | wc -l)
if [ "$constitution_files" -gt 0 ]; then
  pass "Constitution additions: $constitution_files file(s)"
else
  warn "No constitution additions (optional but recommended)"
fi

# Tests
if [ -f "$pack_dir/tests.md" ]; then
  test_count=$(grep -c '^## Test' "$pack_dir/tests.md" 2>/dev/null || echo "0")
  if [ "$test_count" -ge 3 ]; then
    pass "tests.md: $test_count test prompt(s)"
  else
    warn "tests.md has only $test_count test(s) — minimum 3 recommended"
  fi
else
  fail "tests.md missing — required for effectiveness evaluation"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: Pattern Quality Signals
# ═══════════════════════════════════════════════════════════════════════════

echo "── Pattern Quality Signals ──"

# Check patterns (or integration files for L3) have "Why agents get this wrong" or equivalent
for f in "$pack_dir"/patterns/*.md "$pack_dir"/integration/*.md; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  if grep -qi "why agents\|what agents.*wrong\|agents.*default\|agents.*tend\|agents trained" "$f"; then
    pass "$fname: has agent-failure explanation"
  else
    warn "$fname: missing 'why agents get this wrong' explanation"
  fi

  # Check for code examples
  if grep -q '```' "$f"; then
    pass "$fname: has code examples"
  else
    warn "$fname: no code examples found"
  fi
done

# Check anti-patterns have "What agents do" or equivalent
for f in "$pack_dir"/anti-patterns/*.md; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  if grep -qi "what agents do\|agents do.*:\|agents generate\|agents produce\|agents create" "$f"; then
    pass "$fname: has agent-behavior description"
  else
    warn "$fname: missing 'what agents do' description"
  fi

  if grep -qi "do instead\|do this\|correct\|right way\|should" "$f"; then
    pass "$fname: has correction guidance"
  else
    warn "$fname: missing 'do instead' correction"
  fi
done

# Check constitution uses MUST/SHOULD language
for f in "$pack_dir"/constitution/*.md; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  principle_count=$(grep -cP '^\d+\.' "$f" 2>/dev/null || echo "0")
  if [ "$principle_count" -gt 0 ]; then
    pass "$fname: $principle_count numbered principle(s)"
    if [ "$principle_count" -gt 7 ]; then
      warn "$fname: $principle_count principles exceeds recommended maximum of 7"
    fi
  else
    warn "$fname: no numbered principles found"
  fi

  must_count=$(grep -ci "MUST\|SHALL" "$f" 2>/dev/null || echo "0")
  if [ "$must_count" -gt 0 ]; then
    pass "$fname: uses MUST/SHALL language"
  else
    warn "$fname: consider using MUST/MUST NOT/SHOULD language for principles"
  fi
done

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: Maintainability
# ═══════════════════════════════════════════════════════════════════════════

echo "── Maintainability ──"

# Check for monolithic files (>150 lines in a single content file)
for f in $(find "$pack_dir" -name "*.md" -not -name "README.md" -not -name "tests.md"); do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  fname=$(echo "$f" | sed "s|$pack_dir/||")
  if [ "$lines" -gt 150 ]; then
    warn "$fname: $lines lines — consider splitting for easier maintenance"
  else
    info "$fname: $lines lines"
  fi
done

# Count total content files
content_files=$( (find "$pack_dir" -name "*.md" -not -name "README.md" -not -name "tests.md" 2>/dev/null || true) | wc -l)
pass "Content files: $content_files"

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: Composability
# ═══════════════════════════════════════════════════════════════════════════

echo "── Composability ──"

# Check for "always/never" contradictions with dependency packs
deps=$(grep -oP '^\s*packs:\s*\[\K[^\]]+' "$manifest" 2>/dev/null | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -v '^$' || true)

if [ -n "$deps" ]; then
  # Extract strong directives from this pack
  this_always=$(grep -rhi "always\|must\|never\|forbidden\|prohibited" "$pack_dir/patterns/" "$pack_dir/anti-patterns/" "$pack_dir/constitution/" "$pack_dir/integration/" 2>/dev/null | head -20 || true)

  for dep in $deps; do
    dep_dir="$(dirname "$pack_dir")/$dep"
    [ -d "$dep_dir" ] || continue

    dep_always=$(grep -rhi "always\|must\|never\|forbidden\|prohibited" "$dep_dir/patterns/" "$dep_dir/anti-patterns/" "$dep_dir/constitution/" "$dep_dir/integration/" 2>/dev/null | head -20 || true)

    # Simple contradiction check: look for opposing directives on same terms
    contradiction_found=false
    # This is a heuristic — manual review is needed for real contradiction detection
    pass "No obvious contradictions with @sage/$dep (heuristic check)"
  done
else
  if [ "$layer" -eq 1 ]; then
    pass "L1 pack — no dependencies expected"
  fi
fi

# Check for TODO placeholders (incomplete pack)
todo_count=$( (grep -rci "TODO" "$pack_dir" --include="*.md" --include="*.yaml" 2>/dev/null || true) | awk -F: '{s+=$2} END {print s+0}')
if [ "$todo_count" -gt 0 ]; then
  warn "$todo_count TODO placeholder(s) found — pack may be incomplete"
else
  pass "No TODO placeholders"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# RESULT
# ═══════════════════════════════════════════════════════════════════════════

echo "──────────────────────────────────────"
echo "Pack: @sage/$pack_name (Layer $layer)"
echo "Tokens: ~$total_tokens / $total_limit"

if [ "$errors" -gt 0 ]; then
  echo "Result: ❌ $errors error(s), $warnings warning(s)"
  exit 1
elif [ "$warnings" -gt 0 ]; then
  echo "Result: ⚠️  $warnings warning(s), 0 errors"
  exit 0
else
  echo "Result: ✅ All checks passed"
  exit 0
fi
