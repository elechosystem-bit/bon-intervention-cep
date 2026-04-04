import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
TELEGRAM_SURVEILLANCE_CHAT_ID = os.getenv("TELEGRAM_SURVEILLANCE_CHAT_ID")

# Pennylane
PENNYLANE_API_KEY = os.getenv("PENNYLANE_API_KEY")
PENNYLANE_API_URL = "https://app.pennylane.com/api/external/v2"

# Firebase
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")

# Societe Elechosystem dans Firebase
SOCIETE_ID = "elechosystem"
BONS_COLLECTION = f"societes/{SOCIETE_ID}/bons"

# Securite
MAX_DRAFTS_PER_DAY = int(os.getenv("MAX_DRAFTS_PER_DAY", "10"))

# Mode test (skip Pennylane API)
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Anthropic (Claude AI)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALERT_THRESHOLD_PER_HOUR = 3

# TVA
TVA_RATE = 0.10

# SMTP OVH (envoi email compta)
OVH_SMTP_USER = os.getenv("OVH_SMTP_USER", "intervention@cep75.fr")
OVH_SMTP_PASSWORD = os.getenv("OVH_SMTP_PASSWORD")
EMAIL_COMPTA = "cepelecho@gmail.com"

# Societe Elechosystem
SOCIETE_NOM = "Elecho System SARL"
SOCIETE_COULEUR = "#E85D04"
SOCIETE_ADRESSE = "6, rue de Metz, 94240 L'Hay-les-Roses"
SOCIETE_TELEPHONE = "01 56 04 19 96"
SOCIETE_EMAIL = "contact@elechosystem.com"
SOCIETE_SITE_WEB = "www.elechosystem.com"
