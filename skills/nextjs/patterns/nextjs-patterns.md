# Server Components (Default)

**Why agents get this wrong:** Agents add `'use client'` to nearly every component because their training data is pre-RSC. In App Router, components are Server Components by default.

**Server Components can:** directly access databases, file systems, and environment variables. Await async operations at the top level. Import server-only modules (`node:fs`, database clients, API keys). Ship ZERO JavaScript to the browser.

**Client Components (`'use client'`) are needed ONLY for:** event handlers (`onClick`, `onChange`), React hooks (`useState`, `useEffect`), browser APIs (`window`, `document`, `localStorage`), and third-party libraries that use hooks internally.

**Do:** Start server. Push `'use client'` to the lowest possible leaf:

```tsx
// RIGHT — Server Component (default) fetches, Client Component handles interaction
async function ProductPage({ id }) {
  const product = await db.product.findUnique({ where: { id } });
  return <ProductView product={product} />; // Server: zero JS shipped
}

'use client';
function AddToCartButton({ productId }) {  // Client: only the button is JS
  return <button onClick={() => addToCart(productId)}>Add to Cart</button>;
}
```

---

# Data Fetching

**Why agents get this wrong:** Agents use `useEffect` + `fetch` + `useState` in a client component. In App Router, data fetching belongs in Server Components with `async/await` — no hooks, no loading state management, automatic streaming with Suspense.

```tsx
// WRONG — unnecessary client component
'use client';
export default function Users() {
  const [users, setUsers] = useState([]);
  useEffect(() => { fetch('/api/users').then(r => r.json()).then(setUsers); }, []);
  return <UserList users={users} />;
}

// RIGHT — Server Component, direct data access
export default async function Users() {
  const users = await db.user.findMany();
  return <UserList users={users} />;
}
```

Use Suspense boundaries for loading states. Never fetch in useEffect what you can fetch server-side.

---

# Routing and Layouts

**Why agents get this wrong:** Agents create flat page structures without shared layouts, or try to use `getLayout` patterns from Pages Router.

**Do:** The file system IS the router. Key files in each route segment:
- `page.tsx` — the route's UI (required for the route to be accessible)
- `layout.tsx` — persistent wrapper that doesn't remount on navigation
- `loading.tsx` — Suspense fallback (automatic, shows while page loads)
- `error.tsx` — error boundary for this route segment (automatic)
- `not-found.tsx` — custom 404 for this segment
- `route.ts` — API endpoint (cannot coexist with `page.tsx` in same segment)
- Route groups `(groupName)` — organize without affecting URL paths
- `template.tsx` — like layout but re-mounts on navigation (rare)

**Key mental shift:** Layouts persist across navigations. When a user navigates from `/dashboard` to `/dashboard/settings`, the dashboard layout does NOT remount — state, scroll position, and running effects all survive. This is fundamentally different from Pages Router where every navigation remounts the page.

---

# Server Actions

**Why agents get this wrong:** Agents create API routes (`route.ts`) for form submissions and mutations that should use Server Actions. Two files, manual serialization, no progressive enhancement.

**Do:** Use `'use server'` functions for mutations. They handle serialization, CSRF, and progressive enhancement automatically:

```tsx
// WRONG — unnecessary API route + client fetch
// app/api/posts/route.ts + client component with fetch()

// RIGHT — Server Action, one file
async function createPost(formData: FormData) {
  'use server';
  await db.post.create({ data: { title: formData.get('title') } });
  revalidatePath('/posts');
}

export default function NewPost() {
  return <form action={createPost}><input name="title" /><button>Create</button></form>;
}
```

Reserve `route.ts` for external API consumers and webhooks only.

---

# Caching and Revalidation

**Why agents get this wrong:** Agents either ignore caching (every request hits the database) or assume aggressive caching without understanding invalidation.

**Defaults to understand:** `fetch` is cached in App Router. `cookies()` and `headers()` opt into dynamic rendering. Understand the mental model before overriding.

**Do:** Use `revalidatePath()` or `revalidateTag()` in Server Actions after mutations. Use `{ next: { revalidate: N } }` in fetch for time-based ISR. Static where possible, dynamic where necessary. Never blanket `cache: 'no-store'` on every fetch.

---

# Middleware

**Why agents get this wrong:** Agents put business logic in middleware. Next.js middleware runs on the Edge Runtime with limited APIs — it's for routing decisions only.

**Do:** Use middleware ONLY for: redirects, rewrites, auth redirects (not full auth checks), header manipulation, geolocation routing. Keep it thin — under 50 lines. Heavy logic goes in Server Components or Server Actions.

---

# Metadata

**Why agents get this wrong:** Agents use `next/head` (Pages Router) or saget metadata entirely. App Router has a dedicated Metadata API.

**Do:** Export `metadata` object for static metadata, `generateMetadata()` async function for dynamic:

```tsx
// Static
export const metadata = { title: 'Products', description: '...' };

// Dynamic — fetches data for the title
export async function generateMetadata({ params }) {
  const product = await getProduct(params.id);
  return { title: product.name, description: product.summary };
}
```

---

# Streaming and Suspense

**Why agents get this wrong:** Agents render entire pages synchronously — the user sees nothing until ALL data loads. App Router supports streaming: fast shell renders immediately, slow data streams in progressively.

**Do:** Wrap slow data sections in `<Suspense>` with a fallback:
```tsx
export default function Dashboard() {
  return (
    <div>
      <h1>Dashboard</h1>
      <Suspense fallback={<StatsSkeleton />}>
        <SlowStats />  {/* Streams in when ready */}
      </Suspense>
      <Suspense fallback={<ChartSkeleton />}>
        <SlowChart />  {/* Independent stream */}
      </Suspense>
    </div>
  );
}
```

Each Suspense boundary streams independently. The shell renders instantly. No `loading.tsx` needed when you control it at this level.

---

# Image Optimization

**Why agents get this wrong:** Agents use raw `<img>` tags with unoptimized images. Next.js provides `next/image` with automatic optimization, lazy loading, responsive sizing, and CLS prevention.

```tsx
// WRONG — no optimization, no CLS prevention
<img src="/hero.jpg" />

// RIGHT — optimized, lazy-loaded, CLS prevented
import Image from 'next/image';
<Image src="/hero.jpg" alt="Hero" width={1200} height={600} priority />
```

Use `priority` on above-the-fold LCP images. Use `fill` with `sizes` for responsive containers. Never use external URLs without configuring `images.remotePatterns` in `next.config.js`.

---

# Server vs Client Decision

**Why agents get this wrong:** Agents don't have a clear mental model for when to use `'use client'`. They either mark everything client or try to use hooks in server components (build error).

**Decision rule:** Start server. Only add `'use client'` when you hit one of these:
- `onClick`, `onChange`, or any event handler
- `useState`, `useEffect`, `useReducer`, or any hook
- Browser-only APIs (`window`, `document`, `localStorage`)
- Third-party library that uses hooks internally

Everything else stays server. When you need client interactivity inside a server page, extract ONLY the interactive piece as a client component — not the entire page.
