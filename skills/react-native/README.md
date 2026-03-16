# react-native

**Layer 2 — Framework Pack**

React Native patterns for the New Architecture era (0.76+). Fabric, TurboModules,
Expo, navigation, and the mistakes agents make from old Bridge-era training data.

## Philosophy

React Native underwent a fundamental architectural shift. The old Bridge
(async JSON serialization between JS and native) is replaced by JSI (direct
synchronous C++ references). Fabric replaces the old UI Manager. TurboModules
replace legacy Native Modules. Starting from RN 0.82, the New Architecture
is always-on and can't be disabled.

LLMs trained on 2018-2023 content produce Bridge-era patterns: old lifecycle
methods, legacy navigation libraries, manual native module boilerplate. This
pack establishes New Architecture as the baseline and corrects stale patterns.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Patterns | 7 | New Architecture, Expo workflow, navigation, state management, native modules, lists, styling |
| Anti-patterns | 5 | Bridge-era patterns, wrong navigation library, blocking JS thread, inline styles everywhere, unnecessary native modules |
| Constitution | 1 | 5 React Native-specific principles |
| Gate | 1 | RN pattern compliance check |
