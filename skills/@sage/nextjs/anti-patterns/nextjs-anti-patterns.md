# Anti-Pattern: Pages Router Contamination

**What agents do:** Generate `getServerSideProps`, `getStaticProps`, `getInitialProps`, or `next/head` in App Router projects.

**Why agents do this:** Training data is dominated by Pages Router content (2016-2023). App Router was only introduced in Next.js 13.4 (May 2023). Most tutorials, Stack Overflow answers, and blog posts still show Pages Router patterns.

**Why it's wrong:** These are Pages Router APIs that don't exist in App Router. They cause build errors or silently do nothing. Do instead: Server Components for data fetching, Metadata API for head tags.

---

# Anti-Pattern: 'use client' on Everything

**What agents do:** Add `'use client'` to every component "just in case," or at the page level instead of at the leaf component that needs interactivity.

**Why agents do this:** Pre-RSC React was 100% client-side. Agents trained on this default to client components and only encounter errors ("cannot use useState in a server component") that they "fix" by adding `'use client'` at the top.

```tsx
// WRONG — entire page is client, can't use async, ships all JS
'use client';
export default function ProductPage() { ... }

// RIGHT — page is server, only interactive parts are client
export default async function ProductPage() {
  const product = await db.product.findUnique(...);
  return <div><ProductInfo product={product} /><AddToCartButton id={product.id} /></div>;
}
```

**Why it's wrong:** Client components ship JavaScript to the browser, lose streaming, can't access server-only resources. Push `'use client'` to the lowest leaf.

---

# Anti-Pattern: useEffect for Data Fetching

**What agents do:** Create client components with `useEffect` + `fetch('/api/...')` + `useState` for loading/error/data. The single most common agent mistake in App Router.

**Why it's wrong:** Requires an unnecessary API route, adds client JS, loses SSR, needs manual loading/error states. A Server Component with `async/await` does the same thing in 3 lines with zero client JS. Do instead: `async function Page() { const data = await db.query(); return <View data={data} />; }`

---

# Anti-Pattern: API Routes for Internal Mutations

**What agents do:** Create `app/api/*/route.ts` handlers for form submissions and data mutations called from the same application.

**Why it's wrong:** Server Actions replace internal API routes. They handle serialization, CSRF protection, and progressive enhancement automatically. Do instead: `'use server'` functions called directly from forms or `startTransition`. Reserve `route.ts` for external consumers.

---

# Anti-Pattern: Incorrect Caching Assumptions

**What agents do:** Either add `cache: 'no-store'` to every fetch (disabling all caching) or assume everything is cached forever without invalidation.

**Why it's wrong:** Both extremes are wrong. Do instead: Understand defaults — `fetch` is cached, dynamic functions opt out. Use `revalidateTag`/`revalidatePath` in Server Actions after mutations. Static where possible, dynamic where necessary.

---

## Old Patterns (Deprecated Reference)

<details>
<summary>Pages Router APIs — deprecated in App Router (Next.js 13.4+, May 2023)</summary>

These APIs belong to the Pages Router (`pages/` directory) and MUST NOT appear
in App Router (`app/` directory) code:

| Pages Router (deprecated) | App Router replacement |
|--------------------------|----------------------|
| `getServerSideProps` | Server Components with `async/await` |
| `getStaticProps` | Server Components + `generateStaticParams` |
| `getInitialProps` | Server Components (no equivalent needed) |
| `next/head` | `export const metadata` or `generateMetadata()` |
| `next/router` (useRouter from pages) | `next/navigation` (useRouter, usePathname, useSearchParams) |
| `_app.tsx` / `_document.tsx` | Root `layout.tsx` |
| `next/link` with `<a>` child | `next/link` renders `<a>` automatically since Next.js 13 |
| `next/image` with `layout` prop | `next/image` with `fill` prop (layout was removed in 13) |

If you see these in generated code for an `app/` directory project, the agent
is drawing from stale training data. Correct to the App Router equivalent.
</details>

<details>
<summary>React Class Component patterns — deprecated since React 16.8 (Feb 2019)</summary>

Agents occasionally generate class components or class-era lifecycle methods
when hooks are the correct modern approach:

| Class pattern (deprecated) | Hooks replacement |
|---------------------------|------------------|
| `componentDidMount` | `useEffect(() => { ... }, [])` |
| `componentDidUpdate` | `useEffect(() => { ... }, [deps])` |
| `componentWillUnmount` | `useEffect(() => { return () => cleanup }, [])` |
| `this.setState` | `useState` / `useReducer` |
| `this.state` | `useState` initial value |
| `getDerivedStateFromProps` | Usually unnecessary; use `useMemo` or derive in render |
| Higher-Order Components | Custom hooks |
| Render props | Custom hooks |

Class components still work in React but SHOULD NOT be generated for new code.
</details>
