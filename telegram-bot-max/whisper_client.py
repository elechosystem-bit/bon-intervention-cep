"""Transcription vocale via OpenAI Whisper."""

import logging
import openai

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

_client = openai.OpenAI(api_key=OPENAI_API_KEY)


def transcribe_voice(file_path: str) -> str:
    """Transcribe a voice file to text using Whisper."""
    logger.info("Transcription Whisper: {}".format(file_path))
    with open(file_path, "rb") as f:
        result = _client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="fr",
        )
    text = result.text.strip()
    logger.info("Transcription: {}".format(text))
    return text
