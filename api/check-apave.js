// Vérification quotidienne des contrôles électriques Apave (société CEP).
// Pour chaque client dont les travaux sont réalisés depuis >= 300 jours et
// dont l'alerte n'a pas encore été envoyée : envoie un e-mail récapitulatif à
// CEP puis marque le client (alerteApaveEnvoyee) pour ne pas renvoyer.
//
// Déclenché par un cron Vercel ET/OU une tâche planifiée sur le VPS (curl).
// Aucune suppression, aucune écriture sur les bons : uniquement le champ
// alerteApaveEnvoyee / alerteApaveDate sur les fiches societes/cep/apave.

import { initializeApp, cert, getApps } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import nodemailer from 'nodemailer';

function getDb() {
    if (!process.env.FIREBASE_ADMIN_CREDENTIALS) return null;
    try {
        const sa = JSON.parse(process.env.FIREBASE_ADMIN_CREDENTIALS);
        if (getApps().length === 0) initializeApp({ credential: cert(sa) });
        return getFirestore();
    } catch (e) {
        console.error('Erreur init Firebase Admin:', e);
        return null;
    }
}

function joursDepuis(dateStr) {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return null;
    return Math.floor((Date.now() - d.getTime()) / 86400000);
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');

    // Sécurité légère : autorisé si appel cron Vercel OU token connu (?token=apave-quotidien)
    const okCron = req.headers['x-vercel-cron'] === '1';
    const okToken = req.query && req.query.token === 'apave-quotidien';
    if (!okCron && !okToken) return res.status(401).json({ error: 'Non autorisé' });

    const db = getDb();
    if (!db) return res.status(500).json({ error: 'Firebase Admin non configuré (FIREBASE_ADMIN_CREDENTIALS manquant)' });

    const SMTP_USER = process.env.OVH_SMTP_USER || 'intervention@cep75.fr';
    const SMTP_PASSWORD = process.env.OVH_SMTP_PASSWORD;
    const DEST = process.env.APAVE_ALERT_EMAIL || 'contact@cep75.fr';

    try {
        const snap = await db.collection('societes').doc('cep').collection('apave').get();
        const aAlerter = [];
        snap.forEach(doc => {
            const c = doc.data();
            if (!c || !c.travauxFaitsDate) return;
            if (c.alerteApaveEnvoyee) return;
            const j = joursDepuis(c.travauxFaitsDate);
            if (j === null) return;
            if (j >= 300) {
                aAlerter.push({
                    id: doc.id,
                    nom: c.name || '(sans nom)',
                    contact: c.contact || '',
                    jours: j,
                    travauxFaitsDate: c.travauxFaitsDate
                });
            }
        });

        if (aAlerter.length === 0) {
            return res.status(200).json({ ok: true, alertes: 0, message: 'Aucun client à alerter aujourd\'hui' });
        }

        let emailEnvoye = false;
        if (SMTP_PASSWORD) {
            const transporter = nodemailer.createTransport({
                host: 'ssl0.ovh.net',
                port: 465,
                secure: true,
                auth: { user: SMTP_USER, pass: SMTP_PASSWORD }
            });
            const lignes = aAlerter.map(c => {
                const restant = 365 - c.jours;
                const etat = c.jours >= 365
                    ? 'DÉPASSÉ de ' + (c.jours - 365) + ' jour(s)'
                    : 'dans ' + restant + ' jour(s)';
                return '• ' + c.nom + (c.contact ? '  (' + c.contact + ')' : '')
                     + ' — contrôle Apave ' + etat
                     + '   [travaux réalisés le ' + c.travauxFaitsDate + ', soit J+' + c.jours + ']';
            }).join('\n');
            const corps =
'Rappel automatique — contrôles électriques Apave (CEP)\n' +
'==========================================================\n\n' +
aAlerter.length + ' client(s) arrivent à échéance de leur contrôle annuel\n' +
'(300 jours ou plus depuis la réalisation des travaux) :\n\n' +
lignes + '\n\n' +
'Pensez à relancer le cycle Apave pour ces clients\n' +
'(nouveau rapport → devis → travaux).\n\n' +
'— Message envoyé automatiquement par l\'outil Bon d\'intervention.';
            await transporter.sendMail({
                from: '"CEP — Suivi Apave" <' + SMTP_USER + '>',
                to: DEST,
                subject: '⚠ Apave — ' + aAlerter.length + ' client(s) à relancer',
                text: corps
            });
            emailEnvoye = true;
        }

        if (emailEnvoye) {
            const today = new Date().toISOString().slice(0, 10);
            for (const c of aAlerter) {
                await db.collection('societes').doc('cep').collection('apave').doc(c.id).update({
                    alerteApaveEnvoyee: true,
                    alerteApaveDate: today
                });
            }
        }

        return res.status(200).json({
            ok: true,
            alertes: aAlerter.length,
            emailEnvoye,
            destinataire: DEST,
            clients: aAlerter.map(c => c.nom)
        });
    } catch (e) {
        console.error('check-apave error:', e);
        return res.status(500).json({ error: e.message });
    }
}
