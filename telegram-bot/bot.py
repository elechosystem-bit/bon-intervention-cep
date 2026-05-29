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
    TELEGRAM_ADMIN_IDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_SURVEILLANCE_CHAT_ID,
    TEST_MODE,
    TVA_RATE,
)
from firebase_listener import (
    BONS_COLLECTION,
    cleanup_initial_bons_en_attente,
    cleanup_initial_bons_valides_refuses,
    get_bon,
    get_db,
    init_firebase,
    is_bon_signed,
    listen_for_signed_bons,
    log_action,
    search_bons,
    stop_listener,
    update_bon_produits,
    update_bon_statut,
)
from claude_client import apply_modification
from email_client import send_compta_email
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



# ── Helpers ─────────────────────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in TELEGRAM_ADMIN_IDS


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
    """Send bon summary to all admins on Telegram (Mathieu, Frederic, Aurele...)."""
    if bon_id in bons_envoyes:
        return
    # Si Firestore montre que le bon a deja ete notifie sur Telegram (presence
    # de telegram_messages), on ne renvoie pas (utile apres restart du bot,
    # qui perd la memoire mais retrouve l'info dans Firestore).
    if bon_data.get("telegram_messages"):
        bons_envoyes[bon_id] = 0
        return
    # Flag pose par le cleanup au demarrage pour les bons en_attente existants
    # sans telegram_messages : ils ont ete pousses dans une vie precedente du
    # bot, on ne les re-pousse pas a chaque restart.
    if bon_data.get("telegram_push_skip"):
        bons_envoyes[bon_id] = 0
        return

    summary = format_bon_summary(bon_id, bon_data)
    keyboard = get_action_keyboard(bon_id)

    sent_any = False
    last_message_id = 0
    envois = []  # liste {chat_id, message_id} pour pouvoir retirer les boutons plus tard
    for admin_id in TELEGRAM_ADMIN_IDS:
        try:
            msg = await _app.bot.send_message(
                chat_id=admin_id,
                text=f"Nouveau bon signe !\n\n<pre>{summary}</pre>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            sent_any = True
            last_message_id = msg.message_id
            envois.append({"chat_id": admin_id, "message_id": msg.message_id})
            logger.info(f"Bon {bon_id} envoye a admin {admin_id} (message_id={msg.message_id})")
        except Exception as e:
            logger.warning(f"Echec envoi bon {bon_id} a admin {admin_id} : {e}")
    if sent_any:
        bons_envoyes[bon_id] = last_message_id
        # Stocker dans Firestore pour que notif-telegram puisse retirer les boutons
        # quand le bon est valide / refuse depuis l'admin web.
        try:
            db = get_db()
            db.collection(BONS_COLLECTION).document(bon_id).update({
                "telegram_messages": envois,
            })
        except Exception as e:
            logger.warning(f"Echec stockage telegram_messages pour {bon_id} : {e}")


# ── Command handlers ────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acces refuse.")
        return
    await update.message.reply_text(
        "Bot Bons d'Intervention CEP actif.\n"
        "Les bons signes apparaitront ici automatiquement.\n\n"
        "/bon [recherche] - Rappeler un bon (par numero, client, technicien...)\n"
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


async def cmd_bon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search and recall a bon by numero, client, technicien, or description."""
    if not is_admin(update.effective_user.id):
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            "Utilisation : /bon [recherche]\n\n"
            "Exemples :\n"
            "  /bon 20260123\n"
            "  /bon cafe marche\n"
            "  /bon ricardo\n"
            "  /bon ruban led"
        )
        return

    await update.message.reply_text(f"Recherche de \"{query}\"...")

    results = search_bons(query)
    if not results:
        await update.message.reply_text(
            f"Aucun bon trouve pour \"{query}\".\n"
            "Essayez avec un autre mot-cle (numero, client, technicien...)."
        )
        return

    for bon_id, bon_data in results:
        # Check if already has a draft
        already_done = bon_id in brouillons_crees
        summary = format_bon_summary(bon_id, bon_data)

        if already_done:
            await update.message.reply_text(
                f"\u2705 DEJA TRAITE\n\n<pre>{summary}</pre>",
                parse_mode="HTML",
            )
        else:
            keyboard = get_action_keyboard(bon_id)
            msg = await update.message.reply_text(
                f"<pre>{summary}</pre>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            bons_envoyes[bon_id] = msg.message_id


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
    elif data.startswith("mconfirm_"):
        await handle_modify_confirm(query, context)
    elif data.startswith("mcancel_"):
        await handle_modify_cancel(query, context)


async def handle_validate(query, context: ContextTypes.DEFAULT_TYPE):
    """Validate a bon and create a Pennylane draft."""
    bon_id = query.data.replace("valid_", "")

    # Anti-doublon Firestore : si le bon a deja ete traite (valide depuis admin
    # web par exemple, ou valide via Telegram avant un restart), on refuse et
    # on retire les boutons. Survit aux redemarrages du bot.
    try:
        bon_actuel = get_bon(bon_id)
        statut_actuel = (bon_actuel.get("statut") or "").lower() if bon_actuel else ""
        if statut_actuel in ("valide", "validé", "refuse", "refusé"):
            await query.edit_message_reply_markup(reply_markup=None)
            etat = "deja envoye en compta" if statut_actuel in ("valide", "validé") else "deja refuse"
            await query.message.reply_text(f"Bon {bon_id} : {etat}. Action bloquee.")
            return
    except Exception as e:
        logger.warning(f"Check statut Firestore avant validation {bon_id} : {e}")

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
        if TEST_MODE:
            # Mode test: simuler sans appeler Pennylane
            client_name = bon_data.get("client", "?")
            montant = bon_data.get("totalTTC", "0.00EUR")
            brouillons_crees[bon_id] = datetime.now()
            record_draft()

            # Marquer le message original comme traité
            summary = format_bon_summary(bon_id, bon_data)
            await query.edit_message_text(
                text=f"\u2705 BON VALIDE\n\n<pre>{summary}</pre>\n\n"
                     f"\u2705 TEST — Brouillon simule pour {client_name} — {montant}",
                parse_mode="HTML",
            )
        else:
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

            # Marquer le message original comme traité
            summary = format_bon_summary(bon_id, bon_data)
            heure = datetime.now().strftime("%H:%M")
            await query.edit_message_text(
                text=f"\u2705 BON VALIDE — {heure}\n\n<pre>{summary}</pre>\n\n"
                     f"\u2705 Brouillon Pennylane cree (ID: {pennylane_id})",
                parse_mode="HTML",
            )

        # Envoyer email compta avec bandeau VALIDE
        try:
            send_compta_email(bon_data, "valide")
        except Exception as email_err:
            logger.error(f"Erreur envoi email compta: {email_err}")

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
    """Refuse a bon - send to accounting with NE PAS FACTURER, no Pennylane draft."""
    bon_id = query.data.replace("refus_", "")

    # Anti-doublon Firestore : meme principe que handle_validate (survit aux restarts).
    try:
        bon_actuel = get_bon(bon_id)
        statut_actuel = (bon_actuel.get("statut") or "").lower() if bon_actuel else ""
        if statut_actuel in ("valide", "validé", "refuse", "refusé"):
            await query.edit_message_reply_markup(reply_markup=None)
            etat = "deja envoye en compta" if statut_actuel in ("valide", "validé") else "deja refuse"
            await query.message.reply_text(f"Bon {bon_id} : {etat}. Action bloquee.")
            return
    except Exception as e:
        logger.warning(f"Check statut Firestore avant refus {bon_id} : {e}")

    # Log refusal
    log_action(bon_id, "refuse", {
        "timestamp": datetime.now().isoformat(),
    })

    # Marquer le bon comme refuse dans Firestore (sinon il reste compte
    # comme "a valider" dans le rappel quotidien et dans l'admin).
    # Orthographe "refuse" sans accent : coherence avec l'existant.
    try:
        update_bon_statut(bon_id, "refuse")
    except Exception as statut_err:
        logger.error(f"Erreur mise a jour statut refuse: {statut_err}")

    bon_data = get_bon(bon_id)
    if bon_data:
        # Envoyer email compta avec bandeau REFUSE
        try:
            send_compta_email(bon_data, "refuse")
        except Exception as email_err:
            logger.error(f"Erreur envoi email compta (refus): {email_err}")

        # Marquer le message original comme refusé
        summary = format_bon_summary(bon_id, bon_data)
        heure = datetime.now().strftime("%H:%M")
        await query.edit_message_text(
            text=f"\u274c BON REFUSE — {heure}\n\n<pre>{summary}</pre>\n\n"
                 f"\u274c Email envoye a la compta : NE PAS FACTURER",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"Bon {bon_id} refuse.")


# ── Free text search ──────────────────────────────────────────────────
async def handle_bon_search_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Try to find a bon from a free text message."""
    text = update.message.text.strip()

    # Extract search keywords — remove common filler words
    fillers = {"je", "veux", "voudrais", "peux", "tu", "le", "la", "les", "un", "une",
               "des", "du", "de", "mon", "ma", "mes", "ce", "bon", "bons", "cherche",
               "chercher", "trouver", "trouve", "voir", "affiche", "afficher", "montre",
               "montrer", "rappeler", "rappelle", "corriger", "modifier", "modification",
               "intervention", "d'intervention", "numero", "n°", "est", "ou", "et",
               "me", "moi", "stp", "svp", "s'il", "plait", "comment", "faire", "pour",
               "sur", "dans", "avec", "qui", "que", "quoi", "quel", "quelle", "non",
               "oui", "pas", "plus", "alors", "donc", "enfait", "en", "fait"}
    words = text.lower().replace("'", " ").replace("?", "").replace("!", "").split()
    keywords = [w for w in words if w not in fillers and len(w) > 1]

    if not keywords:
        await update.message.reply_text(
            "Je n'ai pas compris. Pour chercher un bon, tapez :\n"
            "/bon [mot-cle]\n\n"
            "Exemples : /bon obus, /bon cafe, /bon ricardo"
        )
        return

    # Search with each keyword until we find results
    all_results = []
    for kw in keywords:
        results = search_bons(kw)
        for r in results:
            if r[0] not in [x[0] for x in all_results]:
                all_results.append(r)

    if not all_results:
        await update.message.reply_text(
            f"Aucun bon trouve pour \"{' '.join(keywords)}\".\n"
            "Essayez /bon [mot-cle] avec un autre terme."
        )
        return

    for bon_id, bon_data in all_results[:3]:
        already_done = bon_id in brouillons_crees
        summary = format_bon_summary(bon_id, bon_data)

        if already_done:
            await update.message.reply_text(
                f"\u2705 DEJA TRAITE\n\n<pre>{summary}</pre>",
                parse_mode="HTML",
            )
        else:
            keyboard = get_action_keyboard(bon_id)
            msg = await update.message.reply_text(
                f"<pre>{summary}</pre>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            bons_envoyes[bon_id] = msg.message_id


# ── Modification flow (natural language via Claude) ───────────────────
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
    produits = list(bon_data.get("produits", []))
    bons_en_modification[str(query.from_user.id)] = {
        "bon_id": bon_id,
        "bon_data": bon_data,
        "produits": produits,
    }

    # Show current bon info and ask for natural language instruction
    lines = [f"MODIFICATION DU BON {bon_data.get('numero', bon_id)}", ""]
    lines.append(f"Client : {bon_data.get('client', 'N/A')}")
    lines.append(f"Adresse : {bon_data.get('address', 'N/A')}")
    lines.append(f"Description : {bon_data.get('description', 'N/A')}")
    lines.append("")
    for i, p in enumerate(produits, 1):
        nom = p.get("nom", "?")
        qty = p.get("quantite", 0)
        prix = p.get("prixUnitaire", 0)
        total = qty * prix
        lines.append(f"  {i}. {nom} — {qty} x {prix:.2f}EUR = {total:.2f}EUR")
    lines.append("")
    lines.append("Decrivez votre modification en francais.")
    lines.append("Exemples :")
    lines.append('  "change l\'adresse a 12 rue de la Paix 75002"')
    lines.append('  "change la quantite du disjoncteur a 3"')
    lines.append('  "ajoute une ligne main d\'oeuvre 200EUR"')
    lines.append("")
    lines.append("Ou envoyez 'annuler' pour annuler.")

    await query.message.reply_text("\n".join(lines))


async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message — either modification flow or free search."""
    if not is_admin(update.effective_user.id):
        return

    user_id = str(update.effective_user.id)
    state = bons_en_modification.get(user_id)

    # If not in modification mode, try to find a bon
    if not state:
        await handle_bon_search_free(update, context)
        return

    text = update.message.text.strip()
    bon_id = state["bon_id"]

    # Cancel
    if text.lower() == "annuler":
        del bons_en_modification[user_id]
        bon_data = get_bon(bon_id)
        if bon_data:
            summary = format_bon_summary(bon_id, bon_data)
            keyboard = get_action_keyboard(bon_id)
            await update.message.reply_text(
                f"Modification annulee.\n\n<pre>{summary}</pre>",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        return

    # Send to Claude for interpretation
    await update.message.reply_text("Analyse de votre demande...")

    try:
        result = apply_modification(state["bon_data"], text)
        new_produits = result["produits"]
        champs_modifies = result.get("champs_modifies", {})
        resume = result.get("resume", "Modification appliquee")

        # Store the proposed modification for confirmation
        state["proposed_produits"] = new_produits
        state["champs_modifies"] = champs_modifies
        state["resume"] = resume

        # Show proposed changes
        lines = [f"Modification proposee : {resume}", ""]
        if champs_modifies:
            for field, value in champs_modifies.items():
                lines.append(f"  {field} : {value}")
            lines.append("")
        for i, p in enumerate(new_produits, 1):
            nom = p.get("nom", "?")
            qty = p.get("quantite", 0)
            prix = p.get("prixUnitaire", 0)
            total = qty * prix
            lines.append(f"  {i}. {nom} — {qty} x {prix:.2f}EUR = {total:.2f}EUR")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Appliquer", callback_data=f"mconfirm_{bon_id}"),
                InlineKeyboardButton("Annuler", callback_data=f"mcancel_{bon_id}"),
            ]
        ])

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Erreur Claude modification: {e}")
        await update.message.reply_text(
            f"Erreur lors de l'analyse : {e}\n\n"
            "Reessayez avec une autre formulation, ou envoyez 'annuler'."
        )


async def handle_modify_confirm(query, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and apply the Claude-proposed modification."""
    bon_id = query.data.replace("mconfirm_", "")
    user_id = str(query.from_user.id)
    state = bons_en_modification.get(user_id)

    if not state or state["bon_id"] != bon_id or "proposed_produits" not in state:
        await query.answer("Session expiree.", show_alert=True)
        return

    await query.edit_message_reply_markup(reply_markup=None)

    # Save modified produits to Firebase
    new_produits = state["proposed_produits"]
    champs_modifies = state.get("champs_modifies", {})
    update_bon_produits(bon_id, new_produits)

    # Save other modified fields to Firebase
    if champs_modifies:
        from firebase_listener import get_db
        from config import BONS_COLLECTION
        get_db().collection(BONS_COLLECTION).document(bon_id).update(champs_modifies)

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
        "resume": state.get("resume", ""),
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
    _app.add_handler(CommandHandler("bon", cmd_bon))

    # Callback query handler (all button presses)
    _app.add_handler(CallbackQueryHandler(handle_callback))

    # Text message handler — modification flow OR free text search (admin only)
    _app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(TELEGRAM_ADMIN_IDS),
        handle_free_text,
    ))

    logger.info("Bot Telegram demarre")

    # Start polling and get the event loop
    _app.post_init = _post_init
    _app.run_polling(allowed_updates=Update.ALL_TYPES)


async def editer_messages_apres_validation_refus():
    """Job periodique : pour chaque bon valide/refuse qui a des messages Telegram
    non encore edites, edite ces messages avec V vert ou X rouge + retrait des
    boutons. Couvre les validations/refus faits via TELEGRAM ou ADMIN WEB.
    Tourne toutes les 30 secondes."""
    try:
        from firebase_listener import get_bons_a_editer, marquer_telegram_edite
        bons = get_bons_a_editer()
        if not bons:
            return
        for b in bons:
            bon_id = b["id"]
            data = b["data"]
            statut = b["statut"].lower()
            est_refus = statut in ("refuse", "refusé")
            heure = datetime.now().strftime("%H:%M")
            numero = data.get("numero", bon_id)
            client = data.get("client", "?")
            montant = data.get("totalTTC", "")
            technicien = data.get("technicien", "")

            if est_refus:
                entete = f"❌ <b>BON REFUSE — {heure}</b>"
                pied = "<i>Refus enregistre. Ne pas facturer.</i>"
            else:
                entete = f"✅ <b>BON VALIDE — {heure}</b>"
                pied = "<i>Envoye en compta.</i>"

            texte = (
                f"{entete}\n\n"
                f"N° {numero} ({client})"
                + (f" — {montant}" if montant else "")
                + "\n"
                + (f"Tech : {technicien}\n" if technicien else "")
                + f"\n{pied}"
            )

            telegram_messages = data.get("telegram_messages", [])
            edited_count = 0
            # Liste des chat_id distincts pour le nouveau push de notification
            chat_ids_uniques = set()
            for m in telegram_messages:
                if not isinstance(m, dict):
                    continue
                chat_id = m.get("chat_id")
                message_id = m.get("message_id")
                if not chat_id or not message_id:
                    continue
                chat_ids_uniques.add(int(chat_id))
                # 1. Editer le message d'origine (V vert + retire les boutons)
                try:
                    await _app.bot.edit_message_text(
                        chat_id=int(chat_id),
                        message_id=int(message_id),
                        text=texte,
                        parse_mode="HTML",
                        reply_markup=None,
                    )
                    edited_count += 1
                except Exception as e:
                    if "not modified" not in str(e).lower() and "not found" not in str(e).lower():
                        logger.warning(f"Edit msg echec bon {bon_id} chat {chat_id}: {e}")

            # 2. Envoyer un nouveau message court (notification sonore).
            #    Si on a des chat_id depuis telegram_messages -> on cible ces admins-la
            #    (cas normal). Sinon, fallback : on envoie a tous les TELEGRAM_ADMIN_IDS
            #    (rattrapage pour les bons valides AVANT que telegram_messages soit stocke).
            cibles_push = chat_ids_uniques if chat_ids_uniques else set(TELEGRAM_ADMIN_IDS)
            push_court = (
                ("❌" if est_refus else "✅")
                + " <b>"
                + ("REFUSE" if est_refus else "VALIDE")
                + "</b> — N° " + str(numero)
                + " (" + str(client) + ")"
                + ((" — " + str(montant)) if montant else "")
            )
            push_count = 0
            for chat_id in cibles_push:
                try:
                    await _app.bot.send_message(
                        chat_id=int(chat_id),
                        text=push_court,
                        parse_mode="HTML",
                    )
                    push_count += 1
                except Exception as e:
                    logger.warning(f"Push notif echec bon {bon_id} chat {chat_id}: {e}")

            # Marquer comme traite pour ne pas re-traiter en boucle
            try:
                marquer_telegram_edite(bon_id)
                logger.info(f"Bon {bon_id} : {edited_count} edites + {push_count} push ({statut})")
            except Exception as e:
                logger.warning(f"Marquage telegram_edite echec bon {bon_id}: {e}")
    except Exception as e:
        logger.error(f"editer_messages_apres_validation_refus echec : {e}")


async def _post_init(application: Application):
    """Called after the application is initialized - start Firebase listener.
    Note : pas de reinit interne du listener -- ca pose des problemes de thread
    avec le client Firestore. La fiabilite vient d'un restart Docker periodique
    cote VPS (tache planifiee Windows toutes les heures).
    """
    global _loop
    _loop = asyncio.get_running_loop()

    # Cleanup one-shot : marquer tous les bons deja valides/refuses comme
    # deja notifies, pour ne pas envoyer un spam de push a chaque demarrage.
    try:
        cleanup_initial_bons_valides_refuses()
    except Exception as e:
        logger.warning(f"Cleanup initial echoue (non bloquant) : {e}")
    # Cleanup en_attente : eviter le re-push des bons existants apres restart.
    try:
        cleanup_initial_bons_en_attente()
    except Exception as e:
        logger.warning(f"Cleanup en_attente echoue (non bloquant) : {e}")

    # Schedule daily summary at 18h + edition des messages Telegram apres
    # validation/refus toutes les 30 sec (couvre Telegram + admin web)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_summary, "cron", hour=18, minute=0)
    scheduler.add_job(editer_messages_apres_validation_refus, "interval", seconds=30)
    scheduler.start()

    listen_for_signed_bons(on_new_signed_bon)
    logger.info("Firebase listener connecte au bot Telegram")


if __name__ == "__main__":
    main()
