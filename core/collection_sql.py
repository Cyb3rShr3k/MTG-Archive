# core/collection_sql.py
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS collection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    set_code TEXT NOT NULL DEFAULT '',
    number TEXT NOT NULL DEFAULT '',
    colors TEXT NOT NULL DEFAULT '[]',
    types TEXT NOT NULL DEFAULT '[]',
    cmc REAL,
    power TEXT,
    toughness TEXT,
    text TEXT,
    image_path TEXT,
    image_url TEXT,
    source TEXT,
    repaired INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Double-faced card support (back face)
    back_name TEXT,
    back_mana_cost TEXT,
    back_colors TEXT,
    back_types TEXT,
    back_oracle_text TEXT,
    back_power TEXT,
    back_toughness TEXT,
    back_image_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_collection_name ON collection(name);
CREATE INDEX IF NOT EXISTS idx_collection_ident ON collection(name, set_code, number);
-- Decks and deck card links
CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    deck_type TEXT NOT NULL DEFAULT '',
    deck_colors TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS deck_cards (
    deck_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(deck_id) REFERENCES decks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_deck_cards_deck ON deck_cards(deck_id);
CREATE INDEX IF NOT EXISTS idx_deck_cards_name ON deck_cards(name);
"""

def _open_conn(path: Path) -> sqlite3.Connection:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Increase default timeout and set busy timeout to reduce 'database is locked'
    conn = sqlite3.connect(str(p), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db(path: Path) -> None:
    with _open_conn(path) as conn:
        conn.executescript(SCHEMA)
        # Improve concurrency: enable WAL so readers don't block writers
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        # Migration: ensure decks.deck_type exists
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(decks)")]  # cid, name, type, ...
            if 'deck_type' not in cols:
                conn.execute("ALTER TABLE decks ADD COLUMN deck_type TEXT NOT NULL DEFAULT ''")
            if 'deck_colors' not in cols:
                conn.execute("ALTER TABLE decks ADD COLUMN deck_colors TEXT NOT NULL DEFAULT '[]'")
            if 'commander' not in cols:
                conn.execute("ALTER TABLE decks ADD COLUMN commander TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
        # Migration: ensure collection.repaired exists
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(collection)")]
            if 'repaired' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN repaired INTEGER DEFAULT 0")
            # Add double-faced card columns
            if 'back_name' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_name TEXT")
            if 'back_mana_cost' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_mana_cost TEXT")
            if 'back_colors' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_colors TEXT")
            if 'back_types' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_types TEXT")
            if 'back_oracle_text' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_oracle_text TEXT")
            if 'back_power' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_power TEXT")
            if 'back_toughness' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_toughness TEXT")
            if 'back_image_url' not in cols:
                conn.execute("ALTER TABLE collection ADD COLUMN back_image_url TEXT")
        except Exception:
            pass
        conn.commit()


def _to_row_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        'name': row['name'],
        'set': row['set_code'],
        'number': row['number'],
        'colors': json.loads(row['colors'] or '[]'),
        'types': json.loads(row['types'] or '[]'),
        'cmc': row['cmc'],
        'power': row['power'],
        'toughness': row['toughness'],
        'text': row['text'],
        'image_path': row['image_path'],
        'image_url': row['image_url'],
        'source': row['source'],
        'back_name': row['back_name'] or '',
        'back_mana_cost': row['back_mana_cost'] or '',
        'back_colors': json.loads(row['back_colors'] or '[]'),
        'back_types': json.loads(row['back_types'] or '[]'),
        'back_oracle_text': row['back_oracle_text'] or '',
        'back_power': row['back_power'],
        'back_toughness': row['back_toughness'],
        'back_image_url': row['back_image_url'] or '',
    }


def _from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    it = dict(item or {})
    return {
        'name': str(it.get('name') or ''),
        'set_code': str(it.get('set') or ''),
        'number': str(it.get('number') or ''),
        'colors': json.dumps(it.get('colors') or []),
        'types': json.dumps(it.get('types') or []),
        'cmc': it.get('cmc'),
        'power': None if it.get('power') is None else str(it.get('power')),
        'toughness': None if it.get('toughness') is None else str(it.get('toughness')),
        'text': it.get('text'),
        'image_path': it.get('image_path'),
        'image_url': it.get('image_url'),
        'source': it.get('source'),
        'back_name': str(it.get('back_name') or ''),
        'back_mana_cost': str(it.get('back_mana_cost') or ''),
        'back_colors': json.dumps(it.get('back_colors') or []),
        'back_types': json.dumps(it.get('back_types') or []),
        'back_oracle_text': str(it.get('back_oracle_text') or ''),
        'back_power': None if it.get('back_power') is None else str(it.get('back_power')),
        'back_toughness': None if it.get('back_toughness') is None else str(it.get('back_toughness')),
        'back_image_url': str(it.get('back_image_url') or ''),
    }


def insert_items(path: Path, items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    ensure_db(path)
    with _open_conn(path) as conn:
        cur = conn.cursor()
        added = 0
        for it in items:
            row = _from_item(it)
            cur.execute(
                """
                INSERT INTO collection
                (name, set_code, number, colors, types, cmc, power, toughness, text, image_path, image_url, source,
                 back_name, back_mana_cost, back_colors, back_types, back_oracle_text, back_power, back_toughness, back_image_url)
                VALUES (:name, :set_code, :number, :colors, :types, :cmc, :power, :toughness, :text, :image_path, :image_url, :source,
                        :back_name, :back_mana_cost, :back_colors, :back_types, :back_oracle_text, :back_power, :back_toughness, :back_image_url)
                """,
                row
            )
            added += 1
        conn.commit()
        return added


def load_all(path: Path) -> List[Dict[str, Any]]:
    ensure_db(path)
    with _open_conn(path) as conn:
        cur = conn.execute("SELECT * FROM collection ORDER BY id ASC")
        return [_to_row_dict(r) for r in cur.fetchall()]


def count_items(path: Path) -> int:
    ensure_db(path)
    with _open_conn(path) as conn:
        cur = conn.execute("SELECT COUNT(1) FROM collection")
        return int(cur.fetchone()[0])


def delete_by_names_counts(path: Path, items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    ensure_db(path)
    # Build a normalized list: name -> remaining count (None = delete all)
    req: Dict[str, int | None] = {}
    for it in items:
        nm = str((it or {}).get('name') or '').strip()
        cnt = it.get('count')
        if not nm:
            continue
        if cnt is None:
            req[nm.lower()] = None
        else:
            try:
                c = int(cnt)
                if c > 0:
                    req[nm.lower()] = c
            except Exception:
                continue
    if not req:
        return 0
    deleted = 0
    with _open_conn(path) as conn:
        cur = conn.cursor()
        for nm, cnt in req.items():
            if cnt is None:
                cur.execute("DELETE FROM collection WHERE lower(name)=?", (nm,))
                deleted += cur.rowcount
            else:
                # delete up to cnt rows deterministically (oldest first)
                cur.execute("SELECT id FROM collection WHERE lower(name)=? ORDER BY id ASC LIMIT ?", (nm, cnt))
                ids = [r[0] for r in cur.fetchall()]
                if ids:
                    qmarks = ",".join(["?"]*len(ids))
                    cur.execute(f"DELETE FROM collection WHERE id IN ({qmarks})", ids)
                    deleted += cur.rowcount
        conn.commit()
    return deleted


def reset_db(path: Path) -> None:
    """Reset the collection table contents safely.
    On Windows, deleting the SQLite file can fail if another connection is open.
    Instead, ensure schema exists and clear the collection table in-place.
    """
    ensure_db(path)
    with _open_conn(Path(path)) as conn:
        conn.execute("DELETE FROM collection")
        conn.commit()

# -------------------- Deck helpers (relational) --------------------

def _get_deck_id(conn: sqlite3.Connection, name: str) -> int | None:
    cur = conn.execute("SELECT id FROM decks WHERE lower(name)=?", (name.strip().lower(),))
    row = cur.fetchone()
    return row[0] if row else None

def create_or_get_deck(path: Path, name: str) -> int:
    ensure_db(path)
    nm = str(name or '').strip()
    if not nm:
        raise ValueError('Deck name required')
    with _open_conn(path) as conn:
        did = _get_deck_id(conn, nm)
        if did is not None:
            return int(did)
        cur = conn.execute("INSERT INTO decks(name) VALUES (?)", (nm,))
        conn.commit()
        return int(cur.lastrowid)

def save_deck(path: Path, name: str, items: List[Dict[str, Any]], deck_type: str | None = None, deck_colors: List[str] | None = None, commander: str | None = None) -> None:
    """Replace deck contents with provided items: [{name, count}]"""
    import time
    ensure_db(path)
    nm = str(name or '').strip()
    if not nm:
        return
    attempts = 0
    last_err: Exception | None = None
    while attempts < 6:
        try:
            with _open_conn(path) as conn:
                try:
                    conn.execute("PRAGMA busy_timeout=15000")
                except Exception:
                    pass
                # Acquire write lock early
                try:
                    conn.execute("BEGIN IMMEDIATE")
                except Exception:
                    # continue anyway; SQLite may auto-begin
                    pass
                did = _get_deck_id(conn, nm)
                if did is None:
                    cur = conn.execute("INSERT INTO decks(name) VALUES (?)", (nm,))
                    did = int(cur.lastrowid)
                # Update deck metadata
                if deck_type is not None:
                    conn.execute("UPDATE decks SET deck_type=? WHERE id=?", (str(deck_type or ''), did))
                if deck_colors is not None:
                    try:
                        import json as _json
                        conn.execute("UPDATE decks SET deck_colors=? WHERE id=?", (_json.dumps(deck_colors), did))
                    except Exception:
                        conn.execute("UPDATE decks SET deck_colors=? WHERE id=?", ('[]', did))
                if commander is not None:
                    conn.execute("UPDATE decks SET commander=? WHERE id=?", (str(commander or ''), did))
                # Clear previous
                conn.execute("DELETE FROM deck_cards WHERE deck_id=?", (did,))
                # Normalize items: aggregate by lower(name)
                agg: Dict[str, int] = {}
                for it in (items or []):
                    nm2 = str((it or {}).get('name') or '').strip()
                    if not nm2:
                        continue
                    try:
                        c = int((it or {}).get('count') or 0)
                    except Exception:
                        c = 0
                    if c <= 0:
                        continue
                    key = nm2.lower()
                    agg[key] = agg.get(key, 0) + c
                rows = [(did, k, v) for k, v in agg.items()]
                if rows:
                    conn.executemany("INSERT INTO deck_cards(deck_id,name,count) VALUES (?,?,?)", rows)
                conn.commit()
                return
        except Exception as e:
            msg = str(e).lower()
            last_err = e
            if 'locked' in msg or 'busy' in msg:
                attempts += 1
                time.sleep(0.2 * attempts)
                continue
            raise
    # Exhausted retries
    raise last_err if last_err else RuntimeError('failed to save deck')

def _is_basic_land(card_name: str) -> bool:
    """Check if a card is a basic land (unlimited in Commander)."""
    basic_lands = {
        'plains', 'island', 'swamp', 'mountain', 'forest', 'wastes',
        'snow-covered plains', 'snow-covered island', 'snow-covered swamp', 
        'snow-covered mountain', 'snow-covered forest'
    }
    return str(card_name or '').strip().lower() in basic_lands

def add_to_deck(path: Path, deck_name: str, card_name: str, count: int = 1) -> None:
    ensure_db(path)
    nm = str(deck_name or '').strip()
    cn = str(card_name or '').strip()
    if not nm or not cn or (count or 0) <= 0:
        return
    with _open_conn(path) as conn:
        did = _get_deck_id(conn, nm)
        if did is None:
            cur = conn.execute("INSERT INTO decks(name) VALUES (?)", (nm,))
            did = int(cur.lastrowid)
        
        # Check if this is a Commander deck
        deck_info = conn.execute("SELECT deck_type FROM decks WHERE id=?", (did,)).fetchone()
        is_commander = deck_info and str(deck_info[0] or '').lower() in ['commander', 'edh']
        
        # Get current count
        cur = conn.execute("SELECT count FROM deck_cards WHERE deck_id=? AND lower(name)=?", (did, cn.lower()))
        row = cur.fetchone()
        current_count = int(row[0]) if row else 0
        
        # Apply Commander deck rules
        if is_commander and not _is_basic_land(cn):
            # For Commander: non-basic lands can only have 1 copy total
            if current_count >= 1:
                # Already at limit, don't add more
                return
            # Limit addition to reach exactly 1
            count = min(int(count), 1 - current_count)
            if count <= 0:
                return
        
        # Update or insert
        if row:
            newc = current_count + int(count)
            conn.execute("UPDATE deck_cards SET count=? WHERE deck_id=? AND lower(name)=?", (newc, did, cn.lower()))
        else:
            conn.execute("INSERT INTO deck_cards(deck_id,name,count) VALUES (?,?,?)", (did, cn, int(count)))
        conn.commit()

def remove_from_deck(path: Path, deck_name: str, card_name: str, count: int = 1) -> None:
    ensure_db(path)
    nm = str(deck_name or '').strip()
    cn = str(card_name or '').strip()
    if not nm or not cn or (count or 0) <= 0:
        return
    with _open_conn(path) as conn:
        did = _get_deck_id(conn, nm)
        if did is None:
            return
        cur = conn.execute("SELECT count FROM deck_cards WHERE deck_id=? AND lower(name)=?", (did, cn.lower()))
        row = cur.fetchone()
        if not row:
            return
        curc = int(row[0]) - int(count)
        if curc > 0:
            conn.execute("UPDATE deck_cards SET count=? WHERE deck_id=? AND lower(name)=?", (curc, did, cn.lower()))
        else:
            conn.execute("DELETE FROM deck_cards WHERE deck_id=? AND lower(name)=?", (did, cn.lower()))
        conn.commit()

def get_decks(path: Path) -> List[Dict[str, Any]]:
    ensure_db(path)
    with _open_conn(path) as conn:
        decks = []
        for d in conn.execute("SELECT id, name, deck_type, deck_colors, commander FROM decks ORDER BY name ASC"):
            did, nm, dtype, dcols, cmdr = d[0], d[1], d[2], d[3], d[4]
            cards = []
            for r in conn.execute("SELECT name, count FROM deck_cards WHERE deck_id=? ORDER BY name ASC", (did,)):
                cards.append({'name': r[0], 'count': int(r[1])})
            try:
                import json as _json
                cols = _json.loads(dcols or '[]')
            except Exception:
                cols = []
            decks.append({'name': nm, 'type': dtype or '', 'colors': cols, 'commander': cmdr or '', 'cards': cards})
        return decks

def usage_counts_by_name(path: Path) -> Dict[str, int]:
    """Return a mapping of lower(name) -> total count used across all decks"""
    ensure_db(path)
    with _open_conn(path) as conn:
        out: Dict[str, int] = {}
        for r in conn.execute("SELECT lower(name) as n, SUM(count) FROM deck_cards GROUP BY lower(name)"):
            if r and r[0]:
                out[str(r[0])] = int(r[1] or 0)
        return out

