---
name: "stack-flutter-firebase"
description: "Integration patterns for Flutter + Firebase + Riverpod — auth, Firestore, Cloud Functions, project structure"
version: "1.0.0"
type: composite
layer: stack
requires:
  sage: ">=1.0.0"
  skills:
    - "mobile"
    - "flutter"
activates-when:
  detected: [flutter, firebase_core]
tags: [flutter,firebase_core]
---

# stack-flutter-firebase

**Layer 3 — Stack Composition**

Integration patterns for the most common Flutter fullstack combination:
Flutter + Firebase (Auth, Firestore, Cloud Functions, Storage) + Riverpod.

## Philosophy

Firebase documentation explains each service in isolation. Riverpod docs explain
state management in isolation. Neither explains: how Firebase Auth state feeds
into Riverpod providers, how Firestore streams compose with Riverpod's reactive
model, how to structure a project where Firebase is the backend and Riverpod
manages the entire state tree.

These seams are where this pack provides value.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Integration | 4 | Firebase Auth + Riverpod, Firestore + Riverpod, Cloud Functions patterns, project structure |
| Anti-patterns | 3 | Direct Firebase in widgets, unstructured Firestore, no security rules |
| Constitution | 1 | 4 stack integration principles |
