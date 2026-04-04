"""Email client for sending bon d'intervention to accounting via SMTP OVH."""

import logging
import smtplib
from email.mime.text import MIMEText

from config import (
    EMAIL_COMPTA,
    OVH_SMTP_PASSWORD,
    OVH_SMTP_USER,
    SOCIETE_NOM,
)

logger = logging.getLogger(__name__)


def send_compta_email(bon_data: dict, statut: str):
    """
    Send bon d'intervention to accounting email in plain text.

    statut: "valide" or "refuse"
    """
    if not OVH_SMTP_PASSWORD:
        logger.error("OVH_SMTP_PASSWORD non configure, email non envoye")
        return

    numero = bon_data.get("numero", "?")
    client = bon_data.get("client", "?")
    date = bon_data.get("date", "?")
    adresse = bon_data.get("address", "")
    technicien = bon_data.get("technicien", "?")
    heure_arrivee = bon_data.get("heureArrivee", "")
    heure_depart = bon_data.get("heureDepart", "")
    description = bon_data.get("description", "")
    total_ttc = bon_data.get("totalTTC", "0.00EUR")
    total_ht = bon_data.get("totalHT", "?")
    total_tva = bon_data.get("totalTVA", "?")

    # Sujet et bandeau selon le statut
    if statut == "valide":
        subject = "VALIDE - Bon {} - {} - {}".format(numero, client, total_ttc)
        bandeau = "VALIDE - Brouillon Pennylane cree"
    else:
        subject = "NE PAS FACTURER - Bon {} - {}".format(numero, client)
        bandeau = "REFUSE - NE PAS FACTURER"

    # Lignes produits
    produits_lines = []
    produits = bon_data.get("produits", [])
    for p in produits:
        nom = p.get("nom", "?")
        qty = p.get("quantite", 0)
        prix = p.get("prixUnitaire", 0)
        total = qty * prix
        produits_lines.append("  - {} : {} x {:.2f} EUR = {:.2f} EUR".format(nom, qty, prix, total))

    # Corps du mail
    lines = []
    lines.append("=" * 45)
    lines.append("  {}".format(bandeau))
    lines.append("=" * 45)
    lines.append("")
    lines.append("Bon d'Intervention {}".format(numero))
    lines.append("")
    lines.append("Date : {}".format(date))
    lines.append("Client : {}".format(client))
    if adresse:
        lines.append("Adresse : {}".format(adresse))
    lines.append("Technicien : {}".format(technicien))
    if description:
        lines.append("Description : {}".format(description))
    if heure_arrivee:
        lines.append("Horaires : {} - {}".format(heure_arrivee, heure_depart))
    lines.append("")

    if produits_lines:
        lines.append("PRESTATIONS :")
        lines.append("-" * 45)
        lines.extend(produits_lines)
        lines.append("-" * 45)
        lines.append("")

    # Main d'oeuvre et deplacement
    mo = bon_data.get("subtotalMO", "")
    depl = bon_data.get("subtotalDepl", "")
    if mo and mo != "0.00EUR":
        lines.append("Main d'oeuvre : {} ({})".format(mo, bon_data.get("moDuree", "")))
    if depl and depl != "0.00EUR":
        lines.append("Deplacement : {}".format(depl))
    if mo or depl:
        lines.append("")

    lines.append("Total HT  : {}".format(total_ht))
    lines.append("TVA (10%) : {}".format(total_tva))
    lines.append("Total TTC : {}".format(total_ttc))
    lines.append("")
    lines.append("=" * 45)

    if statut == "refuse":
        lines.append("")
        lines.append("*** CE BON NE DOIT PAS ETRE FACTURE ***")
        lines.append("")

    lines.append("")
    lines.append("Cordialement,")
    lines.append(SOCIETE_NOM)

    body = "\n".join(lines)

    # Envoi SMTP texte brut
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = "{} <{}>".format(SOCIETE_NOM, OVH_SMTP_USER)
    msg["To"] = EMAIL_COMPTA
    msg["Subject"] = subject

    try:
        with smtplib.SMTP_SSL("ssl0.ovh.net", 465) as server:
            server.login(OVH_SMTP_USER, OVH_SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Email compta envoye pour bon {} (statut={})".format(numero, statut))
    except Exception as e:
        logger.error("Erreur envoi email compta pour bon {}: {}".format(numero, e))
        raise
