// Notification Telegram quand un bon est valide en compta depuis l'admin web.
//
// Apellee par admin.html juste apres l'envoi du mail comptabilite. Envoie un
// message court sur le bot Telegram de la societe correspondante, a tous les
// admins listes dans TELEGRAM_ADMIN_IDS (CSV).
//
// Variables d'environnement attendues (cote Vercel) :
//   TELEGRAM_BOT_TOKEN_CEP     - token du bot @BonInterCEP_bot
//   TELEGRAM_BOT_TOKEN_ELECHO  - token du bot @BoninterElecho_bot
//   TELEGRAM_ADMIN_IDS         - liste d'IDs admin separes par des virgules

async function envoyerTelegram(token, chatId, texte) {
    const r = await fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text: texte, parse_mode: 'HTML' })
    });
    if (!r.ok) {
        const err = await r.text();
        throw new Error('Telegram ' + r.status + ' : ' + err);
    }
    return r.json();
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'POST') return res.status(405).json({ error: 'POST attendu' });

    try {
        const body = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
        const societe = (body.societe || '').toLowerCase();
        const numero = body.numero || '';
        const client = body.client || '';
        const montant = body.montant || '';
        const technicien = body.technicien || '';
        const date = body.date || '';

        if (!numero) return res.status(400).json({ error: 'numero manquant' });

        const token = societe === 'elechosystem' || societe === 'elecho'
            ? process.env.TELEGRAM_BOT_TOKEN_ELECHO
            : process.env.TELEGRAM_BOT_TOKEN_CEP;
        if (!token) return res.status(500).json({ error: 'Token Telegram manquant pour ' + societe });

        const adminsRaw = process.env.TELEGRAM_ADMIN_IDS || '';
        const adminIds = adminsRaw.split(',').map(s => s.trim()).filter(Boolean);
        if (adminIds.length === 0) return res.status(500).json({ error: 'TELEGRAM_ADMIN_IDS vide' });

        const societeNom = (societe === 'elechosystem' || societe === 'elecho') ? 'Elecho' : 'CEP';
        const msg =
            '✅ <b>Bon envoyé en compta — ' + societeNom + '</b>\n' +
            '\n' +
            '<b>N° :</b> ' + numero + '\n' +
            '<b>Client :</b> ' + client + '\n' +
            (technicien ? '<b>Tech :</b> ' + technicien + '\n' : '') +
            (date ? '<b>Date :</b> ' + date + '\n' : '') +
            (montant ? '<b>TTC :</b> ' + montant + '\n' : '') +
            '\n' +
            '<i>Validé depuis l\'admin web</i>';

        const resultats = [];
        for (const id of adminIds) {
            try {
                await envoyerTelegram(token, id, msg);
                resultats.push({ id: id, ok: true });
            } catch (e) {
                resultats.push({ id: id, ok: false, err: e.message });
            }
        }
        const success = resultats.some(r => r.ok);
        return res.status(200).json({ ok: success, resultats: resultats });
    } catch (e) {
        console.error('notif-telegram error:', e);
        return res.status(500).json({ error: e.message });
    }
}
