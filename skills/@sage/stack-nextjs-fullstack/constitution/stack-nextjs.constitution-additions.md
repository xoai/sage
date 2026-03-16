# Stack Next.js Fullstack — Constitution Additions

## Stack Integration Principles

1. Prisma client MUST be instantiated as a singleton using the global registry pattern. Multiple Prisma Client instances cause connection pool exhaustion in development (hot reload creates new instances).
2. All database access MUST happen in server components or server actions. The Prisma client MUST NOT be imported in any file that contains `'use client'`.
3. Authentication checks MUST happen in middleware for route protection AND in server components/actions for data access. Never rely on middleware alone — it can be bypassed by direct API calls.
4. Tailwind CSS classes MUST be the primary styling mechanism. No inline `style` attributes except for truly dynamic values (calculated positions, runtime dimensions). No separate CSS files unless integrating third-party components.
5. All environment variables containing secrets (database URLs, API keys, auth secrets) MUST only be accessed in server code. Variables prefixed with `NEXT_PUBLIC_` are exposed to the client and MUST NOT contain secrets.
