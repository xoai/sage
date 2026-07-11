---
name: "flutter"
description: "Flutter patterns — widget architecture, state management, Impeller renderer, platform-adaptive design"
version: "1.0.0"
type: knowledge
layer: framework
requires:
  sage: ">=1.0.0"
  skills:
    - "mobile"
activates-when:
  detected: [flutter, firebase_core]
tags: [flutter, firebase, riverpod]
---

# flutter

**Layer 2 — Framework Pack**

Flutter patterns for modern development (3.x+). Widget architecture, state
management, Impeller renderer, platform-adaptive design, and the common
mistakes agents make from outdated tutorials.

## Philosophy

Flutter's "everything is a widget" model is simultaneously its greatest strength
and the main source of agent mistakes. Agents build monolithic widget trees with
thousands of lines, misuse `setState` for everything, nest widgets 15 levels
deep, and ignore the widget lifecycle. This pack establishes clean widget
architecture, proper state management selection, and Impeller-era performance
patterns.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Patterns | 7 | Widget architecture, state management, async/data, navigation, platform-adaptive, testing, performance |
| Anti-patterns | 5 | God widgets, setState everywhere, ignoring dispose, hardcoded dimensions, unnecessary packages |
| Constitution | 1 | 5 Flutter-specific principles |
| Gate | 1 | Flutter pattern compliance check |

## Stack Integrations (detection-gated)

When `firebase_core` is detected, read `integration/firebase-integration.md` for
the Flutter + Firebase + Riverpod seams — auth, Firestore, Cloud Functions, and
project structure — that the individual docs don't cover together. This folds in
the former `stack-flutter-firebase` skill; the content is unchanged.
Constitution: `constitution/firebase.constitution-additions.md` ·
anti-patterns: `anti-patterns/firebase-anti-patterns.md`.
