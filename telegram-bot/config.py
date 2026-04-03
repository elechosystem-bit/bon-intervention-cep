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

# Societe CEP dans Firebase
SOCIETE_ID = "cep"
BONS_COLLECTION = f"societes/{SOCIETE_ID}/bons"

# Securite
MAX_DRAFTS_PER_DAY = int(os.getenv("MAX_DRAFTS_PER_DAY", "10"))
ALERT_THRESHOLD_PER_HOUR = 3

# TVA
TVA_RATE = 0.10
