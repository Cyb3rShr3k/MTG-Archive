# enrich.py
import requests

SCRYFALL_URL = "https://api.scryfall.com/cards/named"

def enrich_card(card_name):
    """
    Query Scryfall API by card name (fuzzy search).
    Returns a dict with canonical card data.
    """
    try:
        response = requests.get(SCRYFALL_URL, params={"fuzzy": card_name})
        response.raise_for_status()
        data = response.json()

        # Extract relevant fields
        card_info = {
            "id": data.get("id"),
            "name": data.get("name"),
            "set": data.get("set"),
            "collector_number": data.get("collector_number"),
            "oracle_text": data.get("oracle_text"),
            "mana_cost": data.get("mana_cost"),
            "type_line": data.get("type_line"),
            "power": data.get("power"),
            "toughness": data.get("toughness"),
            "rarity": data.get("rarity"),
            "image_uris": data.get("image_uris", {})
        }
        return card_info

    except requests.exceptions.RequestException as e:
        print(f"Error querying Scryfall: {e}")
        return None
