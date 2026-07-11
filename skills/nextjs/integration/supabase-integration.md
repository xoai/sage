# Dual Supabase Clients: Browser + Server

**Why agents get this wrong:** Agents create one client for everything. App Router requires TWO — Server Components can't write cookies, Client Components can't use `next/headers`. Using the wrong one silently breaks auth.

**Do:** Two factories via `@supabase/ssr` (Supabase official pattern):
```ts
// lib/supabase/client.ts — Client Components only
import { createBrowserClient } from '@supabase/ssr';
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!
  );
}

// lib/supabase/server.ts — Server Components, Actions, Route Handlers
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    { cookies: {
        getAll() { return cookieStore.getAll(); },
        setAll(cookiesToSet) {
          try { cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options));
          } catch { /* Server Component: middleware persists */ }
        },
    }},
  );
}
```

---

# Middleware for Token Refresh

**Why agents get this wrong:** Without middleware, Server Components can't refresh expired tokens (they can't write cookies). Users randomly get logged out.

**Do:** Middleware calls `getUser()` on every request — refreshes token and syncs cookies:
```ts
// middleware.ts
import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';
export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    { cookies: {
        getAll() { return request.cookies.getAll(); },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options));
        },
    }},
  );
  await supabase.auth.getUser(); // Verifies + refreshes
  return response;
}
export const config = { matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg)$).*)'] };
```

Critical: `getUser()` verifies with Auth server. `getSession()` only reads the local JWT without verification — spoofable. Always `getUser()` for server-side auth.

---

# RLS + Indexed Policies on Every Table

**Why agents get this wrong:** Supabase creates tables with RLS disabled by default. SQL Editor bypasses RLS — everything works in dev. In Jan 2025, 170+ apps found with exposed databases from disabled RLS. 83% of exposed Supabase DBs involve RLS misconfigurations.

**Do:** Every migration includes RLS + policy + index:
```sql
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "owner_all" ON posts FOR ALL TO authenticated
  USING (auth.uid() = author_id) WITH CHECK (auth.uid() = author_id);
CREATE POLICY "public_read" ON posts FOR SELECT USING (published = true);
CREATE INDEX idx_posts_author ON posts(author_id);
```
RLS enabled without policies = deny all (empty results, no error). Always add at least one policy.

---

# Typed Queries from Generated Schema

**Why agents get this wrong:** Agents use untyped `supabase.from('posts').select('*')`. Typos are silent runtime errors.

**Do:** `npx supabase gen types typescript --project-id $ID > lib/database.types.ts`. Regenerate after every migration. Use generated types for all queries:
```ts
type Post = Database['public']['Tables']['posts']['Row'];
const { data } = await supabase.from('posts').select('id, title').returns<Post[]>();
```

---

# Server Actions for Mutations

**Why agents get this wrong:** Agents create Route Handlers for every mutation, building a REST API on top of Supabase.

**Do:** Server Actions for same-app mutations. Route Handlers only for webhooks/external consumers:
```ts
'use server';
export async function createPost(formData: FormData) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Unauthorized');
  await supabase.from('posts').insert({
    title: formData.get('title') as string, author_id: user.id,
  });
  revalidatePath('/posts');
}
```
