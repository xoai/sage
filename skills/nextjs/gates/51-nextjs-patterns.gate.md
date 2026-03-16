---
name: 51-nextjs-patterns
order: 51
category: compliance
version: "1.0.0"
modes: [build, architect]
---

# Gate 51: Next.js Pattern Compliance

Verifies that the implementation follows App Router patterns and doesn't
contain Pages Router contamination or client-component overuse.

## Check Criteria

### Pages Router Contamination (FAIL if any found)
- No `getServerSideProps`, `getStaticProps`, `getInitialProps` in any file
- No files in `pages/` directory (except `pages/api/*` if intentional hybrid)
- No `_app.tsx`, `_document.tsx`, `_error.tsx` files
- No imports from `next/router` — use `next/navigation` instead

### Client Component Discipline (FAIL if threshold exceeded)
- Ratio of `'use client'` files to total component files should be < 40%
- No `'use client'` on page.tsx or layout.tsx files (except when required)
- No useEffect-based data fetching in components that could be server components

### Data Fetching (FAIL if patterns violated)
- Server-rendered pages fetch data in the server component, not via API calls
- No `fetch('/api/...')` in server components (access the data source directly)
- Caching strategy explicitly declared (revalidate or dynamic) per route

### Image and Link Compliance (FAIL if raw tags found)
- No `<img>` tags — use `next/image`
- No `<a>` tags for internal navigation — use `next/link`

## Failure Response

On FAIL: Identify the specific violation, explain the correct App Router pattern,
and provide a concrete code fix. The implementer must fix before proceeding.

## Adversarial Guidance

The implementer may claim:
- "I need useEffect for this data fetch" → Challenge: Can this be a server component?
- "The whole page needs 'use client'" → Challenge: Can the interactive part be extracted?
- "I'm using a custom API route for convenience" → Challenge: Would a server action work?

Probe each claim. Most can be resolved with App Router patterns.
