"""Firebase Firestore listener for signed bons d'intervention."""

import logging
import threading
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_CREDENTIALS, BONS_COLLECTION

logger = logging.getLogger(__name__)

_db = None
_listener_unsubscribe = None


def init_firebase():
    """Initialize Firebase Admin SDK."""
    global _db
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("Firebase initialise avec succes")
    return _db


def get_db():
    """Get Firestore client, initializing if needed."""
    global _db
    if _db is None:
        init_firebase()
    return _db


def is_bon_signed(bon_data: dict) -> bool:
    """Check if a bon has been signed (technician + client signatures present)."""
    signatures = bon_data.get("signatures", {})
    if not signatures:
        return False
    tech_sig = signatures.get("technicien")
    client_sig = signatures.get("client")
    # A valid signature is a non-empty data URL (not just a blank canvas)
    blank_canvas = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA"
    for sig in [tech_sig, client_sig]:
        if not sig or not isinstance(sig, str) or len(sig) < 100:
            return False
        # Blank canvas signatures are very short base64
        if sig.startswith(blank_canvas) and len(sig) < 500:
            return False
    return True


def listen_for_signed_bons(callback):
    """
    Listen in real-time for bons with statut='en_attente' that have signatures.
    Calls callback(bon_id, bon_data) for each new signed bon detected.
    """
    global _listener_unsubscribe
    db = get_db()

    # Track already-seen bon IDs to avoid re-processing on listener restart
    seen_bons = set()

    # Pre-load existing bons to avoid processing old ones
    existing = db.collection(BONS_COLLECTION).where("statut", "==", "en_attente").stream()
    for doc in existing:
        seen_bons.add(doc.id)
    logger.info(f"Pre-charge {len(seen_bons)} bons existants en_attente")

    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name in ("ADDED", "MODIFIED"):
                doc = change.document
                bon_data = doc.to_dict()
                bon_id = doc.id

                # Only process en_attente bons with valid signatures
                if bon_data.get("statut") != "en_attente":
                    continue
                if not is_bon_signed(bon_data):
                    continue
                # Skip already processed
                if bon_id in seen_bons and change.type.name == "ADDED":
                    continue

                seen_bons.add(bon_id)
                logger.info(f"Nouveau bon signe detecte: {bon_id}")
                try:
                    callback(bon_id, bon_data)
                except Exception as e:
                    logger.error(f"Erreur callback pour bon {bon_id}: {e}")

    # Subscribe to real-time updates on en_attente bons
    query = db.collection(BONS_COLLECTION).where("statut", "==", "en_attente")
    _listener_unsubscribe = query.on_snapshot(on_snapshot)
    logger.info("Listener Firebase demarre - ecoute des bons signes")


def update_bon_statut(bon_id: str, new_statut: str):
    """Update the statut field of a bon in Firestore."""
    db = get_db()
    db.collection(BONS_COLLECTION).document(bon_id).update({
        "statut": new_statut
    })
    logger.info(f"Bon {bon_id} statut mis a jour: {new_statut}")


def log_action(bon_id: str, action: str, details: dict):
    """Log an action in the bon's Firestore document (sub-field 'telegram_log')."""
    db = get_db()
    log_entry = {
        "action": action,
        "timestamp": datetime.now().isoformat(),
        **details
    }
    db.collection(BONS_COLLECTION).document(bon_id).update({
        "telegram_log": firestore.ArrayUnion([log_entry])
    })


def update_bon_produits(bon_id: str, produits: list):
    """Update the produits array of a bon."""
    db = get_db()
    db.collection(BONS_COLLECTION).document(bon_id).update({
        "produits": produits
    })


def get_bon(bon_id: str) -> dict | None:
    """Fetch a bon document by ID."""
    db = get_db()
    doc = db.collection(BONS_COLLECTION).document(bon_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def stop_listener():
    """Stop the Firestore listener."""
    global _listener_unsubscribe
    if _listener_unsubscribe:
        _listener_unsubscribe.unsubscribe()
        _listener_unsubscribe = None
        logger.info("Listener Firebase arrete")
