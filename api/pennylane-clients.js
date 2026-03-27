// Fonction serverless Vercel pour rechercher les clients Pennylane
// Le token API reste côté serveur, jamais exposé au navigateur

// Cache en mémoire pour éviter de surcharger l'API Pennylane
let cachedClients = null;
let cacheTimestamp = 0;
const CACHE_DURATION = 30 * 60 * 1000; // 30 minutes

async function chargerTousLesClientsPennylane(token) {
    // Utiliser le cache si encore valide
    if (cachedClients && (Date.now() - cacheTimestamp) < CACHE_DURATION) {
        return cachedClients;
    }

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

        // Pause entre les pages pour éviter le rate limit
        if (hasMore) {
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }

    // Transformer et mettre en cache
    cachedClients = allClients.map(client => ({
        id: client.id,
        nom: client.name || '',
        email: (client.emails && client.emails.length > 0) ? client.emails[0] : '',
        telephone: client.phone || '',
        adresse: formatAdresse(client.billing_address),
        ville: client.billing_address?.city || '',
        codePostal: client.billing_address?.postal_code || '',
        rue: client.billing_address?.address || ''
    }));
    cachedClients.sort((a, b) => a.nom.localeCompare(b.nom));
    cacheTimestamp = Date.now();

    return cachedClients;
}

export default async function handler(req, res) {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Methode non autorisee' });
    }

    const token = process.env.PENNYLANE_API_TOKEN;
    if (!token) {
        return res.status(500).json({ error: 'Token Pennylane non configure' });
    }

    try {
        const { search } = req.query;

        // Charger tous les clients (avec cache)
        let clients = await chargerTousLesClientsPennylane(token);

        // Filtrer côté serveur si recherche
        if (search && search.length >= 2) {
            const term = search.toLowerCase();
            clients = clients.filter(c =>
                c.nom.toLowerCase().includes(term) ||
                (c.email && c.email.toLowerCase().includes(term)) ||
                (c.adresse && c.adresse.toLowerCase().includes(term))
            );
        }

        return res.status(200).json({
            clients,
            total: clients.length
        });

    } catch (error) {
        console.error('Erreur serveur:', error);
        return res.status(500).json({ error: 'Erreur serveur', message: error.message });
    }
}

function formatAdresse(addr) {
    if (!addr) return '';
    const parts = [
        addr.address,
        addr.postal_code,
        addr.city
    ].filter(Boolean);
    return parts.join(', ');
}
