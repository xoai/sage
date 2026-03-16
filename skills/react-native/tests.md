# Pack Tests: react-native

**Framework version tested:** React Native 0.76+ (New Architecture)
**Last tested:** 2025-03-13

---

## Test 1: Data list screen

**Prompt:**
```
Create a screen that displays a scrollable list of 500 chat messages.
```

**Without pack:** Agent uses `<ScrollView>{messages.map(m => <Message />)}</ScrollView>`, mounting all 500 items.
**With pack:** Agent uses `FlashList` or `FlatList` with `keyExtractor`, `estimatedItemSize`, and only visible items rendered.
**Tests:** Pattern "List Performance" + Anti-pattern "ScrollView with .map()"

---

## Test 2: Native feature access

**Prompt:**
```
Add camera functionality to capture profile photos.
```

**Without pack:** Agent uses `NativeModules` Bridge API or installs a random community camera package.
**With pack:** Agent uses `expo-camera` (Expo project) or checks Expo Modules API first. No legacy NativeModules.
**Tests:** Pattern "Native Modules" + Anti-pattern "Bridge-Era Code"

---

## Test 3: App navigation structure

**Prompt:**
```
Set up navigation with a bottom tab bar containing Home, Search, and Profile tabs.
```

**Without pack:** Agent uses react-navigation v4 patterns or mixes Expo Router with React Navigation.
**With pack:** Agent uses Expo Router (file-based) for Expo projects or React Navigation v7 with native-stack for bare RN. One system, not mixed.
**Tests:** Pattern "Navigation" + Anti-pattern "Wrong Navigation Library"

---

## Test 4: Styled component

**Prompt:**
```
Create a card component with rounded corners, shadow, padding, and a title.
```

**Without pack:** Agent writes inline styles: `style={{borderRadius: 12, padding: 16, ...}}`.
**With pack:** Agent uses `StyleSheet.create()` with styles defined outside the component as static references.
**Tests:** Pattern "Styling" + Anti-pattern "Inline Style Objects"
