# Configuration Firebase Storage pour les photos

## Problème
Les photos ne s'affichent pas sur d'autres appareils car les règles Firebase Storage bloquent l'accès.

## Solution : Configurer les règles Firebase Storage

1. Allez dans la console Firebase : https://console.firebase.google.com
2. Sélectionnez votre projet : `bon-d-intervention-cep`
3. Allez dans **Storage** > **Règles**
4. Remplacez les règles par :

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // Permettre la lecture publique des photos des bons
    match /bons/{bonId}/{allPaths=**} {
      allow read: if true;
      allow write: if request.auth != null; // Seulement les utilisateurs authentifiés peuvent écrire
    }
  }
}
```

5. Cliquez sur **Publier**

## Alternative : Accès public complet (pour test uniquement)

⚠️ **ATTENTION** : Cette règle permet l'accès public complet. À utiliser uniquement pour les tests.

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} {
      allow read, write: if true;
    }
  }
}
```

## Vérification

Après avoir configuré les règles :
1. Les photos doivent être accessibles depuis n'importe quel appareil
2. Les URLs Firebase Storage doivent fonctionner sans authentification pour la lecture
3. Testez en ouvrant une URL de photo directement dans le navigateur

