# Instructions pour configurer Resend API avec pièces jointes PDF

## 📋 Étape 1 : Créer un compte Resend

1. Allez sur https://resend.com
2. Créez un compte gratuit (3000 emails/mois gratuits)
3. Vérifiez votre domaine email (ou utilisez le domaine de test fourni)

## 📋 Étape 2 : Obtenir votre clé API

1. Dans le dashboard Resend, allez dans "API Keys"
2. Créez une nouvelle clé API
3. Copiez la clé (format : `re_xxxxxxxxxxxxx`)

## 📋 Étape 3 : Déployer sur Vercel

### Option A : Déploiement automatique depuis GitHub

1. Poussez votre code sur GitHub
2. Allez sur https://vercel.com
3. Importez votre repository
4. Ajoutez la variable d'environnement :
   - **Name** : `RESEND_API_KEY`
   - **Value** : Votre clé API Resend
5. Déployez

### Option B : Déploiement via CLI Vercel

```bash
# Installer Vercel CLI
npm i -g vercel

# Se connecter
vercel login

# Ajouter la variable d'environnement
vercel env add RESEND_API_KEY

# Déployer
vercel --prod
```

## 📋 Étape 4 : Configurer le domaine d'envoi

Dans Resend :
1. Allez dans "Domains"
2. Ajoutez votre domaine (ex: `cep75.fr`)
3. Suivez les instructions pour vérifier le domaine (DNS)
4. Une fois vérifié, modifiez dans `api/send-email.js` :
   ```javascript
   from: 'Compagnie d\'Électricité Parisienne <noreply@cep75.fr>',
   ```

## 📋 Étape 5 : Mettre à jour l'URL de l'API dans index.html

Une fois déployé sur Vercel, vous obtiendrez une URL comme :
`https://votre-projet.vercel.app/api/send-email`

Modifiez dans `index.html` la variable `RESEND_API_URL` avec votre URL Vercel.

## 🔒 Sécurité

- **NE JAMAIS** mettre la clé API Resend directement dans le code client
- Utilisez toujours une fonction serverless (Vercel, Netlify, etc.)
- La clé API doit être dans les variables d'environnement du serveur

## 🧪 Test

1. Enregistrez un bon d'intervention
2. Vérifiez la console du navigateur pour les logs
3. Vérifiez votre boîte email pour recevoir le PDF en pièce jointe

## 📝 Alternative : Solution sans serveur (moins sécurisée)

Si vous ne voulez pas utiliser Vercel, vous pouvez utiliser Resend directement depuis le client, mais cela expose votre clé API. **Non recommandé pour la production.**


