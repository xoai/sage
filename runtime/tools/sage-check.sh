#!/usr/bin/env bash
# sage-check.sh — Verify prerequisites and project health
#
# Usage:
#   bash .sage/tools/sage-check.sh
#
# What it checks:
#   1. Sage initialization (.sage/ directory exists)
#   2. Required files (constitution, config)
#   3. Git availability and status
#   4. Node.js / Python / package manager availability
#   5. Extension compatibility with detected stack
#   6. State file consistency (progress.md ↔ plan files)
#
# What it does NOT do:
#   - Analyze code quality (agent's job)
#   - Scan for vulnerabilities (agent's job)
#   - Make recommendations about architecture (agent's job)

set -euo pipefail

SAGE_DIR=".sage"
errors=0
warnings=0

# ─── Helpers ──────────────────────────────────────────────────────────────

pass() { echo "  ✅ $1"; }
warn() { echo "  ⚠️  $1"; warnings=$((warnings + 1)); }
fail() { echo "  ❌ $1"; errors=$((errors + 1)); }

check_cmd() {
  if command -v "$1" &>/dev/null; then
    local version
    version=$("$1" --version 2>&1 | head -1 || echo "unknown")
    pass "$2: $version"
  else
    "$3" "$2: not found"
  fi
}

echo "── Sage Health Check ──"
echo ""

# ─── 1. Sage Initialization ─────────────────────────────────────────────

echo "Framework:"
if [ -d "$SAGE_DIR" ]; then
  pass ".sage/ directory exists"
else
  fail ".sage/ directory not found — run 'npx sage-kit init'"
  echo ""
  echo "Result: $errors error(s), $warnings warning(s)"
  exit 1
fi

if [ -f "$SAGE_DIR/config.yaml" ]; then
  pass "config.yaml exists"
else
  warn "config.yaml missing — using defaults"
fi

echo ""

# ─── 2. Constitution ─────────────────────────────────────────────────────

echo "Constitution:"
if [ -f "$SAGE_DIR/constitution.md" ]; then
  principles=$(grep -c '^\d\+\.' "$SAGE_DIR/constitution.md" 2>/dev/null || echo "0")
  pass "Project constitution ($principles principles)"
else
  warn "No project constitution — recommend creating one"
fi

if [ -f "$HOME/.sage/constitution.md" ]; then
  pass "Org constitution found (~/.sage/constitution.md)"
else
  pass "No org constitution (optional)"
fi

echo ""

# ─── 3. Git Status ────────────────────────────────────────────────────────

echo "Git:"
if command -v git &>/dev/null; then
  if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    pass "Git repository (branch: $branch)"

    # Check for uncommitted changes
    if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
      pass "Working tree clean"
    else
      changed=$(git status --porcelain 2>/dev/null | wc -l)
      warn "$changed uncommitted change(s)"
    fi
  else
    warn "Not a git repository — branching features won't work"
  fi
else
  warn "git not installed — session persistence via commits won't work"
fi

echo ""

# ─── 4. Runtime Environment ──────────────────────────────────────────────

echo "Environment:"
check_cmd "node" "Node.js" warn
check_cmd "npm" "npm" warn
check_cmd "python3" "Python 3" pass  # optional, so pass even if missing
check_cmd "pip3" "pip3" pass

echo ""

# ─── 5. Stack Detection ──────────────────────────────────────────────────

echo "Detected Stack:"
detected=""

if [ -f "package.json" ]; then
  pass "package.json found"

  # Check for specific frameworks
  if grep -q '"react"' package.json 2>/dev/null; then
    pass "React detected"
    detected="${detected}react "
  fi
  if grep -q '"next"' package.json 2>/dev/null; then
    pass "Next.js detected"
    detected="${detected}nextjs "
  fi
  if grep -q '"react-native"' package.json 2>/dev/null; then
    pass "React Native detected"
    detected="${detected}react-native "
  fi
  if grep -q '"expo"' package.json 2>/dev/null; then
    pass "Expo detected"
    detected="${detected}expo "
  fi
fi

if [ -f "pubspec.yaml" ]; then
  pass "pubspec.yaml found (Flutter/Dart)"
  detected="${detected}flutter "
  if grep -q 'firebase_core' pubspec.yaml 2>/dev/null; then
    pass "Firebase detected"
    detected="${detected}firebase "
  fi
fi

if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
  pass "Python project detected"
  detected="${detected}python "
fi

if [ -f "Cargo.toml" ]; then
  pass "Rust project detected"
  detected="${detected}rust "
fi

if [ -f "go.mod" ]; then
  pass "Go project detected"
  detected="${detected}go "
fi

if [ -z "$detected" ]; then
  warn "No known project files detected"
fi

echo ""

# ─── 6. Extension Compatibility ──────────────────────────────────────────

echo "Extensions:"
if [ -f "$SAGE_DIR/config.yaml" ]; then
  enabled=$(grep -A 20 'extensions:' "$SAGE_DIR/config.yaml" 2>/dev/null | grep '^ *- ' | sed 's/.*- //' || echo "")

  if [ -n "$enabled" ]; then
    while IFS= read -r ext; do
      ext=$(echo "$ext" | tr -d ' ')
      [ -z "$ext" ] && continue

      # Check if the extension's stack is detected
      case "$ext" in
        react) echo "$detected" | grep -q "react" && pass "react (stack detected)" || warn "react enabled but React not detected" ;;
        nextjs) echo "$detected" | grep -q "nextjs" && pass "nextjs (stack detected)" || warn "nextjs enabled but Next.js not detected" ;;
        react-native) echo "$detected" | grep -q "react-native" && pass "react-native (stack detected)" || warn "react-native enabled but RN not detected" ;;
        flutter) echo "$detected" | grep -q "flutter" && pass "flutter (stack detected)" || warn "flutter enabled but Flutter not detected" ;;
        *) pass "$ext (enabled)" ;;
      esac
    done <<< "$enabled"
  else
    pass "No extensions enabled (using core only)"
  fi
else
  pass "Default configuration (no extensions)"
fi

echo ""

# ─── 7. State Consistency ────────────────────────────────────────────────

echo "State:"
if [ -f "$SAGE_DIR/progress.md" ]; then
  feature=$(grep -oP 'Feature:\s*\K.*' "$SAGE_DIR/progress.md" 2>/dev/null || echo "")
  plan_path=$(grep -oP 'Plan:\s*\K.*' "$SAGE_DIR/progress.md" 2>/dev/null || echo "")

  if [ -n "$feature" ] && [ "$feature" != "(pending)" ]; then
    pass "Active feature: $feature"

    # Check plan file exists
    if [ -n "$plan_path" ]; then
      if [ -f "$plan_path" ]; then
        done=$(grep -c '^\- \[x\]' "$plan_path" 2>/dev/null || echo "0")
        total=$(grep -c '^\- \[.\]' "$plan_path" 2>/dev/null || echo "0")
        if [ "$total" -gt 0 ]; then
          pass "Plan: $done/$total tasks complete"
        else
          pass "Plan exists (no tasks yet)"
        fi
      else
        warn "progress.md points to $plan_path but file not found"
      fi
    fi
  else
    pass "No active feature"
  fi
else
  pass "No progress state (fresh project)"
fi

# Check for orphaned feature directories (no spec or plan)
if [ -d "$SAGE_DIR/features" ]; then
  for dir in "$SAGE_DIR"/features/*/; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")
    if [ ! -f "$dir/spec.md" ] && [ ! -f "$dir/plan.md" ]; then
      warn "Empty feature directory: $name (no spec or plan)"
    fi
  done
fi

echo ""

# ─── Result ───────────────────────────────────────────────────────────────

echo "──────────────────────────────────────"
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
