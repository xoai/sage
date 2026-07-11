# Expo Router + Auth: Root Layout Guard

**Why agents get this wrong:** Agents add `if (!user) redirect('/login')` in every screen independently. Duplicated, inconsistent, one missed screen = security hole.

**Route structure:**
```
app/
├── _layout.tsx           # Root — checks auth, redirects
├── (auth)/               # Unauthenticated group
│   ├── login.tsx
│   └── register.tsx
├── (app)/                # Authenticated group
│   ├── _layout.tsx       # Tab navigator
│   ├── (tabs)/
│   │   ├── home.tsx
│   │   ├── profile.tsx
│   │   └── settings.tsx
│   └── [id].tsx
```

**Do:** Single guard in root `_layout.tsx`. Protected screens never check auth:
```tsx
// app/_layout.tsx
export default function RootLayout() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <SplashScreen />;
  return <Redirect href={user ? "/(app)" : "/(auth)/login"} />;
}
```

**Token storage:** Auth tokens in `expo-secure-store` (encrypted native storage). NEVER AsyncStorage or MMKV for tokens — they're not encrypted. MMKV only for non-sensitive state (preferences, UI cache).

---

# Zustand + MMKV: Hydration Race Condition

**Why agents get this wrong:** Agents render the app before persistent state has hydrated from MMKV. User sees default state (light theme) for a split second before persisted state (dark theme) loads. Worse: auth store hydrates with "logged in" but app already redirected to login because default was "logged out."

**Do:** Gate rendering on `hasHydrated()`:
```tsx
const hasHydrated = useSettingsStore.persist.hasHydrated();
if (!hasHydrated) return <SplashScreen />;
// Only now render the router
```

---

# TanStack Query + Zustand: State Separation

**Why agents get this wrong:** Agents store API data in Zustand, manually reimplementing caching, loading, error, and refresh:

```tsx
// WRONG — reimplementing TanStack Query poorly
const useProductsStore = create((set) => ({
  products: [], loading: false, error: null,
  fetch: async () => {
    set({ loading: true });
    try {
      const data = await api.getProducts();
      set({ products: data, loading: false });
    } catch (e) { set({ error: e, loading: false }); }
  },
}));

// RIGHT — TanStack Query for server data
const useProducts = () => useQuery({
  queryKey: ['products'],
  queryFn: api.getProducts,
});
// Zustand ONLY for client UI state
const useUIStore = create((set) => ({
  selectedFilter: 'all',
  setFilter: (filter) => set({ selectedFilter: filter }),
}));
```

The manual version has no cache invalidation, no background refetch, no retry, no deduplication. TanStack Query handles all of it. For offline: `networkMode: 'offlineFirst'` serves cache while offline.
