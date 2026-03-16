# Anti-Pattern: Open Security Rules in Production

**What agents do:** Leave database in test mode (`allow read, write: if true` / RLS disabled) during development, then ship to production without changing rules.

**Why agents do this:** Security rules are a separate file in a separate language. Agents are asked to "build the feature," not "secure the database." Test mode rules work during development, so the agent never encounters an error that forces it to write real rules.

**Why it's wrong:** The database is directly accessible from the client. ANY user with your Firebase config or Supabase anon key can read, write, and delete ALL data. Client-side checks are trivially bypassed. This is the #1 BaaS security vulnerability — responsible for hundreds of millions of leaked records. Do instead: Write rules before client code. Default deny. Test with emulator suite. Deploy rules in CI/CD.

---

# Anti-Pattern: Building a REST API in Functions

**What agents do:** Create a Cloud Function / Edge Function for every CRUD operation: `createUser`, `getUsers`, `updateUser`, `deleteUser`. The client calls functions via HTTP, which call the database, format the response, and return it.

**Why agents do this:** This is how agents build custom backends (Express, Django). They apply the same pattern to BaaS, not realizing the client SDK already provides direct database access with caching, real-time, and offline support.

**Why it's wrong:** Loses real-time subscriptions, offline support, client-side caching, and automatic security rule enforcement. Adds cold start latency (200ms-3s) to every request. Functions use the Admin SDK which bypasses security rules — you must reimplement authorization in every function. Costs more (function invocation + database read vs just database read). Do instead: Client SDK for CRUD, functions only for secrets, triggers, and complex server-side logic.

---

# Anti-Pattern: Client-Side Authorization

**What agents do:** Check permissions in the client code: `if (user.role === 'admin') { showDeleteButton(); }`. The delete button is hidden, but the database operation has no server-side protection.

**Why agents do this:** In traditional web apps with a custom backend, the server handles authorization. In BaaS, the "server" is security rules, which agents haven't written. So they put the checks where they know how — in client code.

**Why it's wrong:** Any user can open browser DevTools, modify the client code, and call the database directly. Client checks are UX (don't show buttons users can't use), not security. Do instead: Security rules/RLS enforce every permission. Client UI reflects what rules allow, but rules are the actual gate.

---

# Anti-Pattern: Relational Normalization in NoSQL

**What agents do:** Create separate Firestore collections for every entity with reference IDs, then query collection A, loop through results to query collection B per item, then query collection C for each B result. Three separate queries to render one screen.

**Why agents do this:** Normalization is deeply ingrained from SQL training data. "Don't duplicate data" is treated as a universal rule. Agents apply third normal form to a database that can't JOIN.

**Why it's wrong:** Firestore has no joins. Each collection query is a separate round-trip. N separate lookups for N items means N+1 queries, linear cost growth, and slow screens. Do instead: Denormalize for your read patterns. Embed related data on the document. Accept duplication — sync with triggers when source data changes.

---

# Anti-Pattern: Untyped Raw Data Throughout

**What agents do:** Read `doc.data()` and access fields by string keys everywhere: `data['userName']`, `data['pricce']` (typo). Write raw objects with no validation: `setDoc(ref, { name, price, ... })`.

**Why agents do this:** BaaS SDKs return plain objects by default. The agent gets data, uses it directly, and moves on. Adding a converter/type layer feels like unnecessary boilerplate.

**Why it's wrong:** Field name typos are silent — return `undefined` instead of crashing. Wrong types cause runtime errors in unexpected places. Refactoring a field name requires grep-and-pray across the codebase. Do instead: Typed models with converters at the boundary. Supabase: generate types from schema. Firestore: `withConverter()` on every collection reference.

---

# Anti-Pattern: One-Time Fetches Everywhere

**What agents do:** Use `getDocs()` / `.select()` for all data loading. Poll every 30 seconds for updates. Users see stale data until the next poll cycle.

**Why agents do this:** One-time fetches are the familiar pattern from REST API development. Agents don't think to use real-time subscriptions because their training data is dominated by request-response patterns.

**Why it's wrong:** Wastes the platform's strongest feature. Users see stale data. Polling at scale costs more than subscriptions. Do instead: Real-time listeners (`onSnapshot`, `.subscribe()`) for any data the user is actively viewing. One-time fetch only for truly static data.

---

# Anti-Pattern: No Billing Awareness

**What agents do:** Build features that read entire collections, trigger functions on every document write, create real-time listeners on large tables, and deploy without billing alerts. First production spike results in a surprise bill.

**Why agents do this:** Development uses the emulator (free) or free tier. The agent never encounters cost signals during development. BaaS billing models (per-operation, per-function-invocation) are fundamentally different from flat-rate hosting.

**Why it's wrong:** A single bug (infinite trigger loop, unbounded query, leaked listener) can generate thousands of dollars in charges overnight. Do instead: Paginate all queries, set billing alerts from day one, test with production-like data volumes, audit trigger chains for loops.
