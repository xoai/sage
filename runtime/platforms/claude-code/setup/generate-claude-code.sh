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
CONST_SECTION="## Engineering Principles

Base (all projects):
1. Tests before code — every behavior has a test before implementation
2. No silent failures — errors handled, logged, or propagated
3. Secrets never in code — use env vars or secret managers
4. Dependencies explicit — declared with pinned versions
5. Changes reversible — migrations reversible, deployments rollbackable"

PRINCIPLE_NUM=5

# Read preset if .sage/constitution.md exists
CONST_FILE="$PROJECT_SAGE/constitution.md"
if [ -f "$CONST_FILE" ]; then
  PRESET=$(sed -n '/^---$/,/^---$/{ /^extends:/s/^extends: *//p; }' "$CONST_FILE" 2>/dev/null)
  if [ -n "$PRESET" ] && [ "$PRESET" != "base" ] && [ "$PRESET" != "none" ]; then
    PRESET_FILE="$CORE/constitution/presets/${PRESET}.constitution.md"
    if [ -f "$PRESET_FILE" ]; then
      # Extract principles (lines starting with numbers after ## Additions)
      PRESET_PRINCIPLES=$(sed -n '/^## Additions/,$ { /^[0-9]/p; }' "$PRESET_FILE")
      if [ -n "$PRESET_PRINCIPLES" ]; then
        CONST_SECTION="$CONST_SECTION

${PRESET} preset:"
        while IFS= read -r line; do
          if [ -n "$line" ]; then
            PRINCIPLE_NUM=$((PRINCIPLE_NUM + 1))
            # Replace the original number with sequential numbering
            CLEAN=$(echo "$line" | sed 's/^[0-9]*\. *//')
            CONST_SECTION="$CONST_SECTION
${PRINCIPLE_NUM}. ${CLEAN}"
          fi
        done <<< "$PRESET_PRINCIPLES"
      fi
    fi
  fi

  # Extract project additions (content after frontmatter and ## Project Additions)
  PROJECT_ADDITIONS=$(sed -n '/^## Project Additions/,$ { /^## Project/d; /^$/d; /^(/d; p; }' "$CONST_FILE" 2>/dev/null)
  if [ -n "$PROJECT_ADDITIONS" ]; then
    CONST_SECTION="$CONST_SECTION

Project additions:"
    while IFS= read -r line; do
      if [ -n "$line" ]; then
        PRINCIPLE_NUM=$((PRINCIPLE_NUM + 1))
        CONST_SECTION="$CONST_SECTION
${PRINCIPLE_NUM}. ${line}"
      fi
    done <<< "$PROJECT_ADDITIONS"
  fi
fi

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
  sed -i "s|__CONSTITUTION_PLACEHOLDER__|## Engineering Principles\n\nBase (all projects):\n1. Tests before code\n2. No silent failures\n3. Secrets never in code\n4. Dependencies explicit\n5. Changes reversible|" "$SAGE_ROOT/CLAUDE.md" 2>/dev/null
}

# ── Apply command prefix to CLAUDE.md routing table ──
# Replaces all /command references except /sage (which stays unprefixed).
# Order matters: longer names first to avoid partial matches
# (e.g., /design-review before /design, /build before /b).
if [ -n "$PREFIX" ]; then
  sed -i \
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
    "$SAGE_ROOT/CLAUDE.md"
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

for wf in "$CORE"/workflows/*.workflow.md; do
  [ -f "$wf" ] || continue
  basename_wf=$(basename "$wf" .workflow.md)

  # ── Per-workflow compliance preamble ──
  # Added to the TOP of every command so the agent reads it first
  PREAMBLE=""
  case "$basename_wf" in
    build)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/developer.persona.md for your mindset.
- Announce: "Sage → build workflow." before starting work
- FLAG PARSING: Before any other work, parse $ARGUMENTS by invoking the
  deterministic parser (in order — use the first one that works):
    1. python -m core.flag_parser parse "$ARGUMENTS"
    2. bash sage/core/flag_parser/parse.sh "$ARGUMENTS"
    3. Prose-fallback per sage/core/capabilities/orchestration/flag-parser/SKILL.md
  Trust the JSON output unconditionally. If "error" is non-null, surface
  it to the user and stop. Recognized flags: --quality-locked (loop
  review/revise until clean, cap 10), --autonomous (agent makes
  elicitation decisions from memory/codebase/principles). Announce active
  modes. Persist flag state to manifest.md frontmatter under "flags:".
- MEMORY FIRST: Before writing spec, plan, or starting implementation,
  search sage-memory with the feature domain as query (limit: 5), then
  search again with filter_tags: ["self-learning"] (limit: 5). Use findings
  to avoid past mistakes. This is MANDATORY, not optional.
- Standard+ scope: spec.md MUST EXIST at .sage/work/ before implementing.
  "Design is clear" is NOT a spec. "We discussed this" is NOT a spec.
  A spec is a FILE. No file = no implementation. Write it first.
- [A] = REVIEW: When user picks [A] at spec or plan checkpoint,
  you MUST run auto-review sub-agent BEFORE proceeding to the next phase.
  [S] = Skip review (approve without review). Present [A] Review / [S] Skip
  review at every spec and plan checkpoint. If you proceed without showing
  auto-review findings after [A], you have violated the process.
  Blocked rationalizations:
  - "The spec is straightforward" — [A] means review. Period.
  - "The user wants to move fast" — they picked [A], not [S]
  - "I already reviewed while writing" — self-review is not independent
  - "Task tool might not work" — check first, skip only if truly unavailable
- GATE 3 INDEPENDENT: Code quality review (Gate 3) MUST use sub-agent when
  Task tool is available. Do NOT self-review when sub-agent is possible.
- GATE 8 AUTO-QA: Runs as part of quality gates sequence (Gate 8). Do NOT
  skip because "quality gates already passed." It runs by position in the
  gate sequence, not by your discretion.
- QUALITY-LOCKED LOOP: When --quality-locked flag is active, at every review
  checkpoint use the deterministic checker:
    python -m core.quality_locked check --review-output "<sub-agent text>"
      --iteration <N> --history-json '<JSON of past iterations>'
  Trust the returned JSON (counts, action). Do NOT decide "clean enough"
  by reading findings yourself. See sage/core/capabilities/orchestration/quality-locked/SKILL.md.
- CODING PRINCIPLES: Load sage/core/capabilities/execution/coding-principles/SKILL.md
  before every implementation task. 7 universal principles: clarity, error handling,
  boundary guards, minimal scope, safe APIs, consistency, behavior testing.
- Save ALL artifacts to .sage/work/ or .sage/docs/ — never inline-only
- Checkpoints: present with [A] Review / [S] Skip review / [R] Revise — wait for response
- Choices: present with [1] [2] [3] bracket notation
- Verify: PASTE actual test output before claiming done — no summaries
- Never use code blocks for interaction (checkpoints, options, status)
- If user corrects your approach, store as self-learning before continuing

'
      ;;
    fix)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/debugger.persona.md for your mindset.
- Announce: "Sage → fix workflow." before starting work
- MEMORY FIRST: Before investigating, search sage-memory with the bug
  domain or error message as query, filter_tags: ["self-learning"], limit: 5.
  Check for previous root causes, gotchas, and fixes in this area. MANDATORY.
- MUST complete root cause investigation before ANY fix attempt.
  Present root cause with evidence to user. Wait for [A] confirmation.
  Do NOT skip this gate for ANY reason — not for "obvious" bugs, not for
  "simple" fixes, not for Surgical scope. Every fix needs confirmed diagnosis.
- AFTER root cause confirmed: MUST scope the fix (Surgical/Moderate/Systemic)
  Even Surgical fixes: present scope to user before implementing.
  Moderate+ (3+ files): write fix plan BEFORE implementing.
  Systemic (5+ files, interface changes): ESCALATE to /build or /architect.
  "I know what to change" is NOT a plan file.
- [A] = REVIEW: When user picks [A] at root cause gate or fix plan gate,
  you MUST run auto-review sub-agent BEFORE proceeding. [S] = Skip review
  (approve without review). Present [A] Review / [S] Skip review.
  Low-quality fixes are expensive — independent review catches weak diagnoses
  and incomplete plans. If you proceed without showing findings after [A],
  you violated the process.
- Verify: PASTE actual test output before claiming done — no summaries
- Choices: present with [1] [2] [3] bracket notation
- Never use code blocks for interaction (checkpoints, options, status)
- If user corrects your approach, store as self-learning before continuing

'
      ;;
    architect)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/architect.persona.md for your mindset.
- Announce: "Sage → architect workflow." before starting work
- FLAG PARSING: Before any other work, parse $ARGUMENTS by invoking the
  deterministic parser (in order — use the first one that works):
    1. python -m core.flag_parser parse "$ARGUMENTS"
    2. bash sage/core/flag_parser/parse.sh "$ARGUMENTS"
    3. Prose-fallback per sage/core/capabilities/orchestration/flag-parser/SKILL.md
  Trust the JSON output unconditionally. If "error" is non-null, surface
  it to the user and stop. Recognized flags: --quality-locked (loop
  review/revise until clean, cap 10), --autonomous (agent makes
  elicitation decisions from memory/codebase/principles). Announce active
  modes. Persist flag state to manifest.md frontmatter under "flags:".
- MUST complete all 3 elicitation rounds SEQUENTIALLY before designing
  (unless --autonomous flag is active — see flag-parser skill).
  brief.md MUST EXIST at .sage/work/ before any design work.
  "I understand the system" is NOT a brief. Do NOT compress 3 rounds into 1.
- [A] = REVIEW: When user picks [A] at design or plan checkpoint,
  you MUST run auto-review sub-agent BEFORE proceeding. [S] = Skip review
  (approve without review). Present [A] Review / [S] Skip review at every
  checkpoint. Architecture decisions are the most expensive to reverse —
  independent review is critical. If you proceed without showing findings
  after [A], you violated the process.
- GATE 3 INDEPENDENT: Code quality review MUST use sub-agent when Task tool available.
- GATE 8 AUTO-QA: Runs per milestone as part of quality gates sequence.
- QUALITY-LOCKED LOOP: When --quality-locked flag is active, at every review
  checkpoint use the deterministic checker:
    python -m core.quality_locked check --review-output "<sub-agent text>"
      --iteration <N> --history-json '<JSON of past iterations>'
  Trust the returned JSON (counts, action). Do NOT decide "clean enough"
  by reading findings yourself.
- Save ADRs to .sage/docs/decision-*.md, spec to .sage/work/
- Each milestone in phased build follows build workflow gates independently.
  Do NOT batch-implement milestones without per-milestone checkpoints.
- Checkpoints: present with [A] Review / [S] Skip review / [R] Revise — wait for response
- Choices: present with [1] [2] [3] bracket notation
- Never use code blocks for interaction (checkpoints, options, status)
- If user corrects your approach, store as self-learning before continuing

'
      ;;
    learn)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Announce: "Sage → learn workflow." before starting work
- Present findings to user BEFORE storing in memory
- ONTOLOGY: After storing prose knowledge, create ontology entities for
  structural elements (modules, services, APIs, dependencies). This builds
  a navigable knowledge graph. Read skills/ontology/SKILL.md for encoding.
  Search ontology first to avoid duplicates.
- Checkpoint: [A] Looks correct / [R] Some findings are wrong
- Choices: present with [1] [2] [3] bracket notation
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    autoresearch)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Announce: "Sage → autoresearch workflow." before starting work
- Read skills/autoresearch/SKILL.md BEFORE starting the loop
- MEMORY FIRST: Search sage-memory for priors on this repo + metric domain
  (filter_tags: ["autoresearch"], limit: 5). Use findings as starting context.
- Elicit: goal, metric (name + direction + optional target), verify command,
  writable/frozen scope, per-run budget. Present as brief for [A]/[R] approval.
- ONE CHANGE PER ITERATION. Not two. Not "try A and also B."
- COMMIT BEFORE VERIFY. Never verify uncommitted changes.
- The agent handles REVIEW, IDEATE, MODIFY. Runtime handles COMMIT, VERIFY,
  DECIDE, LOG, REPEAT. Do NOT run verify yourself — the runtime does that.
- After each iteration: update autoresearch.md living doc with what was tried.
- If stuck (5+ consecutive discard/crash): read stuck-recovery.md before IDEATE.
- Never touch the main/master branch. All work on autoresearch/<slug>.
- Choices: present with [1] [2] [3] bracket notation
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    map)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Announce: "Sage → map workflow." before starting work
- Read skills/ontology/SKILL.md for entity encoding format BEFORE creating any entities
- Search existing ontology BEFORE creating entities — no duplicates
- Present discovered structure to user BEFORE storing — checkpoint mandatory
- MCP parameter types: tags is array (not string), limit is integer (not string)
- Choices: present with [1] [2] [3] bracket notation
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    research)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/analyst.persona.md for your mindset.
- Announce: "Sage → research workflow." before starting work
- Present scope options with chain visibility (Zone 1)
- Execute skills in sequence — checkpoint between each skill
- Present findings BEFORE storing in memory
- Findings must be specific, evidence-based, and actionable
- Save all findings to .sage/docs/ with skill-prefix naming
- Use Zone 2 for findings approval, Zone 3 for next steps
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    design)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/analyst.persona.md for your mindset.
- Announce: "Sage → design workflow." before starting work
- Load research context from .sage/docs/ if it exists
- Present scope options with chain visibility (Zone 1)
- Save all artifacts to .sage/work/ with frontmatter
- Checkpoints: Zone 2 with [A] Approve / [R] Revise
- Write handoff field on completion for the build agent
- If no research exists and scope is complex, suggest /research first
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    analyze)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/analyst.persona.md for your mindset.
- Announce: "Sage → analyze workflow." before starting work
- Present scope options with chain visibility (Zone 1)
- Classify every finding by severity: Critical / Major / Minor
- Present findings BEFORE storing — Zone 2 for approval
- Save all findings to .sage/docs/ with skill-prefix naming
- Zone 3 for next steps at completion
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    reflect)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Announce: "Sage → reflect workflow." before starting work
- Review the FULL cycle: artifacts, decisions, approaches tried
- ASK the user for real-world feedback — do not skip this step
- Every learning MUST use WHEN/CHECK/BECAUSE format
- Present learnings BEFORE storing — Zone 2 for approval
- Save reflection report to .sage/docs/reflect-*.md
- Seed the next cycle with concrete recommendations (Zone 3)
- Reflect is for looking back, NOT fixing. Suggest /fix if needed.
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    continue)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Announce: "Sage → continue." before starting work
- Scan .sage/work/*/manifest.md for in-progress/paused cycles
- Read manifest as PRIMARY context source — do not re-scan from scratch
- Follow handoff guidance from the manifest
- Do NOT re-ask questions the previous agent already resolved
- Route to the correct workflow Auto-Pickup with manifest context
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    qa)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Announce: "Sage → qa workflow." before starting work
- Check Lightpanda MCP availability FIRST — if not available, offer
  code-only fallback with setup guidance
- Do NOT fabricate browser test results if no browser is available
- Report completeness: untested routes are "not tested", NOT "pass"
- /qa REPORTS ONLY — do NOT fix bugs. Suggest /fix instead.
- Each bug gets severity AND fix classification (Surgical/Moderate/Systemic)
- Evidence is mandatory for all fail/warning findings
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    design-review)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Announce: "Sage → design-review workflow." before starting work
- Auto-detect design system (skill, DESIGN.md, CSS tokens) — invisible when none
- Layer 1 (general quality) always runs. Layer 2 (compliance) only when system detected.
- Do NOT fabricate browser findings if no Lightpanda
- Do NOT invent design system standards — if none detected, skip Layer 2
- Classify findings as /fix (mechanical) or manual (design decision)
- Do NOT auto-fix design decisions — report only
- AI slop indicators are WARNINGS, not issues. Count, do not grade.
- Never use code blocks for interaction (checkpoints, options, status)

'
      ;;
    status)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- Present with "Sage: Project status" prefix
- Show options with [C] Continue or [1] [2] [3] bracket notation
- Never use code blocks for interaction output

'
      ;;
  esac

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
