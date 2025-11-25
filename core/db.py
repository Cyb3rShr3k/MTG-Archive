# core/db.py
import json
from pathlib import Path
from typing import List


def load_cards_db(path: Path) -> List[str]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
    except Exception:
        pass
    return []


def save_cards_db(path: Path, cards: List[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(sorted(set(cards)), f, ensure_ascii=False, indent=2)


def search_allprintings(sql_path: Path, query: str, limit: int = 25) -> List[str]:
    """
    Naive streaming search through a large .sql dump to find candidate rows containing the query.
    Returns up to `limit` matched line snippets. This is schema-agnostic but effective for quick suggestions.
    """
    matches: List[str] = []
    q = query.strip().lower()
    if not q:
        return matches
    path = Path(sql_path)
    if not path.exists():
        return matches

    try:
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if q in line.lower():
                    # Keep the line trimmed to a reasonable size for UI
                    snippet = line.strip()
                    if len(snippet) > 300:
                        snippet = snippet[:300] + '...'
                    matches.append(snippet)
                    if len(matches) >= limit:
                        break
    except Exception:
        return []

    return matches


def load_collection_db(path: Path) -> List[dict]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def save_collection_db(path: Path, items: List[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure normalized structure before saving
    normalized = [normalize_item(x) for x in items]
    # Atomic write: write to a temp file in the same directory, then replace
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
        f.flush()
    try:
        tmp.replace(path)
    except Exception:
        # Fallback: if replace failed, try to write directly
        with path.open('w', encoding='utf-8') as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)


def add_collection_items(path: Path, new_items: List[dict]) -> int:
    items = [normalize_item(x) for x in load_collection_db(path)]
    existing_keys = {collection_key(it) for it in items}
    added = 0
    for it in new_items:
        it = normalize_item(it)
        k = collection_key(it)
        if k not in existing_keys:
            items.append(it)
            existing_keys.add(k)
            added += 1
    save_collection_db(path, items)
    return added


def add_collection_items_allow_duplicates(path: Path, new_items: List[dict]) -> int:
    """Append all provided items (after normalization) without removing duplicates.
    Returns the number of items appended.
    """
    items = [normalize_item(x) for x in load_collection_db(path)]
    appended = 0
    for it in new_items:
        items.append(normalize_item(it))
        appended += 1
    save_collection_db(path, items)
    return appended


def collection_key(item: dict) -> str:
    name = str(item.get('name', '')).strip().lower()
    set_code = str(item.get('set', '')).strip().lower()
    number = str(item.get('number', '')).strip().lower()
    return f"{name}|{set_code}|{number}"


def parse_card_from_snippet(snippet: str, fallback_name: str = '') -> dict:
    name = ''
    set_code = ''
    number = ''
    buf = snippet
    start = 0
    candidates: List[str] = []
    while True:
        i = buf.find("'", start)
        if i == -1:
            break
        j = buf.find("'", i + 1)
        if j == -1:
            break
        s = buf[i + 1:j]
        if s:
            candidates.append(s)
        start = j + 1
        if len(candidates) > 50:
            break
    for c in candidates:
        if any(ch.isalpha() for ch in c) and len(c) <= 120:
            name = c
            break
    if not name:
        name = fallback_name
    return normalize_item({
        'name': name,
        'set': set_code,
        'number': number,
        'source': 'AllPrintings.sql'
    })


def normalize_item(item: dict) -> dict:
    """Ensure the item has all expected fields for UI filtering and display."""
    d = dict(item or {})
    # Core identifiers
    d.setdefault('name', '')
    d.setdefault('set', '')
    d.setdefault('number', '')
    d.setdefault('source', '')
    # Optional metadata used for filters
    d.setdefault('colors', [])           # list[str] like ["W","U"]
    d.setdefault('types', [])            # list[str] like ["Creature","Elf"]
    d.setdefault('cmc', None)            # int or float
    d.setdefault('power', None)          # int or str (e.g., "*"), store as str for safety
    d.setdefault('toughness', None)      # int or str
    d.setdefault('text', '')             # rules text
    d.setdefault('image_path', '')
    d.setdefault('image_url', '')        # Add image_url field
    # Double-faced card back face fields
    d.setdefault('back_name', '')
    d.setdefault('back_mana_cost', '')
    d.setdefault('back_colors', [])      # list[str] like ["W","U"]
    d.setdefault('back_types', [])       # list[str] like ["Creature","Werewolf"]
    d.setdefault('back_oracle_text', '')
    d.setdefault('back_power', None)     # int or str
    d.setdefault('back_toughness', None) # int or str
    d.setdefault('back_image_url', '')
    return d
