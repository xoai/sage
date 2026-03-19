# Skill Philosophy

How to think about building, maintaining, and using Sage skills.

---

## The Core Principle: Judgment, Not Knowledge

This principle applies equally to knowledge skills and bundles.
Both encode judgment — they differ in WHAT KIND of judgment and HOW they deliver it:

- **Knowledge skills:** Judgment about specific technologies. "In Next.js 15, prefer
  server components. Don't use useEffect for data fetching." Delivered as patterns
  and anti-patterns that add to the workflow.
- **Bundles and process skills:** Judgment about discipline processes. "Start with the user's
  emotional state. Map the full journey before specifying." Delivered as structured
  processes with their own skills that weave into workflow phases.

Both are distinct from raw knowledge (API reference, syntax docs) which is better
served by MCP connections to official documentation.

For the full playbook design philosophy, see `skills/README.md` and
`develop/contracts/playbook.contract.md`.

---

A skill that says "use semantic HTML" is worthless. The LLM already knows that.
A skill that says "in Next.js 15 App Router, don't add `use client` unless you
need interactivity — 90% of components should be server components, and here are the
3 situations where client components are the right call" — that's valuable.

The difference is **judgment**. Official docs tell you what an API does. Extensions
tell you when to use it, when to avoid it, and what the docs don't warn you about.

### What Extensions Should Contain

- **Patterns** (7-10 per framework): The daily-use approaches. How to fetch data,
  manage state, handle routing, structure components, handle errors — the opinionated
  "right way" for this specific framework that goes beyond what generic knowledge covers.

- **Anti-patterns** (5-7 per framework): Mistakes agents make because their training
  data contains outdated patterns. "Don't use getServerSideProps (Pages Router pattern)."
  "Don't use class components (pre-hooks pattern)." "Don't wrap every component in
  use client." These are corrections for stale knowledge.

- **Integration patterns** (2-3 per common companion): How this framework connects
  to its most common partners. Not API docs — integration judgment. Where to put
  the Prisma client. How auth middleware integrates with the router. What breaks
  when you combine these specific tools.

- **Constitution additions** (1 file): Framework-mandated principles. "All images use
  next/image. All links use next/link." These are non-negotiable rules, not suggestions.

- **Framework-specific gates** (0-1): Quality checks the framework demands. Lighthouse
  performance budgets for web. Platform compliance for mobile.

### What Extensions Should NOT Contain

- **Language basics.** Don't teach TypeScript in a React extension. The LLM knows TypeScript.

- **API reference.** Don't document every method of every library. That's the library's
  job. In future versions, MCP connections will provide live API reference from official
  sources. For now, the agent uses its training data plus web search.

- **Tutorials.** Extensions aren't learning materials. They're behavioral guides for
  agents that already understand the fundamentals but need correction on the specifics.

- **Configuration boilerplate.** Don't include tsconfig.json templates or webskill configs.
  Those belong in project scaffolding tools, not in an agent behavioral framework.

---

## Three-Layer Architecture

### Layer 1: Domain Foundations

`web` and `mobile` contain principles that are universal within their
domain and change slowly:

- **Web:** Accessibility (WCAG 2.2 AA), performance budgets (LCP < 2.5s), security
  headers, SEO fundamentals, responsive design principles, semantic HTML, progressive
  enhancement.

- **Mobile:** Offline-first architecture, 60fps rendering discipline, platform
  navigation patterns (back button, swipe gestures), touch target sizes, battery
  and network awareness, platform-specific accessibility.

These load whenever the domain matches. They don't reference specific frameworks.

### Layer 2: Framework Skills

`react`, `nextjs`, `vue`, `flutter`, etc. contain
framework-specific judgment:

- Patterns specific to this framework's mental model
- Anti-patterns from stale training data
- Common mistakes that look right but cause problems
- Framework-specific quality checks

Layer 2 packs can be installed standalone. A developer using React without Next.js
installs `web` + `react` and gets React-specific guidance without
Next.js opinions.

When multiple Layer 2 packs overlap, the more specific skill overrides. `nextjs`
overrides `react`'s data-fetching patterns because Next.js does data fetching
differently (server components vs hooks). The override is explicit in the skill
manifest.

### Layer 3: Stack Compositions

`stack-nextjs-fullstack`, `stack-react-native-expo`, etc. contain
integration judgment for specific framework combinations:

- How the frameworks connect at the seams
- Common pitfalls when combining these specific tools
- Recommended project structure for this combination
- Combined constitution additions

Stack compositions require their component Layer 2 packs. They add the integration
knowledge that no individual framework's docs cover.

Stack compositions are curated — they represent tested, opinionated combinations.
Not every possible permutation gets a stack pack. The high-value combinations that
many developers use are curated by the community.

---

## How Extensions Activate

Extensions don't require manual configuration for every project. The `codebase-scan`
skill detects the tech stack automatically:

```
codebase-scan reads package.json → detects next 15.x, react 19, tailwindcss 4
  → context loader checks installed extensions
  → loads: web (domain match)
  → loads: react (detected framework)
  → loads: nextjs (detected framework, overrides some React patterns)
  → loads: stack-nextjs-fullstack (if installed, all components detected)
```

Extensions that aren't installed are not loaded. Extensions that are installed but
don't match the detected stack are not loaded. This keeps the context budget focused
on relevant knowledge.

---

## Extension Size and Context Budget

Each extension should be small enough that loading it doesn't crowd out working
space in the context window:

| Component | Files | Lines Each | Total per Skill |
|-----------|-------|-----------|----------------|
| Patterns | 7-10 | 50-100 | 350-1,000 |
| Anti-patterns | 5-7 | 30-50 | 150-350 |
| Integration | 2-3 | 40-80 | 80-240 |
| Constitution | 1 | 20-40 | 20-40 |
| Gate | 0-1 | 40-60 | 0-60 |
| **Total** | **15-22** | | **600-1,690 lines** |

Reference files are loaded on demand, not all at once. The context loader picks
the references relevant to the current task. If the agent is working on data
fetching, only the data-fetching pattern loads — not the routing or state
management patterns.

---

## MCP Integration (Future)

In future versions, extensions will declare MCP recommendations:

```yaml
mcp-recommendations:
  - name: context7
    purpose: "Official framework docs for API reference"
    when: "Agent needs specific API syntax or version-specific details"
```

This creates a clean division:
- **Extension provides:** judgment (when to use patterns, when to avoid anti-patterns)
- **MCP provides:** knowledge (current API syntax, version compatibility, config options)

The extension works without MCP — the agent falls back to its training data and
web search for API specifics. MCP makes it more accurate, not fundamentally different.

---

## Building Extensions: The Process

1. **Identify the judgment gap.** What does the LLM get wrong for this framework?
   Build a feature in the framework using a naked LLM (no extension). Document
   every mistake, wrong pattern, and outdated approach. These are your anti-patterns.

2. **Distill the patterns.** For each category (data fetching, state, routing, etc.),
   write the opinionated "right way" for this specific framework. Not every possible
   approach — the approach a senior developer would use for most cases.

3. **Test with pressure.** Run the pressure test methodology: give the agent a task
   WITHOUT the skill, observe failures, then WITH the skill, verify corrections.
   See `develop/validators/pressure/` for the methodology.

4. **Keep it small.** If a skill exceeds 2,000 lines, it's doing too much.
   Split it or move API-level details out (they belong in MCP or official docs).

5. **Version-tag references.** Each pattern file should note which framework version
   it targets. When the framework ships a new major version, the community updates
   the affected patterns.

---

## Maintenance Philosophy

Extensions decay. Framework versions change. New patterns emerge. Old anti-patterns
stop being relevant. The maintenance approach:

- **Patterns** need updating when the framework introduces a fundamentally new way
  of doing something (e.g., React Server Components changing data fetching).
  Minor version changes rarely affect patterns.

- **Anti-patterns** need updating when the old approach stops being in training data.
  If no new model would write class components in React, that anti-pattern can be
  removed. New anti-patterns get added when a framework shift creates a new
  "stale training data" trap.

- **Integration files** need updating when either framework in the pair releases
  a version that changes the integration surface.

- **Constitution additions** rarely change — they capture framework-level principles
  ("use next/image") that are stable across versions.

Community contributions through the `community/` staging area are the primary
maintenance mechanism. Framework experts notice when patterns go stale and submit
updates through the propose → test → review → promote lifecycle.

---

## Ecosystem Design Choices

### Why "Skill" and Not "Pack" or "Plugin"

The AI agent ecosystem converged on "skill" as the standard term for installable
agent capabilities. Anthropic's official guide uses it. Antigravity uses it.
Community marketplaces trade in skills. Fighting the convention would create
unnecessary friction for every new user.

Sage originally used "pack" for technology knowledge and "playbook skill" for
methodology processes. The ecosystem restructuring unified these under one term:
everything installable is a skill. The type field (`knowledge`, `process`,
`composite`, `bundle`) determines integration behavior. Users don't need to know
the type — they just install skills.

Core process steps (specify, plan, implement) were renamed "capabilities" to
avoid collision. They're the engine, not the extensions.

### Why Progressive Enhancement

A community skill with just a SKILL.md and zero Sage metadata works at Layer 0.
Each Sage-specific field in the manifest makes integration smarter but nothing
is required. This means Sage can consume the entire existing skills ecosystem
without requiring authors to add Sage-specific metadata.

Three layers of compatibility:
- **Layer 0:** Any SKILL.md → loads into context, user configures manually
- **Layer 1:** Add type/version → smart integration based on type
- **Layer 2:** Full manifest with relationships → extends/complements/replaces

### Why Three Relationships (extends, complements, replaces)

Skills coexist by default (no declaration = peaceful coexistence). Authors
can opt into:
- `extends` — "I'm a stricter version" (overrides specific patterns)
- `complements` — "I cover different concerns" (explicit compatibility)
- `replaces` — "I'm a complete alternative" (deactivates the other)

This gives compose-by-default with escape hatches for genuine conflicts.
The model was informed by ESLint's config composition and Linux's driver model.

### Why Flat Namespace

`skills/react/` not `skills/knowledge/framework/react/`. Users browse
skills by name, not by type. Flat namespacing with `@scope/` prefixes provides
identity without hierarchy. Two levels (``, ``, `@username/`)
is enough.

### Why Quality Criteria and Self-Review

Skills tell the agent WHAT to do (process steps) and WHAT NOT to do
(constraints, failure modes). Quality criteria add a third dimension:
WHAT GOOD LOOKS LIKE. This closes the loop — the agent can verify its
own output against specific, checkable standards before presenting it.

Without quality criteria, the agent follows steps and hopes the output
is good. With criteria, the agent can self-check: "Did I find emotional
jobs? Did I name the trade-offs? Are my acceptance criteria testable?"
This is the difference between process compliance and output quality.

Self-review makes the agent transparent. Instead of presenting output
as if it's perfect, the agent says: "7/8 criteria met. I couldn't verify
X because Y." The user knows where to focus their attention. Trust is
built through honesty, not through confidence.

Quality criteria also power the `/review` workflow. When an independent
agent reviews an artifact, it uses the producing skill's criteria as the
evaluation framework. This makes review specific and actionable — not
just "does this look good?" but "does this meet the standards that this
domain requires?"
