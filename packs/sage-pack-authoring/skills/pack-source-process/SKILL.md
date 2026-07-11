---
name: pack-source-process
description: >
  Phase 2 of pack building. Gathers sources (docs, blogs, issues, user context)
  and filters them through the judgment-not-knowledge lens. Extracts only
  information that corrects agent mistakes — discards documentation summaries.
version: "1.0.0"
modes: [build, architect]
cost-tier: sonnet
activation: auto
tags: [pack-builder, sources, research]
inputs: [pack-brief]
outputs: [processed-sources]
---

# Pack Source Process

Gather sources and extract agent-failure-relevant insights.

**Core Principle:** Not all sources are equal. Official docs explain HOW things
work — agents already know that from training. Blog posts about mistakes,
migration guides, GitHub issues, and changelog breaking changes reveal WHAT
GOES WRONG — that's what packs need.

## Process

### Step 1: Source Prioritization

For **community packs**, prioritize sources in this order:

1. **Migration guides** (highest value) — they document what changed between
   versions and what old patterns are now wrong. This is exactly what agents
   get wrong: using outdated patterns from training data.

2. **GitHub issues tagged "common mistake" or "FAQ"** — real users hitting
   real problems means agents will hit them too.

3. **Framework changelog / breaking changes** — what APIs were removed or
   renamed. Agents still use removed APIs.

4. **Blog posts about pitfalls and best practices** — especially posts titled
   "X mistakes with [framework]" or "Stop doing X in [framework]."

5. **Official docs** (lowest priority for packs) — use ONLY to verify that
   the corrections are accurate. Don't extract patterns from docs — they're
   documentation, not judgment.

For **project overlays**, the sources are the user's own materials:
- Code convention documents
- Architecture decision records
- API contracts
- Team guidelines
- Existing code examples showing established patterns

### Step 2: Source Processing

For each source, ask ONE question:

**"Does this tell me something agents get WRONG, or does it explain how
something WORKS?"**

- **Tells me what's wrong** → extract it as a candidate pattern or anti-pattern
- **Explains how it works** → skip it (the LLM already knows this)

Extract into a structured format:

```markdown
## Source: [title/url]
## Relevance: [high/medium/low]

### Insight 1
Agent mistake: [what agents do wrong]
Correction: [what to do instead]
Evidence: [how we know agents do this — migration guide, common issue, etc.]

### Insight 2
...
```

### Step 3: Deduplicate and Rank

After processing all sources:
1. Merge overlapping insights (different sources describing the same mistake)
2. Rank by frequency — if 3 sources mention the same mistake, it's high-priority
3. Rank by severity — a mistake that causes crashes outranks a style issue
4. Select top 5-7 insights for patterns and top 5-7 for anti-patterns

**Token awareness:** The pack has a budget (L1: 3500, L2: 5000, L3: 1500).
Each pattern costs ~80-120 tokens, each anti-pattern ~60-90. Budget for 7-9
patterns + 5-7 anti-patterns + constitution. Don't extract 20 insights — pick
the best 7-9.

### Step 4: Project Overlay Processing (Overlay Path Only)

For project overlays, the processing is different:

1. Read the user's project context documents
2. Identify rules that DIFFER from or EXTEND the community pack's guidance
3. Focus on: naming conventions, forbidden patterns, required patterns,
   API-specific formats, team-specific workflows
4. Discard anything that matches the community pack (no duplication)

The overlay should be ONLY the delta — what's specific to this project.

## Output

Save to `.sage/pack-build/sources.md`:

```markdown
# Processed Sources

## Top Agent Failures (ranked)
1. [failure] — Severity: [high/med] — Sources: [N] mentions
2. [failure] — ...

## Candidate Patterns
- [pattern idea from source processing]
- ...

## Candidate Anti-Patterns
- [anti-pattern idea from observation]
- ...

## Project-Specific Rules (overlay only)
- [convention or constraint]
- ...
```

## Failure Modes

- **All sources are documentation:** The user provided official docs but no
  failure-focused content. Ask: "Do you have migration guides, blog posts
  about common mistakes, or GitHub issues? Those are more valuable for packs."
- **Too many insights:** Prioritize by frequency and severity. A pack with
  7 sharp insights beats one with 20 diluted ones.
- **Overlay has no delta:** The project follows the community pack exactly.
  No overlay needed — just use the community pack as-is.
