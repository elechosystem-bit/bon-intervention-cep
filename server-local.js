// Serveur HTTP simple pour tester l'application en local
// Usage: node server-local.js

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = process.env.PORT || 8000; // Utiliser le port 8000 par défaut, ou celui spécifié
const HOST = '0.0.0.0'; // Écouter sur toutes les interfaces (IPv4 et IPv6)

// Types MIME
const mimeTypes = {
    '.html': 'text/html',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.pdf': 'application/pdf',
    '.ico': 'image/x-icon'
};

const server = http.createServer((req, res) => {
    console.log(`${req.method} ${req.url}`);

    // Parser l'URL
    const parsedUrl = url.parse(req.url);
    let pathname = parsedUrl.pathname;

    // Route par défaut
    if (pathname === '/') {
        pathname = '/index.html';
    }

    // Gérer les routes API (simulation)
    if (pathname.startsWith('/api/')) {
        handleAPI(req, res, pathname);
        return;
    }

    // Gérer les routes de paiement
    if (pathname.startsWith('/BI-')) {
        // Rediriger vers payment.html avec le numéro de bon
        const bonNumber = pathname.match(/\/BI-(\d+)/);
        if (bonNumber) {
            res.writeHead(302, {
                'Location': `/payment.html?bon=${bonNumber[1]}`
            });
            res.end();
            return;
        }
    }

    // Construire le chemin du fichier
    const filePath = path.join(__dirname, pathname);

    // Vérifier si le fichier existe
    fs.access(filePath, fs.constants.F_OK, (err) => {
        if (err) {
            // Fichier non trouvé
            res.writeHead(404, { 'Content-Type': 'text/html' });
            res.end('<h1>404 - Fichier non trouvé</h1>');
            return;
        }

        // Lire le fichier
        fs.readFile(filePath, (err, data) => {
            if (err) {
                res.writeHead(500, { 'Content-Type': 'text/html' });
                res.end('<h1>500 - Erreur serveur</h1>');
                return;
            }

            // Déterminer le type MIME
            const ext = path.extname(filePath).toLowerCase();
            const contentType = mimeTypes[ext] || 'application/octet-stream';

            // Envoyer la réponse
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(data);
        });
    });
});

// Gérer les routes API (simulation pour les tests locaux)
function handleAPI(req, res, pathname) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    if (pathname === '/api/payment' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => {
            body += chunk.toString();
        });
        req.on('end', () => {
            try {
                const data = JSON.parse(body);
                console.log('📧 Requête de paiement reçue:', data);
                
                // Simulation d'une réponse GoCardless (pour les tests)
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    customerId: 'CU' + Date.now(),
                    bankAccountId: 'BA' + Date.now(),
                    mandateId: 'MD' + Date.now(),
                    paymentId: 'PM' + Date.now(),
                    status: 'pending',
                    message: '⚠️ Mode simulation - Configurez GoCardless pour la production'
                }));
            } catch (error) {
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Invalid JSON' }));
            }
        });
        return;
    }

    // Autres routes API
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'API endpoint not found' }));
}

server.listen(PORT, HOST, () => {
    console.log('\n🚀 Serveur local démarré !');
    console.log(`📱 Application: http://${HOST}:${PORT}`);
    console.log(`📱 Application (IP): http://127.0.0.1:${PORT}`);
    console.log(`💳 Page de paiement: http://${HOST}:${PORT}/payment.html?bon=20260001`);
    console.log(`🔗 Exemple lien paiement: http://${HOST}:${PORT}/BI-20260001`);
    console.log('\n⚠️  Mode simulation - Les paiements ne seront pas réellement traités');
    console.log('   Configurez GoCardless pour la production\n');
});

