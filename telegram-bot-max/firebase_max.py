"""Firebase functions for Max assistant."""

import logging
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_CREDENTIALS, SOCIETES, ALL_TECHNICIENS

logger = logging.getLogger(__name__)

_db = None


def init_firebase():
    global _db
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("Firebase initialise")
    return _db


def get_db():
    global _db
    if _db is None:
        init_firebase()
    return _db


def search_client(client_name, societe_id):
    """Search for a client by name."""
    db = get_db()
    name_lower = client_name.lower().strip()
    soc = SOCIETES.get(societe_id)
    if soc:
        docs = db.collection(soc["clients_collection"]).stream()
        for doc in docs:
            data = doc.to_dict()
            nom = str(data.get("nom", "")).lower()
            if name_lower in nom or nom in name_lower:
                return data
    # Search in clientsPennylane
    docs = db.collection("clientsPennylane").stream()
    for doc in docs:
        data = doc.to_dict()
        nom = str(data.get("nom", "")).lower()
        if name_lower in nom or nom in name_lower:
            return data
    return None


def create_planning(societe_id, data):
    """Create a planning entry."""
    db = get_db()
    soc = SOCIETES.get(societe_id)
    if not soc:
        raise ValueError("Societe inconnue: {}".format(societe_id))
    rdv = {
        "date": data.get("date", ""),
        "heure": data.get("heure", ""),
        "client": data.get("client", ""),
        "adresse": data.get("adresse", ""),
        "telephone": data.get("telephone", ""),
        "technicien": data.get("technicien", ""),
        "description": data.get("description", ""),
        "societe": societe_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    db.collection(soc["planning_collection"]).add(rdv)
    logger.info("Planning cree: {} - {}".format(data.get("client"), data.get("technicien")))


def get_planning_for_tech(technicien, date_from=None, date_to=None):
    """Get planning entries for a technician."""
    db = get_db()
    societe_id = ALL_TECHNICIENS.get(technicien.upper())
    if not societe_id:
        return []
    soc = SOCIETES.get(societe_id)
    docs = db.collection(soc["planning_collection"]).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if data.get("technicien", "").upper() != technicien.upper():
            continue
        date = data.get("date", "")
        if date_from and date < date_from:
            continue
        if date_to and date > date_to:
            continue
        results.append(data)
    results.sort(key=lambda x: (x.get("date", ""), x.get("heure", "")))
    return results


def search_bon(query, societe_id=None):
    """Search for a bon by client name or number."""
    db = get_db()
    query_lower = query.lower().strip()
    results = []
    societes_to_search = [societe_id] if societe_id else SOCIETES.keys()
    for sid in societes_to_search:
        soc = SOCIETES.get(sid)
        if not soc:
            continue
        docs = db.collection(soc["bons_collection"]).order_by("date", direction="DESCENDING").limit(30).stream()
        for doc in docs:
            data = doc.to_dict()
            numero = str(data.get("numero", "")).lower()
            client = str(data.get("client", "")).lower()
            if query_lower in numero or query_lower in client:
                data["id"] = doc.id
                data["_societe_id"] = sid
                results.append(data)
            if len(results) >= 5:
                break
    return results


def modify_bon(bon_id, societe_id, updates):
    """Modify fields of a bon."""
    db = get_db()
    soc = SOCIETES.get(societe_id)
    if not soc:
        raise ValueError("Societe inconnue")
    db.collection(soc["bons_collection"]).document(bon_id).update(updates)
    logger.info("Bon {} modifie: {}".format(bon_id, updates))


def log_conversation(user_id, role, text):
    """Log a conversation message for history."""
    db = get_db()
    db.collection("max_conversations").add({
        "user_id": str(user_id),
        "role": role,
        "text": text,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })
