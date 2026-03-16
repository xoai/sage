# Anti-Pattern: Web-First Thinking

**What agents do:** Build mobile features as responsive web pages — long scrolling forms, hover-dependent interactions, tiny click targets, always-on connectivity assumption, ignoring the keyboard lifecycle.

**Why it's wrong:** Mobile has fundamentally different constraints: touch input (no hover), unreliable network, small screens, virtual keyboard that covers half the screen, battery limits, OS lifecycle management. Do instead: Touch targets 44pt+, offline-capable, keyboard-aware scrolling, platform navigation patterns, lifecycle-resilient state management.

---

# Anti-Pattern: Blocking the Main Thread

**What agents do:** Run synchronous network requests, large JSON parsing, database queries, or image processing on the main/UI thread. App freezes during these operations.

**Why it's wrong:** The UI thread must complete each frame in 16ms (60fps). A 200ms network timeout freezes the app for 12 frames — users notice and assume it's broken. Do instead: All I/O, computation, and parsing off the main thread. Use background threads, isolates, or workers. Main thread does only UI updates and touch handling.

---

# Anti-Pattern: Ignoring App Lifecycle

**What agents do:** Assume the app runs continuously. Store state only in memory. Don't handle background/foreground transitions. Don't persist in-progress work.

**Why it's wrong:** The OS kills background apps routinely under memory pressure. User switches apps for 30 seconds, comes back to cleared forms, reset scroll position, lost draft messages. The #1 cause of user frustration in mobile apps. Do instead: Persist critical state to disk on background transition. Restore on foreground. Save form drafts automatically. Use state restoration APIs. Test the "killed in background" scenario explicitly.

---

# Anti-Pattern: Hardcoded Dimensions

**What agents do:** Use fixed pixel values: `width: 375, height: 812, paddingTop: 47` — status bar height on one specific iPhone model.

**Why it's wrong:** Devices range from 320pt to 1024pt+ wide. Status bar heights, safe area insets, and navigation bar sizes vary across devices. Hardcoded values break on every device except the developer's test phone. Do instead: Safe area insets (not hardcoded status bar height), flex/relative layout, percentage widths. Test on smallest (iPhone SE) and largest (iPad), plus both orientations.

---

# Anti-Pattern: Permission Spam at Launch

**What agents do:** Request camera, location, notifications, contacts, and microphone permissions all at once on first launch, before the user has done anything.

**Why it's wrong:** Users deny everything they don't understand. On iOS, you get ONE chance to ask — a denied permission requires the user to navigate to Settings to re-enable. On Android, "Don't ask again" permanently blocks the prompt. Do instead: Request permissions contextually at the moment the user needs the feature. Show an explanation screen BEFORE the system dialog ("We need camera access to scan receipts"). Handle denial gracefully — explain what's limited and how to re-enable in Settings.
