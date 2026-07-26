import time
import os
import requests

API_KEY = os.environ.get("POKEMON_TCG_API_KEY", "")
BASE_URL = "https://api.pokemontcg.io/v2"

RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2

_sets_cache = None


def _normalize_name(name):
    """Lowercase a hyphenated suffix like '-GX'/'-EX' to match the API's stored casing."""
    if name and "-" in name:
        base, _, suffix = name.rpartition("-")
        return f"{base}-{suffix.lower()}"
    return name


def _get_with_retry(url, params=None):
    """GET with a few retries, since pokemontcg.io intermittently returns 5xx errors."""
    headers = {"X-Api-Key": API_KEY} if API_KEY else {}

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code >= 500 and attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            resp.raise_for_status()
            return resp
        except requests.Timeout:
            if attempt == RETRY_ATTEMPTS:
                raise
            time.sleep(RETRY_DELAY_SECONDS)


def search_cards_api(name, number=None, hp=None):
    """Sucht Karten in der TCG-API, gibt Liste von Karten-Dicts zurück."""
    query = f'name:"{_normalize_name(name)}"'
    if number is not None:
        query += f" number:{number}"
    if hp is not None:
        query += f" hp:{hp}"

    resp = _get_with_retry(f"{BASE_URL}/cards", params={"q": query})
    return resp.json()["data"]       # Liste von Karten-Objekten


def get_card_by_id(card_id):
    """Lädt eine einzelne Karte anhand ihrer TCG-API-ID."""
    resp = _get_with_retry(f"{BASE_URL}/cards/{card_id}")
    return resp.json()["data"]


def get_card_prices(card):
    """Extrahiert TCGplayer- und Cardmarket-Preise aus einem Karten-Dict."""
    return {
        "tcgplayer": card.get("tcgplayer", {}).get("prices", {}),
        "cardmarket": card.get("cardmarket", {}).get("prices", {}),
    }


def get_sets():
    """Lädt alle verfügbaren Sets von der TCG-API (mit einfachem In-Memory-Cache)."""
    global _sets_cache
    if _sets_cache is None:
        resp = _get_with_retry(f"{BASE_URL}/sets")
        _sets_cache = resp.json()["data"]
    return _sets_cache


def get_set_options():
    """Gibt eine nach Name sortierte Liste von Sets (Code + Name) für Filter-Dropdowns zurück."""
    options = [
        {"code": s.get("ptcgoCode") or s.get("name"), "name": s.get("name")}
        for s in get_sets()
    ]
    return sorted(options, key=lambda o: o["name"])


def search_card_options(name, number, hp=None):
    """Sucht Karten anhand von Name und Nummer im Set.

    Da dieselbe Nummer in mehreren Sets vergeben sein kann, werden alle
    Treffer als vereinfachte Dicts (mit Bild und Set-Info) zurückgegeben,
    damit der Nutzer in der UI die richtige Karte auswählen kann.
    """
    cards = search_cards_api(name, number, hp=hp)

    options = []
    for card in cards:
        set_info = card.get("set", {})
        images = card.get("images", {})
        options.append({
            "id": card.get("id"),
            "name": card.get("name"),
            "number": card.get("number"),
            "set_id": set_info.get("id"),
            "set_name": set_info.get("name"),
            "image_small": images.get("small"),
            "image_large": images.get("large"),
            "prices": get_card_prices(card),
        })

    return options
