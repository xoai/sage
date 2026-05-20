#!/usr/bin/env bash
# Shared workflow preambles for Sage platforms.
#
# Emits a per-workflow preamble (compliance rules prepended to the
# generated command file) for any given workflow name.
#
# Usage:
#   source runtime/platforms/_shared/preambles.sh
#   PREAMBLE=$(emit_preamble "build")
#
# Returns: the preamble text via stdout (or empty string if no preamble
# exists for that workflow).

emit_preamble() {
  local workflow_name="$1"
  local PREAMBLE=""
  case "$workflow_name" in
    build)
      PREAMBLE='RULES (apply to every step — non-negotiable):
- PERSONA: Read sage/core/agents/developer.persona.md for your mindset.
- Announce: "Sage → build workflow." before starting work
- FLAG PARSING: Before any other work, parse $ARGUMENTS by invoking the
  deterministic parser (in order — use the first one that works):
    1. python -m core.flag_parser parse "$ARGUMENTS" --config-path .sage/config.yaml
    2. bash sage/core/flag_parser/parse.sh "$ARGUMENTS" --config-path .sage/config.yaml
    3. Prose-fallback per sage/core/capabilities/orchestration/flag-parser/SKILL.md
  Trust the JSON output unconditionally. If "error" is non-null, surface
  it to the user and stop. Recognized flags:
    --quality-locked     loop review/revise until clean (cap 10)
    --no-quality-locked  override config default to off for this run
    --autonomous         agent makes elicitation decisions
    --no-autonomous      override config default to off for this run
  When announcing active modes, use the quality_locked_source and
  autonomous_source fields from the JSON to label sources, e.g.
  "Modes: --quality-locked (from .sage/config.yaml), --autonomous (from flag)".
  Persist flag state to manifest.md frontmatter under "flags:".
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
      --iteration <N> --history-json "<JSON of past iterations>"
  Trust the returned JSON (counts, action). Do NOT decide "clean enough"
  by reading findings yourself. See sage/core/capabilities/orchestration/quality-locked/SKILL.md.
- AUTO-PICK [A] WHEN BOTH FLAGS ACTIVE: If both --autonomous AND --quality-locked
  are set, do NOT prompt the user at normal approval checkpoints (spec, plan,
  ADR, root cause, fix plan). Auto-pick [A] Review (the only option consistent
  with both flags). Print the auto-pick notice, log to manifest.md
  auto_picked_checkpoints AND decisions.md BEFORE running the review, then
  proceed. Exception checkpoints (quality-locked cap-reached, stuck-escalation,
  autonomous unconfident-questions, sub-agent unavailable) still require user
  input. See sage/core/capabilities/orchestration/autonomous/SKILL.md
  "Auto-Pick at Checkpoints" for full rules.
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
    1. python -m core.flag_parser parse "$ARGUMENTS" --config-path .sage/config.yaml
    2. bash sage/core/flag_parser/parse.sh "$ARGUMENTS" --config-path .sage/config.yaml
    3. Prose-fallback per sage/core/capabilities/orchestration/flag-parser/SKILL.md
  Trust the JSON output unconditionally. If "error" is non-null, surface
  it to the user and stop. Recognized flags:
    --quality-locked     loop review/revise until clean (cap 10)
    --no-quality-locked  override config default to off for this run
    --autonomous         agent makes elicitation decisions
    --no-autonomous      override config default to off for this run
  When announcing active modes, use the quality_locked_source and
  autonomous_source fields from the JSON to label sources, e.g.
  "Modes: --quality-locked (from .sage/config.yaml), --autonomous (from flag)".
  Persist flag state to manifest.md frontmatter under "flags:".
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
      --iteration <N> --history-json "<JSON of past iterations>"
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
  a navigable knowledge graph. Read skills/sage-ontology/SKILL.md for encoding.
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
- Read skills/sage-ontology/SKILL.md for entity encoding format BEFORE creating any entities
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

  # Output the preamble (may be empty)
  printf "%s" "$PREAMBLE"
}
