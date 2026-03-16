#!/usr/bin/env bash
# sage-new-feature.sh — Create a feature branch and directory structure
#
# Usage:
#   bash .sage/tools/sage-new-feature.sh <feature-slug> [--no-branch]
#
# Examples:
#   bash .sage/tools/sage-new-feature.sh jwt-auth
#   bash .sage/tools/sage-new-feature.sh user-onboarding --no-branch
#
# What it does:
#   1. Determines the next feature number (NNN)
#   2. Creates .sage/work/NNN-<slug>/ directory
#   3. Creates a git branch (unless --no-branch)
#   4. Initializes progress.md pointer
#   5. Prints the feature path for the agent to use
#
# What it does NOT do:
#   - Decide what the feature should be (agent's job)
#   - Copy templates (sage-scaffold.sh handles that)
#   - Write specs or plans (agent's job)

set -euo pipefail

SAGE_DIR=".sage"
FEATURES_DIR="$SAGE_DIR/features"

# ─── Arguments ─────────────────────────────────────────────────────────────

slug=""
create_branch=true

for arg in "$@"; do
  case "$arg" in
    --no-branch) create_branch=false ;;
    --help|-h)
      echo "Usage: sage-new-feature.sh <feature-slug> [--no-branch]"
      echo ""
      echo "Creates a numbered feature directory and optional git branch."
      echo "  <feature-slug>  Short kebab-case name (e.g., jwt-auth, user-onboarding)"
      echo "  --no-branch     Skip git branch creation"
      exit 0
      ;;
    -*) echo "Unknown option: $arg"; exit 1 ;;
    *) slug="$arg" ;;
  esac
done

if [ -z "$slug" ]; then
  echo "Error: Feature slug is required."
  echo "Usage: sage-new-feature.sh <feature-slug> [--no-branch]"
  exit 1
fi

# Validate slug format
if ! echo "$slug" | grep -qP '^[a-z0-9][a-z0-9-]*[a-z0-9]$'; then
  echo "Error: Slug must be lowercase kebab-case (e.g., jwt-auth, user-onboarding)"
  exit 1
fi

# ─── Check Prerequisites ──────────────────────────────────────────────────

if [ ! -d "$SAGE_DIR" ]; then
  echo "Error: No .sage/ directory found. Run 'npx sage-kit init' first."
  exit 1
fi

# ─── Determine Next Feature Number ────────────────────────────────────────

mkdir -p "$FEATURES_DIR"

# Find the highest existing feature number
max_num=0
for dir in "$FEATURES_DIR"/*/; do
  [ -d "$dir" ] || continue
  num=$(basename "$dir" | grep -oP '^\d+' || echo "0")
  if [ "$num" -gt "$max_num" ]; then
    max_num=$num
  fi
done

next_num=$((max_num + 1))
# Zero-pad to 3 digits
feature_num=$(printf "%03d" "$next_num")
feature_name="${feature_num}-${slug}"
feature_dir="$FEATURES_DIR/$feature_name"

# Check for duplicate slug
for dir in "$FEATURES_DIR"/*/; do
  [ -d "$dir" ] || continue
  existing_slug=$(basename "$dir" | sed 's/^[0-9]*-//')
  if [ "$existing_slug" = "$slug" ]; then
    echo "Error: Feature with slug '$slug' already exists: $(basename "$dir")"
    exit 1
  fi
done

# ─── Create Directory Structure ───────────────────────────────────────────

mkdir -p "$feature_dir"

echo "Created: $feature_dir/"

# ─── Create Git Branch ────────────────────────────────────────────────────

if [ "$create_branch" = true ]; then
  if command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    branch_name="feature/${feature_name}"

    # Check if branch already exists
    if git show-ref --verify --quiet "refs/heads/$branch_name" 2>/dev/null; then
      echo "Warning: Branch '$branch_name' already exists. Skipping branch creation."
    else
      git checkout -b "$branch_name" 2>/dev/null
      echo "Branch: $branch_name (created and checked out)"
    fi
  else
    echo "Note: Not a git repository. Skipping branch creation."
  fi
fi

# ─── Initialize Progress Pointer ──────────────────────────────────────────

cat > "$SAGE_DIR/progress.md" << EOF
# Progress

Mode: (pending)
Feature: ${feature_name}
Plan: ${feature_dir}/plan.md
Phase: elicitation
Next: Define requirements for ${slug}
Updated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

echo "Progress: $SAGE_DIR/progress.md updated"

# ─── Output for Agent ─────────────────────────────────────────────────────

echo ""
echo "──────────────────────────────────────"
echo "Feature: $feature_name"
echo "Directory: $feature_dir/"
echo "Next: Run sage-scaffold.sh to copy templates"
echo "──────────────────────────────────────"
