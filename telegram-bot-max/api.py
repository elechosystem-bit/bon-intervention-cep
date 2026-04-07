"""API web pour le raccourci iOS Siri."""

import logging
import os
import tempfile

from fastapi import FastAPI, File, UploadFile, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import TELEGRAM_ADMIN_IDS
from firebase_max import init_firebase, log_conversation
from max_brain import process_message
from voice_client import text_to_speech
from whisper_client import transcribe_voice

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Secret pour authentifier les requetes du raccourci iOS
API_SECRET = os.getenv("MAX_API_SECRET", "max-cep-elecho-2026")

app = FastAPI(title="Max API")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    init_firebase()
    logger.info("Max API demarree")


@app.post("/voice")
async def handle_voice(
    file: UploadFile = File(...),
    authorization: str = Header(default=""),
):
    """Receive a voice file, process it, return audio response."""
    # Auth check
    if authorization != "Bearer {}".format(API_SECRET):
        return JSONResponse(status_code=401, content={"error": "Non autorise"})

    # Save uploaded file
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        tmp_path = tmp.name
        content = await file.read()
        tmp.write(content)

    try:
        # 1. Transcribe
        text = transcribe_voice(tmp_path)
        if not text:
            return JSONResponse(content={"text": "Je n'ai pas compris.", "transcription": ""})

        logger.info("Siri transcription: {}".format(text))
        log_conversation("siri", "user_voice", text)

        # 2. Process with Claude
        reply = process_message("siri", text)
        log_conversation("siri", "max", reply)
        logger.info("Max reply: {}".format(reply[:200]))

        # 3. Generate voice
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            audio_path = tmp_audio.name

        text_to_speech(reply, audio_path)

        # Return audio file with text in header
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={"X-Max-Text": reply.replace("\n", " ")[:500]},
        )

    except Exception as e:
        logger.error("Erreur API voice: {}".format(e))
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/text")
async def handle_text(
    body: dict,
    authorization: str = Header(default=""),
):
    """Receive text, process it, return text response for Siri."""
    if authorization != "Bearer {}".format(API_SECRET):
        return JSONResponse(status_code=401, content={"error": "Non autorise"})

    text = body.get("text", "").strip()
    if not text:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content="Je n'ai rien entendu.")

    log_conversation("siri", "user_text", text)

    reply = process_message("siri", text)
    log_conversation("siri", "max", reply)

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=reply)


@app.get("/ask")
async def handle_ask(q: str = ""):
    """Simple GET endpoint - returns plain text response."""
    from fastapi.responses import PlainTextResponse

    if not q.strip():
        return PlainTextResponse(content="Je n'ai rien entendu.")

    log_conversation("siri", "user_text", q)
    reply = process_message("siri", q)
    log_conversation("siri", "max", reply)

    return PlainTextResponse(content=reply)


@app.get("/")
async def home():
    return FileResponse("static/index.html")


@app.get("/speak")
async def speak(text: str = ""):
    """Convert text to speech and return MP3."""
    if not text.strip():
        return JSONResponse(status_code=400, content={"error": "No text"})

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        audio_path = tmp.name

    try:
        text_to_speech(text, audio_path)
        return FileResponse(audio_path, media_type="audio/mpeg", filename="max.mp3")
    except Exception as e:
        logger.error("Erreur speak: {}".format(e))
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/voice-chat")
async def voice_chat(file: UploadFile = File(...)):
    """Full voice chat: Whisper transcription + Claude + ElevenLabs. Returns JSON with audio URL."""
    import uuid

    # Save uploaded audio
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp_path = tmp.name
        content = await file.read()
        tmp.write(content)

    try:
        # 1. Transcribe with Whisper
        transcription = transcribe_voice(tmp_path)
        if not transcription:
            return JSONResponse(content={"reply": "Je n'ai pas compris.", "transcription": "", "audio_url": None})

        logger.info("Voice chat transcription: {}".format(transcription))
        log_conversation("web", "user_voice", transcription)

        # 2. Process with Claude
        reply = process_message("web", transcription)
        log_conversation("web", "max", reply)
        logger.info("Voice chat reply: {}".format(reply[:200]))

        # 3. Generate voice with ElevenLabs
        audio_filename = "max_{}.mp3".format(uuid.uuid4().hex[:8])
        audio_path = os.path.join(tempfile.gettempdir(), audio_filename)

        try:
            text_to_speech(reply, audio_path)
            audio_url = "/audio/{}".format(audio_filename)
        except Exception as e:
            logger.error("TTS error: {}".format(e))
            audio_url = None

        return JSONResponse(content={
            "reply": reply,
            "transcription": transcription,
            "audio_url": audio_url
        })

    except Exception as e:
        logger.error("Voice chat error: {}".format(e))
        return JSONResponse(content={"reply": "Desole, une erreur est survenue.", "transcription": "", "audio_url": None})
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve generated audio files."""
    audio_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(audio_path):
        return FileResponse(audio_path, media_type="audio/mpeg")
    return JSONResponse(status_code=404, content={"error": "Audio not found"})


@app.get("/health")
async def health():
    return {"status": "ok", "name": "Max"}
