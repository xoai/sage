# Pack Tests: @sage/stack-flutter-firebase

**Framework version tested:** Flutter 3.x+ / Firebase 11+ / Riverpod 2+
**Last tested:** 2025-03-13

---

## Test 1: Data display from Firestore

**Prompt:**
```
Create a screen that shows a real-time list of products from Firestore.
```

**Without pack:** Agent calls `FirebaseFirestore.instance.collection('products').snapshots()` directly in the widget's build method, with raw `Map<String, dynamic>` data.
**With pack:** Agent creates a ProductRepository that returns typed `Product` models, exposed via a Riverpod StreamProvider. Widget uses `ref.watch()` with `.when()` for all states.
**Tests:** Integration "Firestore + Riverpod" + Anti-pattern "Direct Firebase in widgets" + Anti-pattern "Unstructured Firestore"

---

## Test 2: Authentication flow

**Prompt:**
```
Add login/logout with Google Sign-In and protect screens for authenticated users only.
```

**Without pack:** Agent checks `FirebaseAuth.instance.currentUser` independently in each screen.
**With pack:** Agent creates an `authStateProvider` (StreamProvider on `authStateChanges()`), chains all auth-dependent providers from it, and uses GoRouter redirect for navigation guard.
**Tests:** Integration "Firebase Auth + Riverpod"

---

## Test 3: Data write with validation

**Prompt:**
```
Create a form to add a new product with name and price to Firestore.
```

**Without pack:** Agent writes directly to Firestore from the widget with no security rules, raw map data, and no server-side validation.
**With pack:** Agent writes via a repository with typed models (toFirestore), and the guidance flags that Firestore security rules must be written before client code ships.
**Tests:** Anti-pattern "No Firestore security rules" + Anti-pattern "Unstructured Firestore"
