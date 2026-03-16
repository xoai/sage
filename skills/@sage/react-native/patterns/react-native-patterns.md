# New Architecture (JSI/Fabric/TurboModules)

**Why agents get this wrong:** Agents generate Bridge-era React Native code — `NativeModules` imports, `UIManager` commands, `.native.js` file extensions. The New Architecture (default since RN 0.76) replaces the Bridge with JSI for synchronous native communication.

**What this enables:** React 18+ features work (Suspense, Transitions, automatic batching). Native module calls can be synchronous when needed. Animations are smoother (Fabric integrates with concurrent rendering).

**Do:** Use Fabric components and TurboModules. Check that native dependencies support the New Architecture before adding them. If a library only supports the Bridge, look for an alternative or file an issue. Never import from `NativeModules` in new code. You don't need to understand JSI internals — just use modern APIs and let the framework handle the bridge removal.

---

# Expo as Default Workflow

**Why agents get this wrong:** Agents treat Expo as "beginner training wheels" and default to bare React Native. Expo is no longer the simple option — it's the official recommended development platform for most React Native apps.

**What Expo provides:**
- Managed builds (EAS Build) — no local Xcode/Android Studio required for CI
- OTA updates (EAS Update) — push JS changes without app store review
- Expo Modules API — write native modules with a simpler API than TurboModules
- Expo SDK — camera, notifications, file system, auth, maps — all New Architecture compatible

**Do:** Start with Expo unless you have a specific reason not to (custom native module not available as Expo Module, existing bare project with heavy native dependencies that can't migrate). Use Expo Modules API for native functionality. Use EAS Build for production builds. Use EAS Update for OTA patches.

---

# Navigation (Expo Router / React Navigation)

**Why agents get this wrong:** Agents use deprecated navigation patterns (react-navigation v4) or mix Expo Router and React Navigation incompatibly.

**Do:** Expo projects → Expo Router (file-based routing, built on React Navigation v7). Bare RN → React Navigation v7 with `@react-navigation/native-stack` (native performance, not JS-based stack). Pick ONE system per project. Never mix both.

```tsx
// Expo Router — file-based, automatic
// app/(tabs)/home.tsx → /home
// app/product/[id].tsx → /product/123

// Bare RN — React Navigation v7
const Stack = createNativeStackNavigator();
<Stack.Navigator>
  <Stack.Screen name="Home" component={HomeScreen} />
</Stack.Navigator>
```

---

# State Management

**Why agents get this wrong:** Agents default to Redux with heavy boilerplate or use AsyncStorage for everything including performance-sensitive reads.

**Do:**
- **Client state:** Zustand (simple, minimal boilerplate, no providers)
- **Server data:** TanStack Query (caching, background refresh, offline support)
- **Persistent storage:** MMKV (10x faster than AsyncStorage, synchronous reads)
- **Sensitive data:** Expo SecureStore (encrypted — tokens, credentials)
- **Never:** AsyncStorage for anything performance-sensitive or frequently read

---

# List Performance

**Why agents get this wrong:** Agents use `ScrollView` with `.map()` for dynamic lists. This renders ALL items immediately — 1000 items = 1000 mounted components, massive memory, frozen screen on mount.

**Do:** `FlashList` (preferred, Shopify) or `FlatList` for any dynamic list over 20 items.

```tsx
// WRONG — renders ALL 500 items at once
<ScrollView>{items.map(i => <Item key={i.id} {...i} />)}</ScrollView>

// RIGHT — virtualizes, only renders visible + buffer
<FlashList
  data={items}
  renderItem={({ item }) => <Item {...item} />}
  estimatedItemSize={80}
  keyExtractor={item => item.id}
/>
```

Never nest scrollable lists in the same direction. Always provide `keyExtractor` with stable IDs.

---

# Native Modules

**Why agents get this wrong:** Agents use the legacy `NativeModules` Bridge API or write custom native code when an Expo Module already exists.

**Do:** Check Expo SDK modules first — they're New Architecture compatible and work with EAS Build. For custom native: use Expo Modules API (Expo projects) or TurboModules (bare RN). Never use `requireNativeComponent` or `NativeModules` in new code.

---

# Styling

**Why agents get this wrong:** Agents create inline style objects in JSX (`style={{margin: 10}}`), creating new references every render and breaking `React.memo`.

**Do:** `StyleSheet.create()` — styles defined once, referenced by ID. Platform-specific: `Platform.select()`. Responsive: `useWindowDimensions()`. Consider NativeWind (Tailwind for RN) for utility-first styling.

```tsx
// WRONG — new object every render, breaks memo
<View style={{flexDirection: 'row', padding: 16}} />

// RIGHT — static reference, memo-safe
const styles = StyleSheet.create({
  row: { flexDirection: 'row', padding: 16 },
});
<View style={styles.row} />
```

---

# Animations (Reanimated)

**Why agents get this wrong:** Agents use the `Animated` API from core React Native, or worse, drive animations with `setState` — both run on the JS thread, causing jank when combined with user interaction.

**Do:** Use Reanimated 3 for all non-trivial animations. Animations run on the UI thread via worklets — zero JS thread involvement. Use `useAnimatedStyle`, `withTiming`, `withSpring`:

```tsx
const style = useAnimatedStyle(() => ({
  transform: [{ scale: withSpring(pressed.value ? 0.95 : 1) }],
}));
```

For gesture-driven animations, combine Reanimated + `react-native-gesture-handler`. Never `Animated.timing` for anything the user interacts with.

---

# Deep Linking and Universal Links

**Why agents get this wrong:** Agents build navigation that only works from in-app flows. External links (push notifications, emails, other apps) can't reach specific screens.

**Do:** Configure deep links from day one — retrofitting is painful:
- Expo Router: file-based routes automatically support deep links
- Bare RN + React Navigation: configure `linking` prop on `NavigationContainer`
- Register URL schemes (`myapp://`) for development, universal links (`https://myapp.com/`) for production
- Test with `npx uri-scheme open myapp://product/123 --ios`
