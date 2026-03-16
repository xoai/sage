# Anti-Pattern: Single Supabase Client

**What agents do:** One `createClient()` imported in both Server and Client Components.

**Why agents do this:** One client works in non-SSR apps. Agents don't realize App Router splits server (can't write cookies) and browser (can't use `next/headers`).

**Why it's wrong:** Server Components using a browser client can't access cookies — auth silently fails. Client Components using a server client crash on `cookies()`. Do instead: Two factories via `@supabase/ssr`.

---

# Anti-Pattern: No Middleware

**What agents do:** Skip middleware. Auth works initially but users get randomly logged out when tokens expire.

**Why agents do this:** Tokens are fresh during development. The agent never tests expired-token SSR.

**Why it's wrong:** Server Components can't write cookies to save refreshed tokens. Without middleware refreshing on every request, expired tokens aren't renewed. Do instead: Middleware that creates a server client and calls `getUser()`.

---

# Anti-Pattern: getSession() for Server Auth

**What agents do:** `supabase.auth.getSession()` in Server Components to check auth.

**Why agents do this:** `getSession()` is simpler and faster. Agents find it first in autocomplete.

**Why it's wrong:** `getSession()` reads the JWT from cookies without verifying against the Auth server. Token could be expired, revoked, or tampered. Supabase docs warn: "cookies can be spoofed by anyone." Do instead: Always `supabase.auth.getUser()` in server code.

---

# Anti-Pattern: RLS Disabled

**What agents do:** Create tables without `ENABLE ROW LEVEL SECURITY`. Or enable RLS but add no policies (table returns empty, no error).

**Why agents do this:** Tables default to RLS-off. SQL Editor bypasses RLS. Everything works in dev.

**Why it's wrong:** Without RLS, the PostgREST API exposes the table publicly. Anyone with your anon key can dump it. Do instead: Every migration: `ENABLE ROW LEVEL SECURITY` + policy + index.

---

# Anti-Pattern: service_role Key Exposed

**What agents do:** Use `service_role` key in client code or `NEXT_PUBLIC_` env vars because it "makes everything work."

**Why agents do this:** `service_role` bypasses RLS, so queries always return data. It's the fastest fix for RLS issues.

**Why it's wrong:** Full unrestricted database access for any browser user. Equivalent to giving visitors the root password. Do instead: `service_role` only in server-side code. Publishable/anon key for all client code.
