---
name: "@sage/stack-nextjs-supabase"
description: "Integration seams for Next.js App Router + Supabase: dual-client auth (browser/server), middleware token refresh, RLS policies, typed queries, and real-time subscriptions"
version: "1.0.0"
type: composite
layer: stack
requires:
  sage: ">=1.0.0"
  skills:
    - "@sage/web"
    - "@sage/baas"
    - "@sage/nextjs"
activates-when:
  detected: [next, @supabase/supabase-js, @supabase/ssr]
tags: [next,@supabase/supabase-js,@supabase/ssr]
---

# @sage/stack-nextjs-supabase

**Layer 3 — Stack Composition**

Integration seams for Next.js App Router + Supabase. Covers the five
critical integration points that neither Next.js docs nor Supabase docs
adequately address together.

## Integration Seams

| Seam | What Goes Wrong |
|------|----------------|
| Dual Clients | Agents create one client — auth silently breaks across server/client boundary |
| Middleware Token Refresh | Agents skip middleware — users randomly get logged out on expired tokens |
| RLS as Authorization | Agents rely on Next.js middleware for auth — database is still publicly accessible |
| Typed Queries | Agents use untyped `select('*')` — typos are silent runtime errors |
| Server Actions | Agents build REST API routes for same-app mutations instead of using Server Actions |

## Grounded In

- Supabase official docs: Server-Side Auth for Next.js, @supabase/ssr package
- Supabase official docs: Row Level Security, Creating a Client for SSR
- Security research: 170+ Lovable apps exposed (CVE-2025-48757), 83% of exposed
  Supabase DBs involve RLS misconfigurations
- Supabase Advanced Guide: CDN caching risks, Vercel Fluid compute client reuse

## Loading Order

```
L1: @sage/web (domain) + @sage/baas (backend domain)
L2: @sage/nextjs (framework) + @sage/react (framework)
L3: @sage/stack-nextjs-supabase (this pack — integration seams)
```
