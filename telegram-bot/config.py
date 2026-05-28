import os
from dotenv import load_dotenv

load_dotenv()

# Telegram - liste d'admins (CSV). Tombe sur TELEGRAM_ADMIN_ID si la nouvelle var n'existe pas (retro-compat).
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_admin_csv = os.getenv("TELEGRAM_ADMIN_IDS", os.getenv("TELEGRAM_ADMIN_ID", "0"))
TELEGRAM_ADMIN_IDS = [int(s.strip()) for s in _admin_csv.split(",") if s.strip().lstrip("-").isdigit()]
# Garde l'ancien nom pour retro-compat (= premier ID, utilise quand un seul destinataire est attendu)
TELEGRAM_ADMIN_ID = TELEGRAM_ADMIN_IDS[0] if TELEGRAM_ADMIN_IDS else 0
TELEGRAM_SURVEILLANCE_CHAT_ID = os.getenv("TELEGRAM_SURVEILLANCE_CHAT_ID")

# Pennylane
PENNYLANE_API_KEY = os.getenv("PENNYLANE_API_KEY")
PENNYLANE_API_URL = "https://app.pennylane.com/api/external/v2"

# Firebase
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")

# Societe CEP dans Firebase
SOCIETE_ID = "cep"
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

# Societe CEP
SOCIETE_NOM = "Compagnie d'Electricite Parisienne"
SOCIETE_COULEUR = "#1a365d"
SOCIETE_ADRESSE = "6, rue de Metz, 94240 L'Hay-les-Roses"
SOCIETE_TELEPHONE = "01 56 04 19 96"
SOCIETE_EMAIL = "contact@cep75.fr"
SOCIETE_SITE_WEB = "www.cep75.fr"
