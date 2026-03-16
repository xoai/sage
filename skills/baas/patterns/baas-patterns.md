# Security Rules ARE Your Authorization Layer

**Why agents get this wrong:** Agents write client-side auth checks (`if (user.role === 'admin')`) and treat the database as trusted. In BaaS, the database is directly accessible from the client — any user with your project config can call it. Security rules are the ONLY server-side enforcement. In 2024, 916 Firebase sites exposed 125 million records due to misconfigured rules.

**Do:** Write rules BEFORE client code. Default deny, open selectively:
```
// Firestore
match /posts/{postId} {
  allow read: if request.auth != null;
  allow create: if request.auth != null
    && request.resource.data.authorId == request.auth.uid;
  allow update, delete: if resource.data.authorId == request.auth.uid;
}

// Supabase RLS
CREATE POLICY "Users read own data" ON profiles
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users update own data" ON profiles
  FOR UPDATE USING (auth.uid() = user_id);
```

Rules validate data shape too — check required fields, types, value bounds. Client validation is UX; rules are security. Test rules with emulators before deployment. Deploy rules in CI/CD alongside client code.

---

# Model Data for Query Patterns, Not Normalization

**Why agents get this wrong:** Agents normalize data like a relational DB — separate tables for everything, foreign keys, third normal form. In NoSQL BaaS, you can't JOIN. Every query hits one collection. Data structure must match your screens.

**Do:** Ask "what will the UI show?" then structure data to answer that in ONE read:
- Post needs author name + avatar? Embed them on the post document (accept duplication)
- User's posts always shown together? Subcollection (`users/{uid}/posts`)
- Need to query ALL posts across users? Root collection with `authorId` field
- Keep documents small (< 1MB). Move large lists to subcollections

**Denormalization rules of thumb:**
- Data read together → store together
- Data queried across parents → root collection with reference IDs
- Frequently changing shared data (username) → duplicate sparingly, sync via triggers
- Many-to-many → junction collection with composite keys (`userId_groupId`)

For Supabase (PostgreSQL): you CAN join, so leverage relational strengths. But still design primary tables for your read patterns. Use views or RPC functions for complex queries rather than multi-step client fetches.

---

# Minimize Serverless Functions

**Why agents get this wrong:** Agents build a full REST API in Cloud Functions / Edge Functions, proxying every database operation through server code. This defeats BaaS — the client SDK provides direct, cached, offline-capable, real-time database access. Routing through functions loses all of that.

**Do:** Client SDK for all standard CRUD. Functions ONLY for:
- **Secrets:** Operations needing API keys the client must never see (payments, email, third-party APIs)
- **Complex validation:** Business logic too complex for security rules (cross-collection checks, external verification)
- **Triggers:** Respond to data changes (send notification on new message, update aggregation counters, sync denormalized fields)
- **Scheduled tasks:** Periodic cleanup, report generation, billing
- **Admin operations:** Bulk deletes, migrations, elevated-privilege operations

If you can do it with security rules + client SDK, don't write a function. Every function adds cold start latency, costs per invocation, and loses offline support.

---

# Design for Real-Time by Default

**Why agents get this wrong:** Agents use one-time fetches for everything, then poll every 30 seconds for updates. BaaS platforms provide real-time subscriptions out of the box — data pushes to clients instantly.

**Do:** Real-time listeners for any data the user is actively viewing:
```ts
// Firestore
const unsubscribe = onSnapshot(
  query(collection(db, 'messages'), orderBy('createdAt', 'desc'), limit(50)),
  (snapshot) => { /* updates push automatically */ }
);

// Supabase
const channel = supabase.channel('messages')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'messages' },
    (payload) => { /* updates push automatically */ })
  .subscribe();
```

One-time fetches only for static data (historical reports, completed orders). Unsubscribe when component unmounts — leaked listeners waste bandwidth and memory. For Supabase, enable real-time only on tables that need it.

---

# Use Platform Auth, Don't Build Your Own

**Why agents get this wrong:** Agents implement custom JWT generation, password hashing, session management from scratch. BaaS platforms provide battle-tested auth that integrates with security rules automatically — custom auth can't use `request.auth.uid` or `auth.uid()` without complex token bridging.

**Do:** Use Firebase Auth or Supabase Auth. You get for free: password hashing (bcrypt/scrypt), email verification, password reset, OAuth providers (Google, Apple, GitHub), session management, token refresh, and rate limiting on auth endpoints.

Use custom claims / app_metadata for roles — set them server-side via Admin SDK or database triggers. Never let clients set their own role:
```ts
// Firebase — set custom claim server-side
await auth.setCustomUserClaims(uid, { role: 'admin' });
// Rule: request.auth.token.role == 'admin'

// Supabase — app_metadata set via service_role
await supabase.auth.admin.updateUserById(uid, { app_metadata: { role: 'admin' } });
// RLS: auth.jwt() ->> 'role' = 'admin'
```

---

# Enable and Design for Offline Support

**Why agents get this wrong:** Agents build BaaS apps assuming constant connectivity — every action needs a network round-trip, failures show error screens, no data available offline. Both Firebase and Supabase provide offline caching that agents never enable.

**Do:** Enable offline persistence (Firebase: default on mobile, opt-in web; Supabase: local-first libraries). Design every screen to render from cache first, update when network data arrives. Show "last updated" instead of error screens when offline.

For writes: queue mutations locally and sync on reconnect (Firebase does this automatically). Design data so offline writes don't conflict — append-only patterns or last-write-wins. Show pending state for unsynced writes so users know what hasn't been confirmed yet.

---

# Typed Models, Not Raw Maps

**Why agents get this wrong:** Agents read and write database records as raw untyped objects — `doc.data()['name']` or bare `data.name`. No type safety, no validation, field name typos cause silent bugs at runtime.

**Do:** Define typed models with serialization at the boundary:
```ts
// Firestore converter
const productConverter = {
  toFirestore: (p: Product) => ({ name: p.name, price: p.price, ownerId: p.ownerId }),
  fromFirestore: (snap): Product => ({ id: snap.id, ...snap.data() as Omit<Product, 'id'> }),
};
const ref = collection(db, 'products').withConverter(productConverter);

// Supabase — generate types from schema
// npx supabase gen types typescript > types/database.ts
type Product = Database['public']['Tables']['products']['Row'];
const { data } = await supabase.from('products').select('*').returns<Product[]>();
```

All reads through converters/types. All writes use typed objects. Field typos become compile errors.

---

# Manage Costs by Understanding the Billing Model

**Why agents get this wrong:** Agents build features without considering BaaS charges per operation, not per GB stored. A query reading 10,000 documents to display 10 wastes 999x the cost. Agents create infinite trigger loops and unbounded listeners.

**Do:** Design to minimize operations:
- Paginate all queries — never read entire collections
- Use `select()` / field masks to fetch only needed fields
- Aggregate counters via triggers instead of `COUNT(*)` on every page load
- Set billing alerts from day one — costs spike overnight from bugs
- Never create infinite trigger loops (function writes doc → triggers same function)
- Create composite indexes proactively (Firestore) — missing indexes force full scans
- For Supabase, monitor connection pool limits and disk usage
