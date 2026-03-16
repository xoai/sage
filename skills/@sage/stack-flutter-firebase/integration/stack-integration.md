# Firestore + Riverpod: Repository Pattern

**Why agents get this wrong:** Agents call `FirebaseFirestore.instance.collection('products').snapshots()` directly in widgets, with raw `Map<String, dynamic>` data. No typing, no separation, Firestore coupled to every widget.

**Do:** Repository → Provider → Widget chain. Only the repository imports Firebase:

```dart
// models/product.dart — typed model with serialization
class Product {
  final String id, name;
  final double price;
  Product({required this.id, required this.name, required this.price});

  factory Product.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data() as Map<String, dynamic>;
    return Product(
      id: doc.id,
      name: data['name'] as String,
      price: (data['price'] as num).toDouble(),
    );
  }
  Map<String, dynamic> toFirestore() => {'name': name, 'price': price};
}

// repositories/product_repo.dart
class ProductRepository {
  Stream<List<Product>> watchProducts() =>
    FirebaseFirestore.instance.collection('products')
      .snapshots()
      .map((snap) => snap.docs.map(Product.fromFirestore).toList());
}

// providers.dart
final productRepoProvider = Provider((_) => ProductRepository());
final productsProvider = StreamProvider((ref) =>
  ref.watch(productRepoProvider).watchProducts());

// Widget — clean, zero Firebase knowledge
ref.watch(productsProvider).when(
  loading: () => CircularProgressIndicator(),
  error: (e, _) => ErrorWidget(e),
  data: (products) => ProductList(products: products),
);
```

Use `freezed` or `json_serializable` for larger models to auto-generate serialization.

---

# Firebase Auth + Riverpod: Auth State Chain

**Why agents get this wrong:** Agents check `FirebaseAuth.instance.currentUser` independently per screen. Auth changes don't propagate. Null checks scattered everywhere.

**Do:** Single auth StreamProvider as root. Chain all auth-dependent providers from it. When auth changes, Riverpod automatically invalidates the entire chain:

```dart
final authProvider = StreamProvider((_) =>
  FirebaseAuth.instance.authStateChanges());

final currentUserProvider = Provider<User?>((ref) =>
  ref.watch(authProvider).value);

final userProfileProvider = FutureProvider<UserProfile?>((ref) {
  final user = ref.watch(currentUserProvider);
  if (user == null) return null;
  return ref.read(userRepoProvider).getProfile(user.uid);
});

// GoRouter redirect — single place for auth navigation
redirect: (context, state) {
  final user = ref.read(authProvider).value;
  if (user == null && !state.matchedLocation.startsWith('/login'))
    return '/login';
  return null;
}
```

---

# Firestore Security Rules

**Why agents get this wrong:** Agents leave Firestore in test mode (`allow read, write: if true`) during development and ship it. This is the #1 security mistake in Firebase apps — multiple production apps have been breached.

**Do:** Write rules BEFORE client code. Default deny, open selectively:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read: if request.auth != null;
      allow write: if request.auth.uid == userId;
    }
    match /products/{productId} {
      allow read: if true;  // Public catalog
      allow create: if request.auth != null
        && request.resource.data.keys().hasAll(['name', 'price'])
        && request.resource.data.price is number;
      allow update, delete: if request.auth.uid == resource.data.ownerId;
    }
  }
}
```

Rules live in `firestore.rules`, versioned with the app. Test with Firebase Emulator Suite. Deploy rules as part of CI/CD — rules and client code ship together.
