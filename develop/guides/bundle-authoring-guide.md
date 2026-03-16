# Bundle Authoring Guide

How to build a Sage bundle that produces expert-quality output.

## Before You Start

A bundle is a discipline-specific process — UX design, product management,
security engineering, content strategy. If you're building technology-specific
guidance (Next.js patterns, Supabase rules), you want a **pack**, not a
bundle. See `develop/guides/pack-authoring-guide.md`.

**The litmus test:** If you switch your entire tech stack, does this still
apply? Yes → bundle. No → pack.

Ask yourself three questions:

1. **"Does this discipline have a structured process?"** JTBD has a process
   (define job performer → map job process → extract desired outcomes). SEO has
   a process (audit → analyze → prioritize → implement). If the discipline is
   just general advice ("be customer-focused"), it's not structured enough for
   a bundle — it belongs in a constitution preset.

2. **"Does this produce a concrete deliverable?"** A JTBD analysis produces a
   job map and outcome statements. A competitive analysis produces a structured
   document with specific sections. If the discipline doesn't produce something
   you can review for quality, it's not specific enough for a bundle.

3. **"Do LLMs get this wrong without guidance?"** Test by asking Claude to do
   the task without any special instructions. If the output is already
   expert-quality, you don't need a bundle. If it produces generic,
   surface-level output that a domain expert would reject, the bundle
   adds real value.

## Bundle Structure

```
skills/<discipline>/
├── bundle.yaml                 # Manifest — integration points, mode depth
├── README.md                     # What this bundle does, who it's for
│
├── skills/                       # Discipline-specific capabilities
│   └── <skill-name>/
│       └── SKILL.md              # Must satisfy skill.contract.md
│
├── references/                   # Curated methodology (the hard part)
│   └── *.md
│
├── constitution/                 # Discipline principles (optional)
│   └── *.constitution-additions.md
│
└── gates/                        # Discipline quality checks (optional)
    └── <NN>-<name>.gate.md       # Order 50+ (core gates are 01-49)
```

Start small. Your first bundle needs: `bundle.yaml`, `README.md`, one
skill in `skills/`, and one or two files in `references/`. Add gates,
constitution, and more skills after the first skill proves the pattern works.

## The Reference Curation Process

This is the hardest part of building a bundle and the part that creates
the most value. A good reference file transforms generic LLM output into
expert-quality work.

### What References Are

References are curated methodology summaries written in your own words. They
encode the structured frameworks, evaluation criteria, and failure modes from
authoritative sources — books, papers, practitioner blogs, official guides.

They are NOT:
- Copied chapters from books (copyright issues, too long)
- Full documentation dumps (that's MCP's job)
- General knowledge the LLM already has (waste of tokens)

They ARE:
- Structured templates the agent follows when producing deliverables
- Evaluation criteria the agent uses to verify quality
- Common failure modes the agent avoids
- Domain-specific vocabulary and framing the agent adopts

### The Curation Workflow

**Step 1: Identify your authoritative sources.**

For each skill, list 3-5 sources that a domain expert would consider canonical.
Books, seminal papers, official methodology guides, respected practitioners.

Example for JTBD:
- Tony Ulwick, "Jobs to be Done: Theory to Practice" (ODI framework)
- Clayton Christensen, "Competing Against Luck" (original theory)
- Bob Moesta, "Demand-Side Sales 101" (switch interviews)
- Jim Kalbach, "The Jobs To Be Done Bundle" (practical templates)

**Step 2: Extract structured frameworks, not prose.**

From each source, extract the specific structures that make the methodology
rigorous. These are usually:

- **Templates:** "A desired outcome statement has the structure: [direction] +
  [metric] + [object of control] + [contextual clarifier]"
- **Taxonomies:** "Job types: functional jobs, emotional jobs, social jobs,
  related jobs"
- **Evaluation criteria:** "A well-defined job performer is specific enough
  that two analysts would identify the same population"
- **Process steps:** "Step 1: Define the job performer. Step 2: Map the job
  process. Step 3: Extract desired outcomes per step."
- **Anti-patterns:** "Common mistake: defining the job too broadly (e.g.,
  'manage my life' is not a job; 'manage monthly expenses' is)"

**Step 3: Write each reference file as a self-contained guide.**

Each reference file should be readable in isolation. The agent reads it fresh
before producing work (the "read before you act" pattern). Structure:

```markdown
# [Methodology Name]

## Purpose
What this methodology produces and when to use it (2-3 sentences).

## Core Concepts
Key vocabulary and definitions the agent must use correctly (bullet list).

## Process
Step-by-step procedure with specific instructions per step.

## Templates / Structures
Exact formats for deliverables, with 2-3 examples.

## Quality Criteria
How to evaluate whether the output is expert-quality (checklist).

## Common Mistakes
What LLMs typically get wrong and why (3-5 items, with root causes).
```

**Step 4: Size each reference file appropriately.**

Target: 150-400 lines per reference file. Under 150 lines is too shallow —
the agent won't have enough structure to produce quality output. Over 400
lines means the reference is trying to cover too much — split it into
two focused references.

The skill body points to specific references using the "Read first" pattern.
The agent reads the reference fresh, applies the methodology, produces the
deliverable. The reference doesn't need to persist in conversation — it
influences the output at the moment of production.

### What to Keep vs Leave to the LLM

**Keep in references (LLM needs this):**
- Specific structural templates (outcome statement format, job map layout)
- Evaluation criteria (what makes a "good" outcome vs a "generic" one)
- Domain-specific anti-patterns (what LLMs actually get wrong)
- Process sequences that must be followed in order

**Leave to the LLM (it already knows this):**
- General definitions ("what is a user persona?")
- Broad methodology overviews ("JTBD is a framework for understanding...")
- Writing quality basics ("be clear and specific")
- Industry examples widely covered in training data

**Fetch via MCP/web at runtime (changes frequently):**
- Current market data, competitor information
- Recent case studies or research
- Industry-specific regulations or standards
- Pricing, feature sets, current product offerings

## Writing Bundle Skills

Each skill follows the standard skill contract (see
`develop/contracts/skill.contract.md`). Bundle skills have the same
structure as core capabilities: frontmatter, When to Use, Process, Rules,
Failure Modes.

The key difference: bundle skills produce **deliverable artifacts**
(documents, analyses, evaluations) rather than code artifacts.

### Skill Anatomy for Document Deliverables

```markdown
---
name: <skill-name>
description: >
  [What it produces] [When to use it] [Trigger phrases]
version: "1.0.0"
modes: [build, architect]
---

# [Skill Name]

## When to Use

[What triggers this skill — user intent, workflow phase, prerequisite artifacts]

## Process

### Step 1: [Name]
[Instructions — what to read first, what to analyze, what to produce]

### Step 2: [Name]
[Instructions...]

## Output

[Exact deliverable format — sections, structure, file path]
Save to: `.sage/work/<YYYYMMDD>-<slug>/<artifact-name>.md`

## Rules

**MUST:**
- [Non-negotiable rules for this skill]

**SHOULD:**
- [Preferred approaches]

**MAY:**
- [Context-dependent choices]

## Failure Modes

- [What goes wrong and how to handle it]
```

### Key Differences from Code Skills

1. **Process steps reference files, not code patterns.** Instead of "read
   `.sage/skills/nextjs/patterns/...`," skills say "read
   `references/outcome-statement-format.md`."

2. **Output is a document, not a commit.** Specify the exact file path, the
   sections the document must contain, and the quality criteria per section.

3. **Verification is criteria-based, not test-based.** Instead of "run tests,"
   the skill defines what "done" looks like: "every desired outcome follows
   the [direction + metric + object + context] format."

4. **The spec should declare `deliverable: document`.** This triggers [DOC]
   task generation in the plan skill, which uses criteria instead of tests
   and skips code-specific gates.

## Writing the Manifest (bundle.yaml)

```yaml
---
name: "play-product-management"
description: "Product management methodology: JTBD, opportunity mapping, PRDs"
version: "0.4.0"
type: bundle

# Phases are discipline-specific. Each bundle defines its own phases.
# PM uses Discovery/Planning/Delivery. UX might use Research/Design/Evaluate.
# Security might use Assess/Remediate/Verify. Sage core doesn't prescribe phases.
phases:
  discovery:
    description: "Understanding problems and customer needs (problem space)"
    skills: [jtbd]
  planning:
    description: "Assessing opportunities, designing research, transitioning to solutions"
    skills: [opportunity-map, user-interview]
  delivery:
    description: "Defining requirements and shipping solutions (solution space)"
    skills: [prd]

integrates-at:
  elicitation:
    skill: jtbd
    mode-depth:
      build: none
      architect: full
    runs: after
    produces: [jtbd-analysis]

  specification:
    skill: opportunity-map
    mode-depth:
      build: light
      architect: full
    runs: after
    produces: [opportunity-map]
    requires-input: [discovery-output]

provides:
  skills: [jtbd, opportunity-map, user-interview, prd]
  references:
    - jtbd-methodology.md
    - opportunity-methodology.md
    - interview-methodology.md
    - prd-methodology.md
    - requirements-writing.md

requires:
  sage-core: ">=1.0.0"
---
```

### Phases

Phases organize skills into the natural workflow of the discipline. They are
declared in the manifest and documented in the README.

**Key rules:**
- **Phases are bundle-specific.** Sage core does not define universal phases.
  Each discipline has its own natural modes of work.
- **Phases are not strict sequences.** PMs move between Discovery, Planning,
  and Delivery iteratively. The phases describe modes of work, not a waterfall.
- **Skills declare which phase they belong to.** The phase structure helps
  users understand which skill to use when.

### Skill Chains

Skills within a bundle often form chains where one skill's output is the
next skill's input:

```
jtbd (produces: outcomes) → opportunity-map (requires: discovery-output)
                            → prd (requires: opportunity-map)
```

Document these chains in the README and in each skill's prerequisites section.
The chain validates itself: weak output from an earlier skill produces weak
input for the next. This is by design — it surfaces quality issues early rather
than hiding them.

Some skills sit alongside the chain rather than in it. The user-interview
skill takes low-confidence claims from ANY phase and produces research plans.
Its position is "alongside" rather than "after" a specific skill.

### Integration Modes

Bundles integrate in two ways:

**Enriching:** The bundle adds skills alongside or after the
code workflow. Both code and discipline artifacts are produced. The UX
bundle works this way — it adds design evaluation alongside specification,
then the code workflow continues.

**Document-producing:** For pure non-code deliverables, the bundle produces
document artifacts using `deliverable: document` in the spec and [DOC] tasks
in the plan. The workflow structure (understand → define → plan → produce →
verify) stays the same — only the production phase adapts. The product
management bundle is the first working example: it produces JTBD analyses,
opportunity maps, research briefs, and PRDs — all documents, no code.

### Reference Tiers (Emerging Pattern)

As bundles multiply, some references will be useful across multiple bundles.
Three tiers are emerging:

| Tier | Scope | Example |
|------|-------|---------|
| Shared | Across bundles | Research methods, confidence tracking |
| Bundle-level | Within one bundle | JTBD methodology, PRD anatomy |
| Skill-specific | One skill only | Interview guide patterns |

For now, keep all references at the bundle level (in `references/`). When a
second bundle needs the same reference, promote it to a shared location. Don't
build shared infrastructure until evidence demands it.

### Mode Behaviors

Sage's three modes (FIX/BUILD/ARCHITECT) are universal — they work for any
discipline. But the **behavior per mode is bundle-specific.** Each bundle
must define what each mode means for each of its skills.

**The universal pattern:**

| Mode | Universal Meaning | Typical Time |
|------|-------------------|:------------:|
| FIX | Targeted correction to an existing artifact | Minutes |
| BUILD | Produce a deliverable with standard quality and depth | 10-30 min |
| ARCHITECT | Comprehensive analysis with full rigor | 30-60+ min |

**What each bundle defines:**

For each skill, document three behaviors in a "Mode Behaviors" section:

```markdown
## Mode Behaviors

**FIX (update):** [What "targeted correction" means for this skill.
Example: update specific claims with new evidence, adjust screener
criteria, revise requirements.]

**BUILD (light):** [What "standard quality" means. Which process steps
run at lighter depth, which are skipped entirely. What the deliverable
looks like at this depth.]

**ARCHITECT (full):** [What "full rigor" means. Every process step at
maximum depth. What the comprehensive deliverable includes.]
```

**Key rules for defining mode behaviors:**

1. **Every skill should have a meaningful BUILD behavior.** BUILD is the
   default mode — it's what users will use most often. If a skill only
   works in ARCHITECT mode, it's too heavy for everyday use.

2. **FIX mode applies to updating existing artifacts.** If the skill only
   produces new deliverables (can't update existing ones), FIX mode may
   not apply. Document this: "FIX mode: not applicable — this skill
   produces new deliverables only."

3. **BUILD should be "quick but not dirty."** It's not a shortcut that
   produces low-quality output. It's a focused version that covers the
   essential steps at reasonable depth. A BUILD-mode JTBD analysis should
   still follow the methodology — just at lighter depth.

4. **ARCHITECT justifies its time.** If ARCHITECT mode produces the same
   output as BUILD mode with 3x the time investment, the extra rigor isn't
   earning its keep. ARCHITECT should produce meaningfully deeper analysis,
   more evidence, more structured output.

5. **Document mode behaviors in the manifest AND the skill.** The manifest
   declares mode-depth (`fix: update`, `build: light`, `architect: full`).
   The skill body documents what each depth level means concretely.

**Mode selection and escalation:**

The user proposes the mode. The framework can suggest escalation during early
steps if scope signals indicate a mismatch:

- Skill detects multiple segments → suggest ARCHITECT
- Skill detects low evidence for a BUILD-mode analysis → suggest gathering
  more data or escalating
- User asks to FIX something that requires structural changes → suggest BUILD

The user always makes the final call. Escalation is a suggestion, not a gate.

## Building Your First Bundle

The fastest path to a working bundle:

### 1. Pick one skill

Don't build the whole discipline. Pick the skill you know best and that
produces the most concrete deliverable.

### 2. Write the reference first

Before writing the skill, write the reference file that encodes the
methodology. This forces you to think about what the LLM actually needs
versus what it already knows. The reference is the knowledge; the skill
is the process for applying it.

### 3. Write the skill

Process steps that read the reference, apply the methodology, and produce
a specific artifact. Rules that catch common LLM mistakes. Failure modes
for when the user's input doesn't fit the methodology.

### 4. Test without the bundle

Give Claude the task without your bundle. Save the output. This is your
"before" baseline.

### 5. Test with the bundle

Give Claude the same task with your skill and reference loaded. Compare the
output. Is it meaningfully better? Does it follow the methodology? Would a
domain expert approve it?

If yes — you have a working bundle skill. Add it to `bundle.yaml` with
integration points.

If no — the reference is likely missing structured templates or specific
evaluation criteria. Improve the reference, not the skill.

### 6. Expand incrementally

Add the next skill only when the first is proven. Each skill's output
should feed naturally into the next skill's input. JTBD produces outcomes
→ PRD uses those outcomes as requirements → Prioritization ranks those
requirements. The chain validates itself.

## Quality Standards

### What Expert-Quality Output Looks Like

A bundle skill's output should pass the "show it to a practitioner" test:

- **Structure:** Follows the discipline's accepted format, not a generic
  LLM bullet-point dump
- **Specificity:** Contains concrete details, not abstract generalizations.
  "Minimize the time it takes to categorize a transaction" is specific.
  "Make expense tracking better" is not.
- **Methodology:** Visibly applies the framework's specific tools
  (job maps, outcome statements, force diagrams) rather than generic analysis
- **Completeness:** Covers all steps the methodology requires, doesn't skip
  the uncomfortable parts (like identifying where the current solution is
  "good enough" and users won't switch)
- **Intellectual honesty:** Acknowledges uncertainty, identifies assumptions,
  flags areas needing validation — not confident assertions about everything

### The Reference Quality Test

A reference file is good enough when:

1. An LLM reading ONLY the reference file (not the original books) produces
   output that follows the methodology correctly
2. The output uses the correct terminology and structures
3. The output avoids the common mistakes listed in the reference
4. A domain expert reviewing the output says "this follows the framework"
   even if they'd refine specific content

### The Bundle Quality Test

A bundle is ready for use when:

1. Each skill produces a concrete, evaluable deliverable
2. The "before vs after" comparison shows meaningful improvement
3. The reference files are self-contained (agent doesn't need the original books)
4. The skill rules catch the LLM's actual failure modes, not hypothetical ones
5. The integration points are correct — the skill activates at the right
   workflow phase and in the right mode depth

## Artifact Placement and Journal Updates

When a bundle skill produces an artifact, two decisions matter: where to
save it, and how to record it.

### Where Artifacts Go

Sage uses two folders for project artifacts (see
`docs/philosophy/project-state-convention.md`):

**`.sage/docs/`** — project-level artifacts that inform decisions.
Analyses, research findings, opportunity maps, decision records. Not scoped to a single
feature. Flat structure.

**`.sage/work/<YYYYMMDD>-<slug>/`** — per-initiative deliverables. PRDs,
specs, implementation artifacts. Scoped to a specific unit of work.
Numbered subdirectories.

**Rule of thumb:** If the artifact informs WHAT to build (upstream thinking),
it goes in `docs/`. If the artifact defines HOW to build a specific
thing (downstream making), it goes in `work/`.

For PM skills: JTBD analyses, opportunity maps, research briefs and findings
→ `docs/`. PRDs and specs → `work/`.

For code skills: decision records → `docs/`. Specs, plans, implementation artifacts
→ `work/`.

### Journal Updates

Every skill that produces or updates an artifact should include a journal
update instruction in its Output section:

```markdown
## Output

Save to `.sage/docs/analysis.md` using the template.

Update `.sage/journal.md`: append a change log entry recording what was
produced, key findings, and recommended next steps. Update the "Current
Artifacts" section to list the new file as Active.
```

The agent maintains the journal as a convention — no tooling enforces it.
But skills should remind the agent to update it. This ensures the journal
stays current across sessions.

See `develop/templates/journal-template.md` for the journal structure.

## Submission Checklist

Before sharing your bundle:

- [ ] `bundle.yaml` has valid integration points with mode depth for all three modes
- [ ] At least one skill with SKILL.md satisfying the skill contract
- [ ] At least one reference file with structured methodology
- [ ] README explains the discipline, what the bundle produces, and who it's for
- [ ] Tested: "before" (without bundle) vs "after" (with bundle) comparison
- [ ] Reference files are 150-400 lines each, self-contained
- [ ] Skills use `deliverable: document` guidance for non-code output
- [ ] Skills define Mode Behaviors (FIX/BUILD/ARCHITECT) in the skill body
- [ ] Skills include journal update instructions in their Output section
- [ ] Artifact output paths use `docs/` or `work/` appropriately
- [ ] No technology-specific content (that belongs in packs)
- [ ] Common LLM failure modes documented in skill rules or reference anti-patterns
