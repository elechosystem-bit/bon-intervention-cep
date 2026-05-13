// Vérification quotidienne des contrôles électriques Apave (société CEP).
//
// Pour chaque client dont les travaux sont réalisés depuis >= 300 jours et dont
// l'alerte n'a pas encore été envoyée : envoie un e-mail récapitulatif à CEP puis
// pose le flag alerteApaveEnvoyee (pour ne pas renvoyer le même cycle).
//
// N'utilise PAS firebase-admin (qui ne se charge pas sur cette plateforme) :
// lit/écrit Firestore via l'API REST + une session anonyme, exactement comme la
// page apave.html. Aucune écriture sur les bons, aucune suppression.
//
// Déclenché par un cron Vercel quotidien ET/OU une tâche planifiée VPS (curl).
// L'endpoint est idempotent : si plusieurs appels ont lieu le même jour, le flag
// empêche tout doublon d'e-mail.

import nodemailer from 'nodemailer';

const FIREBASE_API_KEY = 'AIzaSyAuX2gsGiRGqVbsk93y0wmwJOsT-RuEkE4';
const PROJECT_ID = 'bon-d-intervention-cep';

async function getAnonToken() {
    const r = await fetch('https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=' + FIREBASE_API_KEY, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ returnSecureToken: true })
    });
    if (!r.ok) throw new Error('Auth anonyme échouée : ' + r.status + ' ' + (await r.text()));
    const j = await r.json();
    return j.idToken;
}

async function listApave(token) {
    const docs = [];
    let pageToken = null;
    do {
        let url = 'https://firestore.googleapis.com/v1/projects/' + PROJECT_ID +
            '/databases/(default)/documents/societes/cep/apave?pageSize=300';
        if (pageToken) url += '&pageToken=' + encodeURIComponent(pageToken);
        const r = await fetch(url, { headers: { Authorization: 'Bearer ' + token } });
        if (!r.ok) throw new Error('Lecture Firestore échouée : ' + r.status + ' ' + (await r.text()));
        const j = await r.json();
        (j.documents || []).forEach(d => docs.push(d));
        pageToken = j.nextPageToken || null;
    } while (pageToken);
    return docs;
}

function getField(d, name) {
    const v = d.fields && d.fields[name];
    if (!v) return undefined;
    if (v.stringValue !== undefined) return v.stringValue;
    if (v.booleanValue !== undefined) return v.booleanValue;
    if (v.integerValue !== undefined) return parseInt(v.integerValue, 10);
    if (v.doubleValue !== undefined) return v.doubleValue;
    return undefined;
}

async function poserFlag(token, docResourceName, dateStr) {
    const url = 'https://firestore.googleapis.com/v1/' + docResourceName +
        '?updateMask.fieldPaths=alerteApaveEnvoyee&updateMask.fieldPaths=alerteApaveDate';
    const r = await fetch(url, {
        method: 'PATCH',
        headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({
            fields: {
                alerteApaveEnvoyee: { booleanValue: true },
                alerteApaveDate: { stringValue: dateStr }
            }
        })
    });
    if (!r.ok) throw new Error('Écriture flag échouée : ' + r.status + ' ' + (await r.text()));
}

function joursDepuis(dateStr) {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return null;
    return Math.floor((Date.now() - d.getTime()) / 86400000);
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');

    // Sécurité légère : autorisé si cron Vercel OU token connu (?token=apave-quotidien)
    const okCron = req.headers['x-vercel-cron'] === '1';
    const okToken = req.query && req.query.token === 'apave-quotidien';
    if (!okCron && !okToken) return res.status(401).json({ error: 'Non autorisé' });

    const SMTP_USER = process.env.OVH_SMTP_USER || 'intervention@cep75.fr';
    const SMTP_PASSWORD = process.env.OVH_SMTP_PASSWORD;
    const DEST = process.env.APAVE_ALERT_EMAIL || 'contact@cep75.fr';

    try {
        const token = await getAnonToken();
        const docs = await listApave(token);

        const aAlerter = [];
        for (const d of docs) {
            const travaux = getField(d, 'travauxFaitsDate');
            if (!travaux) continue;
            if (getField(d, 'alerteApaveEnvoyee')) continue;
            const j = joursDepuis(travaux);
            if (j === null || j < 300) continue;
            aAlerter.push({
                docResourceName: d.name,
                nom: getField(d, 'name') || '(sans nom)',
                contact: getField(d, 'contact') || '',
                jours: j,
                travaux: travaux
            });
        }

        if (aAlerter.length === 0) {
            return res.status(200).json({ ok: true, alertes: 0, message: 'Aucun client à alerter aujourd\'hui' });
        }

        let emailEnvoye = false;
        if (SMTP_PASSWORD) {
            const transporter = nodemailer.createTransport({
                host: 'ssl0.ovh.net', port: 465, secure: true,
                auth: { user: SMTP_USER, pass: SMTP_PASSWORD }
            });
            const lignes = aAlerter.map(c => {
                const restant = 365 - c.jours;
                const etat = c.jours >= 365
                    ? 'DÉPASSÉ de ' + (c.jours - 365) + ' jour(s)'
                    : 'dans ' + restant + ' jour(s)';
                return '• ' + c.nom + (c.contact ? '  (' + c.contact + ')' : '')
                     + ' — contrôle de conformité ' + etat
                     + '   [travaux réalisés le ' + c.travaux + ', soit J+' + c.jours + ']';
            }).join('\n');
            const corps =
'Rappel automatique — mises en conformité électrique (CEP)\n' +
'==========================================================\n\n' +
aAlerter.length + ' client(s) arrivent à échéance de leur contrôle annuel\n' +
'(300 jours ou plus depuis la réalisation des travaux) :\n\n' +
lignes + '\n\n' +
'Pensez à relancer le cycle de mise en conformité pour ces clients\n' +
'(nouveau rapport → devis → travaux).\n\n' +
'— Message envoyé automatiquement par l\'outil Bon d\'intervention.';
            await transporter.sendMail({
                from: '"CEP — Mise en conformité" <' + SMTP_USER + '>',
                to: DEST,
                subject: '⚠ Mise en conformité — ' + aAlerter.length + ' client(s) à relancer',
                text: corps
            });
            emailEnvoye = true;
        }

        if (emailEnvoye) {
            const today = new Date().toISOString().slice(0, 10);
            for (const c of aAlerter) {
                try { await poserFlag(token, c.docResourceName, today); }
                catch (e) { console.error('Flag non posé pour', c.nom, ':', e.message); }
            }
        }

        return res.status(200).json({
            ok: true,
            alertes: aAlerter.length,
            emailEnvoye,
            destinataire: DEST,
            clients: aAlerter.map(c => c.nom + ' (J+' + c.jours + ')')
        });
    } catch (e) {
        console.error('check-apave error:', e);
        return res.status(500).json({ error: e.message });
    }
}
