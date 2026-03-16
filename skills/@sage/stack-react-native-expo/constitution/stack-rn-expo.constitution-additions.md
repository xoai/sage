# Stack React Native Expo — Constitution Additions

## Stack Integration Principles

1. Authentication state MUST be checked at the router/layout level using Expo Router's redirect mechanism or React Navigation's auth flow pattern. Individual screens MUST NOT independently check auth — the navigation guard handles it.
2. Zustand stores that persist to MMKV MUST handle hydration asynchronously. The app MUST show a loading/splash state until hydration completes — never render screens with empty/default state that flash before real data appears.
3. TanStack Query MUST be the sole mechanism for server data fetching, caching, and background refresh. Zustand stores MUST NOT duplicate server data. Zustand is for client state (preferences, UI state). TanStack Query is for server state (API data).
4. All Expo SDK modules MUST be used over community alternatives when available. Expo modules are guaranteed New Architecture compatible, receive coordinated updates, and work with EAS Build without configuration.
