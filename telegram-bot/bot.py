"""
Bot Telegram - Bons d'Intervention CEP
=======================================
Detecte les bons signes dans Firebase, envoie un resume sur Telegram,
permet validation/modification/refus, et cree des brouillons Pennylane.

REGLES DE SECURITE:
- Validation humaine obligatoire (jamais d'action automatique)
- Anti-doublon par bon ID
- Maximum MAX_DRAFTS_PER_DAY brouillons par jour
- Pennylane: creation de brouillon UNIQUEMENT
- Boutons desactives apres action
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    ALERT_THRESHOLD_PER_HOUR,
    MAX_DRAFTS_PER_DAY,
    TELEGRAM_ADMIN_ID,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_SURVEILLANCE_CHAT_ID,
    TVA_RATE,
)
from firebase_listener import (
    get_bon,
    init_firebase,
    is_bon_signed,
    listen_for_signed_bons,
    log_action,
    stop_listener,
    update_bon_produits,
    update_bon_statut,
)
from pennylane_client import create_invoice_draft

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── State tracking ──────────────────────────────────────────────────────
# Bons already sent to Telegram (bon_id -> message_id)
bons_envoyes: dict[str, int] = {}
# Bons for which a Pennylane draft was created (bon_id -> timestamp)
brouillons_crees: dict[str, datetime] = {}
# Daily draft counter (reset at midnight)
daily_draft_count = 0
daily_draft_date = datetime.now().date()
# Bons currently being modified (bon_id -> modification state)
bons_en_modification: dict[str, dict] = {}
# Bot paused (safety cutoff)
bot_paused = False
# Hourly draft timestamps for alert detection
hourly_drafts: list[datetime] = []
# Today's validated bons for daily summary
daily_validated: list[dict] = []

# Conversation states for modification flow
MODIF_CHOOSE_LINE, MODIF_EDIT_VALUE, MODIF_CONFIRM = range(3)


# ── Helpers ─────────────────────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id == TELEGRAM_ADMIN_ID


def parse_price_str(value) -> float:
    """Parse '123.45EUR' or '123,45' to float."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("EUR", "").replace("€", "").replace(",", ".").strip())
    except (ValueError, TypeError):
        return 0.0


def format_bon_summary(bon_id: str, bon_data: dict) -> str:
    """Format a bon into a readable Telegram message."""
    produits = bon_data.get("produits", [])

    lines = []
    lines.append(f"{'='*35}")
    lines.append(f"BON D'INTERVENTION {bon_data.get('numero', bon_id)}")
    lines.append(f"{'='*35}")
    lines.append(f"Date : {bon_data.get('date', 'N/A')}")
    lines.append(f"Technicien : {bon_data.get('technicien', 'N/A')}")
    lines.append(f"Client : {bon_data.get('client', 'N/A')}")
    lines.append(f"Adresse : {bon_data.get('address', 'N/A')}")
    lines.append(f"Tel : {bon_data.get('phone', 'N/A')}")
    lines.append("")
    lines.append(f"Description : {bon_data.get('description', 'N/A')}")
    lines.append(f"Horaires : {bon_data.get('heureArrivee', '?')} - {bon_data.get('heureDepart', '?')}")
    lines.append("")

    if produits:
        lines.append("PRESTATIONS :")
        lines.append(f"{'-'*35}")
        for i, p in enumerate(produits, 1):
            nom = p.get("nom", "?")
            qty = p.get("quantite", 0)
            prix = p.get("prixUnitaire", 0)
            total = qty * prix
            lines.append(f"  {i}. {nom}")
            lines.append(f"     {qty} x {prix:.2f}EUR = {total:.2f}EUR")
        lines.append(f"{'-'*35}")

    # Main d'oeuvre
    mo = bon_data.get("subtotalMO", "0.00EUR")
    depl = bon_data.get("subtotalDepl", "0.00EUR")
    if mo and mo != "0.00EUR":
        lines.append(f"Main d'oeuvre : {mo} ({bon_data.get('moDuree', '')})")
    if depl and depl != "0.00EUR":
        lines.append(f"Deplacement : {depl}")
    lines.append("")

    lines.append(f"Total HT  : {bon_data.get('totalHT', '0.00EUR')}")
    lines.append(f"TVA (10%) : {bon_data.get('totalTVA', '0.00EUR')}")
    lines.append(f"Total TTC : {bon_data.get('totalTTC', '0.00EUR')}")
    lines.append(f"{'='*35}")

    return "\n".join(lines)


def get_action_keyboard(bon_id: str) -> InlineKeyboardMarkup:
    """3-button inline keyboard: Modifier / Valider / Refuser."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Modifier", callback_data=f"modif_{bon_id}"),
            InlineKeyboardButton("Valider", callback_data=f"valid_{bon_id}"),
            InlineKeyboardButton("Refuser", callback_data=f"refus_{bon_id}"),
        ]
    ])


def check_daily_limit() -> bool:
    """Check if daily draft limit is reached. Returns True if OK to proceed."""
    global daily_draft_count, daily_draft_date
    today = datetime.now().date()
    if today != daily_draft_date:
        daily_draft_count = 0
        daily_draft_date = today
    return daily_draft_count < MAX_DRAFTS_PER_DAY


def record_draft():
    """Record a new draft creation for safety tracking."""
    global daily_draft_count, bot_paused
    daily_draft_count += 1
    hourly_drafts.append(datetime.now())
    # Clean old hourly entries
    cutoff = datetime.now() - timedelta(hours=1)
    hourly_drafts[:] = [t for t in hourly_drafts if t > cutoff]
    # Check if we hit the daily limit
    if daily_draft_count >= MAX_DRAFTS_PER_DAY:
        bot_paused = True
        logger.warning(f"LIMITE QUOTIDIENNE ATTEINTE ({MAX_DRAFTS_PER_DAY}). Bot en pause.")


# ── Firebase callback (runs in thread) ──────────────────────────────────
def on_new_signed_bon(bon_id: str, bon_data: dict):
    """Called by Firebase listener when a new signed bon is detected."""
    if bot_paused:
        logger.warning(f"Bot en pause, bon {bon_id} ignore")
        return
    if bon_id in bons_envoyes:
        logger.info(f"Bon {bon_id} deja envoye sur Telegram, ignore")
        return

    # Schedule the async send in the bot's event loop
    asyncio.run_coroutine_threadsafe(
        send_bon_to_admin(bon_id, bon_data),
        _loop,
    )


async def send_bon_to_admin(bon_id: str, bon_data: dict):
    """Send bon summary to admin on Telegram."""
    if bon_id in bons_envoyes:
        return

    summary = format_bon_summary(bon_id, bon_data)
    keyboard = get_action_keyboard(bon_id)

    msg = await _app.bot.send_message(
        chat_id=TELEGRAM_ADMIN_ID,
        text=f"Nouveau bon signe !\n\n<pre>{summary}</pre>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    bons_envoyes[bon_id] = msg.message_id
    logger.info(f"Bon {bon_id} envoye a l'admin (message_id={msg.message_id})")


# ── Command handlers ────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acces refuse.")
        return
    await update.message.reply_text(
        "Bot Bons d'Intervention CEP actif.\n"
        "Les bons signes apparaitront ici automatiquement.\n\n"
        "/status - Etat du bot\n"
        "/resume - Reprendre apres pause"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    status = "EN PAUSE" if bot_paused else "ACTIF"
    await update.message.reply_text(
        f"Etat : {status}\n"
        f"Brouillons aujourd'hui : {daily_draft_count}/{MAX_DRAFTS_PER_DAY}\n"
        f"Bons envoyes : {len(bons_envoyes)}\n"
        f"Brouillons crees : {len(brouillons_crees)}"
    )


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_paused
    if not is_admin(update.effective_user.id):
        return
    bot_paused = False
    await update.message.reply_text("Bot repris. Les nouveaux bons seront traites.")


# ── Callback query handlers (button presses) ───────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route button presses to appropriate handlers."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.answer("Acces refuse.", show_alert=True)
        return

    data = query.data
    if data.startswith("valid_"):
        await handle_validate(query, context)
    elif data.startswith("refus_"):
        await handle_refuse(query, context)
    elif data.startswith("modif_"):
        await handle_modify_start(query, context)
    elif data.startswith("mline_"):
        await handle_modify_line_choice(query, context)
    elif data.startswith("mdone_"):
        await handle_modify_done(query, context)
    elif data.startswith("mcancel_"):
        await handle_modify_cancel(query, context)


async def handle_validate(query, context: ContextTypes.DEFAULT_TYPE):
    """Validate a bon and create a Pennylane draft."""
    bon_id = query.data.replace("valid_", "")

    # Anti-doublon: check if draft already created
    if bon_id in brouillons_crees:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"Ce bon ({bon_id}) a deja un brouillon Pennylane. Action bloquee."
        )
        return

    # Daily limit check
    if not check_daily_limit():
        await query.message.reply_text(
            f"Limite quotidienne atteinte ({MAX_DRAFTS_PER_DAY} brouillons). "
            "Bot en pause. Utilisez /resume demain."
        )
        return

    # Disable buttons immediately
    await query.edit_message_reply_markup(reply_markup=None)

    bon_data = get_bon(bon_id)
    if not bon_data:
        await query.message.reply_text(f"Bon {bon_id} introuvable dans Firebase.")
        return

    try:
        # Create Pennylane draft
        result = create_invoice_draft(bon_data, bon_id)
        pennylane_id = result.get("id", "N/A")

        # Record the draft
        brouillons_crees[bon_id] = datetime.now()
        record_draft()

        # Update Firebase statut
        update_bon_statut(bon_id, "validé")

        # Log in Firebase
        log_action(bon_id, "brouillon_cree", {
            "pennylane_id": str(pennylane_id),
            "technicien": bon_data.get("technicien", ""),
            "client": bon_data.get("client", ""),
            "montant": bon_data.get("totalTTC", ""),
        })

        await query.message.reply_text(
            f"Brouillon Pennylane cree pour le bon {bon_data.get('numero', bon_id)}.\n"
            f"ID Pennylane : {pennylane_id}"
        )

        # Notify surveillance channel
        await notify_surveillance(bon_data, bon_id)

        # Check hourly alert
        await check_hourly_alert()

        # Track for daily summary
        daily_validated.append({
            "bon_id": bon_id,
            "numero": bon_data.get("numero", bon_id),
            "client": bon_data.get("client", "?"),
            "montant": bon_data.get("totalTTC", "0"),
            "heure": datetime.now().strftime("%H:%M"),
        })

    except Exception as e:
        logger.error(f"Erreur creation brouillon pour {bon_id}: {e}")
        # Re-enable buttons on error so admin can retry
        keyboard = get_action_keyboard(bon_id)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        await query.message.reply_text(
            f"Erreur lors de la creation du brouillon :\n{e}\n\n"
            "Les boutons sont reactives, vous pouvez reessayer."
        )


async def handle_refuse(query, context: ContextTypes.DEFAULT_TYPE):
    """Refuse a bon - it stays en_attente in Firebase."""
    bon_id = query.data.replace("refus_", "")

    # Disable buttons
    await query.edit_message_reply_markup(reply_markup=None)

    # Log refusal
    log_action(bon_id, "refuse", {
        "timestamp": datetime.now().isoformat(),
    })

    await query.message.reply_text(
        f"Bon {bon_id} refuse. Il reste en attente dans Firebase."
    )


# ── Modification flow ──────────────────────────────────────────────────
async def handle_modify_start(query, context: ContextTypes.DEFAULT_TYPE):
    """Start the modification flow for a bon."""
    bon_id = query.data.replace("modif_", "")

    bon_data = get_bon(bon_id)
    if not bon_data:
        await query.message.reply_text(f"Bon {bon_id} introuvable.")
        return

    # Disable the original 3 buttons
    await query.edit_message_reply_markup(reply_markup=None)

    # Store modification state
    bons_en_modification[str(query.from_user.id)] = {
        "bon_id": bon_id,
        "bon_data": bon_data,
        "produits": list(bon_data.get("produits", [])),
    }

    # Show lines with edit buttons
    await send_modification_menu(query.message, bon_id, bon_data)


async def send_modification_menu(message, bon_id: str, bon_data: dict):
    """Show the interactive modification menu with all editable lines."""
    produits = bon_data.get("produits", [])
    text_lines = ["MODIFICATION DU BON " + bon_data.get("numero", bon_id), ""]

    buttons = []
    for i, p in enumerate(produits):
        nom = p.get("nom", "?")
        qty = p.get("quantite", 0)
        prix = p.get("prixUnitaire", 0)
        total = qty * prix
        text_lines.append(f"{i+1}. {nom} — {qty} x {prix:.2f}EUR = {total:.2f}EUR")
        buttons.append([InlineKeyboardButton(
            f"Modifier ligne {i+1}: {nom}",
            callback_data=f"mline_{bon_id}_{i}"
        )])

    text_lines.append("")
    text_lines.append("Selectionnez une ligne a modifier, ou :")

    buttons.append([
        InlineKeyboardButton("Terminer les modifications", callback_data=f"mdone_{bon_id}"),
        InlineKeyboardButton("Annuler", callback_data=f"mcancel_{bon_id}"),
    ])

    await message.reply_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_modify_line_choice(query, context: ContextTypes.DEFAULT_TYPE):
    """User chose a line to modify."""
    parts = query.data.split("_")
    bon_id = parts[1]
    line_idx = int(parts[2])

    user_id = str(query.from_user.id)
    state = bons_en_modification.get(user_id)
    if not state or state["bon_id"] != bon_id:
        await query.answer("Session de modification expiree.", show_alert=True)
        return

    produit = state["produits"][line_idx]
    state["editing_line"] = line_idx

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"Modification de : {produit.get('nom', '?')}\n"
        f"Quantite actuelle : {produit.get('quantite', 0)}\n"
        f"Prix unitaire actuel : {produit.get('prixUnitaire', 0):.2f}EUR\n\n"
        "Envoyez la nouvelle valeur au format :\n"
        "  quantite prix\n"
        "Exemple : 3 45.00\n\n"
        "Ou envoyez 'supprimer' pour retirer cette ligne.\n"
        "Ou envoyez 'annuler' pour ne rien changer."
    )


async def handle_modify_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process a text message during modification flow."""
    if not is_admin(update.effective_user.id):
        return

    user_id = str(update.effective_user.id)
    state = bons_en_modification.get(user_id)
    if not state or "editing_line" not in state:
        return

    text = update.message.text.strip().lower()
    line_idx = state["editing_line"]
    bon_id = state["bon_id"]

    if text == "annuler":
        del state["editing_line"]
        bon_data = state["bon_data"]
        bon_data["produits"] = state["produits"]
        await send_modification_menu(update.message, bon_id, bon_data)
        return

    if text == "supprimer":
        removed = state["produits"].pop(line_idx)
        del state["editing_line"]
        await update.message.reply_text(f"Ligne supprimee : {removed.get('nom', '?')}")
        bon_data = state["bon_data"]
        bon_data["produits"] = state["produits"]
        await send_modification_menu(update.message, bon_id, bon_data)
        return

    # Parse "quantite prix"
    parts = text.replace(",", ".").split()
    if len(parts) == 2:
        try:
            new_qty = float(parts[0])
            new_prix = float(parts[1])
            state["produits"][line_idx]["quantite"] = new_qty
            state["produits"][line_idx]["prixUnitaire"] = new_prix
            del state["editing_line"]
            nom = state["produits"][line_idx].get("nom", "?")
            await update.message.reply_text(
                f"Ligne mise a jour : {nom} — {new_qty} x {new_prix:.2f}EUR"
            )
            bon_data = state["bon_data"]
            bon_data["produits"] = state["produits"]
            await send_modification_menu(update.message, bon_id, bon_data)
            return
        except ValueError:
            pass

    await update.message.reply_text(
        "Format invalide. Envoyez :\n"
        "  quantite prix (ex: 3 45.00)\n"
        "  supprimer\n"
        "  annuler"
    )


async def handle_modify_done(query, context: ContextTypes.DEFAULT_TYPE):
    """Save modifications and show updated bon with action buttons."""
    bon_id = query.data.replace("mdone_", "")
    user_id = str(query.from_user.id)
    state = bons_en_modification.get(user_id)

    if not state or state["bon_id"] != bon_id:
        await query.answer("Session expiree.", show_alert=True)
        return

    await query.edit_message_reply_markup(reply_markup=None)

    # Save modified produits to Firebase
    new_produits = state["produits"]
    update_bon_produits(bon_id, new_produits)

    # Recalculate totals
    total_produits = sum(
        p.get("quantite", 0) * p.get("prixUnitaire", 0) for p in new_produits
    )
    mo = parse_price_str(state["bon_data"].get("subtotalMO", "0"))
    depl = parse_price_str(state["bon_data"].get("subtotalDepl", "0"))
    total_ht = total_produits + mo + depl
    total_tva = total_ht * TVA_RATE
    total_ttc = total_ht + total_tva

    # Update totals in Firebase
    from firebase_listener import get_db
    from config import BONS_COLLECTION
    get_db().collection(BONS_COLLECTION).document(bon_id).update({
        "subtotalProduits": f"{total_produits:.2f}EUR",
        "totalHT": f"{total_ht:.2f}EUR",
        "totalTVA": f"{total_tva:.2f}EUR",
        "totalTTC": f"{total_ttc:.2f}EUR",
    })

    # Log modification
    log_action(bon_id, "modifie", {
        "nb_lignes": len(new_produits),
        "total_ht": f"{total_ht:.2f}",
    })

    # Refresh bon data and show updated summary
    bon_data = get_bon(bon_id)
    summary = format_bon_summary(bon_id, bon_data)
    keyboard = get_action_keyboard(bon_id)

    await query.message.reply_text(
        f"Bon modifie !\n\n<pre>{summary}</pre>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    # Clean up state
    del bons_en_modification[user_id]


async def handle_modify_cancel(query, context: ContextTypes.DEFAULT_TYPE):
    """Cancel modification and restore action buttons."""
    bon_id = query.data.replace("mcancel_", "")
    user_id = str(query.from_user.id)

    await query.edit_message_reply_markup(reply_markup=None)

    if user_id in bons_en_modification:
        del bons_en_modification[user_id]

    bon_data = get_bon(bon_id)
    if bon_data:
        summary = format_bon_summary(bon_id, bon_data)
        keyboard = get_action_keyboard(bon_id)
        await query.message.reply_text(
            f"Modification annulee.\n\n<pre>{summary}</pre>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# ── Surveillance channel ────────────────────────────────────────────────
async def notify_surveillance(bon_data: dict, bon_id: str):
    """Send silent notification to surveillance channel."""
    if not TELEGRAM_SURVEILLANCE_CHAT_ID:
        return
    heure = datetime.now().strftime("%H:%M")
    client = bon_data.get("client", "?")
    montant = bon_data.get("totalTTC", "?")
    numero = bon_data.get("numero", bon_id)

    await _app.bot.send_message(
        chat_id=TELEGRAM_SURVEILLANCE_CHAT_ID,
        text=f"Brouillon cree — {client} — {montant} — {heure} (Bon {numero})",
        disable_notification=True,
    )


async def check_hourly_alert():
    """Alert if more than ALERT_THRESHOLD_PER_HOUR drafts in the last hour."""
    if not TELEGRAM_SURVEILLANCE_CHAT_ID:
        return
    cutoff = datetime.now() - timedelta(hours=1)
    recent = [t for t in hourly_drafts if t > cutoff]
    if len(recent) > ALERT_THRESHOLD_PER_HOUR:
        await _app.bot.send_message(
            chat_id=TELEGRAM_SURVEILLANCE_CHAT_ID,
            text=(
                f"ALERTE : {len(recent)} brouillons crees en moins d'une heure !\n"
                f"Limite d'alerte : {ALERT_THRESHOLD_PER_HOUR}\n"
                f"Verifiez l'activite du bot."
            ),
        )


async def send_daily_summary():
    """Send daily summary at 18h to surveillance channel."""
    global daily_validated
    if not TELEGRAM_SURVEILLANCE_CHAT_ID:
        return

    if not daily_validated:
        await _app.bot.send_message(
            chat_id=TELEGRAM_SURVEILLANCE_CHAT_ID,
            text=f"Resume du {datetime.now().strftime('%d/%m/%Y')} : Aucun brouillon cree aujourd'hui.",
            disable_notification=True,
        )
    else:
        lines = [f"RESUME DU {datetime.now().strftime('%d/%m/%Y')}", ""]
        total_global = 0.0
        for v in daily_validated:
            lines.append(f"  Bon {v['numero']} — {v['client']} — {v['montant']} — {v['heure']}")
            total_global += parse_price_str(v["montant"])
        lines.append("")
        lines.append(f"Total : {len(daily_validated)} brouillon(s)")
        lines.append(f"Montant cumule : {total_global:.2f}EUR TTC")

        await _app.bot.send_message(
            chat_id=TELEGRAM_SURVEILLANCE_CHAT_ID,
            text="\n".join(lines),
            disable_notification=True,
        )

    # Reset for next day
    daily_validated = []


# ── Main ────────────────────────────────────────────────────────────────
_app: Application = None
_loop: asyncio.AbstractEventLoop = None


def main():
    global _app, _loop

    # Initialize Firebase
    init_firebase()

    # Build Telegram application
    _app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    _app.add_handler(CommandHandler("start", cmd_start))
    _app.add_handler(CommandHandler("status", cmd_status))
    _app.add_handler(CommandHandler("resume", cmd_resume))

    # Callback query handler (all button presses)
    _app.add_handler(CallbackQueryHandler(handle_callback))

    # Text message handler for modification flow (admin only)
    _app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(TELEGRAM_ADMIN_ID),
        handle_modify_message,
    ))

    # Schedule daily summary at 18h
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_summary, "cron", hour=18, minute=0)
    scheduler.start()

    logger.info("Bot Telegram demarre")

    # Start polling and get the event loop
    _app.post_init = _post_init
    _app.run_polling(allowed_updates=Update.ALL_TYPES)


async def _post_init(application: Application):
    """Called after the application is initialized - start Firebase listener."""
    global _loop
    _loop = asyncio.get_running_loop()
    listen_for_signed_bons(on_new_signed_bon)
    logger.info("Firebase listener connecte au bot Telegram")


if __name__ == "__main__":
    main()
