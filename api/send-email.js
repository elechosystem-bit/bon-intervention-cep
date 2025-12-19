// Fonction serverless Vercel pour envoyer l'email avec PDF en pièce jointe via Nodemailer (SMTP OVH)
// Déployez cette fonction sur Vercel pour sécuriser vos identifiants SMTP

import nodemailer from 'nodemailer';

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
        const { email, subject, pdfBase64, pdfFileName, bonData } = req.body;

        // Vérifier les paramètres requis
        if (!email || !subject || !pdfBase64) {
            return res.status(400).json({ error: 'Missing required parameters: email, subject, pdfBase64' });
        }

        // Configuration SMTP OVH depuis les variables d'environnement
        const SMTP_USER = process.env.OVH_SMTP_USER || 'intervention@cep75.fr';
        const SMTP_PASSWORD = process.env.OVH_SMTP_PASSWORD;
        
        if (!SMTP_PASSWORD) {
            return res.status(500).json({ error: 'OVH_SMTP_PASSWORD not configured in Vercel environment variables' });
        }

        // Convertir le PDF base64 en buffer
        const pdfBuffer = Buffer.from(pdfBase64, 'base64');

        // Créer le transporteur Nodemailer avec SMTP OVH
        const transporter = nodemailer.createTransport({
            host: 'ssl0.ovh.net',
            port: 465,
            secure: true, // true pour le port 465 (SSL)
            auth: {
                user: SMTP_USER,
                pass: SMTP_PASSWORD
            }
        });

        // Construire le contenu HTML de l'email
        const htmlContent = `
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h2 style="margin: 0; font-size: 20px;">⚡ Compagnie d'Électricité Parisienne</h2>
                </div>
                <div style="background: #f7fafc; padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <h3 style="color: #1a365d; margin-top: 0;">Bon d'Intervention ${bonData?.numero || ''}</h3>
                    <p>Bonjour,</p>
                    <p>Veuillez trouver ci-joint le PDF de votre bon d'intervention.</p>
                    ${bonData ? `
                        <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                            <p style="margin: 5px 0;"><strong>Date :</strong> ${bonData.date || ''}</p>
                            <p style="margin: 5px 0;"><strong>Client :</strong> ${bonData.client || ''}</p>
                            ${bonData.adresse ? `<p style="margin: 5px 0;"><strong>Adresse :</strong> ${bonData.adresse}</p>` : ''}
                            <p style="margin: 5px 0;"><strong>Technicien :</strong> ${bonData.technicien || ''}</p>
                            ${bonData.heure_arrivee ? `<p style="margin: 5px 0;"><strong>Heure d'arrivée :</strong> ${bonData.heure_arrivee}</p>` : ''}
                            ${bonData.heure_depart ? `<p style="margin: 5px 0;"><strong>Heure de départ :</strong> ${bonData.heure_depart}</p>` : ''}
                        </div>
                    ` : ''}
                    <p style="margin-top: 20px;">Cordialement,<br><strong>Compagnie d'Électricité Parisienne</strong></p>
                    <p style="font-size: 12px; color: #718096; margin-top: 20px;">
                        6, rue de Metz, 94240 L'Haÿ-les-Roses<br>
                        Tél. 01 56 04 19 96 | contact@cep75.fr | www.cep75.fr
                    </p>
                </div>
            </div>
        `;

        // Envoyer l'email via Nodemailer
        const info = await transporter.sendMail({
            from: `Compagnie d'Électricité Parisienne <${SMTP_USER}>`,
            to: email,
            subject: subject,
            html: htmlContent,
            attachments: [
                {
                    filename: pdfFileName || 'bon-intervention.pdf',
                    content: pdfBuffer,
                    contentType: 'application/pdf'
                }
            ]
        });

        console.log('Email envoyé avec succès:', info.messageId);

        return res.status(200).json({ 
            success: true, 
            messageId: info.messageId,
            message: 'Email sent successfully via OVH SMTP' 
        });

    } catch (error) {
        console.error('Error sending email via OVH SMTP:', error);
        return res.status(500).json({ 
            error: error.message || 'Internal server error',
            details: error.response || error.code
        });
    }
}

