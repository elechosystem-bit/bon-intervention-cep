"""Firebase functions for planning bot."""

import logging
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_CREDENTIALS, SOCIETES

logger = logging.getLogger(__name__)

_db = None


def init_firebase():
    global _db
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("Firebase initialise avec succes")
    return _db


def get_db():
    global _db
    if _db is None:
        init_firebase()
    return _db


def search_client(client_name: str, societe_id: str) -> dict | None:
    """Search for a client by name in Firebase (local clients + clientsPennylane)."""
    db = get_db()
    name_lower = client_name.lower().strip()

    # 1. Search in societe clients collection
    soc = SOCIETES.get(societe_id)
    if soc:
        docs = db.collection(soc["clients_collection"]).stream()
        for doc in docs:
            data = doc.to_dict()
            nom = str(data.get("nom", "")).lower()
            if name_lower in nom or nom in name_lower:
                return {
                    "nom": data.get("nom", ""),
                    "adresse": data.get("adresse", ""),
                    "telephone": data.get("telephone", ""),
                    "email": data.get("email", ""),
                }

    # 2. Search in clientsPennylane (global)
    docs = db.collection("clientsPennylane").stream()
    for doc in docs:
        data = doc.to_dict()
        nom = str(data.get("nom", "")).lower()
        if name_lower in nom or nom in name_lower:
            return {
                "nom": data.get("nom", ""),
                "adresse": data.get("adresse", ""),
                "telephone": data.get("telephone", ""),
                "email": data.get("email", ""),
            }

    return None


def create_intervention(societe_id: str, data: dict) -> str:
    """Create an intervention (bon) in Firebase. Returns the numero."""
    db = get_db()
    soc = SOCIETES.get(societe_id)
    if not soc:
        raise ValueError("Societe inconnue: {}".format(societe_id))

    # Generate numero via transaction
    compteur_ref = db.document(soc["compteur_path"])
    annee = datetime.now().year
    numero = 1

    @firestore.transactional
    def update_compteur(transaction):
        nonlocal numero
        snap = compteur_ref.get(transaction=transaction)
        if snap.exists and snap.to_dict().get("annee") == annee:
            numero = snap.to_dict().get("dernierNumero", 0) + 1
        else:
            numero = 1
        transaction.set(compteur_ref, {"annee": annee, "dernierNumero": numero})

    transaction = db.transaction()
    update_compteur(transaction)

    numero_str = "{}{}".format(annee, str(numero).zfill(4))

    # Build the bon document
    bon = {
        "numero": numero_str,
        "date": data.get("date", ""),
        "client": data.get("client", ""),
        "phone": data.get("telephone", ""),
        "email": data.get("email", ""),
        "address": data.get("adresse", ""),
        "technicien": data.get("technicien", ""),
        "description": data.get("description", ""),
        "heureArrivee": data.get("heure", ""),
        "heureDepart": "",
        "moDuree": "0h00",
        "moDemiHeures": "0 demi-heures",
        "moTarif": "35",
        "deplNombre": "0",
        "deplTarif": "70",
        "subtotalProduits": "0.00EUR",
        "subtotalMO": "0.00EUR",
        "subtotalDepl": "0.00EUR",
        "totalHT": "0.00EUR",
        "totalTVA": "0.00EUR",
        "totalTTC": "0.00EUR",
        "statut": "en_attente",
        "societe": societe_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "produits": [],
        "photos": [],
    }

    db.collection(soc["bons_collection"]).add(bon)
    logger.info("Intervention creee: {} - {} - {}".format(numero_str, data.get("client"), data.get("technicien")))
    return numero_str
