// API serverless Vercel pour gérer les paiements GoCardless
// Déployez cette fonction sur Vercel pour sécuriser vos identifiants GoCardless

export default async function handler(req, res) {
    // Activer CORS pour les requêtes depuis le navigateur
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    // Gérer les requêtes OPTIONS (preflight)
    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }
    
    // Vérifier que c'est une requête POST
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { bonId, bonNumber, amount, originalAmount, discount, penalty, iban, accountHolder, clientEmail, clientName } = req.body;

        // Vérifier les paramètres requis
        if (!bonId || !bonNumber || !amount || !iban || !accountHolder) {
            return res.status(400).json({ error: 'Missing required parameters' });
        }

        // Configuration GoCardless depuis les variables d'environnement
        const GOCARDLESS_ACCESS_TOKEN = process.env.GOCARDLESS_ACCESS_TOKEN;
        const GOCARDLESS_ENVIRONMENT = process.env.GOCARDLESS_ENVIRONMENT || 'sandbox';
        
        if (!GOCARDLESS_ACCESS_TOKEN) {
            return res.status(500).json({ error: 'GOCARDLESS_ACCESS_TOKEN not configured in Vercel environment variables' });
        }

        const apiUrl = GOCARDLESS_ENVIRONMENT === 'live' 
            ? 'https://api.gocardless.com' 
            : 'https://api-sandbox.gocardless.com';

        // Étape 1: Créer un customer (client)
        const customerResponse = await fetch(`${apiUrl}/customers`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${GOCARDLESS_ACCESS_TOKEN}`,
                'GoCardless-Version': '2015-07-06',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                customers: {
                    email: clientEmail || `client-${bonNumber}@example.com`,
                    given_name: clientName || accountHolder,
                    family_name: '',
                    address_line1: '',
                    city: '',
                    postal_code: '',
                    country_code: 'FR'
                }
            })
        });

        if (!customerResponse.ok) {
            const errorData = await customerResponse.json();
            console.error('Erreur création customer GoCardless:', errorData);
            throw new Error('Erreur lors de la création du client: ' + (errorData.error?.message || 'Unknown error'));
        }

        const customerData = await customerResponse.json();
        const customerId = customerData.customers.id;

        // Étape 2: Créer un customer bank account (compte bancaire)
        const bankAccountResponse = await fetch(`${apiUrl}/customer_bank_accounts`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${GOCARDLESS_ACCESS_TOKEN}`,
                'GoCardless-Version': '2015-07-06',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                customer_bank_accounts: {
                    account_holder_name: accountHolder,
                    iban: iban,
                    links: {
                        customer: customerId
                    }
                }
            })
        });

        if (!bankAccountResponse.ok) {
            const errorData = await bankAccountResponse.json();
            console.error('Erreur création bank account GoCardless:', errorData);
            throw new Error('Erreur lors de la création du compte bancaire: ' + (errorData.error?.message || 'Unknown error'));
        }

        const bankAccountData = await bankAccountResponse.json();
        const bankAccountId = bankAccountData.customer_bank_accounts.id;

        // Étape 3: Créer un mandat de prélèvement (mandate)
        const mandateResponse = await fetch(`${apiUrl}/mandates`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${GOCARDLESS_ACCESS_TOKEN}`,
                'GoCardless-Version': '2015-07-06',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                mandates: {
                    scheme: 'sepa_core',
                    links: {
                        customer_bank_account: bankAccountId
                    },
                    metadata: {
                        bon_id: bonId,
                        bon_number: bonNumber
                    }
                }
            })
        });

        if (!mandateResponse.ok) {
            const errorData = await mandateResponse.json();
            console.error('Erreur création mandate GoCardless:', errorData);
            throw new Error('Erreur lors de la création du mandat: ' + (errorData.error?.message || 'Unknown error'));
        }

        const mandateData = await mandateResponse.json();
        const mandateId = mandateData.mandates.id;

        // Étape 4: Créer le paiement (payment)
        // Convertir le montant en centimes (GoCardless utilise les centimes)
        const amountInPence = Math.round(amount * 100);

        const paymentResponse = await fetch(`${apiUrl}/payments`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${GOCARDLESS_ACCESS_TOKEN}`,
                'GoCardless-Version': '2015-07-06',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                payments: {
                    amount: amountInPence,
                    currency: 'EUR',
                    links: {
                        mandate: mandateId
                    },
                    metadata: {
                        bon_id: bonId,
                        bon_number: bonNumber,
                        original_amount: originalAmount.toString(),
                        discount: discount.toString(),
                        penalty: penalty.toString()
                    }
                }
            })
        });

        if (!paymentResponse.ok) {
            const errorData = await paymentResponse.json();
            console.error('Erreur création payment GoCardless:', errorData);
            throw new Error('Erreur lors de la création du paiement: ' + (errorData.error?.message || 'Unknown error'));
        }

        const paymentData = await paymentResponse.json();
        const paymentId = paymentData.payments.id;

        // Retourner les IDs pour enregistrement dans Firebase
        return res.status(200).json({
            success: true,
            customerId: customerId,
            bankAccountId: bankAccountId,
            mandateId: mandateId,
            paymentId: paymentId,
            status: paymentData.payments.status
        });

    } catch (error) {
        console.error('Erreur API payment:', error);
        return res.status(500).json({ 
            error: 'Erreur lors du traitement du paiement',
            message: error.message 
        });
    }
}

