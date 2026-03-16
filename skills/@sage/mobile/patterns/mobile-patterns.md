# Offline-First Architecture

**Why agents get this wrong:** Agents build mobile apps assuming constant connectivity, like web apps. Mobile users go through tunnels, elevators, and dead zones regularly.

**Do:** Cache critical data locally (SQLite, MMKV, Hive). Show stale data with a "last updated" indicator rather than an error screen. Queue mutations when offline and replay when connectivity returns. Design every screen to work with cached data. Test by enabling airplane mode mid-flow.

---

# 60fps Performance

**Why agents get this wrong:** Agents don't understand the 16ms frame budget. Mobile GPUs are weaker than desktop — heavy computation during animations causes visible jank.

**Do:** Keep the main/UI thread free during animations and scrolling. Move computation to background threads (Isolates in Flutter, InteractionManager in RN). Use virtualized flat lists for any list over 20 items — not ScrollView with .map(). Optimize images: compress, resize to display size, cache aggressively. Profile with platform tools (Xcode Instruments, Android Profiler) — don't guess.

---

# Touch Targets and Gestures

**Why agents get this wrong:** Agents use web-sized click targets (text links, small icons) that are nearly impossible to tap accurately on mobile.

**Touch targets:** Minimum 44×44pt (iOS) / 48×48dp (Android) for ALL interactive elements. Add padding to increase tap area without increasing visual size. 8pt minimum spacing between adjacent targets. Thumb-reachable zones: place primary actions in the bottom third of the screen for one-hand use. Never put destructive actions near common tap zones without confirmation.

**Gesture conventions — respect the platform, users don't read tutorials:**
- Swipe-to-go-back (iOS left-edge swipe, Android back gesture)
- Pull-to-refresh on scrollable lists
- Long-press for contextual menus
- Pinch-to-zoom on images and maps
- Swipe-to-dismiss on cards, modals, notifications

Never override system gestures. Never invent custom gestures when a platform standard exists.

**Feedback:** Every touch needs immediate visual response. Button press: highlight/ripple within 50ms. Drag: element follows finger with no perceptible lag. Swipe action: reveal the action as the user drags (don't wait for release).

---

# Navigation

**Why agents get this wrong:** Agents build deep nested navigation hierarchies or web-style breadcrumb navigation that doesn't match mobile patterns.

**Platform conventions:**
- **iOS:** Tab bar at bottom for top-level sections. Navigation stack with back button top-left. Modal sheets slide up from bottom. Swipe right from left edge to go back.
- **Android:** Bottom navigation or navigation drawer. System back button/gesture. Material-style transitions (shared element, container transform).

Never mix conventions. An iOS app with a hamburger menu feels wrong to iOS users.

**Architecture:** Keep hierarchy shallow (≤3 levels deep). Provide a "home" escape from deep stacks. Tab state is independent — switching tabs shouldn't reset the other tab's stack. Preserve scroll position and state when navigating back. Support deep links to any screen from day one — retrofitting is painful. Use platform-native transitions.

---

# App Lifecycle

**Why agents get this wrong:** Agents treat mobile apps like they're always running. The OS can suspend or kill your app at any time to reclaim memory.

**Foreground → Background:** Save in-progress work (form drafts, unsent messages, scroll position). Pause non-essential processing (animations, polling). Release expensive resources (camera, audio session). Cancel non-critical network requests.

**Background → Foreground:** Restore state seamlessly — user sees exactly what they left. Refresh stale data silently (don't show a loading spinner for cached data). Re-establish connections (WebSocket, location).

**Terminated → Cold Launch:** Restore last-known state from persistent storage. If previous session had unsaved work, offer to recover it. Don't force onboarding/splash again if user is logged in. Handle this case explicitly — don't assume in-memory state persists.

Test by force-killing and relaunching. Most lifecycle bugs only surface in the terminated → launch path.

---

# Responsive Layout

**Why agents get this wrong:** Agents hardcode layouts for one device size (usually iPhone 14 or Pixel 7). Real users have screens from 320pt phones to 1024pt tablets — and foldables that change width at runtime.

**Device range:** Small phones 320pt (iPhone SE), standard 375-414pt, large 428pt+, tablets 768pt+ (iPad), foldables (dynamic width at runtime).

**Do:** Flexible layouts that adapt: phone = single column, tablet = master-detail. Use safe area insets for all edge content (notch, home indicator, status bar, camera cutout). Support dynamic type (user's preferred text size — accessibility requirement). Never hardcode pixel values for layout. Support both orientations unless there's a strong reason not to. Handle keyboard appearance — content must scroll to keep the focused input visible. Test on the smallest (320pt SE) and largest (tablet) targets.

---

# Platform Conventions

**Why agents get this wrong:** Agents apply iOS conventions to Android or vice versa. Each platform has distinct UX expectations that users have internalized from years of use. Violating conventions creates friction even when the alternative is "better."

**iOS:** Flat design, SF Symbols, SF Pro font, navigation bars, tab bars, action sheets, swipe gestures, haptic feedback.

**Android:** Material Design, Material Icons, Roboto font, top app bars, bottom navigation, floating action buttons, snackbars, ripple effects.

**When in doubt:** Use platform-provided components. They automatically get the right look, feel, animation, and accessibility behavior.

**Shared vs platform-specific:** Share business logic (one implementation). Adapt UI components where it matters (navigation, dialogs, date pickers) — share where it doesn't (content cards, lists, forms). Follow each platform's notification and settings patterns.

---

# Accessibility (Mobile-Specific)

**Why agents get this wrong:** Agents skip mobile accessibility entirely. VoiceOver (iOS) and TalkBack (Android) users can't navigate custom components, gestures have no alternatives, and dynamic content changes aren't announced.

**Do:** Every interactive element needs an accessible label (not just visible text — icons need labels too). Custom gestures (swipe to delete, long press) must have accessible alternatives (button, menu). Use platform accessibility APIs: `accessibilityLabel`, `accessibilityRole`, `accessibilityHint` (RN) or `Semantics` widget (Flutter). Test with VoiceOver/TalkBack enabled — navigate your entire app with eyes closed.

---

# Network State Handling

**Why agents get this wrong:** Agents make API calls without checking or reacting to connectivity state. On mobile, connectivity changes constantly — WiFi to cellular to tunnel to airplane mode.

**Do:** Monitor connectivity state (`NetInfo` in RN, `connectivity_plus` in Flutter). Show a persistent banner when offline — not a one-time toast the user misses. Queue write operations and replay on reconnect. Distinguish between "no connection" (show cached data) and "server error" (retry with backoff). Pre-fetch critical data while on WiFi for predicted offline usage.

---

# Push Notifications

**Why agents get this wrong:** Agents implement push notifications as an afterthought — requesting permissions at launch, not handling background/killed state, and not deep-linking tapped notifications to the correct screen.

**Do:** Request notification permission in context (after the user takes an action that would benefit from notifications). Handle all three tap scenarios: app in foreground (show in-app banner), app in background (navigate to relevant screen), app killed (cold start → navigate). Store notification tokens server-side and refresh on app launch. Handle token rotation gracefully.
