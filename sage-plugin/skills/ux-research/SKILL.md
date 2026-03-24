---
name: ux-research
description: >
  Researches design patterns and best practices from category leaders for a
  specific product type. Analyzes competitor homepages, landing pages, or app
  screens to identify industry conventions and opportunities for differentiation.
  Use when redesigning and the user says "research competitors", "what do others
  do", "best practices for this type of page", or during a redesign task where
  category context would improve decisions.
version: "1.0.0"
modes: [build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: auto
tags: [ux, research, benchmarking, competitors, design-patterns]
inputs: [current-design-system, product-category]
outputs: [category-benchmarks]
playbook: ux-design
requires: [ux-audit]
-->

# UX Research

Benchmark the current design against category leaders. Not to copy — to
understand what conventions users already expect, and where intentional
deviation creates differentiation.

**Core Principle:** Users don't experience your product in isolation. They
bring expectations from every other product in your category. An edtech
homepage that ignores conventions from Duolingo, Coursera, and Khan Academy
isn't being original — it's being confusing. Research identifies what's
convention (match it) vs. what's commodity (differentiate from it).

## When to Use

- After ux-audit completes (you know what you have)
- Before ux-evaluate (you need context for the gap analysis)
- When redesigning a page and category context would improve decisions

Do NOT use for:
- Internal tools with no public competitors
- Entirely novel product categories (research won't find benchmarks)

## Process

### Step 1: Identify Product Category

From the current design system and project context, determine:

```markdown
## Category Definition
Product type:    [edtech / SaaS / e-commerce / marketplace / fintech / ...]
Page type:       [homepage / landing page / dashboard / product page / ...]
Target audience: [students / professionals / developers / consumers / ...]
Market:          [geography, language — affects design conventions]
```

If unclear, ask the user: "Is this primarily a [A] or [B]? This determines
which competitors I research."

### Step 2: Identify 3-5 Category Leaders

Select reference products based on:
- **Direct competitors** — same product type, same market
- **Category leaders** — best-in-class regardless of market
- **Aspirational references** — products known for excellent UX in adjacent categories

```markdown
## Reference Products
1. [Product] — [why selected: direct competitor / category leader / aspirational]
2. [Product] — [why]
3. [Product] — [why]
```

For the Prep homepage example:
1. Duolingo — category leader in language learning UX
2. Coursera — established online education platform
3. Khan Academy — known for accessible learning design
4. EF Education — IELTS-specific competitor
5. Elsa Speak — AI-powered language learning (adjacent)

### Step 3: Analyze Category Patterns

For each reference product, capture (via web search and page analysis):

```markdown
### [Product Name]

**Hero pattern:**
[What's in the hero? Headline copy approach? CTA text? Visual treatment?
Single CTA or multiple? Video? Animation? Social proof in hero?]

**Value proposition:**
[How do they explain what they do? How many words? What framework —
problem → solution → benefit? Feature list? Outcome-focused?]

**Social proof approach:**
[Testimonials? Logos? Numbers? Scores? User photos? Video testimonials?
Placement — above fold or below? How prominent?]

**CTA strategy:**
[Primary CTA text and placement. How many CTAs on page?
Free trial? Demo? Sign up? Pricing? What's the conversion path?]

**Visual style:**
[Color approach? Illustration vs. photography? Light vs. dark?
Playful vs. professional? Information density?]

**Mobile approach:**
[What changes on mobile? What's hidden? What's prioritized?
Sticky nav? Sticky CTA?]
```

### Step 4: Identify Category Conventions

From the analysis, extract patterns that appear in 3+ reference products:

```markdown
## Category Conventions (appearing in most leaders)
1. [Convention]: [what it is, who does it]
   Example: "Hero with single clear CTA — Duolingo, Coursera, Khan Academy
   all use one primary CTA above the fold"

2. [Convention]: [what it is]
   Example: "Social proof near hero — score numbers, student count, or
   testimonials within first viewport"

3. ...
```

### Step 5: Identify Differentiation Opportunities

Patterns where reference products are similar to each other but different
from the audited product — or where the category has a gap:

```markdown
## Differentiation Opportunities
1. [Opportunity]: Most competitors [do X]. Current product [does Y differently].
   Assess: is Y intentionally different (brand identity) or accidentally missing?

2. [Opportunity]: No competitor [does Z]. Could this be a meaningful differentiator?

3. [Opportunity]: Competitors [do X poorly]. An excellent version of X would stand out.
```

### Step 6: Produce Benchmarks Document

Save to `.sage/work/<feature>/category-benchmarks.md`:

```markdown
# Category Benchmarks: [product] — [page type]

**Category:** [edtech / SaaS / ...]
**References analyzed:** [count]
**Date:** [timestamp]

## Reference Products
[from Step 2]

## Category Conventions
[from Step 4 — what most leaders do]

## Differentiation Opportunities
[from Step 5 — where to stand out]

## Detailed Analysis
[from Step 3 — per-product breakdowns]
```

Show to user: "Here's what category leaders do. This feeds into the
design evaluation — we'll compare your current design against these patterns."

## Rules

**MUST (violation = uninformed redesign):**
- MUST analyze at least 3 reference products. Fewer gives insufficient
  pattern signal.
- MUST distinguish conventions (most do this) from individual choices
  (only one does this). Conventions are what users expect.
- MUST include at least one direct competitor and one category leader.

**SHOULD (violation = shallow research):**
- SHOULD use web search to find current state of reference products —
  don't rely on training data which may show outdated designs.
- SHOULD capture the reference products' mobile approach, not just desktop.
- SHOULD note the reference products' copy approach (tone, length, language
  level) since this affects conversion as much as visual design.

**MAY (context-dependent):**
- MAY reduce to 2 references for niche categories with few competitors.
- MAY include references from adjacent categories if direct competitors
  are few (e.g., a fintech app referencing banking apps AND investment apps).
- MAY skip this skill if the user explicitly says "I don't want to look at
  competitors — I have my own vision."

## Failure Modes

- **No web search available (Tier 2 platform):** Ask the user to share 2-3
  competitor URLs directly. Analyze those instead of searching. Note the
  limitation in the report.
- **Competitor pages require login:** Analyze the public-facing pages only
  (homepage, pricing, landing pages). Note what's behind auth.
- **Very niche product with no clear competitors:** Broaden the category.
  "No direct competitor" is itself a finding — note it and research
  adjacent categories.
- **User disagrees with competitor selection:** Replace with their suggestions.
  They know their market better.
