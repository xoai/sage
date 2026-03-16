# Pack Tests: stack-nextjs-fullstack

**Framework version tested:** Next.js 14+ / Prisma 5+ / Auth.js v5 / Tailwind 3+
**Last tested:** 2025-03-13

---

## Test 1: Database query in a page

**Prompt:**
```
Create a products listing page that queries the database.
```

**Without pack:** Agent creates a new `PrismaClient()` instance in the page file, causing connection pool exhaustion in development.
**With pack:** Agent imports from a shared `lib/prisma.ts` singleton using the `globalThis` pattern to survive hot reload.
**Tests:** Integration "Prisma + Next.js" + Anti-pattern "PrismaClient per file"

---

## Test 2: Protected route

**Prompt:**
```
Create an admin dashboard page that only authenticated users can access.
```

**Without pack:** Agent checks auth only in middleware, missing server component protection — or checks auth independently in every page.
**With pack:** Agent checks auth in the Server Component with `auth()` from Auth.js, redirects if unauthenticated. Middleware handles redirects, server components verify access.
**Tests:** Integration "Auth.js + Next.js" + Anti-pattern "Auth only in middleware"

---

## Test 3: Styled component with variants

**Prompt:**
```
Create a Button component with primary, secondary, and danger variants.
```

**Without pack:** Agent uses dynamic class names like `bg-${color}-500` which Tailwind can't detect at build time.
**With pack:** Agent uses explicit complete class names in a variant map: `{ primary: 'bg-blue-500', danger: 'bg-red-500' }`.
**Tests:** Integration "Tailwind + Next.js" + Anti-pattern "Dynamic Tailwind classes"
