"""Claude AI client for natural language bon modifications."""

import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Tu es un assistant expert en gestion de bons d'intervention pour une entreprise d'électricité.
Un technicien fait une intervention chez un client, remplit un bon, et l'admin te demande de modifier ce bon avant de l'envoyer en comptabilité.

L'admin te parle en français naturel, parfois avec des fautes, des abréviations, ou du langage oral. Tu dois TOUJOURS comprendre son intention.

Tu reçois le bon actuel en JSON. Tu dois appliquer la modification demandée et retourner le résultat en JSON.

Voici les champs modifiables :
- "produits" : liste des lignes (chaque ligne a "nom", "quantite", "prixUnitaire")
- "address" : adresse d'intervention
- "phone" : téléphone du client
- "client" : nom du client
- "description" : description des travaux
- "heureArrivee", "heureDepart" : horaires
- "technicien" : nom du technicien
- "moDemiHeures" : nombre de demi-heures de main d'oeuvre
- "moTarif" : tarif par demi-heure
- "deplNombre" : nombre de déplacements
- "deplTarif" : tarif du déplacement

EXEMPLES DE DEMANDES ET CE QUE TU DOIS FAIRE :
- "mets 3 rubans led" → modifier la quantité du produit "Ruban LED" à 3
- "change le prix du ruban à 30" → modifier prixUnitaire du ruban à 30
- "supprime le déplacement" → mettre deplNombre à 0
- "ajoute 2h de main d'oeuvre" → moDemiHeures = 4 (car 2h = 4 demi-heures)
- "change l'adresse à 15 rue de la paix" → modifier le champ address
- "met 1h30 de MO" → moDemiHeures = 3
- "ajoute une ligne prise RJ45 à 25€" → ajouter dans produits
- "enlève la ligne câble" → supprimer le produit qui contient "câble" dans le nom
- "c'est pas Ricardo c'est Christophe" → modifier technicien
- "le client c'est Dupont" → modifier client

FORMAT DE RÉPONSE (JSON uniquement, rien d'autre) :
{
  "produits": [... liste complète des produits même si inchangés ...],
  "champs_modifies": {"champ": "nouvelle_valeur", ...},
  "resume": "courte description en français de ce qui a changé"
}

Si seuls les produits changent, "champs_modifies" doit être {}.
Si seuls des champs hors produits changent, "produits" doit contenir la liste inchangée.
Retourne UNIQUEMENT le JSON, sans texte avant ou après."""


def apply_modification(bon_data: dict, instruction: str) -> dict:
    """
    Use Claude to interpret a natural language modification instruction
    and apply it to the bon data.

    Returns {"produits": [...], "champs_modifies": {...}, "resume": "..."} on success.
    Raises an exception on failure.
    """
    # Build a simplified view of the bon for Claude
    bon_summary = {
        "client": bon_data.get("client", ""),
        "address": bon_data.get("address", ""),
        "phone": bon_data.get("phone", ""),
        "description": bon_data.get("description", ""),
        "technicien": bon_data.get("technicien", ""),
        "heureArrivee": bon_data.get("heureArrivee", ""),
        "heureDepart": bon_data.get("heureDepart", ""),
        "moDemiHeures": bon_data.get("moDemiHeures", ""),
        "moTarif": bon_data.get("moTarif", ""),
        "deplNombre": bon_data.get("deplNombre", ""),
        "deplTarif": bon_data.get("deplTarif", ""),
        "produits": bon_data.get("produits", []),
    }
    bon_json = json.dumps(bon_summary, ensure_ascii=False, indent=2)

    logger.info(f"Claude instruction: {instruction}")
    logger.info(f"Claude bon context: {bon_json[:500]}")

    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Voici le bon actuel :\n"
                    f"```json\n{bon_json}\n```\n\n"
                    f"Demande de l'admin : {instruction}"
                ),
            }
        ],
    )

    response_text = message.content[0].text.strip()
    logger.info(f"Claude response: {response_text[:500]}")

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    result = json.loads(response_text)

    if "produits" not in result:
        raise ValueError("Réponse Claude invalide : pas de clé 'produits'")

    # Ensure champs_modifies exists
    if "champs_modifies" not in result:
        result["champs_modifies"] = {}

    return result
