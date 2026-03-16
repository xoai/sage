---
name: "@sage/stack-react-native-expo"
description: "Integration patterns for Expo + React Navigation + Zustand + MMKV + TanStack Query"
version: "1.0.0"
type: composite
layer: stack
requires:
  sage: ">=1.0.0"
  skills:
    - "@sage/mobile"
    - "@sage/react"
    - "@sage/react-native"
activates-when:
  detected: [expo, react-native]
tags: [expo,react-native]
---

# @sage/stack-react-native-expo

**Layer 3 — Stack Composition**

Integration patterns for the most common React Native stack:
Expo + Expo Router/React Navigation + Zustand + MMKV + TanStack Query.

## Philosophy

Each tool's docs explain how it works alone. They don't explain how they work
together: where the Zustand store plugs into the navigation guard, how MMKV
persistence integrates with Zustand hydration, how TanStack Query's cache
interacts with offline state, how Expo Router layouts compose with auth flows.

These integration seams are where bugs live. This pack documents the gaps.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Integration | 4 | Expo Router + auth, Zustand + MMKV persistence, TanStack Query + offline, project structure |
| Anti-patterns | 3 | Auth in wrong layer, store hydration race, query key chaos |
| Constitution | 1 | 4 stack integration principles |
