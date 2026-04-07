"""
Max - Assistant vocal intelligent CEP / Elechosystem
=====================================================
Interface conversationnelle vocale pour gerer les interventions.
"""

import asyncio
import logging
import os
import tempfile

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import TELEGRAM_ADMIN_IDS, TELEGRAM_BOT_TOKEN
from firebase_max import init_firebase, log_conversation
from max_brain import process_message
from voice_client import text_to_speech
from whisper_client import transcribe_voice

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in TELEGRAM_ADMIN_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Acces refuse.")
        return
    await update.message.reply_text(
        "Salut, c'est Max !\n\n"
        "Envoie-moi un message vocal ou ecris-moi.\n"
        "Je peux planifier des interventions, consulter le planning, "
        "chercher ou modifier des bons.\n\n"
        "Parle naturellement, je comprends le francais."
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages."""
    if not is_admin(update.effective_user.id):
        return

    user_id = str(update.effective_user.id)

    # Download voice file
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    await file.download_to_drive(tmp_path)

    try:
        # 1. Transcribe with Whisper
        text = transcribe_voice(tmp_path)
        if not text:
            await update.message.reply_text("Je n'ai pas compris le message vocal.")
            return

        # Log the transcription
        log_conversation(user_id, "user_voice", text)

        # Send transcription as text
        await update.message.reply_text("{}".format(text), parse_mode=None)

        # 2. Process with Claude
        reply = process_message(user_id, text)

        # Log the response
        log_conversation(user_id, "max", reply)

        # 3. Send text response
        await update.message.reply_text(reply)

        # 4. Generate voice response with ElevenLabs
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            audio_path = tmp_audio.name

        try:
            text_to_speech(reply, audio_path)
            with open(audio_path, "rb") as audio_file:
                await update.message.reply_voice(voice=audio_file)
        except Exception as e:
            logger.error("Erreur TTS: {}".format(e))
            # Text response already sent, voice is bonus
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    if not is_admin(update.effective_user.id):
        return

    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    # Log
    log_conversation(user_id, "user_text", text)

    # Process with Claude
    reply = process_message(user_id, text)

    # Log
    log_conversation(user_id, "max", reply)

    # Send text response
    await update.message.reply_text(reply)

    # Generate voice response
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
        audio_path = tmp_audio.name

    try:
        text_to_speech(reply, audio_path)
        with open(audio_path, "rb") as audio_file:
            await update.message.reply_voice(voice=audio_file)
    except Exception as e:
        logger.error("Erreur TTS: {}".format(e))
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)


def main():
    init_firebase()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(
        (filters.VOICE | filters.AUDIO) & filters.User(user_id=TELEGRAM_ADMIN_IDS),
        handle_voice,
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(user_id=TELEGRAM_ADMIN_IDS),
        handle_text,
    ))

    logger.info("Max demarre")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
