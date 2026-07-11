# Stack Flutter Firebase — Constitution Additions

## Stack Integration Principles

1. Firebase services MUST be accessed through a repository layer, never directly from widgets. Widgets depend on Riverpod providers. Providers depend on repositories. Repositories depend on Firebase. This separation enables testing, offline support, and potential backend migration.
2. Firebase Auth state MUST be the single source of truth for authentication, exposed via a Riverpod StreamProvider. All auth-dependent providers MUST chain from this auth provider — never independently check Firebase Auth state.
3. Firestore security rules MUST be written and tested BEFORE client code is deployed. Client-side validation is UX convenience only — Firestore rules are the actual security boundary. Never assume the client enforces access control.
4. All Firestore document reads MUST use the repository pattern with explicit data models (fromFirestore/toFirestore). Raw Map<String, dynamic> MUST NOT propagate beyond the repository layer — type-safe models are mandatory in the domain and presentation layers.
