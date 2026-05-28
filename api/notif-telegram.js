// Notification Telegram quand un bon est valide en compta depuis l'admin web.
//
// Appelle par admin.html juste apres l'envoi du mail comptabilite. Fait 2 choses :
//   1. Retire les boutons "Valider / Refuser / Modifier" du message Telegram
//      d'origine (s'il y en a) -- pour figer le bon dans la conv.
//   2. Envoie un nouveau message de confirmation a tous les admins
//      ("Bon envoye en compta -- ce bon ne peut plus etre modifie").
//
// Variables d'environnement attendues (cote Vercel) :
//   TELEGRAM_BOT_TOKEN_CEP     - token du bot @BonInterCEP_bot
//   TELEGRAM_BOT_TOKEN_ELECHO  - token du bot @BoninterElecho_bot
//   TELEGRAM_ADMIN_IDS         - liste d'IDs admin separes par des virgules

const FIREBASE_API_KEY = 'AIzaSyAuX2gsGiRGqVbsk93y0wmwJOsT-RuEkE4';
const PROJECT_ID = 'bon-d-intervention-cep';

async function getAnonToken() {
    const r = await fetch('https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=' + FIREBASE_API_KEY, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ returnSecureToken: true })
    });
    if (!r.ok) throw new Error('Auth Firebase echouee : ' + r.status);
    return (await r.json()).idToken;
}

async function lireTelegramMessages(idToken, societeId, bonId) {
    const url = 'https://firestore.googleapis.com/v1/projects/' + PROJECT_ID +
        '/databases/(default)/documents/societes/' + societeId + '/bons/' + bonId +
        '?mask.fieldPaths=telegram_messages';
    const r = await fetch(url, { headers: { Authorization: 'Bearer ' + idToken } });
    if (!r.ok) return [];
    const j = await r.json();
    const arr = j.fields && j.fields.telegram_messages && j.fields.telegram_messages.arrayValue && j.fields.telegram_messages.arrayValue.values;
    if (!Array.isArray(arr)) return [];
    return arr.map(function (v) {
        const f = v.mapValue && v.mapValue.fields;
        if (!f) return null;
        const chat = f.chat_id && (f.chat_id.integerValue || f.chat_id.stringValue);
        const mid = f.message_id && (f.message_id.integerValue || f.message_id.stringValue);
        return chat && mid ? { chat_id: parseInt(chat, 10), message_id: parseInt(mid, 10) } : null;
    }).filter(Boolean);
}

async function retirerBoutons(token, chatId, messageId) {
    const r = await fetch('https://api.telegram.org/bot' + token + '/editMessageReplyMarkup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, message_id: messageId, reply_markup: { inline_keyboard: [] } })
    });
    if (!r.ok) {
        const err = await r.text();
        throw new Error('editMessageReplyMarkup ' + r.status + ' : ' + err);
    }
    return r.json();
}

async function envoyerTelegram(token, chatId, texte) {
    const r = await fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text: texte, parse_mode: 'HTML' })
    });
    if (!r.ok) {
        const err = await r.text();
        throw new Error('sendMessage ' + r.status + ' : ' + err);
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
        const bonId = body.bonId || body.numero || '';
        const numero = body.numero || '';
        const client = body.client || '';
        const montant = body.montant || '';
        const technicien = body.technicien || '';
        const date = body.date || '';

        if (!numero) return res.status(400).json({ error: 'numero manquant' });

        const societeId = (societe === 'elechosystem' || societe === 'elecho') ? 'elechosystem' : 'cep';
        const token = societeId === 'elechosystem'
            ? process.env.TELEGRAM_BOT_TOKEN_ELECHO
            : process.env.TELEGRAM_BOT_TOKEN_CEP;
        if (!token) return res.status(500).json({ error: 'Token Telegram manquant pour ' + societeId });

        const adminsRaw = process.env.TELEGRAM_ADMIN_IDS || '';
        const adminIds = adminsRaw.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        if (adminIds.length === 0) return res.status(500).json({ error: 'TELEGRAM_ADMIN_IDS vide' });

        // 1. Retirer les boutons des messages Telegram d'origine (best effort)
        let boutonsRetires = 0;
        let boutonsEchecs = 0;
        if (bonId) {
            try {
                const idToken = await getAnonToken();
                const messages = await lireTelegramMessages(idToken, societeId, bonId);
                for (const m of messages) {
                    try {
                        await retirerBoutons(token, m.chat_id, m.message_id);
                        boutonsRetires++;
                    } catch (e) {
                        // Si "message is not modified" ou "message to edit not found", pas grave
                        boutonsEchecs++;
                    }
                }
            } catch (e) {
                console.warn('Retrait boutons impossible:', e.message);
            }
        }

        // 2. Envoyer le message de confirmation a tous les admins
        const societeNom = societeId === 'elechosystem' ? 'Elecho' : 'CEP';
        const msg =
            '✅ <b>Bon envoyé en compta — ' + societeNom + '</b>\n' +
            '\n' +
            '<b>N° :</b> ' + numero + '\n' +
            '<b>Client :</b> ' + client + '\n' +
            (technicien ? '<b>Tech :</b> ' + technicien + '\n' : '') +
            (date ? '<b>Date :</b> ' + date + '\n' : '') +
            (montant ? '<b>TTC :</b> ' + montant + '\n' : '') +
            '\n' +
            '<i>Validé depuis l\'admin web — ce bon ne peut plus être modifié.</i>';

        const resultats = [];
        for (const id of adminIds) {
            try {
                await envoyerTelegram(token, id, msg);
                resultats.push({ id: id, ok: true });
            } catch (e) {
                resultats.push({ id: id, ok: false, err: e.message });
            }
        }
        const success = resultats.some(function (r) { return r.ok; });
        return res.status(200).json({
            ok: success,
            boutonsRetires: boutonsRetires,
            boutonsEchecs: boutonsEchecs,
            resultats: resultats
        });
    } catch (e) {
        console.error('notif-telegram error:', e);
        return res.status(500).json({ error: e.message });
    }
}
