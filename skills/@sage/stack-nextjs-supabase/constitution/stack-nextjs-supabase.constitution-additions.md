# Next.js + Supabase Stack — Constitution Additions

## Principles

1. The project MUST maintain two separate Supabase client factories: `createBrowserClient` for Client Components and `createServerClient` for Server Components, Server Actions, and Route Handlers. Using a single client across both contexts is forbidden.
2. A Next.js middleware MUST exist that calls `supabase.auth.getUser()` on every request to refresh expired tokens and sync cookies. Deploying without this middleware is forbidden.
3. Server-side auth checks MUST use `supabase.auth.getUser()` (server-verified). Using `supabase.auth.getSession()` alone for authorization in server code is forbidden — it reads the JWT without verification.
4. Row Level Security MUST be enabled on every table. Every `CREATE TABLE` migration MUST include `ENABLE ROW LEVEL SECURITY`, at least one policy, and indexes on columns used in policies.
5. The `service_role` key MUST NEVER appear in client-side code or `NEXT_PUBLIC_` environment variables. It is restricted to server-side code (Server Actions, Route Handlers) that explicitly requires admin access.
6. Database types MUST be generated from the schema (`supabase gen types`) and used for all queries. Untyped `select('*')` without type annotations is forbidden. Types MUST be regenerated after every migration.
