// Notification Telegram quand un bon est valide en compta depuis l'admin web.
//
// Appelle par admin.html juste apres l'envoi du mail comptabilite.
// Pour chaque message Telegram d'origine (un par admin destinataire),
// EDITE le texte pour afficher "✅ BON VALIDE" et retire les boutons
// "Valider / Refuser / Modifier" (idem comportement clic Telegram natif).
// Si aucun message d'origine n'est trouve (bon ancien sans telegram_messages),
// envoie un nouveau message court a tous les admins en fallback.
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

async function editerMessage(token, chatId, messageId, texte) {
    const r = await fetch('https://api.telegram.org/bot' + token + '/editMessageText', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            chat_id: chatId,
            message_id: messageId,
            text: texte,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [] }
        })
    });
    if (!r.ok) {
        const err = await r.text();
        throw new Error('editMessageText ' + r.status + ' : ' + err);
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
        const action = (body.action || 'valide').toLowerCase();  // 'valide' ou 'refuse'

        if (!numero) return res.status(400).json({ error: 'numero manquant' });

        const societeId = (societe === 'elechosystem' || societe === 'elecho') ? 'elechosystem' : 'cep';
        const token = societeId === 'elechosystem'
            ? process.env.TELEGRAM_BOT_TOKEN_ELECHO
            : process.env.TELEGRAM_BOT_TOKEN_CEP;
        if (!token) return res.status(500).json({ error: 'Token Telegram manquant pour ' + societeId });

        // Heure FR pour l'affichage
        const heureFr = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' });
        const estRefus = action === 'refuse' || action === 'refus';
        const entete = estRefus
            ? '❌ <b>BON REFUSÉ — ' + heureFr + '</b>'
            : '✅ <b>BON VALIDÉ — ' + heureFr + '</b>';
        const piedDePage = estRefus
            ? '<i>Refusé depuis l\'admin web — email \"NE PAS FACTURER\" envoyé à la compta.</i>'
            : '<i>Envoyé en compta depuis l\'admin web.</i>';
        const texteEdit =
            entete + '\n' +
            '\n' +
            'N° ' + numero + (client ? ' (' + client + ')' : '') + (montant ? ' — ' + montant : '') + '\n' +
            (technicien ? 'Tech : ' + technicien + '\n' : '') +
            '\n' +
            piedDePage;

        // 1. Editer chaque message Telegram d'origine (boutons retires + texte remplace)
        let editsOk = 0;
        let editsKo = 0;
        let messages = [];
        if (bonId) {
            try {
                const idToken = await getAnonToken();
                messages = await lireTelegramMessages(idToken, societeId, bonId);
                for (const m of messages) {
                    try {
                        await editerMessage(token, m.chat_id, m.message_id, texteEdit);
                        editsOk++;
                    } catch (e) {
                        editsKo++;
                    }
                }
            } catch (e) {
                console.warn('Edition messages impossible:', e.message);
            }
        }

        // 2. Fallback : si aucun message d'origine connu (bon ancien) -> envoyer
        //    un nouveau message a tous les admins, sinon ils ne sauraient pas.
        let fallbackResultats = [];
        if (editsOk === 0) {
            const adminsRaw = process.env.TELEGRAM_ADMIN_IDS || '';
            const adminIds = adminsRaw.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
            for (const id of adminIds) {
                try {
                    await envoyerTelegram(token, id, texteEdit);
                    fallbackResultats.push({ id: id, ok: true });
                } catch (e) {
                    fallbackResultats.push({ id: id, ok: false, err: e.message });
                }
            }
        }

        return res.status(200).json({
            ok: editsOk > 0 || fallbackResultats.some(function (r) { return r.ok; }),
            editsOk: editsOk,
            editsKo: editsKo,
            fallback: fallbackResultats
        });
    } catch (e) {
        console.error('notif-telegram error:', e);
        return res.status(500).json({ error: e.message });
    }
}
