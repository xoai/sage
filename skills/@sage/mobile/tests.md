# Pack Tests: @sage/mobile

**Framework version tested:** Universal mobile
**Last tested:** 2025-03-13

---

## Test 1: Data list with poor connectivity

**Prompt:**
```
Build a screen that shows a list of articles fetched from an API.
```

**Without pack:** Agent fetches on mount, shows error screen when offline, no caching.
**With pack:** Agent caches data locally, shows cached data with "last updated" indicator when offline, queues refresh for when connectivity returns.
**Tests:** Pattern "Offline-First Architecture" + Anti-pattern "Web-First Thinking"

---

## Test 2: Settings screen with many options

**Prompt:**
```
Create a settings screen with toggle switches for notifications, dark mode, and privacy options.
```

**Without pack:** Agent uses small web-sized toggles, no platform conventions, flat layout.
**With pack:** Agent uses 44pt+ touch targets, platform-appropriate toggle components, proper spacing between interactive elements.
**Tests:** Pattern "Touch Targets and Gestures" + Pattern "Platform Conventions"

---

## Test 3: Permission-dependent feature

**Prompt:**
```
Add a photo upload feature to a user profile screen.
```

**Without pack:** Agent requests camera/photo permissions at app launch or without context.
**With pack:** Agent requests permission when the user taps the upload button, explains why it's needed, handles denial gracefully with a fallback.
**Tests:** Anti-pattern "Permission Spam at Launch"
