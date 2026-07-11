# Anti-Pattern: Direct Firebase in Widgets

**What agents do:** Call `FirebaseFirestore.instance.collection('products').get()` directly in widget `build()` or `initState()`.

**Why agents do this:** Firebase's API is simple enough to call directly. Agents skip the abstraction layer because it seems like unnecessary boilerplate for small apps.

**Why it's wrong:** Firebase coupled to every widget — can't test without live Firebase, can't swap backend (Firestore → Supabase), error handling scattered across 50 files, offline behavior inconsistent. Do instead: Repository pattern. Only repositories import Firebase. Widgets consume typed providers.

---

# Anti-Pattern: Unstructured Firestore (Raw Maps)

**What agents do:** Read and write documents as raw `Map<String, dynamic>`, accessing fields by string keys: `doc.data()['name']`, `doc['price'] as double`.

**Why agents do this:** Firestore returns maps natively. The raw access works immediately without extra code. Agents optimize for getting something working, not for maintainability.

**Why it's wrong:** No compile-time safety. A typo (`'naem'` instead of `'name'`) silently returns null. Type mismatch (`int` stored where `double` expected) crashes at runtime. Refactoring a field name requires finding every string reference. Do instead: Typed models with `fromFirestore`/`toFirestore` factories. All serialization in the model class.

---

# Anti-Pattern: No Security Rules

**What agents do:** Leave Firestore in test mode (`allow read, write: if true`) and focus entirely on client code. Ship to production with open rules.

**Why agents do this:** Security rules are a separate file in a separate language. Agents are asked to "build a feature," not "secure the database." Rules feel like ops work, not dev work.

**Why it's wrong:** Firestore is directly accessible from the client. Without rules, ANY user can read/write/delete ANY data. Client validation is trivially bypassed — anyone with your Firebase config can call Firestore directly. Do instead: Write rules BEFORE client code. Default deny. Test rules with Firebase Emulator Suite. Deploy rules in CI/CD alongside client code.
