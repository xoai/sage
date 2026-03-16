# Pack Tests: nextjs

**Framework version tested:** Next.js 15.x (App Router)
**Last tested:** 2025-03-13

---

## Test 1: Data fetching component

**Prompt:**
```
Create a component that fetches and displays a list of blog posts from the database.
```

**Without pack:** Agent creates a client component with 'use client', useState,
useEffect, and fetch('/api/posts'). Adds loading and error states manually.

**With pack:** Agent creates an async Server Component that queries the database
directly. No 'use client', no useState, no useEffect. Uses Suspense for loading.

**Tests:** Pattern "Server-First Data Fetching" + Anti-pattern "useEffect for data fetching"

---

## Test 2: Form submission

**Prompt:**
```
Add a form to create a new blog post with title and content fields.
```

**Without pack:** Agent creates an API route at /api/posts with POST handler,
then a client component with fetch() to call it. Two files, manual error handling.

**With pack:** Agent creates a Server Action (inline or in a separate actions file),
uses it directly in the form's action prop. One pattern, progressive enhancement.

**Tests:** Pattern "Server Actions" + Anti-pattern "API routes for internal mutations"

---

## Test 3: Layout with shared data

**Prompt:**
```
Create a dashboard layout with a sidebar showing the current user's name
and a main content area for child pages.
```

**Without pack:** Agent might use getServerSideProps (Pages Router pattern),
or create a context provider with 'use client' wrapping the layout.

**With pack:** Agent creates an async layout.tsx that fetches user data
server-side, passes it to a sidebar component. No client-side data fetching
for data that's available at request time.

**Tests:** Pattern "Server Components by default" + Anti-pattern "Pages Router contamination"

---

## Test 4: Dynamic page with metadata

**Prompt:**
```
Create a blog post detail page at /blog/[slug] with proper SEO metadata.
```

**Without pack:** Agent may use next/head (Pages Router), or saget metadata
entirely, or generate it client-side.

**With pack:** Agent uses generateMetadata() async function, fetches post data
for dynamic title/description, uses the Metadata API correctly.

**Tests:** Pattern "Metadata API"

---

## Test 5: Caching behavior

**Prompt:**
```
The blog post list should update within 60 seconds of a new post being published.
```

**Without pack:** Agent adds no-store to fetch, or uses client-side polling,
or doesn't address caching at all.

**With pack:** Agent uses revalidate option (ISR) with a 60-second interval,
or uses revalidatePath/revalidateTag in the Server Action that creates posts.

**Tests:** Pattern "Caching and Revalidation" + Anti-pattern "Incorrect caching assumptions"
