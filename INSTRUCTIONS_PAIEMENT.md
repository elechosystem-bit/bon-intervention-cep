# Instructions - Système de Paiement GoCardless

Ce document explique comment configurer et utiliser le système de paiement intégré à l'application de bons d'intervention.

## 📋 Fonctionnalités

### 1. Génération automatique de lien de paiement
- Chaque bon d'intervention génère automatiquement un lien de paiement unique
- Format : `https://pay.elecho-system.com/BI-20260001`
- Le lien est enregistré dans Firebase lors de la validation du bon

### 2. QR Code et lien cliquable sur le PDF
- Le PDF du bon d'intervention inclut une section "Paiement rapide" en bas
- QR code scannable contenant le lien de paiement
- Lien cliquable pour les clients recevant le PDF sur téléphone
- Conditions de paiement affichées :
  - **Paiement sous 3 jours** : réduction de 5%
  - **Paiement sous 30 jours** : montant normal
  - **Au-delà de 30 jours** : pénalités de retard (5% par mois)

### 3. Page de paiement
- Récapitulatif de l'intervention
- Calcul automatique du montant selon les délais
- Formulaire de saisie IBAN pour prélèvement SEPA
- Enregistrement du client pour les paiements futurs

### 4. Intégration GoCardless
- Prélèvement SEPA via GoCardless
- Frais réduits (~0.2-0.5% vs carte bancaire)
- IBAN enregistré une seule fois par client

### 5. Notifications
- Email automatique à vous lors d'un paiement
- Email automatique à la comptabilité (Nadine)
- Enregistrement du paiement dans Firebase

## 🔧 Configuration

### Étape 1 : Configuration GoCardless

1. **Créer un compte GoCardless**
   - Aller sur https://gocardless.com
   - Créer un compte développeur
   - Obtenir vos clés API (Access Token)

2. **Configurer les variables d'environnement Vercel**
   
   Dans votre projet Vercel, ajoutez ces variables d'environnement :
   
   ```
   GOCARDLESS_ACCESS_TOKEN=votre_access_token_goCardless
   GOCARDLESS_ENVIRONMENT=sandbox  # ou 'live' pour la production
   GOCARDLESS_WEBHOOK_SECRET=votre_webhook_secret
   ADMIN_EMAIL=a.mathieu@elechosystem.com
   COMPTABILITE_EMAIL=nadine@elechosystem.com
   EMAIL_API_URL=https://votre-api.vercel.app/api/send-email
   ```

3. **Configurer le webhook GoCardless**
   
   - Dans votre dashboard GoCardless, allez dans "Developers" > "Webhooks"
   - Ajoutez une nouvelle URL webhook : `https://votre-api.vercel.app/api/webhook-gocardless`
   - Copiez le secret webhook et ajoutez-le dans les variables d'environnement Vercel

### Étape 2 : Configuration du domaine de paiement

1. **Configurer le sous-domaine pay.elecho-system.com**
   
   - Dans votre DNS, créez un enregistrement CNAME :
     ```
     pay.elecho-system.com → votre-domaine-vercel.vercel.app
     ```
   
   - Ou configurez un domaine personnalisé dans Vercel pour pointer vers `payment.html`

2. **Alternative : Utiliser un chemin sur votre domaine principal**
   
   - Si vous préférez, vous pouvez utiliser : `https://votre-domaine.com/payment.html`
   - Dans ce cas, modifiez le lien de paiement dans `index.html` ligne ~1331

### Étape 3 : Configuration Firebase Admin (pour les webhooks)

Pour que les webhooks puissent mettre à jour Firebase, vous devez configurer Firebase Admin :

1. **Obtenir les credentials Firebase Admin**
   - Dans Firebase Console > Paramètres du projet > Comptes de service
   - Cliquez sur "Générer une nouvelle clé privée"
   - Téléchargez le fichier JSON

2. **Ajouter les credentials dans Vercel**
   - Dans Vercel, ajoutez une variable d'environnement :
     ```
     FIREBASE_ADMIN_CREDENTIALS={"type":"service_account",...}
     ```
   - Collez le contenu complet du fichier JSON (sur une seule ligne)

### Étape 4 : Déployer les APIs

Les fichiers API suivants doivent être déployés sur Vercel :

- `api/payment.js` - Création des mandats et paiements GoCardless
- `api/webhook-gocardless.js` - Réception des webhooks GoCardless

Ces fichiers sont automatiquement déployés si vous utilisez Vercel avec la structure de dossiers `/api`.

## 📝 Utilisation

### Pour le technicien

1. Remplir le bon d'intervention comme d'habitude
2. Faire signer le client
3. Cliquer sur "Enregistrer et envoyer"
4. Le lien de paiement est automatiquement généré et inclus dans le PDF

### Pour le client

1. Recevoir le PDF du bon d'intervention (par email)
2. Scanner le QR code ou cliquer sur le lien de paiement
3. Vérifier le récapitulatif et le montant (avec réduction si applicable)
4. Entrer son IBAN et confirmer le paiement
5. Recevoir un email de confirmation

## 🔍 Structure des données Firebase

### Collection `bons`
Chaque bon contient maintenant :
```javascript
{
  // ... données existantes ...
  paymentLink: "https://pay.elecho-system.com/BI-20260001",
  paymentStatus: "pending", // pending, paid, failed, cancelled
  paymentDate: Timestamp,
  paymentAmount: 150.00,
  gocardlessMandateId: "MD123..."
}
```

### Collection `paiements` (nouvelle)
```javascript
{
  bonId: "abc123",
  bonNumber: "20260001",
  amount: 150.00,
  originalAmount: 157.89,
  discount: 7.89,
  penalty: 0,
  status: "pending", // pending, paid_out, failed, cancelled
  iban: "FR76****1234", // Masqué pour sécurité
  accountHolder: "Jean Dupont",
  gocardlessMandateId: "MD123...",
  gocardlessPaymentId: "PM123...",
  paymentDate: Timestamp,
  createdAt: Timestamp
}
```

## 🧪 Tests

### Mode Sandbox GoCardless

1. Utilisez `GOCARDLESS_ENVIRONMENT=sandbox` pour les tests
2. Les IBAN de test GoCardless :
   - `GB82 WEST 1234 5698 7654 32` (succès)
   - `GB33 BUKB 2020 1555 5555 55` (échec)

### Tester le flux complet

1. Créer un bon d'intervention
2. Vérifier que le lien de paiement est généré
3. Ouvrir le PDF et vérifier la section paiement
4. Cliquer sur le lien de paiement
5. Tester avec un IBAN de test GoCardless
6. Vérifier que le paiement est enregistré dans Firebase
7. Vérifier que les emails de notification sont envoyés

## ⚠️ Points d'attention

1. **Sécurité** : Les IBAN sont masqués dans Firebase (seuls les 4 premiers et 4 derniers chiffres sont stockés)

2. **Webhooks** : Les webhooks GoCardless doivent être configurés pour mettre à jour automatiquement le statut des paiements

3. **Frais GoCardless** : 
   - Sandbox : gratuit
   - Production : ~0.2-0.5% par transaction SEPA

4. **Délais de prélèvement** : Les prélèvements SEPA prennent 3-5 jours ouvrés

5. **Gestion des erreurs** : En cas d'échec de prélèvement, GoCardless notifiera via webhook et le statut sera mis à jour dans Firebase

## 🐛 Dépannage

### Le QR code ne s'affiche pas dans le PDF
- Vérifier que la bibliothèque QRCode.js est chargée
- Vérifier la console du navigateur pour les erreurs

### Le lien de paiement ne fonctionne pas
- Vérifier que `payment.html` est accessible
- Vérifier que le domaine `pay.elecho-system.com` est configuré correctement

### Les webhooks ne fonctionnent pas
- Vérifier que l'URL webhook est correcte dans GoCardless
- Vérifier que `GOCARDLESS_WEBHOOK_SECRET` est configuré
- Vérifier les logs Vercel pour les erreurs

### Les emails de notification ne sont pas envoyés
- Vérifier que `EMAIL_API_URL` pointe vers votre API d'envoi d'email
- Vérifier que `ADMIN_EMAIL` et `COMPTABILITE_EMAIL` sont configurés

## 📞 Support

Pour toute question ou problème, contactez le développeur ou consultez la documentation GoCardless :
- Documentation GoCardless : https://developer.gocardless.com/
- Support GoCardless : support@gocardless.com

