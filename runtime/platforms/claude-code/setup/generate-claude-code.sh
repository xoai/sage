#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Claude Code Setup
# Generates CLAUDE.md + .claude/commands/ from Sage core
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
CLAUDE_DIR="$SAGE_ROOT/.claude"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"

echo ""
echo "🚀 Sage → Claude Code Setup"
echo "═══════════════════════════════"

# ── Read prefix config ──
PREFIX=""
if [ -f "$PROJECT_SAGE/config.yaml" ]; then
  if grep -q 'command_prefix: true' "$PROJECT_SAGE/config.yaml" 2>/dev/null; then
    PREFIX="sage:"
  fi
fi

# ── Validate ──
if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  echo "   Run this from the project root where sage/ is located."
  exit 1
fi

# ── Create .claude structure ──
echo ""
echo "📁 Creating .claude/ structure..."
mkdir -p "$CLAUDE_DIR/commands"

# ═══════════════════════════════════════════════════════════════
# CLAUDE.md — Generated from canonical template pattern
# Follows context-loader strategy: Layer 1 (always-on) only
# ═══════════════════════════════════════════════════════════════
echo "📝 Generating CLAUDE.md..."
# Source the shared instructions-body emitter
source "$(dirname "$0")/../../_shared/instructions-body.sh"

emit_instructions_body > "$SAGE_ROOT/CLAUDE.md"

# ── Dynamic constitution merging ──
# Shared with the generic generator — see _shared/constitution.sh for why.
source "$(dirname "$0")/../../_shared/constitution.sh"
CONST_SECTION="$(build_constitution_section "$CORE" "$PROJECT_SAGE")"

# Replace placeholder in CLAUDE.md
# Use a temp file since sed with multi-line replacement is tricky
python3 -c "
import sys
with open('$SAGE_ROOT/CLAUDE.md', 'r') as f:
    content = f.read()
replacement = '''$CONST_SECTION'''
content = content.replace('__CONSTITUTION_PLACEHOLDER__', replacement)
with open('$SAGE_ROOT/CLAUDE.md', 'w') as f:
    f.write(content)
" 2>/dev/null || {
  # Fallback: simple sed if python3 not available
  sed -i.bak "s|__CONSTITUTION_PLACEHOLDER__|## Engineering Principles\n\nBase (all projects):\n1. Tests before code\n2. No silent failures\n3. Secrets never in code\n4. Dependencies explicit\n5. Changes reversible|" "$SAGE_ROOT/CLAUDE.md" 2>/dev/null && rm -f "$SAGE_ROOT/CLAUDE.md.bak"
}

# ── Apply command prefix to CLAUDE.md routing table ──
# Replaces all /command references except /sage (which stays unprefixed).
# Order matters: longer names first to avoid partial matches
# (e.g., /design-review before /design, /build before /b).
if [ -n "$PREFIX" ]; then
  sed -i.bak \
    -e "s|/design-review|/${PREFIX}design-review|g" \
    -e "s|/autoresearch|/${PREFIX}autoresearch|g" \
    -e "s|/architect|/${PREFIX}architect|g" \
    -e "s|/research|/${PREFIX}research|g" \
    -e "s|/continue|/${PREFIX}continue|g" \
    -e "s|/reflect|/${PREFIX}reflect|g" \
    -e "s|/analyze|/${PREFIX}analyze|g" \
    -e "s|/design|/${PREFIX}design|g" \
    -e "s|/review|/${PREFIX}review|g" \
    -e "s|/status|/${PREFIX}status|g" \
    -e "s|/build|/${PREFIX}build|g" \
    -e "s|/learn|/${PREFIX}learn|g" \
    -e "s|/fix|/${PREFIX}fix|g" \
    -e "s|/map|/${PREFIX}map|g" \
    -e "s|/qa|/${PREFIX}qa|g" \
    "$SAGE_ROOT/CLAUDE.md" && rm -f "$SAGE_ROOT/CLAUDE.md.bak"
  echo "  ✓ CLAUDE.md (with ${PREFIX} prefix)"
else
  echo "  ✓ CLAUDE.md"
fi

# ═══════════════════════════════════════════════════════════════
# Commands — Adapted from core/workflows/ for Claude Code
# Path substitution: generic refs → sage/core/... paths
# Adds $ARGUMENTS for Claude Code command system
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📎 Generating .claude/commands/ from core workflows..."

# Source the shared preambles emitter
source "$(dirname "$0")/../../_shared/preambles.sh"

for wf in "$CORE"/workflows/*.workflow.md; do
  [ -f "$wf" ] || continue
  basename_wf=$(basename "$wf" .workflow.md)

  # ── Per-workflow compliance preamble (from shared script) ──
  # Use the x-trick to preserve trailing newlines that $(...) strips.
  PREAMBLE=$({ emit_preamble "$basename_wf"; printf x; })
  PREAMBLE="${PREAMBLE%x}"

  # Special case: sage command is self-contained
  if [ "$basename_wf" = "sage" ]; then
    cat > "$CLAUDE_DIR/commands/sage.md" << 'SAGEEOF'
RULES (apply to every step — non-negotiable):
- Present project state with "Sage:" prefix
- Present options with [1] [2] [3] bracket notation — ALWAYS
- Recommend a specific workflow for Standard+ tasks
- NEVER just ask "What would you like to do?" — present structured choices
- Never use code blocks for interaction output

Sage's intelligent entry point. Assess the project and guide the user.

## Step 1: Read State

Scan `.sage/work/` for active initiatives (read frontmatter: title,
status, phase). Scan `.sage/docs/` for project-level artifacts.
Read `.sage/decisions.md` for recent context.

## Step 2: Present Status and Options

Present what you found, then structured options based on context.

**If work is in progress:**

**Sage:** [Project name] — [feature] is in progress, [phase] phase.

[1] Continue [feature] — resume from [next step]
[2] Start something new
[3] Review what's been done

**If no work in progress but artifacts exist:**

**Sage:** [Project name] — no active work. Previous: [list initiatives].

[1] Start a new task — describe what you want to build
[2] Review existing artifacts
[3] Learn the codebase

**If fresh project:**

**Sage:** Fresh project, no work in progress.

[1] Build something — describe what you want to create
[2] Learn the codebase first
[3] Something else — describe what you need

## Step 3: Route to Workflow

Based on user's choice or free-form input, classify scope and route:
- Lightweight → just do it
- Standard → announce build/fix workflow, start first step
- Comprehensive → present architect workflow card

For complex routing or gap detection, read the sage-navigator at
`sage/core/capabilities/orchestration/sage-navigator/SKILL.md`.

$ARGUMENTS
SAGEEOF
    echo "  ✓ sage.md → /sage (self-contained)"
    continue
  fi

  # Special case: review command uses Task-based sub-agent delegation
  if [ "$basename_wf" = "review" ]; then
    cat > "$CLAUDE_DIR/commands/${PREFIX}review.md" << 'REVIEWEOF'
RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/reviewer.persona.md for your mindset.
- Announce: "Sage → review workflow." before starting work
- Present artifact list with [1] [2] [3] bracket notation
- Present findings with [A] Accept / [R] Revise / [D] Discuss
- Load producing skill's quality criteria — mandatory, not optional
- DELEGATION: If Task tool is available, you MUST use it for review.
  Self-review is NOT independent review. Do NOT review your own work
  and present it as an independent evaluation.
- Never use code blocks for interaction output

Review an artifact with independent evaluation via sub-agent delegation.

## Step 1: Identify What to Review

If not specified, scan `.sage/work/` and `.sage/docs/` for recent
artifacts. Present them:

**Sage:** Available for review:

[1] .sage/work/20260316-checkout/brief.md (updated today)
[2] .sage/work/20260316-checkout/spec.md (updated today)
[3] .sage/docs/ux-audit-homepage.md (updated yesterday)

Which artifact should I review?

If the user specifies an artifact, proceed directly.

## Step 2: Prepare Review Context

Before delegating, gather three pieces of information:

1. **Artifact path** — the file to review
2. **Producing skill path** — find which skill or workflow created it.
   Check filename prefix, content references, or `.sage/decisions.md`.
   The quality criteria are in that skill's `## Quality Criteria` section
   (look in `sage/skills/[skill]/SKILL.md` or `sage/core/workflows/[workflow].workflow.md`)
3. **Memory query** — 3-5 keywords describing the artifact's domain
   (e.g., "billing checkout payment saga")

## Step 3: Delegate to Review Sub-Agent

**Delegation is MANDATORY when Task tool is available.**
Do NOT skip delegation because:
- "I can review this myself" → self-review is not independent review
- "The artifact is simple" → simple artifacts still benefit from fresh eyes
- "It will be faster" → speed is not the goal, independence is

If Task tool is NOT available (e.g., Antigravity platform), proceed with
self-review but announce it: "Sage: Task tool not available. Performing
self-review — note this is not independent evaluation. Consider a
fresh-session /review for critical artifacts."

Tell the user: "Sage: Delegating to a review sub-agent for independent
evaluation. The reviewer gets a fresh context window without my
reasoning from this session."

Use the Task tool to spawn a sub-agent with this prompt:

```
You are independently reviewing a Sage project artifact. You were
NOT involved in producing this work — evaluate it with fresh eyes.

CONTEXT PACKAGE:
1. PERSONA: Read sage/core/agents/reviewer.persona.md for mindset.
2. ARTIFACT: Read the artifact at: [ARTIFACT PATH]
3. CRITERIA: Read quality criteria from: [SKILL/WORKFLOW PATH],
   section titled "## Quality Criteria"
4. DECISIONS: Read .sage/decisions.md for last 5 entries.
5. LEARNINGS: Search sage-memory with the artifact domain as query, limit 5.
   If this tool is not available, check .sage-memory/ folder.

EVALUATE the artifact against EACH quality criterion specifically.

CLASSIFY each finding by severity:
- CRITICAL: Blocks proceeding. Must fix before next step.
- MAJOR: Significant gap. Should fix before next step.
- MINOR: Improvement opportunity. Can fix later.

PRESENT YOUR REVIEW AS:

## Review: [artifact name]

### Critical Issues
[If none, say "None found." Do not omit this section.]

### Major Issues
[If none, say "None found." Do not omit this section.]

### Minor Issues / Improvements
[Specific observations with suggested actions]

### Strengths
[Specific observations — not generic praise]

### Verdict
PASS — ready to proceed [minor notes if any]
NEEDS REVISION — [specific items to address, with severity]
FAIL — [significant gaps, recommend returning to earlier step]
```

## Step 4: Present Findings

Share the sub-agent's review with the user.

**Critical findings block approval.** If the review contains CRITICAL
issues, do NOT present [A] Accept as the first option:

Sage: Review found critical issues that must be addressed:
[critical findings summary]

[R] Address critical issues first
[D] Discuss — let's talk about specific findings
[A] Accept anyway — I understand the risks

If no critical issues:

Sage: Review complete. [verdict summary]

[A] Accept findings — proceed with suggested next step
[R] Revise — I'll address the issues found
[D] Discuss — let's talk about specific findings

Prepend review findings to `.sage/decisions.md`.

$ARGUMENTS
REVIEWEOF
    echo "  ✓ ${PREFIX}review.md → /${PREFIX}review (Task-delegated)"
    continue
  fi

  # /sage stays unprefixed; everything else gets PREFIX
  cmd_name="${basename_wf}"
  [ "$basename_wf" != "sage" ] && cmd_name="${PREFIX}${basename_wf}"

  # Standard: add preamble + strip frontmatter + substitute refs + add $ARGUMENTS
  {
    printf "%s" "$PREAMBLE"
    sed '/^---$/,/^---$/d' "$wf" \
      | sed 's|\*\*sage-navigator\*\* skill|**sage-navigator** skill at `sage/core/capabilities/orchestration/sage-navigator/SKILL.md`|g' \
      | sed "s|sage-navigator's intelligence layer|sage-navigator's intelligence layer (\`sage/core/capabilities/orchestration/sage-navigator/SKILL.md\`, section 2)|g" \
      | sed 's|If relevant Sage skills exist, read and follow them.|If relevant Sage skills exist in `sage/skills/`, read and follow them.|g' \
      | sed '/^$/N;/^\n$/d'
    echo ""
    echo '$ARGUMENTS'
  } > "$CLAUDE_DIR/commands/${cmd_name}.md"

  echo "  ✓ ${cmd_name}.md → /${cmd_name}"
done

# ═══════════════════════════════════════════════════════════════
# Project state — .sage/ initialization
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📊 Checking project state..."
if [ -d "$PROJECT_SAGE" ]; then
  echo "  ✓ .sage/ already exists"
else
  mkdir -p "$PROJECT_SAGE/work" "$PROJECT_SAGE/docs"

  cat > "$PROJECT_SAGE/decisions.md" << 'DECEOF'
# Decisions

Shared log for significant decisions and context.
Both the AI agent and human collaborators write here.

- [init] Sage initialized
DECEOF

  cat > "$PROJECT_SAGE/conventions.md" << 'CONVEOF'
# Project Conventions

Discovered by Sage on first run.
The codebase-scan capability will enrich this automatically.
CONVEOF

  echo "  ✓ .sage/ initialized"
fi

# ═══════════════════════════════════════════════════════════════
# Gate scripts and config — deterministic verification
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🔒 Deploying gate scripts..."

mkdir -p "$PROJECT_SAGE/gates/scripts"
GATE_SCRIPTS="$CORE/gates/scripts"

if [ -d "$GATE_SCRIPTS" ]; then
  for script in "$GATE_SCRIPTS"/*.sh; do
    [ -f "$script" ] || continue
    cp "$script" "$PROJECT_SAGE/gates/scripts/"
    chmod +x "$PROJECT_SAGE/gates/scripts/$(basename "$script")"
    echo "  ✓ $(basename "$script")"
  done
else
  echo "  ⚠ Gate scripts not found at $GATE_SCRIPTS"
fi

# Deploy gate activation config
GATE_CONFIG="$CORE/gates/_config/gate-modes.yaml"
if [ -f "$GATE_CONFIG" ]; then
  cp "$GATE_CONFIG" "$PROJECT_SAGE/gates/gate-modes.yaml"
  echo "  ✓ gate-modes.yaml"
fi

# ═══════════════════════════════════════════════════════════════
# Skill deployment — register skills as platform slash commands
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🧠 Deploying skills to .claude/skills/..."

SKILL_COUNT=0
for skill_dir in "$SAGE_DIR/skills"/*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "$skill_dir")
  [ -f "$skill_dir/SKILL.md" ] || continue

  # Read description from frontmatter
  desc=$(sed -n '/^---$/,/^---$/{ /^description:/s/^description: *//p; }' "$skill_dir/SKILL.md" 2>/dev/null)
  [ -z "$desc" ] && desc="Sage skill: $skill_name"
  # Truncate long descriptions for frontmatter
  desc=$(echo "$desc" | head -1 | cut -c1-120)

  # Create loader SKILL.md (prefix skill directory name if configured)
  target_dir="$CLAUDE_DIR/skills/${PREFIX}${skill_name}"
  mkdir -p "$target_dir"
  cat > "$target_dir/SKILL.md" << LOADEREOF
---
name: ${PREFIX}${skill_name}
description: $desc
---
Read and follow the full skill at sage/skills/$skill_name/SKILL.md
LOADEREOF

  SKILL_COUNT=$((SKILL_COUNT + 1))
done

echo "  ✓ $SKILL_COUNT skills deployed to .claude/skills/"

# ── System skills (ADR-9 delivery class 2) ──
#
# Sage-about-Sage content that used to live in the eager layer and be paid for
# on every turn. It is delivered here instead, where the platform's native
# description-triggered discovery fetches it only when it is relevant.
# (Confirmed on Claude Code 2.1.207 — docs/attestations/.)
#
# Two deliberate differences from the loop above:
#
#   Copied WHOLE, not stubbed. A loader stub costs an extra Read hop, and these
#   are small. More importantly, the stub loop truncates the description to 120
#   characters — which for a system skill would amputate the trigger. The
#   description IS the product here: it is the only thing standing between the
#   model and content it no longer has in front of it.
#
#   Never prefixed. The `sage:` command prefix disambiguates Sage's commands
#   from a project's own; these are already namespaced `sage-*`. Prefixing would
#   make the directory (`sage:sage-routing`) disagree with the frontmatter
#   `name:` (`sage-routing`), and it is not worth finding out which one wins.
SYS_SKILL_COUNT=0
if [ -d "$CORE/system-skills" ]; then
  for sys_dir in "$CORE/system-skills"/*/; do
    [ -d "$sys_dir" ] || continue
    sys_name=$(basename "$sys_dir")
    [ -f "$sys_dir/SKILL.md" ] || continue

    mkdir -p "$CLAUDE_DIR/skills/$sys_name"
    cp "$sys_dir/SKILL.md" "$CLAUDE_DIR/skills/$sys_name/SKILL.md"
    SYS_SKILL_COUNT=$((SYS_SKILL_COUNT + 1))
  done
fi

echo "  ✓ $SYS_SKILL_COUNT system skills deployed (on-demand, not every-turn)"

# ═══════════════════════════════════════════════════════════════
# Session hook — auto-inject Sage context on session start
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🔗 Setting up session hook..."

mkdir -p "$CLAUDE_DIR/hooks"
HOOK_SRC="$CORE/../runtime/platforms/claude-code/hooks/sage-session-init.sh"

if [ -f "$HOOK_SRC" ]; then
  cp "$HOOK_SRC" "$CLAUDE_DIR/hooks/sage-session-init.sh"
  chmod +x "$CLAUDE_DIR/hooks/sage-session-init.sh"
  echo "  ✓ sage-session-init.sh"
fi

# Create or update settings.local.json with hook config (atomic write)
SETTINGS_LOCAL="$CLAUDE_DIR/settings.local.json"
mkdir -p "$CLAUDE_DIR"
TEMP_SETTINGS=$(mktemp "${SETTINGS_LOCAL}.XXXXXX" 2>/dev/null || echo "${SETTINGS_LOCAL}.tmp")
cat > "$TEMP_SETTINGS" << 'HOOKEOF'
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/sage-session-init.sh"
          }
        ]
      }
    ]
  }
}
HOOKEOF

if mv "$TEMP_SETTINGS" "$SETTINGS_LOCAL" 2>/dev/null; then
  echo "  ✓ settings.local.json (session hook)"
else
  echo "  ✗ Could not write settings.local.json: check permissions"
  echo "    The session hook won't activate until this is fixed."
  echo "    Try: sage update (to retry)"
  rm -f "$TEMP_SETTINGS" 2>/dev/null
fi

# ── Enforcement hooks (mechanical Rules 3 / 5 / R29) ──
# Registered in settings.json (committed, shared) — unlike the informational
# session hook, enforcement is a project policy and should travel with the repo.
# Whether the spec-gate actually blocks is gated by hard_enforcement in
# .sage/config.yaml; the degradation log always runs (it records, never blocks).
#
#   sage-spec-gate.sh       PreToolUse  — blocks pre-spec edits, blocks a
#                                         completion that is silent about QA
#   sage-degradation-log.sh PostToolUse — writes the R29 audit line to
#                                         decisions.md itself, so the model
#                                         cannot forget to
#   sage-manifest-sync.sh   PostToolUse — advances the manifest's gate_state when
#                                         source is written, so a resumed session
#                                         cannot read "no tasks started" off a
#                                         cycle whose work is already in the tree
SPEC_GATE_SRC="$CORE/../runtime/platforms/claude-code/hooks/sage-spec-gate.sh"
DEG_LOG_SRC="$CORE/../runtime/platforms/claude-code/hooks/sage-degradation-log.sh"
TDD_GATE_SRC="$CORE/../runtime/platforms/claude-code/hooks/sage-tdd-gate.sh"
MANIFEST_SYNC_SRC="$CORE/../runtime/platforms/claude-code/hooks/sage-manifest-sync.sh"
if [ -f "$SPEC_GATE_SRC" ]; then
  cp "$SPEC_GATE_SRC" "$CLAUDE_DIR/hooks/sage-spec-gate.sh"
  chmod +x "$CLAUDE_DIR/hooks/sage-spec-gate.sh"
  if [ -f "$DEG_LOG_SRC" ]; then
    cp "$DEG_LOG_SRC" "$CLAUDE_DIR/hooks/sage-degradation-log.sh"
    chmod +x "$CLAUDE_DIR/hooks/sage-degradation-log.sh"
  fi
  if [ -f "$TDD_GATE_SRC" ]; then
    cp "$TDD_GATE_SRC" "$CLAUDE_DIR/hooks/sage-tdd-gate.sh"
    chmod +x "$CLAUDE_DIR/hooks/sage-tdd-gate.sh"
  fi
  if [ -f "$MANIFEST_SYNC_SRC" ]; then
    cp "$MANIFEST_SYNC_SRC" "$CLAUDE_DIR/hooks/sage-manifest-sync.sh"
    chmod +x "$CLAUDE_DIR/hooks/sage-manifest-sync.sh"
  fi

  # Merge the hook into settings.json rather than overwriting, so the user's
  # own settings survive; idempotent so re-running never duplicates the entry.
  SETTINGS_JSON="$CLAUDE_DIR/settings.json"
  MERGE_PY=$(mktemp "${TMPDIR:-/tmp}/sage-hookmerge-XXXXXX" 2>/dev/null || echo "")
  if [ -n "$MERGE_PY" ] && command -v python3 >/dev/null 2>&1; then
    cat > "$MERGE_PY" <<'PYEOF'
import json
import sys

path = sys.argv[1]

# (settings event, matcher, script) — each merged idempotently so re-running the
# generator never duplicates an entry and never clobbers the user's own hooks.
WANTED = [
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-spec-gate.sh"),
    ("PreToolUse", "Edit|Write|MultiEdit", "sage-tdd-gate.sh"),
    ("PostToolUse", "Write|Edit", "sage-degradation-log.sh"),
    ("PostToolUse", "Write|Edit", "sage-manifest-sync.sh"),
]

try:
    with open(path) as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        data = {}
except (OSError, ValueError):
    data = {}

hooks = data.setdefault("hooks", {})

for event, matcher, script in WANTED:
    entries = hooks.get(event)
    if not isinstance(entries, list):
        entries = []

    def is_ours(entry, _script=script):
        for h in (entry or {}).get("hooks", []):
            if _script in (h.get("command") or ""):
                return True
        return False

    entries = [e for e in entries if not is_ours(e)]
    entries.append({
        "matcher": matcher,
        "hooks": [{
            "type": "command",
            "command": 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/%s"' % script,
        }],
    })
    hooks[event] = entries

with open(path, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PYEOF
    if python3 "$MERGE_PY" "$SETTINGS_JSON" 2>/dev/null; then
      echo "  ✓ settings.json (spec-gate + tdd-gate + degradation-log hooks)"
    else
      echo "  ✗ Could not register enforcement hooks in settings.json"
    fi
    rm -f "$MERGE_PY"
  fi
fi

# IDE restart warning (only during update, not init)
if [ "${SAGE_UPDATE_MODE:-}" = "true" ]; then
  echo ""
  echo -e "  \033[33m⚠ Restart your IDE to pick up updated hook configuration.\033[0m"
fi

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════"
echo "✅ Sage → Claude Code setup complete"
echo ""
CMD_COUNT=$(find "$CLAUDE_DIR/commands" -name "*.md" 2>/dev/null | wc -l)
echo "  CLAUDE.md            → always-on project instructions"
echo "  .claude/commands/    → $CMD_COUNT slash commands"
echo "  .claude/hooks/       → session init hook"
echo "  .sage/               → project state directory"
echo ""
echo "Next steps:"
echo "  1. Open this project in Claude Code"
echo "  2. Type /sage and describe what you want to build"
echo "  3. Type /status to check project state"
echo ""
