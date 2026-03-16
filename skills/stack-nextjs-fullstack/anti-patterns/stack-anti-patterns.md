# Anti-Pattern: PrismaClient Per File

**What agents do:** `new PrismaClient()` in every file that needs database access.

**Why agents do this:** Each file looks self-contained. The agent doesn't realize hot reload re-executes module-level code, creating a new connection each time.

**Why it's wrong:** Connection pool exhaustion after a few edits in development. In production, cold starts create multiple clients. Do instead: Import from shared singleton `lib/db.ts` using globalThis pattern.

---

# Anti-Pattern: Auth Only in Middleware

**What agents do:** Check auth in middleware, then trust it everywhere else. Pages and server actions assume middleware handled it.

**Why agents do this:** Middleware feels like the "front door" — if you lock it, surely everything inside is safe.

**Why it's wrong:** Middleware runs on Edge Runtime with limited APIs — it can redirect but can't do full auth checks. A direct API call or CSRF attack bypasses middleware entirely. One missed matcher config exposes a route. Do instead: Three layers — middleware redirects, server components scope data by user, server actions verify ownership per mutation.

---

# Anti-Pattern: Dynamic Tailwind Classes

**What agents do:** `className={\`bg-${color}-500\`}` — template literal with variable interpolation.

**Why agents do this:** Dynamic class generation works in CSS-in-JS (styled-components, Emotion) which dominates training data. Agents apply the same pattern to Tailwind.

**Why it's wrong:** Tailwind's build-time scanner never sees the complete class string. The class is missing from the output CSS. Works in dev (JIT compiles everything), breaks in production. Do instead: Explicit variant maps with complete class names.
