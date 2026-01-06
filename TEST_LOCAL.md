# 🚀 Tester l'application en local

## Démarrage rapide

### 1. Lancer le serveur local

Ouvrez un terminal dans le dossier du projet et exécutez :

```bash
npm run local
```

Ou directement :

```bash
node server-local.js
```

### 2. Accéder à l'application

Une fois le serveur démarré, ouvrez votre navigateur et allez sur :

- **Application principale** : http://localhost:3000
- **Page de paiement (exemple)** : http://localhost:3000/payment.html?bon=20260001
- **Lien de paiement (exemple)** : http://localhost:3000/BI-20260001

## 📝 Comment tester le système de paiement

### Étape 1 : Créer un bon d'intervention

1. Ouvrez http://localhost:3000
2. Remplissez un bon d'intervention
3. Cliquez sur "Enregistrer et envoyer"
4. Le lien de paiement sera généré automatiquement

### Étape 2 : Voir le PDF avec le QR code

1. Après l'enregistrement, le PDF est généré
2. En bas du PDF, vous verrez la section "PAIEMENT RAPIDE" avec :
   - Les conditions de paiement
   - Un QR code
   - Un lien cliquable

### Étape 3 : Tester la page de paiement

1. Cliquez sur le lien de paiement dans le PDF, ou
2. Allez sur http://localhost:3000/BI-[NUMERO_BON]
3. Vous verrez :
   - Le récapitulatif de l'intervention
   - Le montant calculé (avec réduction si < 3 jours)
   - Le formulaire de paiement

### Étape 4 : Simuler un paiement

⚠️ **Mode simulation** : Le serveur local simule les paiements GoCardless. Aucun vrai paiement ne sera effectué.

1. Entrez un IBAN de test (ex: `FR76 1234 5678 9012 3456 7890 123`)
2. Cliquez sur "Payer"
3. Vous verrez un message de succès (simulation)

## 🔧 Configuration pour les tests

### Tester avec un bon existant

Si vous avez déjà des bons dans Firebase, vous pouvez tester avec leur numéro :

```
http://localhost:3000/BI-20260001
```

### Modifier le numéro de bon dans l'URL

Remplacez `20260001` par le numéro de votre bon d'intervention.

## ⚠️ Limitations du mode local

- Les paiements sont **simulés** (pas de vraie transaction GoCardless)
- Les emails ne sont **pas envoyés**
- Les webhooks GoCardless ne fonctionnent **pas en local**
- Firebase fonctionne normalement (vraies données)

## 🐛 Dépannage

### Le serveur ne démarre pas

Vérifiez que le port 3000 n'est pas déjà utilisé :
```bash
netstat -ano | findstr :3000
```

Si le port est utilisé, modifiez `PORT` dans `server-local.js`

### La page de paiement ne charge pas les données

1. Vérifiez que Firebase est bien configuré
2. Vérifiez que le numéro de bon existe dans Firebase
3. Ouvrez la console du navigateur (F12) pour voir les erreurs

### Le QR code ne s'affiche pas dans le PDF

1. Vérifiez que la bibliothèque QRCode.js est chargée
2. Ouvrez la console du navigateur pour voir les erreurs
3. Le QR code peut prendre quelques secondes à générer

## 📱 Tester sur mobile

Pour tester sur votre téléphone en local :

1. Trouvez l'adresse IP locale de votre ordinateur :
   ```bash
   ipconfig
   ```
   Cherchez "Adresse IPv4" (ex: 192.168.1.100)

2. Sur votre téléphone, connecté au même WiFi, allez sur :
   ```
   http://192.168.1.100:3000
   ```

3. Remplacez `192.168.1.100` par votre vraie adresse IP

## ✅ Checklist de test

- [ ] Le serveur démarre sans erreur
- [ ] L'application principale se charge (http://localhost:3000)
- [ ] Je peux créer un bon d'intervention
- [ ] Le PDF contient la section "PAIEMENT RAPIDE"
- [ ] Le QR code s'affiche dans le PDF
- [ ] Le lien de paiement fonctionne
- [ ] La page de paiement charge les données du bon
- [ ] Le calcul du montant fonctionne (réduction si < 3 jours)
- [ ] Le formulaire de paiement s'affiche
- [ ] La simulation de paiement fonctionne

