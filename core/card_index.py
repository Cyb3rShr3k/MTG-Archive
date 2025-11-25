# core/card_index.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Iterable, List, Optional
import sqlite3
from .sql_utils import split_values_rows, parse_sql_values_tuple

SCHEMA = {
    'cards': {
        'columns': [
            'name',           # TEXT
            'set',            # TEXT
            'number',         # TEXT
            'colors',         # TEXT JSON or comma string
            'types',          # TEXT JSON or comma string
            'cmc',            # REAL
            'power',          # TEXT
            'toughness',      # TEXT
            'text'            # TEXT
        ]
    }
}


def open_db(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            name TEXT,
            "set" TEXT,
            number TEXT,
            colors TEXT,
            types TEXT,
            cmc REAL,
            power TEXT,
            toughness TEXT,
            text TEXT
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);")
    return conn


def insert_cards(conn: sqlite3.Connection, items: Iterable[Dict[str, Any]]):
    rows = []
    for it in items:
        rows.append((
            it.get('name') or '',
            it.get('set') or '',
            it.get('number') or '',
            encode_list(it.get('colors')),
            encode_list(it.get('types')),
            to_float(it.get('cmc')),
            stringify(it.get('power')),
            stringify(it.get('toughness')),
            it.get('text') or ''
        ))
    if rows:
        conn.executemany(
            "INSERT INTO cards (name,\"set\",number,colors,types,cmc,power,toughness,text) VALUES (?,?,?,?,?,?,?,?,?)",
            rows
        )
        conn.commit()


def lookup_by_name(conn: sqlite3.Connection, name: str, limit: int = 10) -> List[Dict[str, Any]]:
    q = f"%{name}%"
    cur = conn.execute(
        "SELECT name,\"set\",number,colors,types,cmc,power,toughness,text FROM cards WHERE name LIKE ? LIMIT ?",
        (q, limit)
    )
    rows = cur.fetchall()
    return [row_to_item(r) for r in rows]


def row_to_item(row) -> Dict[str, Any]:
    name, set_code, number, colors, types, cmc, power, toughness, text = row
    return {
        'name': name or '',
        'set': set_code or '',
        'number': number or '',
        'colors': decode_list(colors),
        'types': decode_list(types),
        'cmc': cmc,
        'power': power,
        'toughness': toughness,
        'text': text or ''
    }


def stringify(v) -> str:
    return '' if v is None else str(v)


def to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def encode_list(v) -> str:
    if not v:
        return ''
    if isinstance(v, str):
        return v
    try:
        return ','.join(str(x) for x in v)
    except Exception:
        return ''


def decode_list(v) -> List[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [s for s in str(v).split(',') if s]


# --- Index Builder from .sql dump ---

ALIASES = {
    'name': ['name', 'card_name', 'printed_name'],
    'set': ['set', 'set_code', 'expansion_code', 'code'],
    'number': ['collector_number', 'number', 'collectornumber'],
    'colors': ['colors', 'color_identity', 'printed_colors', 'mana_colors'],
    'types': ['types', 'type_line', 'type', 'type_line_text'],
    'cmc': ['cmc', 'mana_value', 'converted_mana_cost'],
    'power': ['power'],
    'toughness': ['toughness'],
    'text': ['oracle_text', 'text', 'rules_text', 'printed_text']
}


def _find_col(cols: List[str], names: List[str]) -> Optional[int]:
    lc = [c.strip().strip('`"').lower() for c in cols]
    for alias in names:
        if alias in lc:
            return lc.index(alias)
    return None


def _extract_item(cols: List[str], values: List[Any]) -> Dict[str, Any]:
    def get(names: List[str]):
        idx = _find_col(cols, names)
        return values[idx] if idx is not None and idx < len(values) else None

    name = get(ALIASES['name']) or ''
    set_code = get(ALIASES['set']) or ''
    number = get(ALIASES['number']) or ''
    colors = get(ALIASES['colors'])
    types = get(ALIASES['types'])
    cmc = get(ALIASES['cmc'])
    power = get(ALIASES['power'])
    toughness = get(ALIASES['toughness'])
    text = get(ALIASES['text']) or ''

    def to_list(v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        s = str(v)
        # split on non-alnum separators
        parts = [p for p in [t.strip() for t in s.replace('|', ',').replace(';', ',').replace('/', ',').split(',')] if p]
        return parts

    item = {
        'name': name or '',
        'set': set_code or '',
        'number': str(number) if number is not None else '',
        'colors': to_list(colors),
        'types': to_list(types),
        'cmc': _to_float_safe(cmc),
        'power': '' if power is None else str(power),
        'toughness': '' if toughness is None else str(toughness),
        'text': text or ''
    }
    return item


def _to_float_safe(v):
    try:
        return float(v)
    except Exception:
        return None


def build_index_from_sql(
    sql_path: Path,
    db_path: Path,
    table_name_hint: str = 'card',
    max_rows: Optional[int] = None,
    progress_cb: Optional[callable] = None,
    cancel_cb: Optional[callable] = None,
) -> int:
    """
    Stream the AllPrintings.sql file and insert parsed rows into SQLite index.
    We detect INSERT INTO statements whose table name contains the hint (e.g., 'card').
    Returns number of rows inserted.
    """
    sql_path = Path(sql_path)
    conn = open_db(db_path)
    inserted = 0
    if not sql_path.exists():
        return inserted

    current_cols: List[str] = []
    buffering = False
    buffer_lines: List[str] = []
    target_table = None

    def flush_values(values_section: str):
        nonlocal inserted
        rows = split_values_rows(values_section)
        items: List[Dict[str, Any]] = []
        for row in rows:
            if cancel_cb and cancel_cb():
                break
            values = parse_sql_values_tuple(row)
            items.append(_extract_item(current_cols, values))
            if max_rows and (inserted + len(items)) >= max_rows:
                break
        insert_cards(conn, items)
        inserted += len(items)
        if progress_cb:
            try:
                progress_cb(inserted)
            except Exception:
                pass

    with sql_path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            s = line.strip()
            if not buffering:
                if s.lower().startswith('insert into'):
                    # Parse header: INSERT INTO table (col1,col2,...) VALUES
                    low = s.lower()
                    # find table name
                    try:
                        after_into = low.split('insert into', 1)[1].strip()
                        tbl_and_cols = after_into.split('values', 1)[0].strip()
                        # table name up to first '('
                        tname = tbl_and_cols.split('(' ,1)[0].strip().strip('`"')
                        if table_name_hint in tname:
                            target_table = tname
                            # columns inside parentheses
                            cols_part = tbl_and_cols.split('(', 1)[1].rsplit(')', 1)[0]
                            cols = [c.strip() for c in cols_part.split(',')]
                            current_cols = cols
                            buffering = True
                            buffer_lines = []
                            # if there's content after VALUES on same line, keep it
                            if 'values' in low:
                                after_values = s.lower().split('values', 1)[1]
                                remainder = s[len(s) - len(after_values):]
                                buffer_lines.append(remainder)
                    except Exception:
                        pass
            else:
                buffer_lines.append(s)
                if s.endswith(';'):
                    values_section = ' '.join(buffer_lines)[:-1]  # drop semicolon
                    try:
                        flush_values(values_section)
                    except Exception:
                        pass
                    buffering = False
                    buffer_lines = []
                    if max_rows and inserted >= max_rows:
                        break

    return inserted
