# React Native Extension — Constitution Additions

## React Native Principles

1. All new projects MUST target the New Architecture (Fabric + TurboModules). Bridge-era patterns (legacy Native Modules, old UIManager) MUST NOT appear in new code. The New Architecture is the default since RN 0.76 and always-on since RN 0.82.
2. Use Expo as the default development platform unless a specific native module requirement mandates bare React Native. Expo provides managed builds, OTA updates, and a curated module ecosystem that eliminates most native configuration work.
3. All lists MUST use FlashList (or FlatList with proper optimization) — never ScrollView with .map() for dynamic data. Lists are the primary performance bottleneck in React Native apps.
4. Navigation MUST use React Navigation (v7+) or Expo Router. Legacy navigation libraries (react-native-navigation by Wix, react-navigation v4 and earlier) MUST NOT be used in new projects.
5. Heavy computation (JSON parsing, image processing, data transformation) MUST be offloaded from the JS thread using background processing, worklets (Reanimated), or native modules. The JS thread must stay responsive for UI updates.
