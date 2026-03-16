# Anti-Pattern: Bridge-Era Code

**What agents do:** Generate `import { NativeModules } from 'react-native'`, use `UIManager.dispatchViewManagerCommand`, or create `.native.js` bridge files.

**Why agents do this:** Training data is dominated by 2018-2022 React Native content, when the Bridge was the only architecture. Most tutorials, blog posts, and Stack Overflow answers still show Bridge patterns.

**Why it's wrong:** The Bridge is being removed. New Architecture uses JSI for synchronous native calls. Bridge code won't work in future RN versions and misses performance benefits. Do instead: Expo Modules API or TurboModules for native functionality.

---

# Anti-Pattern: Wrong Navigation Library

**What agents do:** Use react-navigation v4 patterns (`createStackNavigator` from `react-navigation-stack`), or use Expo Router in a bare RN project, or mix Expo Router and React Navigation.

**Why it's wrong:** V4 is deprecated and incompatible with current RN. Expo Router requires Expo — it won't work bare. Mixing causes conflicts. Do instead: Expo Router for Expo projects, React Navigation v7 with native-stack for bare RN. One system.

---

# Anti-Pattern: ScrollView with .map() for Lists

**What agents do:** `<ScrollView>{items.map(i => <Item key={i.id} />)}</ScrollView>` for lists of any size. The single most common React Native performance mistake.

**Why agents do this:** In web React, rendering a list with `.map()` inside a scrollable div is standard and works fine — the browser handles virtualization. Agents apply the same pattern to React Native, where there's no browser to help.

**Why it's wrong:** Renders ALL items immediately. 500 items = 500 mounted components, 500 layout calculations, massive memory. Screen freezes on mount. Do instead: `FlashList` or `FlatList` — only renders visible items plus small buffer. Set `estimatedItemSize`. Provide stable `keyExtractor`.

---

# Anti-Pattern: Blocking the JS Thread

**What agents do:** Run expensive computations (JSON parsing large payloads, complex array operations, image manipulation) synchronously on the JavaScript thread during user interaction.

**Why it's wrong:** The JS thread handles both UI updates and touch events. Block it and animations freeze, touches are delayed, the app feels unresponsive. Do instead: Offload to native (Worklets via Reanimated) or chunk with `InteractionManager.runAfterInteractions`.

---

# Anti-Pattern: Inline Style Objects

**What agents do:** Pass `style={{flexDirection: 'row', padding: 16, backgroundColor: '#fff'}}` directly in JSX throughout the component.

**Why it's wrong:** Creates a new object every render, breaking `React.memo` and causing unnecessary re-renders of children. Do instead: `StyleSheet.create()` defines styles once as static references. Use `Platform.select()` for platform-specific variants.

---

## Old Patterns (Deprecated Reference)

<details>
<summary>Bridge Architecture — superseded by New Architecture (React Native 0.76+, Oct 2024)</summary>

The Bridge was React Native's original communication layer between JS and
native. It was async-only, JSON-serialized, and caused "bridge congestion"
under heavy load. These patterns MUST NOT appear in new code:

| Bridge pattern (deprecated) | New Architecture replacement |
|----------------------------|------------------------------|
| `NativeModules.MyModule` | TurboModules (codegen'd, synchronous via JSI) |
| `UIManager.dispatchViewManagerCommand` | Fabric components with direct method calls |
| `requireNativeComponent` | Fabric `codegenNativeComponent` |
| `.native.js` bridge files | Expo Modules API or TurboModules |
| `NativeEventEmitter` (Bridge-based) | TurboModule event emitters |
| `InteractionManager` for all deferrals | Worklets (Reanimated) for animation-related work |

New Architecture is default since RN 0.76. The Bridge still works as a
compatibility layer but will be removed in a future version.
</details>

<details>
<summary>React Navigation v4/v5 patterns — v7 current (Oct 2024)</summary>

| Old pattern | Current replacement |
|------------|-------------------|
| `createStackNavigator` (from `react-navigation-stack`) | `createNativeStackNavigator` (from `@react-navigation/native-stack`) |
| `navigation.navigate('Screen', { params })` returning void | Same API but type-safe with `RootStackParamList` |
| `createBottomTabNavigator` with custom tab bar hack | `@react-navigation/bottom-tabs` v7 with Material-style support |
| Static route configuration object | `linking` config with deep link prefixes |
| Manual header configuration per screen | `screenOptions` in navigator or per-group |

For Expo projects, SHOULD use Expo Router instead of React Navigation
directly — it wraps React Navigation with file-based routing.
</details>
