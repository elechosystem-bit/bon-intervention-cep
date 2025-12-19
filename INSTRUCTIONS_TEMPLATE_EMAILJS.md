# Instructions pour créer/modifier le template EmailJS pour les bons d'intervention

## 📋 Variables disponibles dans le template

Voici toutes les variables que le code envoie à EmailJS. Vous pouvez les utiliser dans votre template avec la syntaxe `{{variable}}` :

### Variables principales :
- `{{email}}` - Adresse email du destinataire (To Email)
- `{{subject}}` - Sujet de l'email (pour le client uniquement)
- `{{numero}}` - Numéro du bon d'intervention
- `{{date}}` - Date de l'intervention
- `{{client}}` - Nom du client
- `{{adresse}}` - Adresse complète du client
- `{{telephone}}` - Téléphone du client
- `{{technicien}}` - Nom du technicien
- `{{description}}` - Description de l'intervention
- `{{statut}}` - Statut du bon ("En attente" pour client, "Validé" pour comptabilité)
- `{{heure_arrivee}}` - Heure d'arrivée du technicien (format HH:MM)
- `{{heure_depart}}` - Heure de départ du technicien (format HH:MM)

### Variables financières (comptabilité uniquement) :
- `{{totalHT}}` - Total HT
- `{{totalTVA}}` - TVA (20%)
- `{{totalTTC}}` - Total TTC
- `{{total_ht}}` - Total HT (format alternatif)
- `{{total_tva}}` - TVA (format alternatif)
- `{{total_ttc}}` - Total TTC (format alternatif)
- `{{subtotal_produits}}` - Sous-total produits

### Variables détaillées :
- `{{produits}}` - Liste des produits utilisés (format HTML/text)
- `{{main_oeuvre}}` - Détails main d'œuvre
- `{{deplacement}}` - Détails déplacement
- `{{photos}}` - Liste des photos (URLs)
- `{{message}}` - Message complet formaté (corps de l'email)

## 🎨 Exemple de template HTML pour EmailJS

Voici un exemple de template HTML que vous pouvez utiliser dans EmailJS :

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { background: #f7fafc; padding: 20px; border: 1px solid #e2e8f0; border-top: none; }
        .info-row { margin: 10px 0; padding: 10px; background: white; border-radius: 4px; }
        .info-label { font-weight: bold; color: #1a365d; }
        .status { display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .status.en-attente { background: #f6ad55; color: white; }
        .status.valide { background: #48bb78; color: white; }
        .footer { margin-top: 20px; padding: 15px; background: #e2e8f0; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px; color: #718096; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚡ Bon d'Intervention</h1>
        </div>
        
        <div class="content">
            <div class="info-row">
                <span class="info-label">Numéro :</span> {{numero}}
            </div>
            
            <div class="info-row">
                <span class="info-label">Date :</span> {{date}}
            </div>
            
            <div class="info-row">
                <span class="info-label">Client :</span> {{client}}
            </div>
            
            <div class="info-row">
                <span class="info-label">Technicien :</span> {{technicien}}
            </div>
            
            <div class="info-row">
                <span class="info-label">Statut :</span> 
                <span class="status {{#if (eq statut "Validé")}}valide{{else}}en-attente{{/if}}">
                    {{statut}}
                </span>
            </div>
            
            {{#if description}}
            <div class="info-row">
                <span class="info-label">Description :</span><br>
                {{description}}
            </div>
            {{/if}}
            
            {{#if total_ttc}}
            <div class="info-row" style="background: #fffaf0; border: 2px solid #f6ad55;">
                <span class="info-label">Total TTC :</span> 
                <strong style="font-size: 18px; color: #dd6b20;">{{total_ttc}}</strong>
            </div>
            {{/if}}
            
            <div class="info-row">
                <span class="info-label">Détails complets :</span><br>
                <pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{{message}}</pre>
            </div>
        </div>
        
        <div class="footer">
            Compagnie d'Électricité Parisienne<br>
            Email généré automatiquement
        </div>
    </div>
</body>
</html>
```

## 📝 Instructions pour créer/modifier le template dans EmailJS

1. **Connectez-vous au dashboard EmailJS** :
   - Allez sur https://dashboard.emailjs.com/admin
   - Connectez-vous avec vos identifiants

2. **Accédez aux templates** :
   - Cliquez sur "Email Templates" dans le menu de gauche
   - Cliquez sur "Create New Template" pour créer un nouveau template
   - OU cliquez sur votre template existant (`template_qsnhl5e`) pour le modifier

3. **Configurez le template** :
   - **Template Name** : "Bon d'intervention CEP" (ou un nom de votre choix)
   - **Subject** : `Bon d'intervention {{numero}} - {{client}}`
   - **To Email** : `{{email}}` (IMPORTANT : utilisez cette variable pour l'adresse du destinataire)
   - **From Name** : "Compagnie d'Électricité Parisienne"
   - **Reply To** : Votre adresse email

4. **Éditez le contenu HTML** :
   - Cliquez sur "Edit" dans la section "Content"
   - Collez le template HTML ci-dessus (ou créez le vôtre)
   - Utilisez les variables listées ci-dessus avec la syntaxe `{{variable}}`

5. **Sauvegardez le template** :
   - Cliquez sur "Save"
   - Copiez le **Template ID** (format : `template_xxxxxxx`)

6. **Mettez à jour le code** :
   - Dans `admin.html` (ligne ~512) et `index.html` (ligne ~510)
   - Modifiez `templateID` dans `EMAILJS_CONFIG` avec votre nouveau Template ID

## 🔧 Template simple (texte brut)

Si vous préférez un template texte simple, voici un exemple :

```
BON D'INTERVENTION {{numero}}

Date : {{date}}
Client : {{client}}
Technicien : {{technicien}}
Statut : {{statut}}

{{#if description}}
Description : {{description}}
{{/if}}

{{#if total_ttc}}
Total TTC : {{total_ttc}}
{{/if}}

---
Compagnie d'Électricité Parisienne
```

## ⚠️ Notes importantes

- Le champ **To Email** doit absolument contenir `{{email}}` pour que l'email soit envoyé à la bonne adresse
- Les variables sont sensibles à la casse : utilisez exactement `{{numero}}` et non `{{Numero}}`
- Vous pouvez créer deux templates différents : un pour le client (sans prix) et un pour la comptabilité (avec prix)
- Si vous créez un nouveau template, n'oubliez pas de mettre à jour le `templateID` dans le code

## 🎯 Template recommandé pour la comptabilité

Pour la comptabilité, vous pouvez créer un template avec :
- Titre : "Bon d'intervention - Comptabilité"
- Numéro, Date, Client, Technicien
- **Total TTC** en évidence
- Statut "Validé"
- Détails complets (produits, main d'œuvre, déplacement)

## 🎯 Template recommandé pour le client

Pour le client, vous pouvez créer un template avec :
- Titre : "Bon d'intervention"
- Numéro, Date, Client, Technicien
- **PAS de prix** (totalTTC, etc.)
- Statut "En attente"
- Description et détails sans prix

