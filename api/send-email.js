// Fonction serverless Vercel pour envoyer l'email avec PDF en piece jointe via Nodemailer (SMTP OVH)
// Deployer cette fonction sur Vercel pour securiser vos identifiants SMTP

import nodemailer from 'nodemailer';

export default async function handler(req, res) {
    // Activer CORS pour les requetes depuis le navigateur
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    // Gerer les requetes OPTIONS (preflight)
    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }
    
    // Verifier que c'est une requete POST
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { email, subject, pdfBase64, pdfFileName, bonData, photos } = req.body;

        // Verifier les parametres requis
        if (!email || !subject || !pdfBase64) {
            return res.status(400).json({ error: 'Missing required parameters: email, subject, pdfBase64' });
        }

        // Recuperer les infos de la societe depuis bonData (avec valeurs par defaut CEP)
        const societe = bonData?.societe || {};
        const societeNom = societe.nom || 'Compagnie d\'Electricite Parisienne';
        const societeAdresse = societe.adresse || '6, rue de Metz, 94240 L\'Hay-les-Roses';
        const societeTelephone = societe.telephone || '01 56 04 19 96';
        const societeEmail = societe.email || 'contact@cep75.fr';
        const societeSiteWeb = societe.siteWeb || 'www.cep75.fr';
        const societeCouleur = societe.couleur || '#1a365d';

        // Configuration SMTP OVH depuis les variables d'environnement
        const SMTP_USER = process.env.OVH_SMTP_USER || 'intervention@cep75.fr';
        const SMTP_PASSWORD = process.env.OVH_SMTP_PASSWORD;
        
        if (!SMTP_PASSWORD) {
            return res.status(500).json({ error: 'OVH_SMTP_PASSWORD not configured in Vercel environment variables' });
        }

        // Convertir le PDF base64 en buffer
        const pdfBuffer = Buffer.from(pdfBase64, 'base64');

        // Creer le transporteur Nodemailer avec SMTP OVH
        const transporter = nodemailer.createTransport({
            host: 'ssl0.ovh.net',
            port: 465,
            secure: true, // true pour le port 465 (SSL)
            auth: {
                user: SMTP_USER,
                pass: SMTP_PASSWORD
            }
        });

        // Preparer les pieces jointes (PDF + photos)
        const attachments = [
            {
                filename: pdfFileName || 'bon-intervention.pdf',
                content: pdfBuffer,
                contentType: 'application/pdf'
            }
        ];

        // Ajouter les photos comme pieces jointes
        if (photos && Array.isArray(photos) && photos.length > 0) {
            photos.forEach((photo, index) => {
                if (photo.base64) {
                    // Extraire le type MIME et les donnees base64
                    const base64Data = photo.base64.includes(',') 
                        ? photo.base64.split(',')[1] 
                        : photo.base64;
                    
                    // Determiner le type MIME
                    let mimeType = 'image/jpeg';
                    if (photo.base64.includes('data:image/png')) {
                        mimeType = 'image/png';
                    } else if (photo.base64.includes('data:image/jpeg') || photo.base64.includes('data:image/jpg')) {
                        mimeType = 'image/jpeg';
                    }
                    
                    attachments.push({
                        filename: `photo-${index + 1}.${mimeType === 'image/png' ? 'png' : 'jpg'}`,
                        content: base64Data,
                        encoding: 'base64',
                        contentType: mimeType
                    });
                }
            });
        }

        // Construire le contenu HTML de l'email avec les photos integrees
        let photosHtml = '';
        if (photos && photos.length > 0) {
            photosHtml = `<div style="margin-top: 20px;"><h4 style="color: ${societeCouleur};">Photos de l'intervention :</h4>`;
            photos.forEach((photo, index) => {
                if (photo.base64) {
                    photosHtml += `<div style="margin: 10px 0;">
                        <p style="margin: 5px 0; font-weight: bold;">Photo ${index + 1} :</p>
                        <img src="${photo.base64}" alt="Photo ${index + 1}" style="max-width: 100%; height: auto; border-radius: 6px; border: 1px solid #e2e8f0;" />
                    </div>`;
                }
            });
            photosHtml += '</div>';
        }

        const htmlContent = `
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, ${societeCouleur} 0%, ${societeCouleur}dd 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h2 style="margin: 0; font-size: 20px;">${societeNom}</h2>
                </div>
                <div style="background: #f7fafc; padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <h3 style="color: ${societeCouleur}; margin-top: 0;">Bon d'Intervention ${bonData?.numero || ''}</h3>
                    <p>Bonjour,</p>
                    <p>Veuillez trouver ci-joint le PDF de votre bon d'intervention${photos && photos.length > 0 ? ' ainsi que les photos de l\'intervention' : ''}.</p>
                    ${bonData ? `
                        <div style="background: white; padding: 15px; border-radius: 6px; margin: 15px 0;">
                            <p style="margin: 5px 0;"><strong>Date :</strong> ${bonData.date || ''}</p>
                            <p style="margin: 5px 0;"><strong>Client :</strong> ${bonData.client || ''}</p>
                            ${bonData.adresse ? `<p style="margin: 5px 0;"><strong>Adresse :</strong> ${bonData.adresse}</p>` : ''}
                            <p style="margin: 5px 0;"><strong>Technicien :</strong> ${bonData.technicien || ''}</p>
                            ${bonData.heure_arrivee ? `<p style="margin: 5px 0;"><strong>Heure d'arrivee :</strong> ${bonData.heure_arrivee}</p>` : ''}
                            ${bonData.heure_depart ? `<p style="margin: 5px 0;"><strong>Heure de depart :</strong> ${bonData.heure_depart}</p>` : ''}
                        </div>
                    ` : ''}
                    ${photosHtml}
                    <p style="margin-top: 20px;">Cordialement,<br><strong>${societeNom}</strong></p>
                    <p style="font-size: 12px; color: #718096; margin-top: 20px;">
                        ${societeAdresse}<br>
                        Tel. ${societeTelephone} | ${societeEmail} | ${societeSiteWeb}
                    </p>
                </div>
            </div>
        `;

        // Envoyer l'email via Nodemailer
        const info = await transporter.sendMail({
            from: `${societeNom} <${SMTP_USER}>`,
            to: email,
            subject: subject,
            html: htmlContent,
            attachments: attachments
        });

        console.log('Email envoye avec succes:', info.messageId);

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
