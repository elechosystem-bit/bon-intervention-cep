"""Claude AI client for natural language planning."""

import json
import logging
from datetime import datetime, timedelta

import anthropic

from config import ANTHROPIC_API_KEY, ALL_TECHNICIENS

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Build technicien list for the prompt
_tech_list = ", ".join(ALL_TECHNICIENS.keys())

SYSTEM_PROMPT = """Tu es un assistant de planification pour deux entreprises d'electricite : CEP et Elechosystem.
Tu recois des messages en francais naturel pour planifier des interventions.

Date du jour : {today}

Techniciens disponibles :
- CEP : CHRISTOPHE, RICARDO, MATHIEU
- Elechosystem : AURELIEN, FRED, WILL

Tu dois extraire les informations suivantes du message :
- client : nom du client ou lieu (obligatoire)
- description : type d'intervention / travaux (obligatoire)
- date : au format YYYY-MM-DD (obligatoire). Interprete "demain", "jeudi", "lundi prochain", etc.
- heure : au format HH:MM (obligatoire). Interprete "14h", "9h30", "le matin" (=09:00), "l'aprem" (=14:00)
- technicien : prenom du technicien en MAJUSCULES (obligatoire). Corrige les approximations : "Thomas" → pas dans la liste, "Chris" → CHRISTOPHE, "Rico" → RICARDO, "Matt" → MATHIEU, "Fred" → FRED, "Will" → WILL, "Aurel" → AURELIEN

REGLES IMPORTANTES :
- Si une info est clairement presente dans le message, extrais-la
- Si une info manque ou est ambigue, mets null
- Pour les jours de la semaine : calcule la DATE EXACTE a partir d'aujourd'hui. "jeudi" = le prochain jeudi. "lundi prochain" = le lundi de la semaine prochaine.
- Pour "demain" = date du jour + 1
- Si le technicien n'existe pas dans la liste, mets null

FORMAT DE REPONSE (JSON uniquement) :
{{
  "client": "nom du client" ou null,
  "description": "description des travaux" ou null,
  "date": "YYYY-MM-DD" ou null,
  "heure": "HH:MM" ou null,
  "technicien": "PRENOM" ou null,
  "societe": "cep" ou "elechosystem" ou null
}}

La societe est determinee automatiquement par le technicien. Si pas de technicien, mets null.
Retourne UNIQUEMENT le JSON."""


def parse_planning_request(message: str) -> dict:
    """Parse a natural language planning request using Claude."""
    today = datetime.now().strftime("%Y-%m-%d (%A)")

    prompt = SYSTEM_PROMPT.format(today=today)

    logger.info("Claude planning: {}".format(message))

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=prompt,
        messages=[
            {
                "role": "user",
                "content": "Message de l'admin : {}".format(message),
            }
        ],
    )

    response_text = response.content[0].text.strip()
    logger.info("Claude planning response: {}".format(response_text))

    # Extract JSON
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    result = json.loads(response_text)

    # Auto-determine societe from technicien
    tech = result.get("technicien")
    if tech and tech.upper() in ALL_TECHNICIENS:
        result["technicien"] = tech.upper()
        result["societe"] = ALL_TECHNICIENS[tech.upper()]

    return result
