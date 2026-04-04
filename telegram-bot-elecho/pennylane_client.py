"""Pennylane API client - DRAFT CREATION ONLY.

REGLE ABSOLUE: Ce module ne peut QUE creer des brouillons de facture.
Aucun endpoint de finalisation, modification, comptabilite, paiement ou banque.
"""

import logging
from datetime import date

import httpx

from config import PENNYLANE_API_KEY, PENNYLANE_API_URL

logger = logging.getLogger(__name__)


def _headers():
    return {
        "Authorization": f"Bearer {PENNYLANE_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def create_invoice_draft(bon_data: dict, bon_id: str) -> dict:
    """
    Create a draft invoice in Pennylane from a bon d'intervention.

    Returns the Pennylane API response dict on success.
    Raises an exception on failure.
    """
    # Build line items from produits
    line_items = []

    produits = bon_data.get("produits", [])
    for p in produits:
        qty = p.get("quantite", 0)
        prix = p.get("prixUnitaire", 0)
        if qty > 0 and prix > 0:
            line_items.append({
                "label": p.get("nom", "Prestation"),
                "quantity": qty,
                "currency_amount": prix,
                "unit": p.get("unite", "piece"),
                "vat_rate": "FR_100",  # TVA 10%
                "description": p.get("reference", ""),
            })

    # Main d'oeuvre
    mo_tarif = _parse_price(bon_data.get("moTarif", "35"))
    mo_demi_heures = _parse_demi_heures(bon_data.get("moDemiHeures", "0"))
    if mo_demi_heures > 0 and mo_tarif > 0:
        mo_total = mo_demi_heures * mo_tarif
        line_items.append({
            "label": f"Main d'oeuvre ({bon_data.get('moDuree', '')})",
            "quantity": mo_demi_heures,
            "currency_amount": mo_tarif,
            "unit": "demi-heure",
            "vat_rate": "FR_100",
        })

    # Deplacement
    depl_nombre = int(bon_data.get("deplNombre", "0") or 0)
    depl_tarif = _parse_price(bon_data.get("deplTarif", "70"))
    if depl_nombre > 0:
        line_items.append({
            "label": "Deplacement",
            "quantity": depl_nombre,
            "currency_amount": depl_tarif,
            "unit": "forfait",
            "vat_rate": "FR_100",
        })

    if not line_items:
        raise ValueError(f"Bon {bon_id}: aucune ligne facturable")

    # Build the draft payload
    payload = {
        "invoice": {
            "date": bon_data.get("date", date.today().isoformat()),
            "deadline": bon_data.get("date", date.today().isoformat()),
            "draft": True,
            "currency": "EUR",
            "label": f"Bon d'intervention {bon_data.get('numero', bon_id)}",
            "customer_name": bon_data.get("client", "Client inconnu"),
            "line_items": line_items,
        }
    }

    logger.info(f"Creation brouillon Pennylane pour bon {bon_id}")
    logger.debug(f"Payload: {payload}")

    # POST - creation de brouillon UNIQUEMENT
    url = f"{PENNYLANE_API_URL}/customer_invoices"
    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=payload, headers=_headers())

    if response.status_code in (200, 201):
        result = response.json()
        logger.info(f"Brouillon cree avec succes pour bon {bon_id}: {result.get('id', 'N/A')}")
        return result
    else:
        error_msg = f"Erreur Pennylane {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)


def _parse_price(value) -> float:
    """Parse a price string like '35' or '35.00EUR' to float."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace("EUR", "").replace("€", "").replace(",", ".").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _parse_demi_heures(value) -> int:
    """Parse '3 demi-heures' to int 3."""
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).split()[0])
    except (ValueError, IndexError):
        return 0
