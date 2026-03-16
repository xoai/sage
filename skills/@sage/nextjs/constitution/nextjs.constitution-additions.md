# Next.js Extension — Constitution Additions

## Next.js Principles

1. All components are server components by default. Only add `'use client'` when the component needs event handlers, hooks, or browser APIs. When in doubt, keep it on the server.
2. All images MUST use `next/image`. All internal navigation MUST use `next/link`. No raw `<img>` or `<a>` tags for internal assets and routes.
3. Data fetching for page rendering MUST happen in server components using async/await, NOT in client components using useEffect. Client-side fetching is only for post-load interactivity.
4. All mutations MUST use server actions (functions marked with `'use server'`), NOT custom API route handlers, unless the mutation requires streaming, webhooks, or third-party callback URLs.
5. Pages Router patterns (getServerSideProps, getStaticProps, getInitialProps, pages/ directory routing) MUST NOT appear in App Router code. These are legacy patterns.
6. Route segment configuration (dynamic, revalidate, runtime) MUST be explicitly set per route based on the data freshness requirements — never rely on implicit defaults.
