// API serverless Vercel pour recevoir les webhooks GoCardless
// Configurez cette URL dans votre dashboard GoCardless comme endpoint webhook

import { initializeApp, cert } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';

// Initialiser Firebase Admin (nécessite les credentials dans les variables d'environnement)
let db;
try {
    if (!process.env.FIREBASE_ADMIN_CREDENTIALS) {
        console.warn('FIREBASE_ADMIN_CREDENTIALS not configured, webhook will use client SDK');
    } else {
        const serviceAccount = JSON.parse(process.env.FIREBASE_ADMIN_CREDENTIALS);
        initializeApp({
            credential: cert(serviceAccount)
        });
        db = getFirestore();
    }
} catch (error) {
    console.error('Erreur initialisation Firebase Admin:', error);
}

export default async function handler(req, res) {
    // GoCardless envoie les webhooks en POST
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        // Vérifier la signature du webhook (sécurité)
        const webhookSecret = process.env.GOCARDLESS_WEBHOOK_SECRET;
        const signature = req.headers['webhook-signature'];
        
        // TODO: Implémenter la vérification de signature GoCardless
        // Pour l'instant, on fait confiance (à sécuriser en production)
        
        const { events } = req.body;

        if (!events || !Array.isArray(events)) {
            return res.status(400).json({ error: 'Invalid webhook payload' });
        }

        // Traiter chaque événement
        for (const event of events) {
            await processWebhookEvent(event);
        }

        return res.status(200).json({ received: true });

    } catch (error) {
        console.error('Erreur traitement webhook GoCardless:', error);
        return res.status(500).json({ 
            error: 'Erreur lors du traitement du webhook',
            message: error.message 
        });
    }
}

async function processWebhookEvent(event) {
    const { resource_type, action, links } = event;
    
    console.log(`Webhook GoCardless: ${resource_type} - ${action}`);

    // Si c'est un événement de paiement
    if (resource_type === 'payments') {
        const paymentId = links?.payment;
        
        if (!paymentId) {
            console.warn('Payment ID manquant dans le webhook');
            return;
        }

        // Récupérer les détails du paiement depuis GoCardless
        const GOCARDLESS_ACCESS_TOKEN = process.env.GOCARDLESS_ACCESS_TOKEN;
        const GOCARDLESS_ENVIRONMENT = process.env.GOCARDLESS_ENVIRONMENT || 'sandbox';
        const apiUrl = GOCARDLESS_ENVIRONMENT === 'live' 
            ? 'https://api.gocardless.com' 
            : 'https://api-sandbox.gocardless.com';

        try {
            const paymentResponse = await fetch(`${apiUrl}/payments/${paymentId}`, {
                headers: {
                    'Authorization': `Bearer ${GOCARDLESS_ACCESS_TOKEN}`,
                    'GoCardless-Version': '2015-07-06'
                }
            });

            if (!paymentResponse.ok) {
                throw new Error('Erreur récupération paiement GoCardless');
            }

            const paymentData = await paymentResponse.json();
            const payment = paymentData.payments;
            const metadata = payment.metadata || {};
            const bonId = metadata.bon_id;
            const bonNumber = metadata.bon_number;

            if (!bonId || !bonNumber) {
                console.warn('Bon ID ou numéro manquant dans les métadonnées du paiement');
                return;
            }

            // Mettre à jour le statut du paiement dans Firebase
            if (db) {
                // Utiliser Firebase Admin
                const paiementsRef = db.collection('paiements');
                const querySnapshot = await paiementsRef
                    .where('gocardlessPaymentId', '==', paymentId)
                    .get();

                if (!querySnapshot.empty) {
                    const paiementDoc = querySnapshot.docs[0];
                    await paiementDoc.ref.update({
                        status: payment.status,
                        updatedAt: new Date()
                    });
                }

                // Mettre à jour le statut du bon
                const bonsRef = db.collection('bons');
                const bonSnapshot = await bonsRef
                    .where('numero', '==', bonNumber)
                    .get();

                if (!bonSnapshot.empty) {
                    const bonDoc = bonSnapshot.docs[0];
                    const newStatus = payment.status === 'paid_out' ? 'paid' : 
                                     payment.status === 'failed' ? 'failed' : 
                                     payment.status === 'cancelled' ? 'cancelled' : 'pending';
                    
                    await bonDoc.ref.update({
                        paymentStatus: newStatus,
                        paymentUpdatedAt: new Date()
                    });
                }
            } else {
                // Fallback: utiliser le client SDK (moins sécurisé)
                console.warn('Firebase Admin non configuré, webhook ne peut pas mettre à jour Firebase');
            }

            // Envoyer les notifications email si le paiement est réussi
            if (payment.status === 'paid_out') {
                await sendPaymentNotifications(bonNumber, payment.amount / 100, metadata);
            }

        } catch (error) {
            console.error('Erreur traitement événement paiement:', error);
        }
    }
}

async function sendPaymentNotifications(bonNumber, amount, metadata) {
    try {
        // Appeler votre API d'envoi d'email
        const emailApiUrl = process.env.EMAIL_API_URL || 'https://votre-api.vercel.app/api/send-email';
        
        // Email pour vous
        await fetch(emailApiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: process.env.ADMIN_EMAIL || 'a.mathieu@elechosystem.com',
                subject: `✅ Paiement reçu - Bon ${bonNumber}`,
                html: `
                    <h2>Paiement reçu</h2>
                    <p>Un paiement a été effectué pour le bon d'intervention <strong>BI-${bonNumber}</strong>.</p>
                    <p><strong>Montant:</strong> ${amount.toFixed(2)}€</p>
                    ${metadata.discount > 0 ? `<p><strong>Réduction appliquée:</strong> ${metadata.discount}€</p>` : ''}
                    ${metadata.penalty > 0 ? `<p><strong>Pénalités:</strong> ${metadata.penalty}€</p>` : ''}
                    <p>Le paiement a été traité avec succès via GoCardless.</p>
                `
            })
        });

        // Email pour la comptabilité (Nadine)
        const comptabiliteEmail = process.env.COMPTABILITE_EMAIL || 'nadine@elechosystem.com';
        if (comptabiliteEmail) {
            await fetch(emailApiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: comptabiliteEmail,
                    subject: `💰 Paiement reçu - Bon ${bonNumber}`,
                    html: `
                        <h2>Paiement reçu</h2>
                        <p>Un paiement a été effectué pour le bon d'intervention <strong>BI-${bonNumber}</strong>.</p>
                        <p><strong>Montant:</strong> ${amount.toFixed(2)}€</p>
                        <p>Le paiement a été traité avec succès via GoCardless.</p>
                    `
                })
            });
        }

    } catch (error) {
        console.error('Erreur envoi notifications email:', error);
    }
}

