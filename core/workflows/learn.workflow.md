---
name: learn
version: "1.0.0"
mode: learn
---

# Learn Workflow

Deliberate knowledge capture. Use to onboard to a new codebase, deeply
understand a module, or build persistent memory for a project area.

## Step 1: Determine Scope

If a path is specified, that's the target — deep dive.
If no path, broad scan of the whole project.

```
1) Broad scan — learn the project structure, stack, patterns, conventions
2) Deep dive — learn a specific module, service, or area
3) Something else — describe what you want to understand
```

## Step 2: Search Existing Knowledge

Search sage-memory for any prior knowledge about this project or area.
Don't re-learn what's already known — build on it.

If prior knowledge exists, summarize: "I already know [X] about this
area from previous sessions. I'll focus on what's new or missing."

## Step 3: Scan and Analyze

### Broad Scan

1. Read project structure — file tree, key directories
2. Read README, package.json / pyproject.toml / go.mod, config files
3. Identify tech stack, frameworks, build tools
4. Read entry points — main modules, routing, API surface
5. Identify architectural patterns — MVC, microservices, monolith, etc.
6. Note conventions — naming, file organization, testing approach

### Deep Dive

1. Read all files in the target area
2. Trace dependencies — what it imports, what imports it (depth 3 max)
3. Map data flow — inputs, transformations, outputs
4. Identify design patterns, error handling, edge cases
5. Assess quality — strengths, risks, technical debt

## Step 4: Store Knowledge

Store focused memories using sage-memory. Each memory should be one
clear insight with a specific title and domain vocabulary.

For broad scans, aim for 10-20 entries covering:
- Tech stack and framework choices
- Project structure and organization
- Key architectural patterns
- Conventions and coding standards
- Domain concepts and business logic
- Notable dependencies and integrations

For deep dives, aim for 5-10 entries covering:
- Module purpose and role in the system
- Key components and their responsibilities
- Data flow and integration points
- Patterns specific to this area
- Risks, debt, or improvement opportunities

Tag entries appropriately:
- Domain tags always (e.g., `billing`, `auth`)
- `ontology` tag for entity relationships and dependencies
- `learning` tag for gotchas or non-obvious behavior discovered

If sage-memory is not available, note findings in the knowledge report
(Step 5) — the report becomes the primary knowledge artifact.

## Step 5: Generate Knowledge Report

Save a human-readable report to `.sage/docs/memory-{name}.md`.

Follow the memory skill's `references/knowledge-report.md` guide:
- Adapt structure to content (don't force a rigid template)
- Include mermaid diagrams when they clarify architecture or data flow
- Focus on insights, not inventory
- Note how many memory entries were stored

## Step 6: Report Summary

```
Learning complete: [area name]

Knowledge stored:
  • [X] memories in sage-memory
  • Report: .sage/docs/memory-{name}.md

Key findings:
  • [Top 3-4 insights, one line each]

[C] Continue — anything else to explore?
```

## Rules

- Search before storing — don't duplicate existing knowledge.
- Store insights, not facts readable from files.
- One insight per memory entry — focused entries retrieve precisely.
- Adapt depth to scope — broad scans stay high-level, deep dives
  trace dependencies and assess quality.
- The knowledge report is for humans. Memory entries are for the agent.
  Both should exist for significant learning.
