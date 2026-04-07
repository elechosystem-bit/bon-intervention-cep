"""Synthese vocale via ElevenLabs."""

import logging
import httpx

from config import ELEVENLABS_API_KEY

logger = logging.getLogger(__name__)

# Voix francaise par defaut (Charlotte - voix feminine francaise)
VOICE_ID = "XB0fDUnXU5powFXDhCwa"  # Charlotte


def text_to_speech(text: str, output_path: str) -> str:
    """Convert text to speech and save as mp3. Returns the file path."""
    logger.info("ElevenLabs TTS: {} chars".format(len(text)))

    url = "https://api.elevenlabs.io/v1/text-to-speech/{}".format(VOICE_ID)
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=data, headers=headers)

    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        logger.info("Audio genere: {}".format(output_path))
        return output_path
    else:
        logger.error("Erreur ElevenLabs {}: {}".format(response.status_code, response.text))
        raise Exception("Erreur ElevenLabs: {}".format(response.status_code))
