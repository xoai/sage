# Pack Tests: stack-nextjs-supabase

**Framework version tested:** Next.js 14+, @supabase/ssr 0.5+
**Last tested:** 2026-03-13

---

## Test 1: Set Up Supabase Auth

**Prompt:**
```
Add Supabase authentication to this Next.js App Router project.
```

**Without pack:** Single `createClient()` shared everywhere. No middleware. `getSession()` used for auth checks. Token refresh breaks on SSR.

**With pack:** Two client factories (browser + server). Middleware with `getUser()` for token refresh. Server-side auth uses `getUser()` (verified). Cookie-based auth with `@supabase/ssr`.

**Tests:** Integration "Dual Clients" + "Middleware" + Anti-pattern "getSession for Auth"

---

## Test 2: Protected Dashboard Page

**Prompt:**
```
Create a dashboard page that only authenticated users can see. Show their data.
```

**Without pack:** `getSession()` check. No RLS. Middleware redirect but no database-level protection. Untyped queries.

**With pack:** `getUser()` in Server Component. RLS on the data table (`auth.uid() = user_id`). Typed query with generated types. Middleware handles token refresh. Data scoped by RLS, not just application-level check.

**Tests:** Integration "RLS" + "Typed Queries" + Anti-pattern "RLS Disabled" + "getSession"

---

## Test 3: Create Post Form

**Prompt:**
```
Build a form where authenticated users can create blog posts.
```

**Without pack:** Creates an API Route Handler. No RLS WITH CHECK. No type safety on insert. `service_role` key to bypass RLS issues.

**With pack:** Server Action with `getUser()` auth check. Typed insert using generated Database types. RLS policy with `WITH CHECK (auth.uid() = author_id)`. `revalidatePath` after mutation. Publishable key only.

**Tests:** Integration "Server Actions" + "Typed Queries" + Anti-pattern "service_role in Client"

---

## Test 4: Production Security Audit

**Prompt:**
```
Review this Next.js + Supabase app for security issues.
```

**Without pack:** Checks for HTTPS and basic input validation. Misses RLS audit, service_role exposure, getSession vs getUser, middleware presence.

**With pack:** Audits every table for RLS enabled + policies + indexes. Verifies middleware exists and calls getUser(). Checks no NEXT_PUBLIC_ vars contain service_role key. Verifies server code uses getUser() not getSession(). Checks typed queries throughout.

**Tests:** All anti-patterns — comprehensive security review
