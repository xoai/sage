# BaaS — Constitution Additions

## Principles

1. Security rules / Row-Level Security MUST be written and tested BEFORE client code that accesses the data ships. Default test-mode rules (`allow read, write: if true` / RLS disabled) MUST NOT exist in any deployed environment. Rules are the authorization layer — client checks are UX only.
2. All database operations MUST use the client SDK directly unless the operation requires secrets, complex server-side validation, elevated privileges, or third-party API calls. Building a REST API proxy in serverless functions when the client SDK suffices is forbidden.
3. Data models MUST be designed for the application's primary query patterns, not for normalization purity. In NoSQL BaaS, denormalization is expected — if a screen needs data from what would be two SQL tables, that data SHOULD be embedded or co-located to satisfy the read in one query.
4. All database reads and writes MUST use typed models with serialization at the boundary (Firestore converters, Supabase generated types). Reading raw untyped objects (`doc.data()['fieldName']`) throughout the codebase is forbidden.
5. Real-time listeners MUST be used for any data the user is actively viewing that can change. One-time fetches with manual polling SHOULD be used only for truly static data. All listeners MUST be unsubscribed when the component unmounts or navigates away.
6. Platform authentication (Firebase Auth / Supabase Auth) MUST be used for all user authentication. Custom JWT generation or password hashing MUST NOT be implemented when platform auth is available. Role assignments MUST be set server-side via custom claims or app_metadata — never client-set.
7. All collection queries MUST be paginated. Reading an entire collection without limits is forbidden. Billing alerts MUST be configured before production deployment.
8. Serverless function trigger chains MUST be audited for infinite loops before deployment. A function that writes to a collection it is triggered by MUST include explicit loop prevention.
