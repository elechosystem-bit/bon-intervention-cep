"""
Bot Telegram - Planification des interventions CEP / Elechosystem
=================================================================
Permet de creer des interventions en langage naturel.
Exemple : "Changer ampoules Les Trois Obus jeudi 14h Christophe"
"""

import asyncio
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ALL_TECHNICIENS, SOCIETES, TELEGRAM_ADMIN_ID, TELEGRAM_BOT_TOKEN
from claude_planning import parse_planning_request
from firebase_planning import create_intervention, init_firebase, search_client

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Pending interventions waiting for missing info or confirmation
# user_id -> {parsed data + state}
pending: dict[str, dict] = {}

JOURS_FR = {
    "Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
    "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi",
    "Sunday": "Dimanche",
}


def is_admin(user_id: int) -> bool:
    return user_id == TELEGRAM_ADMIN_ID


def format_date_fr(date_str: str) -> str:
    """Format YYYY-MM-DD to 'Jeudi 10 avril'."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        jour = JOURS_FR.get(d.strftime("%A"), d.strftime("%A"))
        mois_fr = ["janvier", "fevrier", "mars", "avril", "mai", "juin",
                    "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]
        return "{} {} {}".format(jour, d.day, mois_fr[d.month - 1])
    except Exception:
        return date_str


def format_summary(data: dict) -> str:
    """Format intervention data for display."""
    lines = []
    lines.append("Client : {}".format(data.get("client", "?")))
    lines.append("Description : {}".format(data.get("description", "?")))
    date_str = data.get("date", "?")
    if date_str and date_str != "?":
        lines.append("Date : {}".format(format_date_fr(date_str)))
    else:
        lines.append("Date : ?")
    lines.append("Heure : {}".format(data.get("heure", "?")))
    lines.append("Technicien : {}".format(data.get("technicien", "?")))
    if data.get("adresse"):
        lines.append("Adresse : {}".format(data["adresse"]))
    soc = data.get("societe", "?")
    if soc and soc in SOCIETES:
        lines.append("Societe : {}".format(SOCIETES[soc]["nom"]))
    return "\n".join(lines)


def get_missing_fields(data: dict) -> list:
    """Return list of missing required fields."""
    required = ["client", "description", "date", "heure", "technicien"]
    missing = []
    for field in required:
        if not data.get(field):
            missing.append(field)
    return missing


def missing_field_question(field: str) -> str:
    """Return a human-friendly question for a missing field."""
    questions = {
        "client": "Quel est le client ou le lieu ?",
        "description": "Quel type d'intervention ? (ex: changer ampoules, depannage...)",
        "date": "Quelle date ? (ex: jeudi, demain, 10 avril...)",
        "heure": "A quelle heure ? (ex: 14h, 9h30...)",
        "technicien": "Quel technicien ? ({})".format(", ".join(ALL_TECHNICIENS.keys())),
    }
    return questions.get(field, "Valeur pour {} ?".format(field))


# ── Commands ──────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acces refuse.")
        return
    await update.message.reply_text(
        "Bot Planification CEP / Elechosystem actif.\n\n"
        "Envoyez un message pour planifier une intervention.\n"
        "Exemple : \"Changer ampoules Les Trois Obus jeudi 14h Christophe\"\n\n"
        "/annuler - Annuler la planification en cours"
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in pending:
        del pending[user_id]
        await update.message.reply_text("Planification annulee.")
    else:
        await update.message.reply_text("Rien a annuler.")


# ── Message handler ───────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    # If we're waiting for a missing field
    state = pending.get(user_id)
    if state and state.get("waiting_for"):
        await handle_missing_field_response(update, context, state, text)
        return

    # New planning request
    await update.message.reply_text("Analyse...")

    try:
        parsed = parse_planning_request(text)
    except Exception as e:
        logger.error("Erreur Claude planning: {}".format(e))
        await update.message.reply_text(
            "Je n'ai pas compris. Essayez par exemple :\n"
            "\"Depannage Dupont vendredi 10h Ricardo\""
        )
        return

    # Search for client address in Firebase
    client_name = parsed.get("client")
    societe_id = parsed.get("societe")
    if client_name and societe_id:
        client_info = search_client(client_name, societe_id)
        if client_info:
            parsed["adresse"] = client_info.get("adresse", "")
            parsed["telephone"] = client_info.get("telephone", "")
            parsed["email"] = client_info.get("email", "")
            if client_info.get("nom"):
                parsed["client"] = client_info["nom"]

    # Check for missing fields
    missing = get_missing_fields(parsed)

    if missing:
        # Store pending and ask for first missing field
        parsed["waiting_for"] = missing[0]
        parsed["missing_fields"] = missing
        pending[user_id] = parsed
        await update.message.reply_text(
            "Il me manque des informations.\n\n{}".format(
                missing_field_question(missing[0])
            )
        )
    else:
        # Everything is here, ask for confirmation
        pending[user_id] = parsed
        await ask_confirmation(update, parsed)


async def handle_missing_field_response(update, context, state, text):
    """Handle response to a missing field question."""
    user_id = str(update.effective_user.id)
    field = state["waiting_for"]

    # Use Claude to parse the response if it's a date or time
    if field in ("date", "heure", "technicien"):
        try:
            mini_parsed = parse_planning_request(
                "{} pour le champ {}".format(text, field)
            )
            if field == "date" and mini_parsed.get("date"):
                state["date"] = mini_parsed["date"]
            elif field == "heure" and mini_parsed.get("heure"):
                state["heure"] = mini_parsed["heure"]
            elif field == "technicien" and mini_parsed.get("technicien"):
                state["technicien"] = mini_parsed["technicien"]
                state["societe"] = mini_parsed.get("societe") or state.get("societe")
            else:
                state[field] = text
        except Exception:
            state[field] = text
    else:
        state[field] = text

    # Check if more fields are missing
    remaining = get_missing_fields(state)
    if remaining:
        state["waiting_for"] = remaining[0]
        state["missing_fields"] = remaining
        pending[user_id] = state
        await update.message.reply_text(missing_field_question(remaining[0]))
    else:
        state.pop("waiting_for", None)
        state.pop("missing_fields", None)

        # Search client address if we now have client + societe
        if not state.get("adresse") and state.get("client") and state.get("societe"):
            client_info = search_client(state["client"], state["societe"])
            if client_info:
                state["adresse"] = client_info.get("adresse", "")
                state["telephone"] = client_info.get("telephone", "")
                state["email"] = client_info.get("email", "")
                if client_info.get("nom"):
                    state["client"] = client_info["nom"]

        pending[user_id] = state
        await ask_confirmation(update, state)


async def ask_confirmation(update, data):
    """Show summary and ask for confirmation."""
    summary = format_summary(data)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Confirmer", callback_data="plan_confirm"),
            InlineKeyboardButton("Annuler", callback_data="plan_cancel"),
        ]
    ])
    await update.message.reply_text(
        "Intervention a creer :\n\n{}\n\nConfirmer ?".format(summary),
        reply_markup=keyboard,
    )


# ── Callback handler ──────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = str(query.from_user.id)
    data = query.data

    if data == "plan_confirm":
        await handle_confirm(query, user_id)
    elif data == "plan_cancel":
        await handle_cancel_callback(query, user_id)


async def handle_confirm(query, user_id):
    """Create the intervention in Firebase."""
    state = pending.get(user_id)
    if not state:
        await query.edit_message_text("Session expiree. Reenvoyez votre demande.")
        return

    await query.edit_message_reply_markup(reply_markup=None)

    societe_id = state.get("societe")
    if not societe_id:
        await query.message.reply_text("Erreur : societe non determinee.")
        return

    try:
        numero = create_intervention(societe_id, state)

        date_fr = format_date_fr(state.get("date", ""))
        heure = state.get("heure", "?")
        client = state.get("client", "?")
        tech = state.get("technicien", "?")

        await query.edit_message_text(
            "Intervention creee !\n\n"
            "Bon {} - {} - {} {} - {}\n"
            "{}".format(
                numero, client, date_fr, heure, tech,
                "Adresse : {}".format(state["adresse"]) if state.get("adresse") else ""
            )
        )

        # Clean up
        del pending[user_id]

    except Exception as e:
        logger.error("Erreur creation intervention: {}".format(e))
        await query.message.reply_text("Erreur : {}".format(e))


async def handle_cancel_callback(query, user_id):
    """Cancel the planning."""
    if user_id in pending:
        del pending[user_id]
    await query.edit_message_text("Planification annulee.")


# ── Main ──────────────────────────────────────────────────────────────
def main():
    init_firebase()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("annuler", cmd_cancel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(TELEGRAM_ADMIN_ID),
        handle_message,
    ))

    logger.info("Bot Planification demarre")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
