"""Max's brain - Claude AI for understanding and responding."""

import json
import logging
from datetime import datetime, timedelta

import anthropic

from config import ANTHROPIC_API_KEY, ALL_TECHNICIENS
from firebase_max import (
    create_planning,
    get_planning_for_tech,
    modify_bon,
    search_bon,
    search_client,
)

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_tech_list = ", ".join(ALL_TECHNICIENS.keys())

SYSTEM_PROMPT = """Tu es Max, un assistant vocal intelligent pour deux entreprises d'electricite : CEP et Elechosystem.
Tu parles en francais de maniere naturelle, amicale et efficace. Tu es concis.

Date et heure actuelles : {now}

Techniciens :
- CEP : CHRISTOPHE, RICARDO, MATHIEU
- Elechosystem : AURELIEN, FRED, WILL

TU PEUX FAIRE :
- Planifier des interventions (creer des RDV dans le planning)
- Consulter le planning d'un technicien
- Chercher un bon d'intervention
- Modifier un bon d'intervention (adresse, description, produits, etc.)

TU NE PEUX PAS FAIRE :
- Valider un bon (envoyer en compta)
- Refuser un bon
- Supprimer quoi que ce soit

FONCTIONNEMENT :
1. Analyse le message de l'utilisateur
2. Determine l'action a effectuer
3. Si des infos manquent, demande-les naturellement (pas une par une, demande tout d'un coup)
4. Reponds de maniere naturelle et concise

Pour les dates : "demain" = jour+1, "jeudi" = prochain jeudi, etc. Si un jour de la semaine est mentionne, prends la date exacte.
Pour les techniciens : corrige les approximations (Chris→CHRISTOPHE, Rico→RICARDO, Matt→MATHIEU, Fred→FRED, etc.)

REPONSE EN JSON :
{{
  "action": "planifier" | "consulter_planning" | "chercher_bon" | "modifier_bon" | "conversation",
  "data": {{ ... donnees extraites ... }},
  "response": "ta reponse naturelle a l'utilisateur",
  "complete": true | false,
  "missing": ["liste des infos manquantes"]
}}

Pour "planifier" data: {{"client", "description", "date" (YYYY-MM-DD), "heure" (HH:MM), "technicien"}}
Pour "consulter_planning" data: {{"technicien", "date_from" (YYYY-MM-DD), "date_to" (YYYY-MM-DD)}}
Pour "chercher_bon" data: {{"query"}}
Pour "modifier_bon" data: {{"query", "modifications": {{"champ": "valeur"}}}}
Pour "conversation" data: {{}}

Retourne UNIQUEMENT le JSON."""

# Conversation history per user
_histories: dict[str, list] = {}


def get_history(user_id: str) -> list:
    if user_id not in _histories:
        _histories[user_id] = []
    return _histories[user_id]


def add_to_history(user_id: str, role: str, content: str):
    history = get_history(user_id)
    history.append({"role": role, "content": content})
    # Keep last 20 messages
    if len(history) > 20:
        _histories[user_id] = history[-20:]


def process_message(user_id: str, text: str) -> str:
    """Process a user message and return Max's response text."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    prompt = SYSTEM_PROMPT.format(now=now)

    add_to_history(user_id, "user", text)
    history = get_history(user_id)

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=prompt,
            messages=history,
        )
        response_text = response.content[0].text.strip()
        logger.info("Max brain: {}".format(response_text[:300]))

        # Parse JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)
        action = result.get("action", "conversation")
        data = result.get("data", {})
        reply = result.get("response", "Je n'ai pas compris.")
        complete = result.get("complete", False)

        # Execute action if complete
        if complete and action == "planifier":
            reply = execute_planifier(data, reply)
        elif complete and action == "consulter_planning":
            reply = execute_consulter_planning(data, reply)
        elif complete and action == "chercher_bon":
            reply = execute_chercher_bon(data, reply)
        elif complete and action == "modifier_bon":
            reply = execute_modifier_bon(data, reply)

        add_to_history(user_id, "assistant", reply)
        return reply

    except json.JSONDecodeError:
        # Claude responded with plain text
        reply = response_text if response_text else "Desole, je n'ai pas compris."
        add_to_history(user_id, "assistant", reply)
        return reply
    except Exception as e:
        logger.error("Erreur Max brain: {}".format(e))
        return "Desole, j'ai eu un probleme. Reessaie."


def execute_planifier(data, reply):
    """Create a planning entry."""
    try:
        technicien = data.get("technicien", "").upper()
        societe_id = ALL_TECHNICIENS.get(technicien)
        if not societe_id:
            return "Je ne connais pas ce technicien. Les techniciens disponibles sont : {}".format(_tech_list)

        # Search client address
        client_name = data.get("client", "")
        if client_name:
            client_info = search_client(client_name, societe_id)
            if client_info:
                if not data.get("adresse"):
                    data["adresse"] = client_info.get("adresse", "")
                if client_info.get("nom"):
                    data["client"] = client_info["nom"]

        create_planning(societe_id, data)
        return reply
    except Exception as e:
        logger.error("Erreur planification: {}".format(e))
        return "Desole, erreur lors de la planification : {}".format(e)


def execute_consulter_planning(data, reply):
    """Get planning for a technician."""
    try:
        technicien = data.get("technicien", "")
        date_from = data.get("date_from", datetime.now().strftime("%Y-%m-%d"))
        date_to = data.get("date_to", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))

        entries = get_planning_for_tech(technicien, date_from, date_to)
        if not entries:
            return "Aucun RDV prevu pour {} entre le {} et le {}.".format(technicien, date_from, date_to)

        lines = ["Planning de {} :".format(technicien)]
        for e in entries:
            lines.append("- {} a {} : {} ({})".format(
                e.get("date", "?"), e.get("heure", "?"),
                e.get("client", "?"), e.get("description", "")
            ))
        return "\n".join(lines)
    except Exception as e:
        logger.error("Erreur consultation planning: {}".format(e))
        return "Erreur lors de la consultation du planning."


def execute_chercher_bon(data, reply):
    """Search for a bon."""
    try:
        query = data.get("query", "")
        results = search_bon(query)
        if not results:
            return "Aucun bon trouve pour \"{}\".".format(query)

        lines = ["J'ai trouve {} bon(s) :".format(len(results))]
        for b in results:
            lines.append("- Bon {} : {} - {} - {} - {}".format(
                b.get("numero", "?"), b.get("client", "?"),
                b.get("technicien", "?"), b.get("date", "?"),
                b.get("totalTTC", "?")
            ))
        return "\n".join(lines)
    except Exception as e:
        logger.error("Erreur recherche bon: {}".format(e))
        return "Erreur lors de la recherche."


def execute_modifier_bon(data, reply):
    """Modify a bon."""
    try:
        query = data.get("query", "")
        modifications = data.get("modifications", {})
        results = search_bon(query)
        if not results:
            return "Aucun bon trouve pour \"{}\".".format(query)

        bon = results[0]
        modify_bon(bon["id"], bon["_societe_id"], modifications)
        return reply
    except Exception as e:
        logger.error("Erreur modification bon: {}".format(e))
        return "Erreur lors de la modification : {}".format(e)
