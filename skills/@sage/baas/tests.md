# Pack Tests: @sage/baas

**Framework version tested:** Universal (Firebase, Supabase)
**Last tested:** 2026-03-13

---

## Test 1: Basic CRUD App

**Prompt:**
```
Build a task management app with Firebase/Supabase where users can create, read, update, and delete their own tasks.
```

**Without pack:** Creates Cloud Functions for every CRUD operation. No security rules. Client calls functions via HTTP. No real-time updates. Raw `doc.data()` throughout.

**With pack:** Client SDK direct access with security rules enforcing ownership (`authorId == auth.uid`). Real-time listener on the task list. Typed Task model with converter. Rules written first.

**Tests:** Patterns "Security Rules" + "Minimize Functions" + "Real-Time" + "Typed Models"

---

## Test 2: Chat Feature

**Prompt:**
```
Add real-time chat to an existing app. Users can send messages in chat rooms.
```

**Without pack:** One-time fetch with 5-second polling. Messages stored as array on room document. No pagination. No offline support.

**With pack:** Real-time listener on messages subcollection. Messages as subcollection under rooms (not array on room doc). Cursor-based pagination for history. Offline persistence enabled. Security rules: authenticated users can read room messages, only message author can edit/delete.

**Tests:** Patterns "Real-Time" + "Data Modeling" + "Security Rules" + "Offline Support"

---

## Test 3: Role-Based Access

**Prompt:**
```
Create an admin dashboard where admins can manage all users but regular users can only see their own data.
```

**Without pack:** Client-side `if (user.role === 'admin')` check. No security rules for role distinction. Admin role stored in user-editable document field.

**With pack:** Custom claims set server-side (`auth.setCustomUserClaims`). Security rules check `request.auth.token.role == 'admin'`. Admin operations use security rules, not client checks. Client UI reflects role but doesn't enforce it.

**Tests:** Patterns "Security Rules" + "Platform Auth" + Anti-pattern "Client-Side Authorization"

---

## Test 4: E-commerce Product Catalog

**Prompt:**
```
Build a product listing with categories, search, and user reviews using Firestore.
```

**Without pack:** Normalized: separate collections for products, categories, reviews. N+1 queries to assemble product cards. No pagination. Price stored as string.

**With pack:** Category name embedded on product document (denormalized). Reviews as subcollection. Pagination with cursor tokens. Composite indexes created proactively. Typed Product model. Aggregated reviewCount/avgRating on product doc updated via trigger.

**Tests:** Patterns "Data Modeling" + "Typed Models" + "Cost Management" + Anti-pattern "Relational Normalization"

---

## Test 5: Production Readiness Review

**Prompt:**
```
Review this BaaS app and make it production-ready.
```

**Without pack:** Adds error handling. Maybe adds loading states. Misses security rules audit, billing alerts, offline support, real-time optimization, type safety.

**With pack:** Audits security rules for coverage (every collection has explicit rules). Sets billing alerts. Enables offline persistence. Converts one-time fetches to real-time where appropriate. Adds typed models. Verifies no infinite trigger loops. Checks function usage for unnecessary proxying. Reviews data model for N+1 patterns.

**Tests:** All patterns — comprehensive production readiness check
