// Fonction serverless Vercel pour rechercher les clients Pennylane
// Le token API reste côté serveur, jamais exposé au navigateur

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
        const { search, page = 1 } = req.query;

        // Construire l'URL Pennylane avec filtre si recherche
        let url = `https://app.pennylane.com/api/external/v2/customers?page=${page}&per_page=100`;

        if (search && search.length >= 2) {
            // Filtre par nom via l'API Pennylane
            const filter = JSON.stringify([{"field": "name", "operator": "contains", "value": search}]);
            url += `&filter=${encodeURIComponent(filter)}`;
        }

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Erreur Pennylane:', response.status, errorText);
            return res.status(response.status).json({ error: 'Erreur API Pennylane', details: errorText });
        }

        const data = await response.json();

        // Extraire uniquement les infos utiles (lecture seule)
        const clients = (data.items || []).map(client => ({
            id: client.id,
            nom: client.name || '',
            email: (client.emails && client.emails.length > 0) ? client.emails[0] : '',
            telephone: client.phone || '',
            adresse: formatAdresse(client.billing_address),
            ville: client.billing_address?.city || '',
            codePostal: client.billing_address?.postal_code || '',
            rue: client.billing_address?.address || ''
        }));

        return res.status(200).json({
            clients,
            total: clients.length,
            has_more: data.has_more || false
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
