---
name: pack-discover
description: >
  Phase 1 of pack building. Identifies what pack to create, checks for
  existing packs, classifies the layer, and forks between community pack
  and project overlay paths. Triggers on: build a pack, create a pack,
  customize pack, make a skill pack.
version: "1.0.0"
modes: [build, architect]
cost-tier: sonnet
activation: auto
tags: [pack-builder, discovery, planning]
inputs: [codebase-context]
outputs: [pack-brief]
---

# Pack Discover

Determine what pack to build and which path to follow.

**Core Principle:** Every pack starts from observed agent failures, not from
documentation summaries. If you can't name a specific mistake agents make,
you don't have a pack — you have a reference doc.

## Process

### Step 1: Fork — Community Pack or Project Overlay?

Ask the user:

**"Are you building a shareable pack for a framework, or customizing an
existing pack for your project's specific conventions?"**

- **Community pack** → continue to Step 2
- **Project overlay** → skip to Step 5

### Step 2: Identify the Framework/Domain

Ask:
- What framework or domain? (e.g., React Query, Vue, Express, PostgreSQL)
- What version? (e.g., React Query v5, Vue 3 Composition API)

### Step 3: Check for Existing Packs

Look in `packs/` directory for an existing pack covering this framework.
Also check if a Layer 1 pack exists that this should build on.

- **Pack already exists** → "There's already <name>. Would you like to
  contribute improvements to it, or create a project overlay for your
  specific conventions?"
- **No pack exists** → continue to Step 4

### Step 4: Classify the Layer

Apply the three-layer test:

- **"Does this apply to any project in the domain regardless of framework?"**
  Yes → Layer 1 (domain foundation). Examples: web, mobile, api, data.
  
- **"Does this apply to projects using this specific framework?"**
  Yes → Layer 2 (framework pack). Examples: react, nextjs, vue, express.
  
- **"Does this apply only when these specific tools are used together?"**
  Yes → Layer 3 (stack composition). Examples: nextjs+prisma, flutter+firebase.

Record: framework name, version, layer, L1 dependency (if L2/L3).

### Step 5: Project Overlay Path

For project overlays, ask:
- Which existing pack to customize? (or which framework if no pack exists)
- What project-specific conventions need to be captured?
- What constraints does your team have? (forbidden patterns, required patterns,
  API conventions, naming rules, architecture decisions)

Ask the user to provide their context:
- Code convention documents
- Architecture decision records
- API contracts or documentation
- Team guidelines or style guides
- Any other project-specific rules

Record: target pack name, project context sources.

### Step 6: Identify Known Agent Failures

**This is the most important step.** Ask:

"What mistakes have you seen AI agents make with [framework]? Be specific —
describe the bad code agents produce, not general problems."

If the user isn't sure, prompt with:
- "When you ask an agent to [common task], what does it get wrong?"
- "What patterns from old versions does the agent keep using?"
- "What does the agent do that your team always has to fix?"

Record at least 3-5 specific agent failures. These become anti-patterns and
drive pattern selection.

## Output

Save to `.sage/pack-build/brief.md`:

```markdown
# Pack Brief

## Path: [community-pack / project-overlay]
## Framework: [name]
## Version: [version]
## Layer: [1/2/3]
## Dependencies: [L1 pack, etc.]

## Observed Agent Failures
1. [specific failure]
2. [specific failure]
3. [specific failure]

## Sources to Process
- [urls, docs, or "user will provide"]

## Project Context (overlay only)
- [conventions provided]
- [constraints provided]
```

## Failure Modes

- **User can't name agent failures:** The pack idea isn't ready. Suggest:
  "Try giving an agent 3-5 tasks in this framework first. Watch what it gets
  wrong. Come back with those observations."
- **Pack already exists and user wants community pack:** Redirect to contributing
  to the existing pack rather than creating a duplicate.
- **Framework is too niche:** If the framework has <1000 GitHub stars, the pack
  may not be worth community effort. Suggest a project overlay instead.
