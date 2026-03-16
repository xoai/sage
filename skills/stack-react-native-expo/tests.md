# Pack Tests: stack-react-native-expo

**Framework version tested:** Expo SDK 50+ / Zustand 4+ / TanStack Query 5+ / MMKV 2+
**Last tested:** 2025-03-13

---

## Test 1: Authentication flow

**Prompt:**
```
Implement login/logout with protected screens that redirect unauthenticated users.
```

**Without pack:** Agent adds `if (!user) redirect('/login')` in every screen component independently.
**With pack:** Agent creates a single auth guard in the root `_layout.tsx` using Expo Router's redirect. Individual screens don't check auth.
**Tests:** Integration "Expo Router + Auth" + Anti-pattern "Auth check per screen"

---

## Test 2: Persistent user preferences

**Prompt:**
```
Add a dark mode toggle that persists across app restarts.
```

**Without pack:** Agent uses AsyncStorage with useState, or renders the app before hydration completes (flash of wrong theme).
**With pack:** Agent uses Zustand + MMKV persistence, shows splash screen until `hasHydrated()` returns true, then renders.
**Tests:** Integration "Zustand + MMKV Persistence" + Anti-pattern "Store hydration race condition"

---

## Test 3: Server data management

**Prompt:**
```
Build a product catalog that caches data and works offline.
```

**Without pack:** Agent stores API data in Zustand with manual loading/error/refresh logic.
**With pack:** Agent uses TanStack Query for server data (with `offlineFirst` networkMode), keeps Zustand only for client UI state (selected filters).
**Tests:** Integration "TanStack Query + Offline" + Anti-pattern "Duplicating server data in Zustand"
