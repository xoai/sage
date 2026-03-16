---
name: onboard
description: >
  First-run project setup that detects tech stack, selects quality packs, and
  generates .sage/ directory with CLAUDE.md. For new projects, guides
  technology selection. Use when no .sage/ directory exists, when the user
  says "set up sage", "initialize", "get started", or when starting a brand
  new project from scratch.
version: "1.0.0"
modes: [fix, build, architect]
---

<!-- sage-metadata
cost-tier: sonnet
activation: manual
tags: [setup, onboarding, initialization, context]
inputs: [codebase-or-nothing]
outputs: [sage-directory, claude-md, conventions]
-->

# Onboard

Set up Sage for a project. Detect what exists, configure what's needed,
generate the agent instructions. This is the FIRST thing that runs.

**Core Principle:** A beginner should go from "I have a project" (or "I have
an idea") to "Sage is configured and ready" in under 3 minutes.

## When to Use

- First time using Sage on a project (no `.sage/` directory exists)
- User says "set up sage", "onboard", "initialize", or "get started"
- Sage detects no `.sage/` directory and prompts: "This project isn't set up
  with Sage yet. Want me to set it up? (Takes ~2 minutes)"

## Process

### Step 0: Detect Project State

Check what exists:
- Does `.sage/` exist? → Already onboarded. Offer to re-scan or update.
- Does `package.json` / `requirements.txt` / `pubspec.yaml` exist? → Existing project.
- Is the directory empty or near-empty? → New project (greenfield).

Branch accordingly:

---

### Path A: Existing Project

#### A1. Scan the Stack

Read dependency files to detect the tech stack:

```
package.json  → detect: next, react, vue, svelte, express, supabase, firebase
pubspec.yaml  → detect: flutter, firebase
requirements.txt / pyproject.toml → detect: django, flask, fastapi
go.mod → detect: gin, echo, fiber
```

Produce a stack summary:
```
DETECTED STACK:
  Frontend: Next.js 14 (App Router), React 19, Tailwind CSS 4
  Backend:  Supabase (@supabase/ssr, @supabase/supabase-js)
  Testing:  Vitest, Testing Library
  Build:    Turbopack
```

Show to user: "I detected this stack. Anything I missed or got wrong?"

#### A2. Select Packs

Based on detected stack, select which packs activate:

```
PACKS TO LOAD:
  L1: web (web application detected)
  L1: baas (Supabase detected)
  L2: nextjs (Next.js detected)
  L2: react (React detected)
  L3: stack-nextjs-supabase (Next.js + Supabase detected)
```

Show to user: "These packs will guide code quality. Look right?"

#### A3. Discover Conventions

Scan the codebase for established patterns:
- File naming (kebab-case? PascalCase? camelCase?)
- Component structure (co-located files? flat directories?)
- State management approach
- Test patterns and locations
- Import style (absolute? relative? aliases?)
- Formatting (Prettier? ESLint config?)

Save to `.sage/conventions.md`.

#### A4. Generate Configuration

Create the `.sage/` directory and all files. See [Output](#output) below.

---

### Path B: New Project (Greenfield)

#### B1. Ask What They're Building

One question: **"What are you building? Describe it in a sentence or two."**

Examples of what they might say:
- "A task management app for my team"
- "An e-commerce site for my bakery"
- "A mobile app for tracking workouts"
- "A SaaS dashboard for analytics"

#### B2. Guide Tech Stack Selection

Based on what they described, recommend a stack. Ask focused questions:

**Question 1: Platform**
"Is this a web app, mobile app, or both?"
- Web only → React/Next.js path
- Mobile only → Flutter or React Native path
- Both → Next.js (web) + React Native (mobile) or Flutter (both)

**Question 2: Backend complexity**
"Will this need complex backend logic (custom algorithms, complex queries, multi-step workflows), or is it mostly storing/fetching data with user accounts?"
- Mostly CRUD + auth → Supabase or Firebase (BaaS path)
- Complex backend → Custom API (Express/Django + database)

**Question 3: Scale expectation** (only if unclear)
"Is this an MVP/prototype, or do you need it production-ready from day one?"
- MVP → optimize for speed, BaaS recommended
- Production → optimize for control, consider custom backend

Based on answers, recommend:
```
RECOMMENDED STACK:
  You're building a web app with user accounts and data storage.
  For fast MVP delivery, I recommend:

  Frontend: Next.js (App Router) + React + Tailwind CSS
  Backend:  Supabase (auth, database, storage — no backend to build)
  Testing:  Vitest + Testing Library
  Deploy:   Vercel

  This gets you from idea to deployed app fastest.
  Ready to go with this, or want to explore alternatives?
```

If user wants alternatives, explain trade-offs briefly. Don't overwhelm.

#### B3. Scaffold the Project

After stack approval, create the project structure:
- Run the framework's project creator (`npx create-next-app`, `flutter create`, etc.)
- Set up initial dependencies
- Create initial configuration files
- Set up testing infrastructure

#### B4. Generate Configuration

Same as A4 — create `.sage/` directory. Conventions will be minimal for
a new project (establish them as the first code is written).

---

## Output

### Create `.sage/` Directory

```
.sage/
├── config.yaml           # Project configuration
├── conventions.md         # Discovered or established patterns
├── progress.md            # Current state pointer
├── journal.md             # Project journal (artifact index + change log)
├── docs/                  # Project-level knowledge (flat, skill-prefixed)
└── work/                  # Per-initiative (YYYYMMDD-slug/ subfolders)
```

### .sage/config.yaml
```yaml
sage-version: "1.0.0"
project-name: "<detected or provided>"
mode-default: build
packs:
  enabled:
    - web
    - baas
    - nextjs
    - react
    - stack-nextjs-supabase
constitution:
  base: sage/core/constitution/base.constitution.md
  preset: startup  # or enterprise, opensource
```

### .sage/progress.md
```markdown
# Progress

Mode: idle
Feature: none
Phase: ready
Next: "Tell me what to build, or say 'sage help' for guidance"
Updated: <timestamp>
```

### .sage/conventions.md
```markdown
# Project Conventions

Discovered by Sage onboard on <date>.
Update this file as conventions evolve.

## Naming
- Files: <detected pattern>
- Components: <detected pattern>
- Variables: <detected pattern>

## Structure
- Components: <detected layout>
- Tests: <detected location and framework>
- Styles: <detected approach>

## Patterns
- State management: <detected or TBD>
- Data fetching: <detected or TBD>
- Error handling: <detected or TBD>
```

### .sage/journal.md
```markdown
# Project Journal

## Current Artifacts

### Active (being worked on)

### Reference (done, still relevant)
- `.sage/config.yaml` — Project configuration
- `.sage/conventions.md` — Discovered project conventions

### Archived (superseded or no longer relevant)

---

## Change Log

### <date> — Project initialized
**Produced:** .sage/ directory with config, conventions, progress tracker
**Key:** Sage installed. Detected stack: [stack]. Packs: [packs].
**Next:** Start building — describe what you want to create.
```

### Generate CLAUDE.md

Use the template at `core/context-loader/CLAUDE.md.template`:
- Replace `{{CONSTITUTION_PRINCIPLES}}` with the loaded constitution
- Replace `{{LOADED_PACKS}}` with summaries from enabled packs
- Replace `{{CONVENTIONS}}` with `.sage/conventions.md` content

Save to project root as `CLAUDE.md`.

### Discover MCP Tools (if configured)

If `.claude/mcp.json` or `.sage/mcp.json` exists, run tool discovery:

```bash
bash sage/runtime/mcp/discover.sh .
```

This connects to each configured MCP server, lists available tools, and caches
the manifest at `.sage/mcp-manifest.json`. The CLAUDE.md generation includes
a lightweight tool summary (~50 tokens per server) so you know what's available
without consuming context with full schemas.

If no MCP config exists, skip this step. Layer 1 tools (bash scripts) are always
available regardless of MCP configuration.

Show the user: "Sage is set up. Here's what I configured: [summary].
Tell me what to build, or say 'sage help' for guidance on what to do next."

## Rules

**MUST (violation = broken setup or confused user):**
- MUST NOT skip user confirmation on detected stack or recommended stack.
- MUST generate `.sage/` directory and CLAUDE.md — they're the minimum viable setup.
- MUST detect packs from the stack — don't ask the user to pick packs manually.

**SHOULD (violation = suboptimal experience):**
- SHOULD NOT overwhelm with options — recommend ONE stack, explain alternatives only if asked.
- SHOULD recommend BaaS (Supabase/Firebase) for MVPs, custom backend for complex products.
- SHOULD respect the existing stack — don't suggest rewriting what's already there.

**MAY (context-dependent):**
- MAY skip pack selection confirmation if only L1 packs apply (no framework-specific packs detected).
- MAY suggest additional packs if the user mentions planned additions ("we'll add Firebase later").

## Failure Modes

- **Can't detect stack:** Ask the user directly. "I can't tell what framework this uses. What's the main technology?"
- **Mixed/unusual stack:** Load what you can detect, note gaps. "I found React but couldn't detect the backend. What are you using for data?"
- **User wants a stack you don't have packs for:** Proceed without L2/L3 packs. L1 packs (web, mobile, api, baas) still apply. "I don't have specialized guidance for [framework] yet, but general web/API best practices will still apply."
