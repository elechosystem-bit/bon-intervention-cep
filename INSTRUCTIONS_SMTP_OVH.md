# Instructions pour configurer SMTP OVH avec Nodemailer

## 📋 Étape 1 : Vérifier vos identifiants OVH

Vous devez avoir :
- **Email expéditeur** : `intervention@cep75.fr`
- **Mot de passe** : Le mot de passe de cette boîte email OVH
- **Serveur SMTP** : `ssl0.ovh.net`
- **Port** : `465` (SSL)

## 📋 Étape 2 : Installer les dépendances

La fonction serverless nécessite Nodemailer. Vercel l'installera automatiquement lors du déploiement grâce au `package.json`.

## 📋 Étape 3 : Déployer sur Vercel

### Option A : Déploiement automatique depuis GitHub

1. Poussez votre code sur GitHub
2. Allez sur https://vercel.com
3. Importez votre repository
4. Ajoutez les variables d'environnement :
   - **Name** : `OVH_SMTP_USER`
   - **Value** : `intervention@cep75.fr` (optionnel, cette valeur est utilisée par défaut)
   - **Name** : `OVH_SMTP_PASSWORD`
   - **Value** : Le mot de passe de `intervention@cep75.fr`
5. Déployez

### Option B : Déploiement via CLI Vercel

```bash
# Installer Vercel CLI
npm i -g vercel

# Se connecter
vercel login

# Ajouter les variables d'environnement
vercel env add OVH_SMTP_USER
# (Entrez: intervention@cep75.fr - optionnel, valeur par défaut)

vercel env add OVH_SMTP_PASSWORD
# (Entrez le mot de passe quand demandé)

# Déployer
vercel --prod
```

## 📋 Étape 4 : Mettre à jour l'URL de l'API dans index.html

Une fois déployé sur Vercel, vous obtiendrez une URL comme :
`https://votre-projet.vercel.app/api/send-email`

Modifiez dans `index.html` la variable `SMTP_API_URL` (ligne ~520) avec votre URL Vercel :
```javascript
const SMTP_API_URL = 'https://votre-projet.vercel.app/api/send-email';
```

## 🔒 Sécurité

- **NE JAMAIS** mettre le mot de passe SMTP directement dans le code
- Utilisez toujours les variables d'environnement Vercel
- Le mot de passe doit être dans `OVH_SMTP_PASSWORD` (variables d'environnement)

## 🧪 Test

1. Enregistrez un bon d'intervention
2. Vérifiez la console du navigateur pour les logs
3. Vérifiez votre boîte email pour recevoir le PDF en pièce jointe
4. Vérifiez que l'email vient bien de `intervention@cep75.fr`

## 🔄 Fallback EmailJS

Si l'envoi SMTP échoue, le système bascule automatiquement sur EmailJS (backup) avec un lien vers le PDF stocké dans Firebase Storage.

## ⚠️ Dépannage

### Erreur "OVH_SMTP_PASSWORD not configured"
- Vérifiez que la variable d'environnement est bien configurée dans Vercel
- Redéployez après avoir ajouté la variable

### Erreur d'authentification SMTP
- Vérifiez que le mot de passe est correct
- Vérifiez que l'email `intervention@cep75.fr` existe et est actif
- Vérifiez que le compte email permet l'envoi SMTP (pas de restrictions)

### Erreur de connexion
- Vérifiez que le serveur `ssl0.ovh.net` est accessible
- Vérifiez que le port 465 n'est pas bloqué par un firewall

