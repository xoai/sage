---
name: 51-react-native-patterns
order: 51
category: compliance
version: "1.0.0"
modes: [build, architect]
---

# Gate 51: React Native Pattern Compliance

## Check Criteria

**Bridge-Era Code (FAIL if found):**
- No `NativeModules.X` imports (use TurboModules or Expo Modules)
- No `react-native link` commands in documentation
- No references to the Bridge in code comments or architecture docs
- No legacy `UIManager` direct usage

**List Implementation (FAIL if violated):**
- No `ScrollView` + `.map()` for dynamic data exceeding 20 items
- All lists use FlashList or FlatList with proper optimization props
- `keyExtractor` uses stable unique IDs, never array index

**Navigation (FAIL if wrong library):**
- Uses React Navigation v7+ or Expo Router
- No `react-native-navigation` (Wix) in new projects
- Deep linking configured for all navigable screens

**Performance (FAIL if main thread blocked):**
- No synchronous network calls on JS thread
- No large JSON parsing on JS thread without backgrounding
- StyleSheet.create used (no pervasive inline style objects)

## Failure Response

Identify the violation, explain the modern pattern, provide a concrete fix.
