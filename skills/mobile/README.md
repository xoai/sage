# mobile

**Layer 1 — Domain Foundation**

Universal mobile development principles that apply to every mobile project
regardless of framework. React Native, Flutter, Swift, Kotlin — these hold.

## Philosophy

Mobile is not "web on a small screen." The constraints are fundamentally
different: unreliable networks, limited battery, touch as primary input,
platform-specific user expectations, background/foreground lifecycle, and
physical device variations from $80 phones to $1500 flagships.

This pack encodes the mobile-specific principles that agents consistently
miss when applying web-first thinking to mobile development.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Patterns | 7 | Offline-first, performance/60fps, touch & gestures, navigation, lifecycle, responsive layout, platform conventions |
| Anti-patterns | 5 | Web-first thinking, blocking main thread, ignoring lifecycle, hardcoded dimensions, permission spam |
| Constitution | 1 | 6 non-negotiable mobile principles |

## What This Pack Does NOT Cover

- Framework-specific patterns (see `react-native`, `flutter`)
- Backend/API design (see future `backend`)
- Specific platform guidelines (Apple HIG, Material Design) in depth
