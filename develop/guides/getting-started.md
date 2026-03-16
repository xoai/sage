# Getting Started with Sage

## 30-Second Version

1. Open your project in Claude Code (or your AI coding tool)
2. The agent sees Sage and asks: "Want me to set up Sage?" → Say yes
3. Sage detects your stack, configures quality packs, generates instructions
4. Tell the agent what you want to build
5. It asks a few questions (~2 min), makes a plan, builds task by task with tests
6. You approve at checkpoints. Done.

**Don't know what to say?** Just type "sage help" — it tells you exactly what to do next.

---

## Three Ways to Use Sage

### 🔧 Fix Something (FIX mode — minutes)

> "This login form is broken — it returns 401 even with correct credentials"

The agent debugs systematically: reproduce → diagnose root cause → write a test that
captures the bug → fix it → verify the fix → commit. No planning overhead.

### 🏗️ Build a Feature (BUILD mode — hours)

> "Add a user profile page where people can update their name and avatar"

The agent scans your codebase, asks targeted questions about what you want (~2 min),
creates a plan with small tasks, then builds each task with tests. You approve the
spec and plan before implementation starts.

### 🏛️ Start From Scratch (ARCHITECT mode — days)

> "I want to build a SaaS dashboard for tracking social media analytics"

The agent helps you choose your tech stack, designs the architecture, creates a
full project plan, then builds it phase by phase. Deeper elicitation, more
checkpoints, architectural decision records.

---

## Your First Project

### If you have an existing project:

```
1. Open your project directory in Claude Code
2. Say: "Set up Sage for this project"
3. Sage scans your package.json / requirements.txt / pubspec.yaml
4. Shows detected stack and recommended quality packs
5. You confirm → .sage/ directory and CLAUDE.md are created
6. Say: "Add [feature]" and the BUILD workflow begins
```

### If you're starting fresh:

```
1. Create an empty directory and open it in Claude Code
2. Say: "I want to build [describe your app]"
3. Sage asks: Web or mobile? Complex backend or simple data storage?
4. Recommends a tech stack (e.g., Next.js + Supabase for web MVPs)
5. You confirm → project scaffolded, Sage configured
6. Describe your first feature → BUILD workflow begins
```

---

## What Happens During a Build

Here's the actual sequence when you say "build a user profile page":

**Phase 1 — Understand (automatic, ~2 min)**
The agent scans the relevant part of your codebase. Notes patterns, conventions,
test setup.

**Phase 2 — Specify (interactive, ~2 min)**
Three rounds of questions:
- "What should this do when it's working perfectly?"
- "What should it NOT do? Any constraints?"
- "How will we know it works?"

Shows you a spec. You approve or adjust.

**Phase 3 — Plan (automatic, ~1 min)**
Breaks the spec into small tasks (2-5 minutes each). Each task has:
- Exact file paths to create or modify
- What code to write
- What test to write
- How to verify it works

Shows you the plan. You approve or adjust.

**Phase 4 — Implement (autonomous with checkpoints)**
For each task:
1. Writes a failing test (TDD)
2. Writes code to pass the test
3. Runs quality checks (security, spec compliance, code quality)
4. Commits
5. Shows progress, moves to next task

You can say "pause" anytime between tasks.

**Phase 5 — Review**
Final quality check on everything together. Shows you the result.
You decide: merge, create PR, or keep working.

---

## Key Commands

| Say this | What happens |
|----------|-------------|
| "sage help" | Shows what to do next based on current state |
| "set up sage" | First-time project setup (onboard) |
| "fix [bug description]" | FIX mode — debug and fix systematically |
| "build [feature description]" | BUILD mode — spec → plan → implement |
| "I want to build [app description]" | ARCHITECT mode — full project from scratch |
| "pause" | Stop between tasks, save progress |
| "status" | Show current progress on active feature |
| "skip elicitation" | Jump straight to planning (you provide the spec) |

---

## How Quality Works

Sage has 12 quality packs that automatically guide the agent based on your stack.
You don't configure them — they activate when your tech stack is detected.

| If your project uses... | These packs activate |
|------------------------|---------------------|
| Any web framework | @sage/web (accessibility, performance, security) |
| React, Next.js | @sage/react + @sage/nextjs (framework-specific) |
| Flutter | @sage/flutter (widget architecture, state) |
| React Native | @sage/react-native (native patterns, performance) |
| Firebase | @sage/baas + stack pack (security rules, data modeling) |
| Supabase | @sage/baas + stack pack (RLS, typed queries) |
| Custom API (Express, etc.) | @sage/api (validation, pagination, auth) |

The agent follows these packs automatically. You don't need to know the details —
they prevent common mistakes behind the scenes.

---

## FAQ

**Q: Do I need to learn Sage's structure to use it?**
No. Just talk to the agent normally. Sage works in the background. Say "sage help"
if you're ever unsure what to do.

**Q: Can I skip the spec/plan and just start coding?**
Yes. Say "just do it" or provide your own detailed spec. Sage respects your autonomy
but notes the risk of skipping planning.

**Q: What if I disagree with Sage's suggestion?**
Override it. Sage recommends, you decide. Say "I want to use X instead" and the
agent adapts.

**Q: Does this work with tools other than Claude Code?**
Sage is designed for Claude Code but the skills and packs are standard markdown.
Adapters for Cursor, Codex, and others are in `runtime/platforms/`.

**Q: How do I resume after closing my terminal?**
Just open the project again. The agent reads `.sage/progress.md` and picks up where
you left off. All progress is saved in the plan file checkboxes.
