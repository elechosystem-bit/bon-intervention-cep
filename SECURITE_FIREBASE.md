# 🔒 Sécurité Firebase - Configuration

## ⚠️ État actuel de la sécurité

### Problèmes identifiés :

1. **Firestore** : Pas de règles de sécurité configurées (accès public par défaut)
2. **Storage** : Règles peut-être non configurées
3. **Authentification** : Pas d'authentification Firebase (seulement code admin côté client)
4. **Clés API** : Exposées dans le code client (normal pour Firebase, mais nécessite des règles strictes)

## ✅ Solutions recommandées

### 1. Configurer les règles Firestore

1. Allez dans la console Firebase : https://console.firebase.google.com
2. Sélectionnez votre projet : `bon-d-intervention-cep`
3. Allez dans **Firestore Database** > **Règles**
4. Copiez le contenu du fichier `firestore.rules` dans ce projet
5. Cliquez sur **Publier**

### 2. Configurer les règles Storage

1. Dans la console Firebase, allez dans **Storage** > **Règles**
2. Copiez le contenu du fichier `storage.rules` dans ce projet
3. Cliquez sur **Publier**

### 3. Implémenter Firebase Authentication (Recommandé)

Pour une sécurité optimale, il est recommandé d'implémenter Firebase Authentication :

1. Activez Firebase Authentication dans la console
2. Activez la méthode "Email/Password" ou "Anonymous"
3. Modifiez les règles pour utiliser `request.auth != null`
4. Ajoutez l'authentification dans `index.html` et `admin.html`

### 4. Restreindre les domaines autorisés (Recommandé)

Dans la console Firebase :
1. Allez dans **Authentication** > **Paramètres** > **Domaines autorisés**
2. Ajoutez uniquement vos domaines de production (ex: `bon-intervention-cep.vercel.app`)
3. Retirez les domaines de test si nécessaire

## 📋 Règles actuelles (temporaires)

Les règles fournies dans `firestore.rules` et `storage.rules` sont **temporaires** et permettent :
- ✅ Lecture publique (nécessaire pour l'affichage)
- ⚠️ Écriture publique (TEMPORAIRE - à sécuriser)

## 🔐 Sécurité recommandée (à implémenter)

Pour une sécurité optimale, modifiez les règles pour :

```javascript
// Firestore
allow create: if request.auth != null;
allow update: if request.auth != null;

// Storage
allow write: if request.auth != null;
```

## ⚠️ Limitations actuelles

- Les données peuvent être modifiées par n'importe qui ayant accès à l'application
- Pas de protection contre les abus (rate limiting)
- Les clés API sont publiques (normal pour Firebase, mais nécessite des règles strictes)

## ✅ Actions immédiates

1. ✅ Configurer les règles Firestore (fichier `firestore.rules`)
2. ✅ Configurer les règles Storage (fichier `storage.rules`)
3. ⚠️ Implémenter Firebase Authentication (recommandé)
4. ⚠️ Restreindre les domaines autorisés (recommandé)


