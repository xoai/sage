#!/usr/bin/env bash
# sage-scaffold.sh — Copy template files into a feature directory based on mode
#
# Usage:
#   bash .sage/tools/sage-scaffold.sh <feature-name> <mode>
#
# Examples:
#   bash .sage/tools/sage-scaffold.sh 001-jwt-auth build
#   bash .sage/tools/sage-scaffold.sh 002-payment-system architect
#
# What it does:
#   - BUILD mode:  copies minimal spec template + standard plan template
#   - ARCHITECT mode: copies full spec template + standard plan template + decision record template
#   - FIX mode: no templates needed (fixes don't have specs/plans)
#
# What it does NOT do:
#   - Write the content (agent's job)
#   - Make decisions about what to build (agent's job)
#   - Run any analysis (agent's job)

set -euo pipefail

SAGE_DIR=".sage"
FEATURES_DIR="$SAGE_DIR/features"

# ─── Arguments ─────────────────────────────────────────────────────────────

feature_name="${1:-}"
mode="${2:-}"

if [ -z "$feature_name" ] || [ -z "$mode" ]; then
  echo "Usage: sage-scaffold.sh <feature-name> <mode>"
  echo ""
  echo "  <feature-name>  Feature directory name (e.g., 001-jwt-auth)"
  echo "  <mode>          build | architect"
  echo ""
  echo "Templates copied per mode:"
  echo "  build:     minimal spec + standard plan"
  echo "  architect: full spec + standard plan + decision record template"
  exit 1
fi

mode=$(echo "$mode" | tr '[:upper:]' '[:lower:]')

if [ "$mode" != "build" ] && [ "$mode" != "architect" ]; then
  echo "Error: Mode must be 'build' or 'architect'. FIX mode doesn't use templates."
  exit 1
fi

# ─── Verify Paths ─────────────────────────────────────────────────────────

feature_dir="$FEATURES_DIR/$feature_name"

if [ ! -d "$feature_dir" ]; then
  echo "Error: Feature directory not found: $feature_dir"
  echo "Run sage-new-feature.sh first to create it."
  exit 1
fi

# Find templates — check .sage/develop/templates/ first (project overrides), then framework defaults
find_template() {
  local subpath="$1"

  # Project override
  if [ -f "$SAGE_DIR/develop/templates/$subpath" ]; then
    echo "$SAGE_DIR/develop/templates/$subpath"
    return 0
  fi

  # Framework default (when installed via CLI, templates are in .sage/develop/templates/)
  # Also check relative to script location for development
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local sage_root
  sage_root="$(cd "$script_dir/.." && pwd)"

  if [ -f "$sage_root/develop/templates/$subpath" ]; then
    echo "$sage_root/develop/templates/$subpath"
    return 0
  fi

  echo ""
  return 1
}

# ─── Copy Templates ───────────────────────────────────────────────────────

copied=0

copy_template() {
  local template_path="$1"
  local dest_name="$2"
  local dest="$feature_dir/$dest_name"

  if [ -f "$dest" ]; then
    echo "  Skip: $dest_name (already exists)"
    return 0
  fi

  local source
  source=$(find_template "$template_path")

  if [ -z "$source" ]; then
    echo "  Warning: Template not found: $template_path"
    return 0
  fi

  cp "$source" "$dest"
  echo "  Copied: $dest_name"
  copied=$((copied + 1))
}

echo "Scaffolding $feature_name ($mode mode):"
echo ""

case "$mode" in
  build)
    copy_template "spec/minimal.spec-template.md" "spec.md"
    copy_template "plan/standard.plan-template.md" "plan.md"
    ;;

  architect)
    copy_template "spec/full.spec-template.md" "spec.md"
    copy_template "plan/standard.plan-template.md" "plan.md"
    copy_template "architecture/decision-template.md" "adr.md"
    ;;
esac

# ─── Update Progress Pointer ─────────────────────────────────────────────

if [ -f "$SAGE_DIR/progress.md" ]; then
  # Update the mode in progress.md
  if grep -q '^Mode:' "$SAGE_DIR/progress.md"; then
    sed -i "s/^Mode:.*/Mode: $mode/" "$SAGE_DIR/progress.md"
  fi
  if grep -q '^Updated:' "$SAGE_DIR/progress.md"; then
    sed -i "s/^Updated:.*/Updated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")/" "$SAGE_DIR/progress.md"
  fi
fi

# ─── Output ───────────────────────────────────────────────────────────────

echo ""
if [ "$copied" -gt 0 ]; then
  echo "Done: $copied template(s) copied to $feature_dir/"
else
  echo "Done: All templates already existed. Nothing copied."
fi
echo ""
echo "Next: Fill in the spec, then create the plan."
