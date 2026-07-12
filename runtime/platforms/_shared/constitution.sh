#!/usr/bin/env bash
# Shared constitution merge for Sage platform generators.
#
# Builds the "## Engineering Principles" section that replaces
# __CONSTITUTION_PLACEHOLDER__ in the instructions body: the base five, plus the
# project's preset additions, plus the project's own additions — renumbered
# continuously so a project addition reads as a peer of the base five, which is
# exactly what it is.
#
# Extracted here because the claude-code generator had it inline and the generic
# generator needed the same 50 lines. Two copies of a merge like this drift, and
# the failure is silent: a project's own constitution quietly stops being applied
# on one platform and nobody finds out, because nothing compares the two outputs.
#
# Usage:
#   source runtime/platforms/_shared/constitution.sh
#   CONST_SECTION="$(build_constitution_section "$CORE" "$PROJECT_SAGE")"

build_constitution_section() {
  local core="$1"
  local project_sage="$2"

  # Each principle names what enforces it. The eval that produced this version of
  # Sage found that mechanically-enforced rules moved behavior and prose ones, on
  # their own, did not — so a reader deserves to know which kind each one is.
  # "Judgment" is not a euphemism for "optional"; it means the only thing standing
  # behind the rule is someone noticing, and that is worth being honest about.
  local section="## Engineering Principles

Base (all projects):
1. Tests before code — every behavior has a test first [sage-tdd-gate: blocks the edit]
2. No silent failures — errors handled, logged, or propagated [Gate 3: judgment]
3. Secrets never in code — env vars or a secret manager [Gate 3: judgment]
4. Dependencies explicit — declared, pinned [Gate 4: sage-hallucination-check]
5. Changes reversible — migrations reversible, deploys rollbackable [Gate 3: judgment]

Full text, project additions, and the reasoning: the sage-constitution skill."

  local num=5
  local const_file="$project_sage/constitution.md"
  [ -f "$const_file" ] || { printf '%s\n' "$section"; return 0; }

  # ── Preset additions ──
  local preset
  preset=$(sed -n '/^---$/,/^---$/{ /^extends:/s/^extends: *//p; }' "$const_file" 2>/dev/null)
  if [ -n "$preset" ] && [ "$preset" != "base" ] && [ "$preset" != "none" ]; then
    local preset_file="$core/constitution/presets/${preset}.constitution.md"
    if [ -f "$preset_file" ]; then
      local preset_principles
      preset_principles=$(sed -n '/^## Additions/,$ { /^[0-9]/p; }' "$preset_file")
      if [ -n "$preset_principles" ]; then
        section="$section

${preset} preset:"
        while IFS= read -r line; do
          if [ -n "$line" ]; then
            num=$((num + 1))
            local clean
            clean=$(echo "$line" | sed 's/^[0-9]*\. *//')
            section="$section
${num}. ${clean}"
          fi
        done <<< "$preset_principles"
      fi
    fi
  fi

  # ── Project additions ──
  local project_additions
  project_additions=$(sed -n '/^## Project Additions/,$ { /^## Project/d; /^$/d; /^(/d; p; }' "$const_file" 2>/dev/null)
  if [ -n "$project_additions" ]; then
    section="$section

Project additions:"
    while IFS= read -r line; do
      if [ -n "$line" ]; then
        num=$((num + 1))
        section="$section
${num}. ${line}"
      fi
    done <<< "$project_additions"
  fi

  printf '%s\n' "$section"
}
