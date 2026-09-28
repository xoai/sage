---
name: "nextjs"
description: "Next.js 14/15 App Router patterns — server components, data fetching, caching, server actions"
version: "1.0.0"
type: knowledge
layer: framework
requires:
  sage: ">=1.0.0"
  skills:
    - "web"
    - "react"
activates-when:
  detected: [next, "@supabase/ssr", "@supabase/supabase-js", prisma, tailwindcss]
tags: [next, supabase, prisma, tailwindcss, fullstack]
---

# nextjs

**Layer 2 — Framework Pack**

Next.js 14/15 App Router patterns. Server components, data fetching, caching,
server actions, and the specific mistakes agents make from Pages Router
training data contamination.

## Philosophy

Next.js is where the "judgment not knowledge" principle matters most. The
framework underwent a fundamental paradigm shift from Pages Router to App Router.
Server components changed how data fetching works. Server actions changed how
mutations work. The caching model changed between Next.js 14 and 15.

LLMs trained on pre-App-Router content produce code that technically runs but
uses wrong patterns — `getServerSideProps` in App Router projects, `useEffect`
for data fetching that should happen on the server, `'use client'` on every
component because the agent doesn't understand the server-first model.

This pack establishes the App Router mental model as the default and explicitly
corrects the most common Pages Router contamination patterns.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Patterns | 7 | Server components, data fetching, routing/layouts, server actions, caching, middleware, metadata |
| Anti-patterns | 5 | Pages Router patterns, use-client-everywhere, useEffect data fetching, client-side routing, wrong caching |
| Constitution | 1 | 6 Next.js-specific principles |
| Gate | 1 | Next.js pattern compliance check |

## Overrides

When installed alongside `react`, this pack overrides React's
data-fetching pattern. In Next.js, data fetching happens in server components,
not via TanStack Query in client components (unless you specifically need
client-side real-time data).

## Key Mental Model

**Server-first.** Components are server components by default. They run on the
server, have direct access to databases and file systems, and ship zero JavaScript
to the browser. Only add `'use client'` when you need interactivity (event handlers,
hooks, browser APIs). Most components (70-90% in a typical app) should remain
server components.

## Stack Integrations (detection-gated)

Next.js rarely ships alone. When a dependency below is detected, read the
matching integration reference — the cross-framework seams that neither tool's
own docs cover. These fold in the former `stack-nextjs-supabase` and
`stack-nextjs-fullstack` skills; the content is unchanged, now surfaced through
`nextjs` on detection.

- **`@supabase/ssr` / `@supabase/supabase-js`** → `integration/supabase-integration.md`
  — dual browser/server clients, middleware token refresh, RLS as authorization,
  typed queries, Server Actions.
  Constitution: `constitution/supabase.constitution-additions.md` ·
  anti-patterns: `anti-patterns/supabase-anti-patterns.md`.
- **`prisma` + `tailwindcss` (+ Auth.js)** → `integration/fullstack-integration.md`
  — Prisma client singleton, Auth.js × App Router middleware, Tailwind × server
  components.
  Constitution: `constitution/fullstack.constitution-additions.md` ·
  anti-patterns: `anti-patterns/fullstack-anti-patterns.md`.
