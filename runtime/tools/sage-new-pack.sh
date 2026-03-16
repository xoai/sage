#!/usr/bin/env bash
# sage-new-pack.sh — Scaffold a new pack with correct structure
#
# Usage:
#   bash .sage/tools/sage-new-pack.sh <pack-name> [--layer <1|2|3>]
#
# Examples:
#   bash .sage/tools/sage-new-pack.sh vue --layer 2
#   bash .sage/tools/sage-new-pack.sh api --layer 1
#   bash .sage/tools/sage-new-pack.sh stack-nuxt-fullstack --layer 3

set -euo pipefail

# ─── Arguments ─────────────────────────────────────────────────────────────

pack_name=""
layer="2"

while [ $# -gt 0 ]; do
  case "$1" in
    --layer) layer="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: sage-new-pack.sh <pack-name> [--layer <1|2|3>]"
      echo ""
      echo "Scaffolds a new pack with the correct directory structure."
      echo "  <pack-name>   Kebab-case name (e.g., vue, express, stack-nuxt)"
      echo "  --layer       1=domain, 2=framework (default), 3=stack"
      exit 0
      ;;
    -*) echo "Unknown option: $1"; exit 1 ;;
    *) pack_name="$1"; shift ;;
  esac
done

if [ -z "$pack_name" ]; then
  echo "Error: Pack name required."
  echo "Usage: sage-new-pack.sh <pack-name> [--layer <1|2|3>]"
  exit 1
fi

if ! echo "$layer" | grep -qP '^[123]$'; then
  echo "Error: Layer must be 1, 2, or 3."
  exit 1
fi

# ─── Resolve paths ────────────────────────────────────────────────────────

# Try to find the packs directory
PACKS_DIR=""
if [ -d "packs" ]; then
  PACKS_DIR="packs"
elif [ -d ".sage/skills" ]; then
  PACKS_DIR=".sage/skills"
else
  # Development context — relative to script
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  sage_root="$(cd "$script_dir/.." && pwd)"
  if [ -d "$sage_root/packs" ]; then
    PACKS_DIR="$sage_root/packs"
  else
    echo "Error: Cannot find packs directory."
    exit 1
  fi
fi

pack_dir="$PACKS_DIR/$pack_name"

if [ -d "$pack_dir" ]; then
  echo "Error: Pack '$pack_name' already exists at $pack_dir"
  exit 1
fi

# ─── Determine layer properties ───────────────────────────────────────────

case "$layer" in
  1) layer_name="domain"; token_budget="3500"; dep_note="none (L1 is the root)" ;;
  2) layer_name="framework"; token_budget="5000"; dep_note="must declare L1 pack dependency" ;;
  3) layer_name="stack"; token_budget="1500"; dep_note="must declare L2 pack dependencies" ;;
esac

# ─── Create directory structure ───────────────────────────────────────────

mkdir -p "$pack_dir/patterns"
mkdir -p "$pack_dir/anti-patterns"
mkdir -p "$pack_dir/constitution"
mkdir -p "$pack_dir/gates"

echo "Creating pack: $pack_name (Layer $layer — $layer_name)"

# ─── Generate SKILL.md manifest ──────────────────────────────────────────────────

cat > "$pack_dir/SKILL.md manifest" << EOF
---
name: "$pack_name"
description: "TODO: One sentence describing what agent mistakes this pack corrects"
version: "1.0.0"
license: "MIT"
layer: $layer

provides:
  skills: []
  gates: []
  constitution-additions: [$pack_name.constitution-additions.md]
  templates: []
  agents: []

requires:
  sage-core: ">=1.0.0"
  packs: []  # TODO: $dep_note

activates-in: [fix, build, architect]

activates-when:
  detected: [$pack_name]  # TODO: Package names that trigger this pack

framework-version: ">=0.0.0"  # TODO: Framework version range this targets
last-verified: "$(date +%Y-%m-%d)"
---
EOF
echo "  ✓ SKILL.md manifest"

# ─── Generate README ──────────────────────────────────────────────────────

cat > "$pack_dir/README.md" << EOF
# $pack_name

**Layer $layer — ${layer_name^} Pack**

TODO: 2-3 sentences explaining what agent mistakes this pack corrects and
why those corrections matter.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Patterns | 1 | TODO |
| Anti-patterns | 1 | TODO |
| Constitution | 1 | TODO principles |
| Gates | 0 | (optional) |

## Token Budget

Layer $layer budget: ≤$token_budget tokens total.
Current usage: TODO tokens.
EOF
echo "  ✓ README.md"

# ─── Generate pattern template ────────────────────────────────────────────

cat > "$pack_dir/patterns/${pack_name}-patterns.md" << 'EOF'
# Pattern: TODO Name

**Why agents get this wrong:** TODO — explain the specific agent tendency
this pattern corrects. What do agents default to? Why is that wrong in
this framework?

**Do this:**
```
TODO: Concrete code example of the correct approach
```

**Not this:**
```
TODO: Concrete code example of what agents produce by default
```

---

<!-- Add more patterns below. Each pattern should:
  - Start with "Why agents get this wrong"
  - Show concrete code (right and wrong)
  - Be under 400 tokens
  - Address ONE concept per pattern
  - Maximum 7 patterns per pack
-->
EOF
echo "  ✓ patterns/${pack_name}-patterns.md"

# ─── Generate anti-pattern template ──────────────────────────────────────

cat > "$pack_dir/anti-patterns/${pack_name}-anti-patterns.md" << 'EOF'
# Anti-Pattern: TODO Name

**What agents do:** TODO — describe the exact code agents produce.
You must have SEEN an agent do this. Not hypothetical.

**Why agents do this:** TODO — stale training data? Common Stack Overflow
pattern? Framework defaults that changed?

**Why it's wrong:** TODO — what breaks, what's the user impact, what's the
performance cost?

**Do instead:** TODO — the correct approach in 1-2 sentences.

---

<!-- Add more anti-patterns below. Each should:
  - Describe real observed agent behavior
  - Explain root cause
  - Be under 300 tokens
  - Maximum 7 anti-patterns per pack
-->
EOF
echo "  ✓ anti-patterns/${pack_name}-anti-patterns.md"

# ─── Generate constitution template ──────────────────────────────────────

cat > "$pack_dir/constitution/${pack_name}.constitution-additions.md" << EOF
# ${pack_name^} — Constitution Additions

## Principles

1. TODO: First non-negotiable principle using MUST/MUST NOT language.
2. TODO: Second principle.
3. TODO: Third principle.

<!-- Guidelines:
  - Use MUST/MUST NOT/SHOULD/SHOULD NOT language
  - Maximum 7 principles per pack
  - Each principle is framework-specific, not generic
  - Numbered for traceability in gate results
-->
EOF
echo "  ✓ constitution/${pack_name}.constitution-additions.md"

# ─── Generate tests.md ────────────────────────────────────────────────────

cat > "$pack_dir/tests.md" << EOF
# Pack Tests: $pack_name

**Framework version tested:** TODO
**Last tested:** $(date +%Y-%m-%d)

---

## Test 1: TODO descriptive name

**Prompt:**
\`\`\`
TODO: The exact prompt to give the agent
\`\`\`

**Without pack:** TODO — what the agent does wrong
**With pack:** TODO — what the agent should do instead
**Tests:** TODO — which pattern or anti-pattern

---

## Test 2: TODO descriptive name

**Prompt:**
\`\`\`
TODO: prompt
\`\`\`

**Without pack:** TODO
**With pack:** TODO
**Tests:** TODO

---

## Test 3: TODO descriptive name

**Prompt:**
\`\`\`
TODO: prompt
\`\`\`

**Without pack:** TODO
**With pack:** TODO
**Tests:** TODO
EOF
echo "  ✓ tests.md"

# ─── Done ─────────────────────────────────────────────────────────────────

echo ""
echo "──────────────────────────────────────"
echo "Pack scaffolded: $pack_dir/"
echo "Layer: $layer ($layer_name) — token budget: ≤$token_budget"
echo ""
echo "Next steps:"
echo "  1. Edit SKILL.md manifest — fill in description, dependencies, activation"
echo "  2. Write patterns (why agents get it wrong + code examples)"
echo "  3. Write anti-patterns (real observed agent mistakes)"
echo "  4. Write constitution principles (MUST/SHOULD language)"
echo "  5. Write test prompts in tests.md (≥3 tests)"
echo "  6. Run: bash .sage/tools/sage-check-pack.sh $pack_dir"
echo "  7. Read develop/guides/pack-authoring-guide.md for full guidance"
echo "──────────────────────────────────────"
