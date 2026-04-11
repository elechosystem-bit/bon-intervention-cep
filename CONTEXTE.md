# Bon d'Intervention CEP (Variante)

## Description
Fork/variante du projet bon-intervention avec configuration specifique CEP. Meme systeme de gestion des bons d'intervention mais potentiellement un environnement de staging ou une version deployee separement.

## Stack Technique
- Frontend : Vanilla JavaScript (HTML/CSS/JS)
- Backend : Firebase (Firestore, Storage, Auth)
- Node.js (server-local.js, paiements)
- Emails : Nodemailer
- Chiffrement : TweetNaCl
- Comptabilite : Pennylane (sync auto)
- Deploiement : Vercel

## URL
- Deploye sur Vercel

## Etat Actuel
**Fonctionnel** - Derniere mise a jour : avril 2026 ("Sync auto Pennylane"). Commits legerement anterieurs au repo bon-intervention principal.

## Ce Qui Reste a Faire
- Auditer les differences avec bon-intervention principal
- Verifier que les regles Firestore sont identiques
- Tester le flux de paiement sur l'infra CEP
- Clarifier la relation entre ce repo et bon-intervention (fusionner ou documenter les differences)
