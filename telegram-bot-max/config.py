import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_admin_ids = os.getenv("TELEGRAM_ADMIN_ID", "0")
TELEGRAM_ADMIN_IDS = [int(x.strip()) for x in _admin_ids.split(",") if x.strip()]

FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

SOCIETES = {
    "cep": {
        "id": "cep",
        "nom": "CEP",
        "planning_collection": "societes/cep/planning",
        "bons_collection": "societes/cep/bons",
        "clients_collection": "societes/cep/clients",
        "techniciens": ["CHRISTOPHE", "RICARDO", "MATHIEU"],
    },
    "elechosystem": {
        "id": "elechosystem",
        "nom": "Elechosystem",
        "planning_collection": "societes/elechosystem/planning",
        "bons_collection": "societes/elechosystem/bons",
        "clients_collection": "societes/elechosystem/clients",
        "techniciens": ["AURELIEN", "FRED", "WILL"],
    },
}

ALL_TECHNICIENS = {}
for soc_id, soc in SOCIETES.items():
    for tech in soc["techniciens"]:
        ALL_TECHNICIENS[tech.upper()] = soc_id
