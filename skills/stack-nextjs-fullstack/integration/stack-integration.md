# Prisma + Next.js: Client Singleton

**Why agents get this wrong:** Agents write `new PrismaClient()` in each file. Hot reload re-executes module code → connection pool exhaustion after a few edits.

**Do:** One singleton using the globalThis pattern:
```ts
// lib/db.ts
const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };
export const db = globalForPrisma.prisma || new PrismaClient();
if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = db;
```

Import `db` everywhere. Never `new PrismaClient()` directly.

**Where Prisma can be used** (requires Node.js — never in client components):
```tsx
// Server Component (data fetching)
export default async function UsersPage() {
  const users = await db.user.findMany();
  return <UserList users={users} />;
}

// Server Action (mutations)
'use server';
export async function createUser(formData: FormData) {
  await db.user.create({ data: { name: formData.get('name') as string } });
  revalidatePath('/users');
}

// Route Handler (webhooks, external APIs only)
export async function POST(request: Request) {
  const data = await request.json();
  await db.event.create({ data });
  return Response.json({ ok: true });
}
```

**Data access layer:** Don't scatter queries across components. Centralize:
```
lib/db.ts              → Prisma singleton
lib/data/users.ts      → getUserById, listUsers, createUser
lib/data/products.ts   → getProduct, searchProducts
```

---

# Auth.js + Next.js: Three-Layer Auth

**Why agents get this wrong:** Agents check auth only in middleware or only in pages. All three layers must check independently — defense in depth.

**Setup:**
```tsx
// lib/auth.ts
export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PrismaAdapter(db),
  providers: [...],
  callbacks: {
    session: ({ session, user }) => ({
      ...session, user: { ...session.user, id: user.id },
    }),
  },
});

// app/api/auth/[...nextauth]/route.ts
import { handlers } from '@/lib/auth';
export const { GET, POST } = handlers;
```

**Layer 1 — Middleware (route protection):**
```tsx
export default auth((req) => {
  if (!req.auth && req.nextUrl.pathname.startsWith('/dashboard'))
    return Response.redirect(new URL('/login', req.nextUrl));
});
export const config = { matcher: ['/dashboard/:path*', '/settings/:path*'] };
```

**Layer 2 — Server Component (data scoping):**
```tsx
export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user) redirect('/login');
  const projects = await db.project.findMany({
    where: { userId: session.user.id },  // Scope data to user
  });
  return <Dashboard projects={projects} />;
}
```

**Layer 3 — Server Action (mutation authorization):**
```tsx
'use server';
export async function deleteProject(projectId: string) {
  const session = await auth();
  if (!session?.user) throw new Error('Unauthorized');
  const project = await db.project.findUnique({ where: { id: projectId } });
  if (project?.userId !== session.user.id) throw new Error('Forbidden');
  await db.project.delete({ where: { id: projectId } });
  revalidatePath('/dashboard');
}
```

Never rely on middleware alone. Middleware protects routes. Server components scope data. Server actions verify ownership.

---

# Tailwind + Next.js: No Dynamic Classes

**Why agents get this wrong:** Agents write `bg-${color}-500`. Tailwind scans source for complete class strings at build time — dynamic interpolation produces classes Tailwind never sees → missing styles in production.

```tsx
// WRONG — Tailwind never sees "bg-blue-500" as a complete string
<button className={`bg-${color}-500`} />

// RIGHT — complete strings in a variant map
const variants = { primary: 'bg-blue-500 text-white', danger: 'bg-red-500 text-white' };
<button className={variants[variant]} />
```
