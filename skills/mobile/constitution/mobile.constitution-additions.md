# Mobile Extension — Constitution Additions

## Mobile Principles

1. All network-dependent features MUST handle the offline case. Users lose connectivity in elevators, tunnels, airplanes, and rural areas. The app MUST NOT crash, show blank screens, or lose user data when offline.
2. All animations and transitions MUST run at 60fps (16ms per frame). Heavy computation MUST NOT run on the main/UI thread. If an operation takes >16ms, move it to a background thread/isolate.
3. All touch targets MUST be at minimum 44×44 points (iOS) / 48×48dp (Android). Adjacent interactive elements MUST have sufficient spacing to prevent mis-taps.
4. The app MUST handle the full lifecycle: background, foreground, terminated, memory pressure. In-progress work MUST be preserved when the OS kills the app for resources. State restoration on return is mandatory.
5. Permission requests MUST be contextual — explain WHY the permission is needed BEFORE requesting it, at the moment the user needs the feature. Never request all permissions at app launch.
6. All layouts MUST adapt to the full range of device sizes including phones, tablets, foldables, and both orientations. No hardcoded pixel dimensions for layout. Use relative sizing, safe area insets, and dynamic type support.
