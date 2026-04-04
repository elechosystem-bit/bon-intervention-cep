import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))

# Firebase
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")

# Anthropic (Claude AI)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Societes disponibles
SOCIETES = {
    "cep": {
        "id": "cep",
        "nom": "CEP",
        "bons_collection": "societes/cep/bons",
        "clients_collection": "societes/cep/clients",
        "compteur_path": "societes/cep/compteurs/bons",
        "techniciens": ["CHRISTOPHE", "RICARDO", "MATHIEU"],
    },
    "elechosystem": {
        "id": "elechosystem",
        "nom": "Elechosystem",
        "bons_collection": "societes/elechosystem/bons",
        "clients_collection": "societes/elechosystem/clients",
        "compteur_path": "societes/elechosystem/compteurs/bons",
        "techniciens": ["AURELIEN", "FRED", "WILL"],
    },
}

# Tous les techniciens avec leur societe
ALL_TECHNICIENS = {}
for soc_id, soc in SOCIETES.items():
    for tech in soc["techniciens"]:
        ALL_TECHNICIENS[tech.upper()] = soc_id
