---
name: "baas"
description: "Corrects the most common BaaS architecture mistakes agents make — security rules as authorization, data modeling for queries, minimizing serverless functions, real-time by default, and client-direct access patterns. Applies to Firebase, Supabase, and similar platforms."
version: "1.0.0"
type: knowledge
layer: domain
requires:
  sage: ">=1.0.0"
activates-when:
  detected: [firebase, @firebase/app, @supabase/supabase-js, supabase, firebase-admin, @angular/fire, reactfire, flutterfire]
tags: [firebase,@firebase/app,@supabase/supabase-js,supabase,firebase-admin]
---

# baas

**Layer 1 — Domain Foundation**

Universal Backend-as-a-Service principles that apply regardless of platform.
Firebase, Supabase, Appwrite — these principles hold.

## Philosophy

BaaS is a fundamentally different architecture from custom backends. There are
no controllers, no middleware, no routes. The client talks directly to platform
services, and security rules replace the API layer. Agents trained on custom
backend patterns (Express, Django) apply those patterns to BaaS — building REST
APIs in Cloud Functions, normalizing data for a database that can't JOIN, and
treating security as a client-side concern. Every pattern in this pack corrects
a specific failure that arises from applying custom-backend thinking to BaaS.

## What's Included

| Type | Count | Coverage |
|------|-------|----------|
| Patterns | 8 | Security rules as auth, data modeling for queries, minimize functions, real-time by default, platform auth, offline support, typed models, cost management |
| Anti-patterns | 7 | Open rules in production, REST API in functions, client-side auth, relational normalization in NoSQL, untyped raw data, one-time fetches everywhere, no billing awareness |
| Constitution | 8 | principles |

Grounded in: Firebase official docs, Supabase official docs, Firebase security
checklist, ModernPentest security research (2024-2025), Fireship data modeling
guides, and community best practices.

## Activation

Loads when the project is detected as using a BaaS platform (Firebase SDK,
Supabase client, or similar in dependencies).

## What This Pack Does NOT Cover

- Platform-specific API details (see future `firebase`, `supabase`)
- Framework integration patterns (see `stack-flutter-firebase`, etc.)
- Custom backend patterns (see `api` for custom API development)
