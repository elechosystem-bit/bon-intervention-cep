# RÈGLES CRITIQUES — BON D'INTERVENTION

## INTERDICTIONS ABSOLUES — FIREBASE / FIRESTORE

1. **Ne JAMAIS supprimer de bons d'intervention** dans Firestore. Aucun `delete` sur la collection `bons`, ni dans `societes/*/bons`, ni dans l'ancienne structure `/bons`. JAMAIS.

2. **Ne JAMAIS modifier le fichier `firestore.rules`** sans vérifier que les règles concernent bien ce projet (collections : bons, clients, societes, parametres, astreintes, catalogue_perso, compteurs, clientsPennylane, paiements). Les bons doivent TOUJOURS avoir `allow delete: if false`.

3. **Ne JAMAIS déployer de règles Firestore** (`firebase deploy --only firestore:rules`) sans avoir vérifié que le fichier `firestore.rules` contient les bonnes collections du bon d'intervention et que `delete: if false` est présent sur les bons.

4. **Toujours vérifier que le projet Firebase actif est `bon-d-intervention-cep`** avant toute opération Firebase/Firestore. Ne jamais mélanger avec un autre projet.

5. **Ne JAMAIS utiliser** `firestore_delete_document`, `firestore_delete_database`, ou toute opération de suppression sur Firebase, quelle que soit la raison.

## PENNYLANE

- JAMAIS modifier les données Pennylane. Uniquement lire (GET). Aucun POST/PUT/DELETE.

## GIT

- Toujours commiter et pusher après chaque modification.
