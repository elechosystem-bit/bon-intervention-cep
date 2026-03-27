// Synchronise les clients Pennylane vers Firestore
// Appeler GET /api/sync-pennylane pour lancer la synchronisation

import { initializeApp, cert, getApps } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';

function getDb() {
    if (!process.env.FIREBASE_ADMIN_CREDENTIALS) return null;
    try {
        const serviceAccount = JSON.parse(process.env.FIREBASE_ADMIN_CREDENTIALS);
        if (getApps().length === 0) {
            initializeApp({ credential: cert(serviceAccount) });
        }
        return getFirestore();
    } catch (error) {
        console.error('Erreur initialisation Firebase Admin:', error);
        return null;
    }
}

async function chargerTousLesClientsPennylane(token) {
    let allClients = [];
    let hasMore = true;
    let cursor = null;

    while (hasMore) {
        let url = 'https://app.pennylane.com/api/external/v2/customers?per_page=100';
        if (cursor) {
            url += `&cursor=${encodeURIComponent(cursor)}`;
        }

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`Pennylane API error: ${response.status}`);
        }

        const data = await response.json();
        allClients = allClients.concat(data.items || []);
        hasMore = data.has_more || false;
        cursor = data.next_cursor || null;

        if (hasMore) {
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }

    return allClients;
}

function formatAdresse(addr) {
    if (!addr) return '';
    const parts = [addr.address, addr.postal_code, addr.city].filter(Boolean);
    return parts.join(', ');
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');

    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Méthode non autorisée' });
    }

    const token = process.env.PENNYLANE_API_TOKEN;
    if (!token) {
        return res.status(500).json({ error: 'Token Pennylane non configuré' });
    }
    const db = getDb();
    if (!db) {
        return res.status(500).json({ error: 'Firebase Admin non configuré (FIREBASE_ADMIN_CREDENTIALS manquant)' });
    }

    try {
        // 1. Charger tous les clients depuis Pennylane
        const clientsPennylane = await chargerTousLesClientsPennylane(token);

        // 2. Écrire dans Firestore par batch (max 500 par batch)
        const collection = db.collection('clientsPennylane');
        const batchSize = 450;

        for (let i = 0; i < clientsPennylane.length; i += batchSize) {
            const batch = db.batch();
            const chunk = clientsPennylane.slice(i, i + batchSize);

            chunk.forEach(client => {
                const doc = collection.doc(String(client.id));
                batch.set(doc, {
                    id: client.id,
                    nom: client.name || '',
                    nomLower: (client.name || '').toLowerCase(),
                    email: (client.emails && client.emails.length > 0) ? client.emails[0] : '',
                    telephone: client.phone || '',
                    adresse: formatAdresse(client.billing_address),
                    ville: client.billing_address?.city || '',
                    codePostal: client.billing_address?.postal_code || '',
                    rue: client.billing_address?.address || '',
                    syncDate: new Date().toISOString()
                });
            });

            await batch.commit();
        }

        return res.status(200).json({
            success: true,
            message: `${clientsPennylane.length} clients synchronisés dans Firestore`,
            total: clientsPennylane.length
        });

    } catch (error) {
        console.error('Erreur sync:', error);
        return res.status(500).json({ error: error.message });
    }
}
