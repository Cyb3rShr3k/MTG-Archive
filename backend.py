# backend.py
from pathlib import Path
from core import db, image_utils, card_index
from core import collection_sql as csql
import json
import urllib.parse
import urllib.request
import urllib.error
import threading
import time
import os
import httpx

class Api:
    def __init__(self):
        # Store as plain strings and keep them private so pywebview doesn't introspect internals
        self._db_path = 'cards_db.json'
        self._image_dir = 'assets/Card Images'
        self._allprintings_sql = 'assets/AllPrintings.sql'
        # External images directory requested by user
        self._external_images_dir = 'G:/PyWeb/Images'
        # Structured collection database (SQLite)
        self._collection_db_path = 'collection.db'
        # Deck persistence (simple JSON)
        self._decks_db_path = 'decks_db.json'
        # External decklist database (from convert.py)
        self._decklist_db_path = 'decklist_cards.db'
        # Local index built from AllPrintings.sql for fast, structured lookups
        self._index_db_path = 'assets/allprintings_index.sqlite'
        # Preconstructed decks directory
        self._precon_dir = 'assets/AllDeckFiles'
        # Build state
        self._build_lock = threading.Lock()
        self._build_thread = None
        self._build_cancel = False
        self._build_inserted = 0
        self._build_running = False
        # App state file
        self._app_state_path = 'app_state.json'
        # Repair (Scryfall enrichment) progress state
        self._repair_lock = threading.Lock()
        self._repair_running = False
        self._repair_total = 0
        self._repair_updated = 0
        self._repair_errors = 0
        self._repair_errors_list: list[str] = []
        # CSV Import progress state
        self._import_lock = threading.Lock()
        self._import_running = False
        self._import_current = 0
        self._import_total = 0
        # PreCon deck import progress state
        self._precon_lock = threading.Lock()
        self._precon_running = False
        self._precon_current = 0
        self._precon_total = 0
        
        # Scanner GUI window reference
        self._scanner_window = None
        
        # Multi-user support: current user ID (set by main.py from session)
        self._current_user_id = 1  # Default to user 1 for backward compatibility
        

    def get_card_names(self):
        return db.load_cards_db(Path(self._db_path))

    def add_card(self, name):
        cards = db.load_cards_db(Path(self._db_path))
        if name not in cards:
            cards.append(name)
            db.save_cards_db(Path(self._db_path), cards)
            return True
        return False

    def import_images(self, paths):
        return [str(p) for p in image_utils.import_images_to_folder(paths, Path(self._image_dir))]

    def run_ocr(self, filename):
        return image_utils.try_ocr(Path(self._image_dir) / filename)

    def search_cards(self, query: str, limit: int = 25):
        """Search the AllPrintings.sql dump for lines containing the query.
        Returns a list of text snippets useful for suggestions.
        """
        return db.search_allprintings(Path(self._allprintings_sql), query, limit=limit)

    # --- Scryfall integrations ---
    def _http_get_json(self, url: str):
        req = urllib.request.Request(url, headers={
            'User-Agent': 'PyWeb-Client/1.0 (+https://scryfall.com/docs/api)'
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = resp.read()
                return json.loads(data.decode('utf-8', errors='ignore'))
        except urllib.error.HTTPError as e:
            # Scryfall returns 404 JSON when no results. Treat as empty.
            if e.code == 404:
                try:
                    body = e.read().decode('utf-8', errors='ignore')
                    obj = json.loads(body)
                    return obj if isinstance(obj, dict) else { 'data': [] }
                except Exception:
                    return { 'data': [] }
            raise

    def _map_scryfall_card(self, c: dict) -> dict:
        # Prefer normal image_uris; fallback to first face
        img = ''
        if isinstance(c.get('image_uris'), dict):
            img = c['image_uris'].get('normal') or c['image_uris'].get('large') or ''
        elif isinstance(c.get('card_faces'), list) and c['card_faces']:
            face0 = c['card_faces'][0]
            if isinstance(face0.get('image_uris'), dict):
                img = face0['image_uris'].get('normal') or face0['image_uris'].get('large') or ''
        
        # Extract back face data for double-faced cards
        back_data = {}
        if isinstance(c.get('card_faces'), list) and len(c['card_faces']) > 1:
            face1 = c['card_faces'][1]
            back_img = ''
            if isinstance(face1.get('image_uris'), dict):
                back_img = face1['image_uris'].get('normal') or face1['image_uris'].get('large') or ''
            
            back_data = {
                'back_name': face1.get('name', ''),
                'back_mana_cost': face1.get('mana_cost', ''),
                'back_colors': face1.get('colors') or [],
                'back_types': (face1.get('type_line', '') or '').split(' — ')[0].split(' '),
                'back_oracle_text': face1.get('oracle_text', ''),
                'back_power': face1.get('power'),
                'back_toughness': face1.get('toughness'),
                'back_image_url': back_img,
            }
        
        return db.normalize_item({
            'name': c.get('name', ''),
            'set': c.get('set', ''),
            'number': c.get('collector_number', ''),
            'colors': c.get('colors') or c.get('color_identity') or [],
            'types': (c.get('type_line', '') or '').split(' — ')[0].split(' '),
            'cmc': c.get('cmc'),
            'power': c.get('power'),
            'toughness': c.get('toughness'),
            'text': c.get('oracle_text', ''),
            'image_path': '',
            'image_url': img,
            'source': 'scryfall',
            **back_data
        })

    def search_scryfall(self, query: str, limit: int = 50):
        q = (query or '').strip()
        if not q:
            return []
        # unique=prints to get per-printing rows; cap with page size
        try:
            enc = urllib.parse.quote(q, safe='')
            url = f"https://api.scryfall.com/cards/search?q={enc}&unique=prints&order=released&dir=desc"
            data = self._http_get_json(url)
            items = []
            if isinstance(data, dict) and isinstance(data.get('data'), list):
                for c in data['data']:
                    items.append(self._map_scryfall_card(c))
                    if len(items) >= limit:
                        break
            return items
        except Exception:
            return []

    

    # --- App state management ---
    def save_app_state(self, state: dict):
        try:
            p = Path(self._app_state_path)
            with p.open('w', encoding='utf-8') as f:
                json.dump(state or {}, f, ensure_ascii=False, indent=2)
            return { 'ok': True }
        except Exception as e:
            return { 'ok': False, 'error': str(e) }

    def load_app_state(self):
        try:
            p = Path(self._app_state_path)
            if not p.exists():
                return { 'ok': True, 'state': {} }
            obj = json.loads(p.read_text(encoding='utf-8'))
            return { 'ok': True, 'state': obj if isinstance(obj, dict) else {} }
        except Exception as e:
            return { 'ok': False, 'state': {}, 'error': str(e) }

    def close_app(self):
        """No-op for web version - browser handles closing."""
        return { 'ok': True }

    def get_decklist_deck_cards(self, deck_id: str):
        """Return cards for a given deck_id from decklist_cards.db as a list of {name, set_code, collector_number, quantity, type_line}."""
        import sqlite3
        p = Path(self._decklist_db_path)
        if not p.exists():
            return []
        try:
            conn = sqlite3.connect(str(p))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT name, set_code, collector_number, type_line, COALESCE(quantity,1) AS quantity FROM cards WHERE deck_id=?", (deck_id,))
            rows = cur.fetchall()
            conn.close()
            out = []
            for r in rows:
                out.append({
                    'name': str(r['name'] or ''),
                    'set_code': str(r['set_code'] or ''),
                    'collector_number': str(r['collector_number'] or ''),
                    'type_line': str(r['type_line'] or ''),
                    'quantity': int(r['quantity'] or 0),
                })
            return out
        except Exception:
            return []

    def pick_precon_json(self):
        """For web version, file selection handled by HTML input."""
        # This method is not used in web version - files uploaded via HTML form
        return ''

    def pick_csv_file(self):
        """For web version, file selection handled by HTML input."""
        # This method is not used in web version - files uploaded via HTML form
        return ''

    def launch_scanner_gui(self):
        """Launch the MTG scanner GUI as a separate window in the same application."""
        try:
            # Import the scanner GUI class
            from mtg_scanner_gui import MTGScannerApp
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QTimer
            
            # Get or create QApplication instance
            app = QApplication.instance()
            if app is None:
                return {'ok': False, 'error': 'Qt application not available'}
            
            # Check if scanner window already exists and is hidden
            if hasattr(self, '_scanner_window') and self._scanner_window is not None:
                # Just show the existing window
                self._scanner_window.show()
                self._scanner_window.raise_()
                self._scanner_window.activateWindow()
                return {'ok': True, 'method': 'reused'}
            
            # Create scanner window using a timer to avoid blocking
            def create_scanner():
                try:
                    self._scanner_window = MTGScannerApp()
                    self._scanner_window.show()
                    self._scanner_window.raise_()
                    self._scanner_window.activateWindow()
                except Exception as e:
                    print(f"Error creating scanner: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Use QTimer to create window on next event loop iteration
            QTimer.singleShot(0, create_scanner)
            
            return {'ok': True, 'method': 'integrated'}
        except ImportError as e:
            return {'ok': False, 'error': f'Failed to import scanner: {str(e)}'}
        except Exception as e:
            import traceback
            return {'ok': False, 'error': str(e), 'traceback': traceback.format_exc()}

    # --- Preconstructed deck import ---
    def list_precon_decks(self, query: str | None = None):
        """List available preconstructed decks from the decklist_cards.db database.
        - Searches for Commander decks in the database
        - If query provided, performs case-insensitive multi-word fuzzy match against deck name
        Returns a list of { name, deck_id, deck_type, card_count, image_uri }.
        """
        # Use the existing search_decklist_db function
        decks = self.search_decklist_db(query)
        
        # Filter to only Commander decks and format for frontend
        out = []
        for deck in decks:
            # Only show Commander decks in precon list (deck_type is "Commander Deck")
            deck_type = deck.get('deck_type', '').lower()
            if 'commander' in deck_type:
                out.append({
                    'name': deck['deck_name'],
                    'deck_id': deck['deck_id'],
                    'deck_type': deck['deck_type'],
                    'card_count': deck['card_count'],
                    'filename': deck['deck_name'],  # For compatibility with frontend
                    'path': f"deck_id:{deck['deck_id']}",  # Virtual path
                    'image_uri': '',  # Could be enhanced to fetch commander card image
                    'size_bytes': 0
                })
        return out

    # --- Decklist.db integrations ---
    def search_decklist_db(self, query: str | None = None):
        """Search decks in decklist_cards.db by fuzzy name contains across words.
        Returns a list of { deck_id, deck_name, deck_type, card_count }.
        """
        import sqlite3
        q = (query or '').strip().lower()
        words = [w for w in q.split() if w]
        p = Path(self._decklist_db_path)
        if not p.exists():
            return []
        try:
            conn = sqlite3.connect(str(p))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT deck_id, deck_name, deck_type FROM decks")
            decks = cur.fetchall()
            out = []
            for d in decks:
                name = str(d['deck_name'] or '')
                target = (name + ' ' + str(d['deck_type'] or '')).lower()
                if words and not all(w in target for w in words):
                    continue
                try:
                    row = conn.execute("SELECT SUM(COALESCE(quantity,1)) FROM cards WHERE deck_id=?", (d['deck_id'],)).fetchone()
                    cnt = int(row[0] or 0)
                except Exception:
                    cnt = 0
                out.append({
                    'deck_id': d['deck_id'],
                    'deck_name': name,
                    'deck_type': d['deck_type'] or '',
                    'card_count': cnt,
                })
            conn.close()
            out.sort(key=lambda x: x['deck_name'])
            return out
        except Exception:
            return []

    def import_deck_from_db(self, deck_id: str):
        """Import a deck from decklist.db by deck_id into collection.db and create a deck with the same name.
        Fetches card data from Scryfall using scryfall_id for accurate metadata.
        Returns { added, total, errors, deck_name }.
        """
        import sqlite3, time
        p = Path(self._decklist_db_path)
        if not p.exists():
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'decklist.db not found'] }
        deck_name = ''
        try:
            conn = sqlite3.connect(str(p))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Get deck name
            try:
                cur.execute("SELECT deck_name, deck_type FROM decks WHERE deck_id=?", (deck_id,))
                rname = cur.fetchone()
                if rname:
                    deck_name = str(rname[0] or '')
                    deck_type = str(rname[1] or '')
            except Exception:
                deck_name = ''
                deck_type = ''
            # Get card rows with scryfall_id and quantity
            cur.execute("SELECT scryfall_id, name, COALESCE(quantity,1) AS quantity FROM cards WHERE deck_id=?", (deck_id,))
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'Failed to read deck: {e}'] }
        if not rows:
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': ['No cards found for deck'] }
        
        # Initialize progress tracking
        with self._precon_lock:
            self._precon_running = True
            self._precon_current = 0
            self._precon_total = len(rows)
        
        items = []
        counts_by_name: dict[str, int] = {}
        color_set: set[str] = set()
        errors: list[str] = []
        
        try:
            for r in rows:
                with self._precon_lock:
                    self._precon_current += 1
                
                scryfall_id = str(r['scryfall_id'] or '').strip()
                fallback_name = str(r['name'] or '').strip()
                qty = 0
                try:
                    qty = int(r['quantity'] or 0)
                except Exception:
                    qty = 0
                qty = max(1, qty)
                
                enriched = None
                # Fetch from Scryfall using scryfall_id
                if scryfall_id:
                    try:
                        url = f"https://api.scryfall.com/cards/{urllib.parse.quote(scryfall_id)}"
                        data = self._http_get_json(url)
                        if isinstance(data, dict) and data.get('object') == 'card':
                            enriched = self._map_scryfall_card(data)
                        time.sleep(0.12)
                    except Exception as e:
                        errors.append(f"{fallback_name} ({scryfall_id}): {e}")
                        enriched = None
                
                # Fallback to basic card info if Scryfall fetch failed
                if enriched is None:
                    enriched = db.normalize_item({ 'name': fallback_name, 'scryfall_id': scryfall_id })
                
                enriched['source'] = f'decklist:{deck_name or "unknown"}'
                
                # Track colors for deck
                try:
                    for c in (enriched.get('colors') or []):
                        if c in ('W','U','B','R','G','C'):
                            color_set.add(c)
                except Exception:
                    pass
                
                # Push repeated by quantity for collection inserts
                for _ in range(qty):
                    items.append(enriched)
                
                # Count by normalized enriched name to match collection rows
                ename = str(enriched.get('name') or fallback_name or '').strip()
                ename = ename.replace('\r','\n').split('\n')[0].strip().strip('"').strip()
                if ename:
                    counts_by_name[ename] = counts_by_name.get(ename, 0) + qty
            
            inserted = csql.insert_items(Path(self._collection_db_path), items)
        except Exception as e:
            with self._precon_lock:
                self._precon_running = False
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'Insert failed: {e}'] }
        
        self._sync_card_names_from_collection()
        
        # Create or update a deck with the same name and place cards
        try:
            if deck_name:
                deck_items = [{ 'name': n, 'count': c } for n, c in counts_by_name.items() if n]
                colors_sorted = [c for c in ['W','U','B','R','G','C'] if c in color_set]
                csql.save_deck(Path(self._collection_db_path), deck_name, deck_items, deck_type=deck_type or None, deck_colors=colors_sorted)
        except Exception:
            # Do not fail import if deck save fails
            pass
        
        total = self.get_collection_count()
        
        # Clear progress tracking
        with self._precon_lock:
            self._precon_running = False
        
        return { 'added': int(inserted), 'total': total, 'errors': errors, 'deck_name': deck_name }

    def import_deck_from_db_with_commander(self, deck_id: str, commander: str = ''):
        """Import a deck from decklist.db with commander selection into collection.db.
        This is identical to import_deck_from_db but saves the commander field.
        """
        import sqlite3, time
        print(f"\n=== IMPORT DEBUG: import_deck_from_db_with_commander called ===")
        print(f"deck_id: {deck_id}")
        print(f"commander: {commander}")
        p = Path(self._decklist_db_path)
        if not p.exists():
            print(f"ERROR: decklist.db not found at {p}")
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'decklist.db not found'] }
        deck_name = ''
        try:
            conn = sqlite3.connect(str(p))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Get deck name
            try:
                cur.execute("SELECT deck_name, deck_type FROM decks WHERE deck_id=?", (deck_id,))
                rname = cur.fetchone()
                if rname:
                    deck_name = str(rname[0] or '')
                    deck_type = str(rname[1] or '')
            except Exception:
                deck_name = ''
                deck_type = ''
            # Get card rows with scryfall_id and quantity
            cur.execute("SELECT scryfall_id, name, COALESCE(quantity,1) AS quantity FROM cards WHERE deck_id=?", (deck_id,))
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'Failed to read deck: {e}'] }
        if not rows:
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': ['No cards found for deck'] }
        
        # Initialize progress tracking
        with self._precon_lock:
            self._precon_running = True
            self._precon_current = 0
            self._precon_total = len(rows)
        
        items = []
        counts_by_name: dict[str, int] = {}
        color_set: set[str] = set()
        errors: list[str] = []
        
        try:
            for r in rows:
                with self._precon_lock:
                    self._precon_current += 1
                
                scryfall_id = str(r['scryfall_id'] or '').strip()
                fallback_name = str(r['name'] or '').strip()
                qty = 0
                try:
                    qty = int(r['quantity'] or 0)
                except Exception:
                    qty = 0
                qty = max(1, qty)
                
                enriched = None
                # Fetch from Scryfall using scryfall_id
                if scryfall_id:
                    try:
                        url = f"https://api.scryfall.com/cards/{urllib.parse.quote(scryfall_id)}"
                        data = self._http_get_json(url)
                        if isinstance(data, dict) and data.get('object') == 'card':
                            enriched = self._map_scryfall_card(data)
                        time.sleep(0.12)
                    except Exception as e:
                        errors.append(f"{fallback_name} ({scryfall_id}): {e}")
                        enriched = None
                
                # Fallback to basic card info if Scryfall fetch failed
                if enriched is None:
                    enriched = db.normalize_item({ 'name': fallback_name, 'scryfall_id': scryfall_id })
                
                enriched['source'] = f'decklist:{deck_name or "unknown"}'
                
                # Track colors for deck
                try:
                    for c in (enriched.get('colors') or []):
                        if c in ('W','U','B','R','G','C'):
                            color_set.add(c)
                except Exception:
                    pass
                
                # Push repeated by quantity for collection inserts
                for _ in range(qty):
                    items.append(enriched)
                
                # Count by normalized enriched name to match collection rows
                ename = str(enriched.get('name') or fallback_name or '').strip()
                ename = ename.replace('\r','\n').split('\n')[0].strip().strip('"').strip()
                if ename:
                    counts_by_name[ename] = counts_by_name.get(ename, 0) + qty
            
            inserted = csql.insert_items(Path(self._collection_db_path), items)
        except Exception as e:
            with self._precon_lock:
                self._precon_running = False
            return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'Insert failed: {e}'] }
        
        self._sync_card_names_from_collection()
        
        # Create or update a deck with the same name and place cards, including commander
        try:
            if deck_name:
                deck_items = [{ 'name': n, 'count': c } for n, c in counts_by_name.items() if n]
                
                # Apply commander deck rules if importing to commander deck
                is_commander = str(deck_type or '').lower() in ['commander', 'edh']
                if is_commander:
                    # For commander decks, limit non-basic lands to 1 copy
                    corrected_items = []
                    basic_lands = {
                        'plains', 'island', 'swamp', 'mountain', 'forest', 'wastes',
                        'snow-covered plains', 'snow-covered island', 'snow-covered swamp', 
                        'snow-covered mountain', 'snow-covered forest'
                    }
                    
                    for item in deck_items:
                        name = str(item.get('name', '')).strip()
                        count = int(item.get('count', 0))
                        
                        if name.lower() in basic_lands:
                            # Basic lands: keep original count
                            corrected_items.append(item)
                        else:
                            # Non-basic cards: limit to 1 copy
                            corrected_items.append({ 'name': name, 'count': 1 })
                    
                    deck_items = corrected_items
                
                colors_sorted = [c for c in ['W','U','B','R','G','C'] if c in color_set]
                # Pass commander to save_deck function
                csql.save_deck(Path(self._collection_db_path), deck_name, deck_items, deck_type=deck_type or None, deck_colors=colors_sorted, commander=commander or '')
        except Exception as e:
            # Log deck save errors for troubleshooting
            print(f"Warning: Failed to save deck metadata: {e}")
        
        total = self.get_collection_count()
        
        # Clear progress tracking
        with self._precon_lock:
            self._precon_running = False
        
        result = { 'added': int(inserted), 'total': total, 'errors': errors, 'deck_name': deck_name }
        print(f"=== IMPORT RESULT: {result} ===\n")
        return result

    def update_deck_commander(self, deck_name: str, commander: str):
        """Update the commander for an existing deck"""
        try:
            from pathlib import Path
            from core import collection_sql as csql
            import sqlite3
            
            db_path = Path(self._collection_db_path)
            csql.ensure_db(db_path)
            
            with sqlite3.connect(str(db_path)) as conn:
                # Check if deck exists
                cur = conn.cursor()
                cur.execute("SELECT id FROM decks WHERE name = ?", (deck_name,))
                result = cur.fetchone()
                
                if not result:
                    return {"ok": False, "error": "Deck not found"}
                
                # Update commander
                conn.execute("UPDATE decks SET commander = ? WHERE name = ?", (commander or '', deck_name))
                conn.commit()
                
                return {"ok": True, "message": f"Updated commander for '{deck_name}' to '{commander or 'none'}'"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def import_precon_deck(self, filename: str):
        """Import a preconstructed deck by filename or absolute path.
        Prefer local index enrichment; fallback to Scryfall by name with light throttling.
        Supports lines like: "3 Sol Ring", "Sol Ring x3", "3x Sol Ring".
        """
        import re, time
        root = Path(self._precon_dir)
        # Support absolute path or just filename under precon dir
        cand = Path(str(filename))
        p = cand if cand.is_absolute() else (root / str(filename))
        if not p.exists() or not p.is_file():
            # Try resolving relative to precon dir even if absolute check failed
            alt = root / Path(str(filename)).name
            if alt.exists() and alt.is_file():
                p = alt
            else:
                return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'File not found: {filename}'] }

        def parse_line(line: str):
            s = (line or '').strip()
            if not s:
                return None
            # Patterns: "3 Card Name", "Card Name x3", "3x Card Name"
            m = re.match(r"^(\d+)\s+(.+)$", s)
            if m:
                return int(m.group(1)), m.group(2).strip()
            m = re.match(r"^(.+?)\s*[xX]\s*(\d+)$", s)
            if m:
                return int(m.group(2)), m.group(1).strip()
            m = re.match(r"^(\d+)[xX]\s+(.+)$", s)
            if m:
                return int(m.group(1)), m.group(2).strip()
            # Fallback count=1
            return 1, s

        # Prepare local index
        self.ensure_index()
        try:
            idx_conn = card_index.open_db(Path(self._index_db_path))
        except Exception:
            idx_conn = None

        added = 0
        errors: list[str] = []
        try:
            lines = p.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            try:
                lines = p.read_text(encoding='latin-1', errors='ignore').splitlines()
            except Exception:
                return { 'added': 0, 'total': self.get_collection_count(), 'errors': [f'Failed to read: {filename}'] }

        for raw in lines:
            parsed = parse_line(raw)
            if not parsed:
                continue
            count, name = parsed
            name = (name or '').strip()
            if not name:
                continue
            enriched = None
            # 1) Local index by name
            try:
                if idx_conn:
                    rows_idx = card_index.lookup_by_name(idx_conn, name, limit=1)
                    if rows_idx:
                        enriched = rows_idx[0]
            except Exception:
                enriched = None
            # 2) Scryfall by name
            if enriched is None:
                try:
                    res = self.search_scryfall(name, limit=1) or []
                    if res:
                        enriched = res[0]
                    time.sleep(0.12)
                except Exception:
                    enriched = None
            # 3) Minimal fallback
            if enriched is None:
                enriched = db.normalize_item({'name': name, 'set': '', 'number': ''})
            # Tag with precon filename and sanitize record
            base_tag = Path(filename).name
            enriched['source'] = f'precon:{base_tag}'
            enriched = self._sanitize_import_item(enriched, source_tag=f'precon:{base_tag}')
            # Insert count copies
            recs = [enriched for _ in range(max(1, int(count)))]
            try:
                inserted = csql.insert_items(Path(self._collection_db_path), recs)
                added += int(inserted)
            except Exception as e:
                errors.append(f"Failed to insert {name}: {e}")
        if idx_conn:
            try:
                idx_conn.close()
            except Exception:
                pass
        self._sync_card_names_from_collection()
        total = self.get_collection_count()
        return { 'added': added, 'total': total, 'errors': errors }

    def _sanitize_import_item(self, item: dict, source_tag: str | None = None) -> dict:
        """Return a cleaned, normalized card item safe for collection insertion.
        - Clean name: strip quotes/newlines/whitespace, limit length.
        - Validate colors to W/U/B/R/G/C.
        - Ensure types is a list of strings.
        - Coerce power/toughness to str or None.
        - Ensure text and image fields are strings.
        - Optionally override source tag.
        """
        it = dict(item or {})
        # name cleanup
        nm = str(it.get('name') or '').replace('\r','\n').split('\n')[0].strip().strip('"').strip()
        if len(nm) > 120:
            nm = nm[:120]
        it['name'] = nm
        # identifiers
        it['set'] = str(it.get('set') or '')
        it['number'] = str(it.get('number') or '')
        # colors
        cols = it.get('colors') or []
        try:
            cols = [c for c in cols if c in ('W','U','B','R','G','C')]
        except Exception:
            cols = []
        it['colors'] = cols
        # types
        tys = it.get('types') or []
        if not isinstance(tys, list):
            tys = []
        tys = [str(t) for t in tys if str(t).strip()]
        it['types'] = tys
        # numbers
        it['cmc'] = it.get('cmc') if isinstance(it.get('cmc'), (int, float)) else None
        it['power'] = None if it.get('power') is None else str(it.get('power'))
        it['toughness'] = None if it.get('toughness') is None else str(it.get('toughness'))
        # text/images
        it['text'] = str(it.get('text') or '')
        it['image_path'] = it.get('image_path') or ''
        it['image_url'] = it.get('image_url') or ''
        # source
        if source_tag:
            it['source'] = source_tag
        else:
            it['source'] = it.get('source') or 'import'
        return it

    def run_importscryfall(self, csv_path: str):
        """Import cards by Scryfall ID from a CSV file into collection.db.
        The CSV is expected to have Scryfall card IDs in the first column per row.
        This mirrors the intent of importscryfall.py but runs in-process and writes
        normalized records into the 'collection' table.
        Returns { ok, added, total, errors }.
        """
        print(f"[DEBUG] run_importscryfall called with path: {csv_path}")
        import csv, time
        p = Path(str(csv_path or '')).resolve()
        print(f"[DEBUG] Resolved path: {p}, exists: {p.exists()}")
        if not p.exists() or not p.is_file():
            return { 'ok': False, 'added': 0, 'total': self.get_collection_count(), 'errors': [f'CSV not found: {csv_path}'] }
        added = 0
        errors: list[str] = []
        items_batch: list[dict] = []
        
        # Count total rows first
        with self._import_lock:
            self._import_running = True
            self._import_current = 0
            self._import_total = 0
        
        try:
            # First pass: count rows
            with p.open('r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and str(row[0] or '').strip():
                        with self._import_lock:
                            self._import_total += 1
            
            print(f"[DEBUG] Total rows to process: {self._import_total}")
            
            # Second pass: process rows
            with p.open('r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    scry_id = str(row[0] or '').strip()
                    if not scry_id:
                        continue
                    
                    with self._import_lock:
                        self._import_current += 1
                    
                    print(f"[DEBUG] Processing row {self._import_current}/{self._import_total}: {scry_id}")
                    
                    try:
                        url = f"https://api.scryfall.com/cards/{urllib.parse.quote(scry_id)}"
                        data = self._http_get_json(url)
                        if isinstance(data, dict) and data.get('object') == 'card':
                            it = self._map_scryfall_card(data)
                            it['source'] = 'csv-import'
                            items_batch.append(it)
                            print(f"[DEBUG] Added card to batch: {it.get('name', 'Unknown')}")
                        else:
                            print(f"[DEBUG] Invalid card data for {scry_id}")
                        # polite throttle
                        time.sleep(0.12)
                    except Exception as e:
                        print(f"[DEBUG] Error processing {scry_id}: {e}")
                        errors.append(f"{scry_id}: {e}")
            
            if items_batch:
                print(f"[DEBUG] Attempting to insert {len(items_batch)} items into collection.db")
                added = csql.insert_items(Path(self._collection_db_path), items_batch)
                print(f"[DEBUG] insert_items returned: {added}")
                self._sync_card_names_from_collection()
            total = self.get_collection_count()
            print(f"[DEBUG] Import complete - added: {added}, total in collection: {total}")
            return { 'ok': True, 'added': int(added), 'total': total, 'errors': errors }
        except Exception as e:
            print(f"[DEBUG] Import exception: {e}")
            import traceback
            traceback.print_exc()
            return { 'ok': False, 'added': 0, 'total': self.get_collection_count(), 'errors': [str(e)] }
        finally:
            with self._import_lock:
                self._import_running = False

    def run_importscryfall_bytes(self, data_base64_or_text: str):
        """Accept CSV content (UTF-8 text or base64-encoded), write to a temp file, and import.
        Returns { ok, added, total, errors }.
        """
        import base64, tempfile
        s = data_base64_or_text or ''
        if not isinstance(s, str) or not s:
            return { 'ok': False, 'added': 0, 'total': self.get_collection_count(), 'errors': ['no content'] }
        # Try base64 decode; fall back to raw text
        raw: bytes
        try:
            raw = base64.b64decode(s, validate=True)
        except Exception:
            raw = s.encode('utf-8', errors='ignore')
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tf:
                tf.write(raw)
                tf.flush()
                temp_path = tf.name
        except Exception as e:
            return { 'ok': False, 'added': 0, 'total': self.get_collection_count(), 'errors': [f'write temp failed: {e}'] }
        try:
            return self.run_importscryfall(temp_path)
        finally:
            try:
                import os
                os.remove(temp_path)
            except Exception:
                pass

    def autocomplete_scryfall(self, query: str, limit: int = 20):
        """Return Scryfall autocomplete suggestions for a partial card name."""
        q = (query or '').strip()
        if not q:
            return []
        try:
            enc = urllib.parse.quote(q, safe='')
            url = f"https://api.scryfall.com/cards/autocomplete?q={enc}"
            data = self._http_get_json(url)
            if isinstance(data, dict) and isinstance(data.get('data'), list):
                arr = [str(x) for x in data['data']]
                return arr[:limit]
        except Exception:
            pass
        return []

    def ocr_and_search_images(self, files: list[dict], limit_per_image: int = 10):
        """Accepts a list of {name: str, data_base64: str}. Saves to temp, runs OCR, queries Scryfall
        with extracted name fragments, returns combined results with per-image grouping.
        """
        import base64, tempfile
        out: list[dict] = []
        if not files:
            return out
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for f in files:
                try:
                    name = str(f.get('name') or 'image')
                    b64 = f.get('data_base64') or ''
                    if not b64:
                        continue
                    raw = base64.b64decode(b64)
                    p = tdir / name
                    p.write_bytes(raw)
                    text = image_utils.try_ocr(p) or ''
                    # Extract a candidate query: first reasonable line or longest word group
                    cand = ''
                    for line in str(text).splitlines():
                        s = line.strip()
                        if len(s) >= 3:
                            cand = s
                            break
                    if not cand:
                        cand = p.stem.replace('_', ' ').replace('-', ' ')
                    # Query Scryfall
                    items = self.search_scryfall(cand, limit=limit_per_image)
                    out.append({
                        'image': name,
                        'ocr_text': text,
                        'query': cand,
                        'results': items,
                    })
                except Exception:
                    continue
        return out

    # --- Structured index functions ---
    def ensure_index(self, max_rows: int | None = None):
        """Build the local SQLite index from AllPrintings.sql if it does not exist or is empty."""
        need_build = not Path(self._index_db_path).exists()
        if not need_build:
            try:
                conn = card_index.open_db(Path(self._index_db_path))
                cur = conn.execute('SELECT COUNT(1) FROM cards')
                cnt = cur.fetchone()[0]
                conn.close()
                need_build = (cnt == 0)
            except Exception:
                need_build = True
        if need_build:
            card_index.build_index_from_sql(self._allprintings_sql, self._index_db_path, table_name_hint='card')

    def build_index(self, max_rows: int | None = None):
        """Force rebuild or build the index synchronously and return rows inserted."""
        self._build_inserted = 0
        def on_progress(n):
            self._build_inserted = int(n or 0)
        inserted = card_index.build_index_from_sql(
            self._allprintings_sql,
            self._index_db_path,
            table_name_hint='card',
            max_rows=max_rows,
            progress_cb=on_progress,
            cancel_cb=lambda: self._build_cancel
        )
        return { 'inserted': inserted }

    # --- Async build controls for UI progress/cancel ---
    def start_build_index(self, max_rows: int | None = None):
        """Start index build in background thread and return immediately."""
        with self._build_lock:
            if self._build_running:
                return { 'started': False, 'reason': 'already_running' }
            self._build_cancel = False
            self._build_inserted = 0
            self._build_running = True
            def run():
                try:
                    def on_progress(n):
                        self._build_inserted = int(n or 0)
                    card_index.build_index_from_sql(
                        self._allprintings_sql,
                        self._index_db_path,
                        table_name_hint='card',
                        max_rows=max_rows,
                        progress_cb=on_progress,
                        cancel_cb=lambda: self._build_cancel
                    )
                finally:
                    self._build_running = False
            t = threading.Thread(target=run, daemon=True)
            self._build_thread = t
            t.start()
            return { 'started': True }

    def get_build_progress(self):
        with self._build_lock:
            return {
                'running': self._build_running,
                'inserted': self._build_inserted,
                'cancel': self._build_cancel
            }

    def cancel_build(self):
        with self._build_lock:
            self._build_cancel = True
            return { 'cancelling': True }

    def search_structured(self, name: str, limit: int = 20):
        self.ensure_index()
        conn = card_index.open_db(Path(self._index_db_path))
        items = card_index.lookup_by_name(conn, name, limit=limit)
        conn.close()
        return items

    def list_images(self):
        """List images in the external images folder as file URIs for display in the UI."""
        exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
        images_root = Path(self._external_images_dir)
        if not images_root.exists():
            return []
        items = []
        for p in sorted(images_root.iterdir()):
            if p.is_file() and p.suffix.lower() in exts:
                # Build a file URI for use in <img src>
                try:
                    uri = p.as_uri()
                except Exception:
                    path_str = str(p).replace('\\', '/')
                    uri = 'file:///' + path_str
                items.append({
                    'name': p.name,
                    'path': str(p),
                    'uri': uri,
                    'size': p.stat().st_size
                })
        return items

    def suggest_deck(self, prompt: str):
        """Stubbed deck suggestion based on simple keyword matching in existing collection.
        Replace with a real LLM integration as desired.
        """
        prompt_l = (prompt or '').lower()
        # Use collection summary names if available; fallback to legacy JSON list
        try:
            items = self.get_collection_summary()
            cards = [str((it or {}).get('name') or '') for it in (items or [])]
            if not cards:
                raise RuntimeError('empty')
        except Exception:
            cards = db.load_cards_db(Path(self._db_path))
        # Very naive keyword filter
        keywords = [w for w in prompt_l.split() if len(w) > 3]
        if keywords:
            suggestions = [c for c in cards if any(k in c.lower() for k in keywords)]
        else:
            suggestions = cards[:20]
        return suggestions[:20]

    # --- Simple AI-style chat endpoints for UI ---
    def ai_chat(self, prompt: str):
        return { 'text': 'Assistant is disabled.' }

    def deck_help(self, deck_name: str, prompt: str, mode: str = 'collection'):
        return { 'text': 'Deck help is disabled.' }

    # --- Collection processing & counters ---
    def get_collection_count(self):
        return csql.count_items(Path(self._collection_db_path))

    def get_collection_items(self):
        """Return full collection items for UI display and client-side filtering."""
        return csql.load_all(Path(self._collection_db_path))

    def reset_collection_db(self):
        """Delete and recreate an empty SQLite collection DB. Returns path and total."""
        p = Path(self._collection_db_path)
        csql.reset_db(p)
        return { 'path': str(p.resolve()), 'total': 0 }

    def get_collection_db_path(self):
        """Return diagnostics for the collection DB file: absolute path, existence, size, and total rows."""
        p = Path(self._collection_db_path)
        exists = p.exists()
        size = 0
        total = 0
        try:
            if exists:
                size = p.stat().st_size
                total = csql.count_items(p)
        except Exception:
            pass
        return { 'path': str(p.resolve()), 'exists': exists, 'size': int(size), 'total': int(total) }

    # --- User-Specific Collections ---
    def _get_user_collection_path(self, user_id: int | str) -> Path:
        """Get the path to a user's collection database."""
        users_dir = Path('users')
        users_dir.mkdir(exist_ok=True)
        return users_dir / f"user_{user_id}_collection.db"

    def init_user_collection(self, user_id: int | str = None):
        """Initialize a user's collection database (copy from template or create new)."""
        if user_id is None:
            user_id = self._current_user_id
        
        user_db_path = self._get_user_collection_path(user_id)
        
        # If already exists, return it
        if user_db_path.exists():
            return {'success': True, 'path': str(user_db_path.resolve()), 'message': 'Collection already exists'}
        
        try:
            # Create parent directory
            user_db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # If template collection.db exists, copy it; otherwise create empty
            template_path = Path(self._collection_db_path)
            if template_path.exists():
                import shutil
                shutil.copy2(str(template_path), str(user_db_path))
                return {'success': True, 'path': str(user_db_path.resolve()), 'message': 'Collection initialized from template'}
            else:
                # Create empty database
                csql.reset_db(user_db_path)
                return {'success': True, 'path': str(user_db_path.resolve()), 'message': 'Collection created (empty)'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_user_collection_count(self, user_id: int | str = None):
        """Get card count for user's collection."""
        if user_id is None:
            user_id = self._current_user_id
        
        user_db_path = self._get_user_collection_path(user_id)
        if not user_db_path.exists():
            self.init_user_collection(user_id)
        
        try:
            return csql.count_items(user_db_path)
        except Exception:
            return 0

    def get_user_collection_items(self, user_id: int | str = None):
        """Get all items in user's collection."""
        if user_id is None:
            user_id = self._current_user_id
        
        user_db_path = self._get_user_collection_path(user_id)
        if not user_db_path.exists():
            self.init_user_collection(user_id)
        
        try:
            return csql.load_all(user_db_path)
        except Exception:
            return []

    def get_user_decks(self, user_id: int | str = None):
        """Get all decks for a user."""
        if user_id is None:
            user_id = self._current_user_id
        
        user_db_path = self._get_user_collection_path(user_id)
        if not user_db_path.exists():
            self.init_user_collection(user_id)
        
        try:
            return csql.get_decks(user_db_path)
        except Exception:
            return []

    def save_user_deck(self, deck_name: str, items: list[dict], deck_type: str | None = None, commander: str | None = None, user_id: int | str = None):
        """Save a deck for a user."""
        if user_id is None:
            user_id = self._current_user_id
        
        user_db_path = self._get_user_collection_path(user_id)
        if not user_db_path.exists():
            self.init_user_collection(user_id)
        
        import time
        name = str(deck_name or '')
        attempts = 0
        last_err = None
        
        while attempts < 6:
            try:
                csql.save_deck(user_db_path, name, items or [], deck_type, None, commander)
                return {'success': True, 'message': f'Deck "{name}" saved'}
            except Exception as e:
                msg = str(e)
                last_err = e
                if 'database is locked' in msg.lower() or 'busy' in msg.lower():
                    time.sleep(0.2 * (attempts + 1))
                    attempts += 1
                    continue
                return {'success': False, 'error': msg}
        
        return {'success': False, 'error': f"database is locked after retries: {last_err}"}

    def add_to_user_collection(self, card_name: str, quantity: int = 1, user_id: int | str = None):
        """Add cards to user's collection."""
        if user_id is None:
            user_id = self._current_user_id
        
        user_db_path = self._get_user_collection_path(user_id)
        if not user_db_path.exists():
            self.init_user_collection(user_id)
        
        try:
            csql.add_item(user_db_path, card_name, quantity)
            return {'success': True, 'message': f'Added {quantity} {card_name} to collection'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_user_collection_db_path(self, user_id: int | str = None):
        """Get diagnostics for user's collection database."""
        if user_id is None:
            user_id = self._current_user_id
        
        p = self._get_user_collection_path(user_id)
        exists = p.exists()
        size = 0
        total = 0
        try:
            if exists:
                size = p.stat().st_size
                total = csql.count_items(p)
        except Exception:
            pass
        return {'path': str(p.resolve()), 'exists': exists, 'size': int(size), 'total': int(total), 'user_id': str(user_id)}

    # --- Decks (SQL) ---
    def list_decks(self):
        """Return decks stored in collection.db with their card lists and types."""
        try:
            return csql.get_decks(Path(self._collection_db_path))
        except Exception:
            return []

    def save_deck_items(self, deck_name: str, items: list[dict], deck_type: str | None = None, commander: str | None = None):
        """Replace a deck's contents with provided items: [{name, count}]. Optionally set deck_type/commander."""
        import time
        name = str(deck_name or '')
        attempts = 0
        last_err = None
        while attempts < 6:
            try:
                csql.save_deck(Path(self._collection_db_path), name, items or [], deck_type, None, commander)
                return { 'ok': True }
            except Exception as e:
                msg = str(e)
                last_err = e
                # Retry transient SQLite lock errors
                if 'database is locked' in msg.lower() or 'busy' in msg.lower():
                    time.sleep(0.2 * (attempts + 1))
                    attempts += 1
                    continue
                return { 'ok': False, 'error': msg }
        return { 'ok': False, 'error': f"database is locked after retries: {last_err}" }

    # --- Deck persistence helpers ---
    def _load_decks(self) -> list[dict]:
        p = Path(self._decks_db_path)
        if not p.exists():
            return []
        try:
            with p.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict)]
        except Exception:
            pass
        return []

    def _save_decks(self, decks: list[dict]) -> None:
        p = Path(self._decks_db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with p.open('w', encoding='utf-8') as f:
                json.dump(decks, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Public deck APIs (minimal)
    def get_decks(self):
        return self._load_decks()

    def add_to_deck(self, deck_name: str, card_name: str, count: int = 1):
        dname = str(deck_name or '').strip()
        cname = str(card_name or '').strip()
        if not dname or not cname or (count or 0) <= 0:
            return { 'ok': False }
        decks = self._load_decks()
        deck = None
        for d in decks:
            if str(d.get('name','')).strip().lower() == dname.lower():
                deck = d; break
        if deck is None:
            deck = { 'name': dname, 'cards': [] }
            decks.append(deck)
        # find card
        found = None
        for c in deck.get('cards', []):
            if str(c.get('name','')).strip().lower() == cname.lower():
                found = c; break
        if found is None:
            deck['cards'].append({ 'name': cname, 'count': int(count) })
        else:
            found['count'] = int(found.get('count', 0)) + int(count)
        self._save_decks(decks)
        return { 'ok': True }

    def remove_from_deck(self, deck_name: str, card_name: str, count: int = 1):
        dname = str(deck_name or '').strip()
        cname = str(card_name or '').strip()
        if not dname or not cname or (count or 0) <= 0:
            return { 'ok': False }
        decks = self._load_decks()
        for d in decks:
            if str(d.get('name','')).strip().lower() == dname.lower():
                new_cards = []
                for c in d.get('cards', []):
                    if str(c.get('name','')).strip().lower() == cname.lower():
                        cur = int(c.get('count', 0))
                        cur -= int(count)
                        if cur > 0:
                            new_cards.append({ 'name': c.get('name'), 'count': cur })
                    else:
                        new_cards.append(c)
                d['cards'] = new_cards
                break
        self._save_decks(decks)
        return { 'ok': True }

    def get_collection_summary(self):
        """Return aggregated collection by name with qty, available, and decks list.
        Also includes simple aggregates for colors (unique), cmc (avg), and exemplar PT/text.
        """
        items = csql.load_all(Path(self._collection_db_path))
        # group by name
        groups: dict[str, dict] = {}
        for it in items:
            name = str((it or {}).get('name','')).strip()
            if not name:
                continue
            key = name.lower()
            g = groups.get(key)
            if g is None:
                g = {
                    'name': name,
                    'qty': 0,
                    'colors': set(),
                    'types': set(),
                    'cmcs': [],
                    'powers': [],
                    'toughnesses': [],
                    'texts': [],
                    'back_name': '',
                    'back_mana_cost': '',
                    'back_colors': set(),
                    'back_types': set(),
                    'back_oracle_text': '',
                    'back_power': '',
                    'back_toughness': '',
                }
                groups[key] = g
            g['qty'] += 1
            for c in (it.get('colors') or []):
                g['colors'].add(str(c))
            for t in (it.get('types') or []):
                g['types'].add(str(t))
            if it.get('cmc') is not None:
                try:
                    g['cmcs'].append(float(it.get('cmc')))
                except Exception:
                    pass
            if it.get('power') is not None:
                g['powers'].append(str(it.get('power')))
            if it.get('toughness') is not None:
                g['toughnesses'].append(str(it.get('toughness')))
            if it.get('text'):
                g['texts'].append(str(it.get('text')))
            # Collect back face data (first non-empty wins)
            if it.get('back_name') and not g['back_name']:
                g['back_name'] = str(it.get('back_name'))
            if it.get('back_mana_cost') and not g['back_mana_cost']:
                g['back_mana_cost'] = str(it.get('back_mana_cost'))
            for c in (it.get('back_colors') or []):
                g['back_colors'].add(str(c))
            for t in (it.get('back_types') or []):
                g['back_types'].add(str(t))
            if it.get('back_oracle_text') and not g['back_oracle_text']:
                g['back_oracle_text'] = str(it.get('back_oracle_text'))
            if it.get('back_power') and not g['back_power']:
                g['back_power'] = str(it.get('back_power'))
            if it.get('back_toughness') and not g['back_toughness']:
                g['back_toughness'] = str(it.get('back_toughness'))
        # compute decks usage from SQLite decks; fallback to JSON decks if needed
        usage_by_name: dict[str, int] = {}
        decks_by_name: dict[str, list[str]] = {}
        try:
            # Build usage map and deck name mapping from SQL
            usage_by_name = csql.usage_counts_by_name(Path(self._collection_db_path))
            for d in csql.get_decks(Path(self._collection_db_path)):
                dname = str(d.get('name','')).strip()
                for c in (d.get('cards') or []):
                    nm = str(c.get('name','')).strip()
                    cnt = int(c.get('count', 0))
                    if cnt > 0 and nm:
                        decks_by_name.setdefault(nm.lower(), []).append(dname)
        except Exception:
            # Fallback to legacy JSON decks store
            try:
                decks = self._load_decks()
                for d in decks:
                    dname = str(d.get('name','')).strip()
                    for c in (d.get('cards') or []):
                        nm = str(c.get('name','')).strip()
                        cnt = int(c.get('count', 0))
                        k = nm.lower()
                        usage_by_name[k] = usage_by_name.get(k, 0) + max(0, cnt)
                        if cnt > 0:
                            decks_by_name.setdefault(k, []).append(dname)
            except Exception:
                usage_by_name = {}
                decks_by_name = {}

        # finalize summary
        out = []
        for k, g in groups.items():
            qty = int(g['qty'])
            used = int(usage_by_name.get(k, 0))
            avail = max(0, qty - used)
            colors = sorted(list(g['colors']))
            types = sorted(list(g['types']))
            cmc = None
            if g['cmcs']:
                cmc = round(sum(g['cmcs'])/len(g['cmcs']), 1)
            power = next((p for p in g['powers'] if p), '')
            tough = next((t for t in g['toughnesses'] if t), '')
            text = next((t for t in g['texts'] if t), '')
            out.append({
                'name': g['name'],
                'qty': qty,
                'available': avail,
                'decks': sorted(list(set(decks_by_name.get(k, [])))),
                'colors': colors,
                'types': types,
                'cmc': cmc,
                'power': power,
                'toughness': tough,
                'text': text,
                'back_name': g['back_name'],
                'back_mana_cost': g['back_mana_cost'],
                'back_colors': sorted(list(g['back_colors'])),
                'back_types': sorted(list(g['back_types'])),
                'back_oracle_text': g['back_oracle_text'],
                'back_power': g['back_power'],
                'back_toughness': g['back_toughness'],
            })
        out.sort(key=lambda x: x['name'])
        return out

    # --- Deck APIs backed by SQLite ---
    def save_deck(self, deck_name: str, items: list[dict], commander: str | None = None):
        """Create/replace a deck with a list of {name, count}."""
        import time
        name = str(deck_name or '')
        attempts = 0
        last_err = None
        while attempts < 6:
            try:
                csql.save_deck(Path(self._collection_db_path), name, items or [], None, None, commander)
                return { 'ok': True }
            except Exception as e:
                msg = str(e)
                last_err = e
                if 'database is locked' in msg.lower() or 'busy' in msg.lower():
                    time.sleep(0.2 * (attempts + 1))
                    attempts += 1
                    continue
                return { 'ok': False, 'error': msg }
        return { 'ok': False, 'error': f"database is locked after retries: {last_err}" }

    def create_deck(self, deck_name: str, deck_type: str | None = None, deck_colors: list[str] | None = None, commander: str | None = None):
        """Create a deck if missing and optionally set deck_type/colors/commander. Does not change cards."""
        import time
        name = str(deck_name or '').strip()
        if not name:
            return { 'ok': False, 'error': 'name_required' }
        attempts = 0
        last_err = None
        while attempts < 6:
            try:
                p = Path(self._collection_db_path)
                did = csql.create_or_get_deck(p, name)
                try:
                    import json as _json
                    with csql._open_conn(p) as conn:  # type: ignore
                        conn.execute("PRAGMA busy_timeout=5000")
                        if deck_type is not None and deck_colors is not None and commander is not None:
                            conn.execute("UPDATE decks SET deck_type=?, deck_colors=?, commander=? WHERE id=?", (str(deck_type or ''), _json.dumps(deck_colors or []), str(commander or ''), int(did)))
                        elif deck_type is not None and deck_colors is not None:
                            conn.execute("UPDATE decks SET deck_type=?, deck_colors=? WHERE id=?", (str(deck_type or ''), _json.dumps(deck_colors or []), int(did)))
                        elif deck_type is not None and commander is not None:
                            conn.execute("UPDATE decks SET deck_type=?, commander=? WHERE id=?", (str(deck_type or ''), str(commander or ''), int(did)))
                        elif deck_colors is not None and commander is not None:
                            conn.execute("UPDATE decks SET deck_colors=?, commander=? WHERE id=?", (_json.dumps(deck_colors or []), str(commander or ''), int(did)))
                        elif deck_type is not None:
                            conn.execute("UPDATE decks SET deck_type=? WHERE id=?", (str(deck_type or ''), int(did)))
                        elif deck_colors is not None:
                            conn.execute("UPDATE decks SET deck_colors=? WHERE id=?", (_json.dumps(deck_colors or []), int(did)))
                        elif commander is not None:
                            conn.execute("UPDATE decks SET commander=? WHERE id=?", (str(commander or ''), int(did)))
                        conn.commit()
                except Exception:
                    pass
                return { 'ok': True }
            except Exception as e:
                msg = str(e)
                last_err = e
                if 'database is locked' in msg.lower() or 'busy' in msg.lower():
                    time.sleep(0.2 * (attempts + 1))
                    attempts += 1
                    continue
                return { 'ok': False, 'error': msg }
        return { 'ok': False, 'error': f"database is locked after retries: {last_err}" }

    def get_decks_sql(self):
        try:
            return csql.get_decks(Path(self._collection_db_path))
        except Exception:
            return []

    # --- Deck card mutations (SQL) ---
    def add_cards_to_deck(self, deck_name: str, items: list[dict]):
        import time
        name = str(deck_name or '').strip()
        if not name:
            return { 'ok': False, 'error': 'name_required' }
        
        # Check if this is a commander deck and validate rules
        deck_info = self._get_deck_info(name)
        is_commander = deck_info and str(deck_info.get('type', '')).lower() in ['commander', 'edh']
        
        if is_commander:
            # Validate commander deck rules before adding
            violations = self._validate_commander_deck_additions(name, items)
            if violations:
                return { 'ok': False, 'error': 'commander_rules_violation', 'violations': violations }
        
        attempts = 0
        last_err = None
        while attempts < 6:
            try:
                p = Path(self._collection_db_path)
                # First add to deck
                for it in (items or []):
                    nm = str((it or {}).get('name') or '').strip()
                    cnt = int((it or {}).get('count') or 0)
                    if nm and cnt > 0:
                        csql.add_to_deck(p, name, nm, cnt)
                # Then ensure inventory has at least as many copies as used across decks
                try:
                    used_map = csql.usage_counts_by_name(p)
                except Exception:
                    used_map = {}
                import sqlite3, json as _json
                with csql._open_conn(p) as conn:  # type: ignore
                    for it in (items or []):
                        nm = str((it or {}).get('name') or '').strip()
                        if not nm:
                            continue
                        used = int(used_map.get(nm.lower(), 0))
                        cur = conn.execute("SELECT COUNT(1) FROM collection WHERE lower(name)=?", (nm.lower(),))
                        total = int(cur.fetchone()[0] or 0)
                        missing = max(0, used - total)
                        if missing > 0:
                            row = {
                                'name': nm,
                                'set_code': '',
                                'number': '',
                                'colors': _json.dumps([]),
                                'types': _json.dumps([]),
                                'cmc': None,
                                'power': None,
                                'toughness': None,
                                'text': None,
                                'image_path': None,
                                'image_url': None,
                                'source': 'deck_add',
                            }
                            conn.executemany(
                                "INSERT INTO collection(name,set_code,number,colors,types,cmc,power,toughness,text,image_path,image_url,source) VALUES(:name,:set_code,:number,:colors,:types,:cmc,:power,:toughness,:text,:image_path,:image_url,:source)",
                                [row]*missing
                            )
                    conn.commit()
                return { 'ok': True }
            except Exception as e:
                msg = str(e)
                last_err = e
                if 'locked' in msg.lower() or 'busy' in msg.lower():
                    time.sleep(0.2 * (attempts + 1))
                    attempts += 1
                    continue
                return { 'ok': False, 'error': msg }
        return { 'ok': False, 'error': f"database is locked after retries: {last_err}" }

    def _get_deck_info(self, deck_name: str) -> dict | None:
        """Get deck information including type and current cards."""
        try:
            p = Path(self._collection_db_path)
            with csql._open_conn(p) as conn:
                deck_row = conn.execute(
                    "SELECT id, deck_type, commander FROM decks WHERE lower(name)=?", 
                    (str(deck_name or '').strip().lower(),)
                ).fetchone()
                
                if not deck_row:
                    return None
                
                deck_id, deck_type, commander = deck_row
                
                # Get current cards
                cards = {}
                for row in conn.execute("SELECT name, count FROM deck_cards WHERE deck_id=?", (deck_id,)):
                    cards[str(row[0]).lower()] = int(row[1])
                
                return {
                    'type': str(deck_type or ''),
                    'commander': str(commander or ''),
                    'cards': cards
                }
        except Exception:
            return None
    
    def _is_basic_land(self, card_name: str) -> bool:
        """Check if a card is a basic land (unlimited in Commander)."""
        basic_lands = {
            'plains', 'island', 'swamp', 'mountain', 'forest', 'wastes',
            'snow-covered plains', 'snow-covered island', 'snow-covered swamp', 
            'snow-covered mountain', 'snow-covered forest'
        }
        return str(card_name or '').strip().lower() in basic_lands
    
    def _validate_commander_deck_additions(self, deck_name: str, items: list[dict]) -> list[str]:
        """Validate cards being added to a commander deck. Returns list of rule violations."""
        violations = []
        deck_info = self._get_deck_info(deck_name)
        
        if not deck_info:
            return violations
        
        current_cards = deck_info['cards']
        
        for item in (items or []):
            name = str((item or {}).get('name', '')).strip()
            count = int((item or {}).get('count', 0))
            
            if not name or count <= 0:
                continue
            
            name_lower = name.lower()
            
            # Skip basic lands (no limit)
            if self._is_basic_land(name):
                continue
            
            current_count = current_cards.get(name_lower, 0)
            
            # Commander rule: max 1 copy of non-basic cards
            if current_count >= 1:
                violations.append(f"'{name}' already in deck (max 1 copy allowed in Commander)")
            elif current_count + count > 1:
                violations.append(f"Cannot add {count} copies of '{name}' (max 1 copy allowed in Commander)")
        
        return violations

    def remove_cards_from_deck(self, deck_name: str, items: list[dict]):
        import time
        name = str(deck_name or '').strip()
        if not name:
            return { 'ok': False, 'error': 'name_required' }
        attempts = 0
        last_err = None
        while attempts < 6:
            try:
                for it in (items or []):
                    nm = str((it or {}).get('name') or '').strip()
                    cnt = int((it or {}).get('count') or 0)
                    if nm and cnt > 0:
                        csql.remove_from_deck(Path(self._collection_db_path), name, nm, cnt)
                return { 'ok': True }
            except Exception as e:
                msg = str(e)
                last_err = e
                if 'locked' in msg.lower() or 'busy' in msg.lower():
                    time.sleep(0.2 * (attempts + 1))
                    attempts += 1
                    continue
                return { 'ok': False, 'error': msg }
        return { 'ok': False, 'error': f"database is locked after retries: {last_err}" }

    def delete_deck(self, deck_name: str):
        import time, sqlite3
        name = str(deck_name or '').strip()
        if not name:
            return { 'ok': False, 'error': 'name_required' }
        attempts = 0
        last_err = None
        p = Path(self._collection_db_path)
        while attempts < 6:
            try:
                # Before deleting the deck, remove that many copies from collection
                with csql._open_conn(p) as conn:  # type: ignore
                    conn.execute("PRAGMA busy_timeout=5000")
                    # Find deck id and its cards
                    cur = conn.execute("SELECT id FROM decks WHERE lower(name)=?", (name.lower(),))
                    row = cur.fetchone()
                    if row:
                        did = int(row[0])
                        # Build list of {name, count}
                        cur2 = conn.execute("SELECT name, count FROM deck_cards WHERE deck_id=?", (did,))
                        to_remove = [{'name': r[0], 'count': int(r[1] or 0)} for r in cur2.fetchall()]
                    else:
                        to_remove = []
                # Delete requested counts from collection
                try:
                    removed = 0
                    if to_remove:
                        removed = int(csql.delete_by_names_counts(p, to_remove) or 0)
                except Exception:
                    removed = 0
                # Finally, delete the deck (and its deck_cards via FK CASCADE or explicit deletes)
                with csql._open_conn(p) as conn:  # type: ignore
                    conn.execute("PRAGMA busy_timeout=5000")
                    # Ensure deck_cards removed first for safety on older schemas
                    conn.execute("DELETE FROM deck_cards WHERE deck_id IN (SELECT id FROM decks WHERE lower(name)=?)", (name.lower(),))
                    conn.execute("DELETE FROM decks WHERE lower(name)=?", (name.lower(),))
                    conn.commit()
                return { 'ok': True, 'removed_from_collection': removed, 'planned': sum(int(x.get('count') or 0) for x in (to_remove or [])) }
            except Exception as e:
                msg = str(e)
                last_err = e
                if 'locked' in msg.lower() or 'busy' in msg.lower():
                    time.sleep(0.2 * (attempts + 1))
                    attempts += 1
                    continue
                return { 'ok': False, 'error': msg }
        return { 'ok': False, 'error': f"database is locked after retries: {last_err}" }

    def _sync_card_names_from_collection(self):
        items = csql.load_all(Path(self._collection_db_path))
        names = sorted({str(it.get('name', '')).strip() for it in items if str(it.get('name', '')).strip()})
        db.save_cards_db(Path(self._db_path), names)

    def process_manual_entry(self, text: str):
        """Process one or multiple manual entries (comma or newline separated) via AllPrintings.sql.
        Adds parsed card metadata into collection_db.json and updates the names list.
        Returns dict with counts and items added.
        """
        if not text:
            return { 'added': 0, 'total': self.get_collection_count(), 'items': [] }
        # Split on newlines/commas
        parts = []
        for line in str(text).splitlines():
            parts.extend([p.strip() for p in line.split(',') if p.strip()])
        new_items = []
        for q in parts:
            # Prefer structured index lookup
            try:
                structured = self.search_structured(q, limit=1)
            except Exception:
                structured = []
            if structured:
                item = structured[0]
                item['source'] = 'index'
                new_items.append(item)
            else:
                # Fallback to basic manual record; avoid SQL snippet parsing to prevent bad names
                new_items.append({ 'name': q, 'set': '', 'number': '', 'source': 'manual' })
        added = csql.insert_items(Path(self._collection_db_path), new_items)
        # Sync simple names list for other pages
        self._sync_card_names_from_collection()
        total = self.get_collection_count()
        return { 'added': added, 'total': total, 'items': new_items }

    def repair_collection_names(self, max_rows: int = 500):
        """Repair obvious bad collection rows where name has surrounding quotes or embedded text.
        Strategy:
        - Select rows where name starts/ends with quotes or contains newlines or very long length.
        - Clean name (strip quotes, take first line), then re-enrich via structured index; fallback to Scryfall; fallback to cleaned minimal.
        - Update the row's normalized fields in-place.
        Returns { scanned, repaired }.
        """
        import sqlite3, json as _json
        p = Path(self._collection_db_path)
        csql.ensure_db(p)
        # Ensure index ready
        self.ensure_index()
        repaired = 0
        scanned = 0
        try:
            with csql._open_conn(p) as conn:  # type: ignore
                conn.execute("PRAGMA busy_timeout=5000")
                rows = conn.execute(
                    "SELECT id, name, set_code, number FROM collection WHERE name LIKE '""%' OR name LIKE '%""' OR instr(name, char(10))>0 OR length(name)>120 LIMIT ?",
                    (int(max_rows),)
                ).fetchall()
                for r in rows:
                    scanned += 1
                    rid = int(r[0])
                    raw_name = str(r[1] or '')
                    cleaned = raw_name.replace('\r','\n').split('\n')[0].strip().strip('"').strip()
                    set_code = str(r[2] or '')
                    number = str(r[3] or '')
                    enriched = None
                    # Try index by exact name
                    try:
                        idx_conn = card_index.open_db(Path(self._index_db_path))
                    except Exception:
                        idx_conn = None
                    try:
                        if idx_conn and cleaned:
                            rows_idx = card_index.lookup_by_name(idx_conn, cleaned, limit=1) or []
                            if rows_idx:
                                enriched = rows_idx[0]
                    except Exception:
                        enriched = None
                    finally:
                        if idx_conn:
                            try: idx_conn.close()
                            except Exception: pass
                    # Try Scryfall by set/number, else by name
                    if enriched is None and set_code and number:
                        try:
                            url = f"https://api.scryfall.com/cards/{urllib.parse.quote(set_code)}/{urllib.parse.quote(number)}"
                            data = self._http_get_json(url)
                            if isinstance(data, dict) and data.get('object') == 'card':
                                enriched = self._map_scryfall_card(data)
                        except Exception:
                            enriched = None
                    if enriched is None and cleaned:
                        try:
                            res = self.search_scryfall(cleaned, limit=1) or []
                            if res:
                                enriched = res[0]
                        except Exception:
                            enriched = None
                    if enriched is None:
                        enriched = { 'name': cleaned, 'set': set_code, 'number': number, 'colors': [], 'types': [], 'cmc': None, 'power': None, 'toughness': None, 'text': '', 'image_path': None, 'image_url': None, 'source': 'repair' }
                    # Update row fields
                    try:
                        conn.execute(
                            "UPDATE collection SET name=?, set_code=?, number=?, colors=?, types=?, cmc=?, power=?, toughness=?, text=? WHERE id=?",
                            (
                                str(enriched.get('name') or cleaned),
                                str(enriched.get('set') or set_code),
                                str(enriched.get('number') or number),
                                _json.dumps(enriched.get('colors') or []),
                                _json.dumps(enriched.get('types') or []),
                                enriched.get('cmc'),
                                None if enriched.get('power') is None else str(enriched.get('power')),
                                None if enriched.get('toughness') is None else str(enriched.get('toughness')),
                                str(enriched.get('text') or ''),
                                rid,
                            )
                        )
                        repaired += 1
                    except Exception:
                        pass
                conn.commit()
        except Exception:
            pass
        # refresh name list
        self._sync_card_names_from_collection()
        return { 'scanned': scanned, 'repaired': repaired }

    def enrich_collection(self, max_items: int | None = None):
        """Backfill metadata for existing entries using the structured index."""
        self.ensure_index()
        items = csql.load_all(Path(self._collection_db_path))
        updated = 0
        conn = card_index.open_db(Path(self._index_db_path))
        out = []
        for it in items:
            out.append(it)
            if max_items and updated >= max_items:
                continue
            # If already has key metadata, skip
            if it.get('types') or it.get('cmc') is not None or it.get('text'):
                continue
            name = str(it.get('name', ''))
            if not name:
                continue
            rows = card_index.lookup_by_name(conn, name, limit=1)
            if not rows:
                continue
            enriched = rows[0]
            # Merge preserving identifiers and image_path
            enriched['image_path'] = it.get('image_path', enriched.get('image_path', ''))
            enriched['source'] = it.get('source', 'enriched')
            # Replace in out
            out[-1] = enriched
            updated += 1
        conn.close()
        # Replace contents: reset and insert
        csql.reset_db(Path(self._collection_db_path))
        csql.insert_items(Path(self._collection_db_path), out)
        self._sync_card_names_from_collection()
        return { 'updated': updated, 'total': len(out) }

    def repair_collection(self, max_items: int | None = None):
        """Repair/enrich existing collection rows by fetching from Scryfall.
        For each row, prefer exact printing (set_code + number); otherwise fuzzy by name.
        Updates columns: scryfall_id, mana_cost, oracle_text, cmc, colors, types, image_url, power, toughness.
        Returns { updated, total, errors }.
        """
        import sqlite3, urllib.parse
        path = Path(self._collection_db_path)
        updated = 0
        errors: list[str] = []
        try:
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            rows = list(cur.execute("SELECT id, name, set_code, number FROM collection"))
            count = 0
            for r in rows:
                if max_items and updated >= max_items:
                    break
                rid = int(r['id'])
                name = str(r['name'] or '')
                sc = str(r['set_code'] or '')
                no = str(r['number'] or '')
                data = None
                try:
                    if sc and no:
                        url = f"https://api.scryfall.com/cards/{urllib.parse.quote(sc)}/{urllib.parse.quote(no)}"
                        data = self._http_get_json(url)
                    if not isinstance(data, dict) or data.get('object') != 'card':
                        # fallback by name
                        q = urllib.parse.quote(name or '', safe='')
                        url = f"https://api.scryfall.com/cards/named?fuzzy={q}"
                        data = self._http_get_json(url)
                    if not isinstance(data, dict) or data.get('object') != 'card':
                        continue
                    # Extract fields
                    scry_id = str(data.get('id') or '')
                    type_line = data.get('type_line') or ''
                    mana_cost = data.get('mana_cost') or ''
                    cmc = data.get('cmc')
                    colors = data.get('colors') or data.get('color_identity') or []
                    # Simple types array
                    tys_main = (type_line or '').split(' — ')[0]
                    types_arr = [t for t in tys_main.replace('-', ' ').split() if t]
                    # Text
                    oracle_text = data.get('oracle_text') or ''
                    power = data.get('power')
                    toughness = data.get('toughness')
                    # Image with fallback to first face
                    img = ''
                    if isinstance(data.get('image_uris'), dict):
                        iu = data.get('image_uris')
                        img = iu.get('normal') or iu.get('large') or iu.get('small') or ''
                    elif isinstance(data.get('card_faces'), list) and data['card_faces']:
                        f0 = data['card_faces'][0]
                        iu2 = f0.get('image_uris') or {}
                        img = iu2.get('normal') or iu2.get('large') or iu2.get('small') or ''
                    # Update row
                    cur.execute(
                        """
                        UPDATE collection
                        SET scryfall_id=?, mana_cost=?, oracle_text=?, cmc=?, colors=?, types=?, image_url=?, power=?, toughness=?
                        WHERE id=?
                        """,
                        (
                            scry_id,
                            str(mana_cost or ''),
                            str(oracle_text or ''),
                            cmc,
                            json.dumps(colors or []),
                            json.dumps(types_arr or []),
                            str(img or ''),
                            None if power is None else str(power),
                            None if toughness is None else str(toughness),
                            rid,
                        )
                    )
                    updated += 1
                    count += 1
                    # polite throttle each few requests
                    if (count % 8) == 0:
                        time.sleep(0.12)
                except Exception as e:
                    errors.append(f"{name}: {e}")
                    continue
            conn.commit()
            conn.close()
            self._sync_card_names_from_collection()
            return { 'updated': updated, 'total': len(rows), 'errors': errors }
        except Exception as e:
            return { 'updated': updated, 'total': 0, 'errors': [str(e)] }

    def start_repair_collection(self, max_items: int | None = None):
        """Start repair in background and track progress."""
        with self._repair_lock:
            if self._repair_running:
                return { 'started': False, 'reason': 'already_running' }
            self._repair_running = True
            self._repair_total = 0
            self._repair_updated = 0
            self._repair_errors = 0
            self._repair_errors_list = []
        def run():
            try:
                import sqlite3, urllib.parse
                path = Path(self._collection_db_path)
                conn = sqlite3.connect(str(path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # Select cards that need repair:
                # 1. Unrepaired cards
                # 2. Missing oracle_text
                # 3. Missing types
                # 4. Creatures missing power or toughness
                rows = list(cur.execute("""
                    SELECT id, name, set_code, number, types FROM collection 
                    WHERE (repaired IS NULL OR repaired = 0) 
                    OR (oracle_text IS NULL OR oracle_text = '')
                    OR (types IS NULL OR types = '' OR types = '[]')
                    OR (types LIKE '%Creature%' AND (power IS NULL OR toughness IS NULL))
                """))
                total = len(rows)
                with self._repair_lock:
                    self._repair_total = total
                count = 0
                for r in rows:
                    if max_items and count >= max_items:
                        break
                    rid = int(r['id'])
                    # sanitize incoming name: strip quotes/newlines/whitespace
                    name = str(r['name'] or '')
                    nm_clean = name.replace('\r','\n').split('\n')[0].strip().strip('"')
                    sc = str(r['set_code'] or '')
                    no = str(r['number'] or '')
                    try:
                        data = None
                        if sc and no:
                            url = f"https://api.scryfall.com/cards/{urllib.parse.quote(sc)}/{urllib.parse.quote(no)}"
                            data = self._http_get_json(url)
                        if not isinstance(data, dict) or data.get('object') != 'card':
                            q = urllib.parse.quote(nm_clean or '', safe='')
                            url = f"https://api.scryfall.com/cards/named?fuzzy={q}"
                            data = self._http_get_json(url)
                        if not isinstance(data, dict) or data.get('object') != 'card':
                            with self._repair_lock:
                                self._repair_updated += 1
                            count += 1
                            continue
                        scry_id = str(data.get('id') or '')
                        type_line = data.get('type_line') or ''
                        mana_cost = data.get('mana_cost') or ''
                        cmc = data.get('cmc')
                        colors = data.get('colors') or data.get('color_identity') or []
                        tys_main = (type_line or '').split(' — ')[0]
                        types_arr = [t for t in tys_main.replace('-', ' ').split() if t]
                        oracle_text = data.get('oracle_text') or ''
                        power = data.get('power')
                        toughness = data.get('toughness')
                        img = ''
                        
                        # Extract back face data if double-faced
                        back_name = ''
                        back_mana_cost = ''
                        back_colors = []
                        back_types = []
                        back_oracle_text = ''
                        back_power = None
                        back_toughness = None
                        back_image_url = ''
                        
                        card_faces = data.get('card_faces') or []
                        if isinstance(card_faces, list):
                            if len(card_faces) > 0:
                                f0 = card_faces[0]
                                iu2 = f0.get('image_uris') or {}
                                img = iu2.get('normal') or iu2.get('large') or iu2.get('small') or ''
                            if len(card_faces) > 1:
                                f1 = card_faces[1]
                                back_name = f1.get('name') or ''
                                back_mana_cost = f1.get('mana_cost') or ''
                                back_colors = f1.get('colors') or []
                                back_type_line = f1.get('type_line') or ''
                                back_tys_main = back_type_line.split(' — ')[0]
                                back_types = [t for t in back_tys_main.replace('-', ' ').split() if t]
                                back_oracle_text = f1.get('oracle_text') or ''
                                back_power = f1.get('power')
                                back_toughness = f1.get('toughness')
                                back_iu = f1.get('image_uris') or {}
                                back_image_url = back_iu.get('normal') or back_iu.get('large') or back_iu.get('small') or ''
                        elif isinstance(data.get('image_uris'), dict):
                            iu = data.get('image_uris')
                            img = iu.get('normal') or iu.get('large') or iu.get('small') or ''
                        
                        # also update cleaned name if changed and mark as repaired
                        cur.execute(
                            """
                            UPDATE collection
                            SET name=?, scryfall_id=?, mana_cost=?, oracle_text=?, cmc=?, colors=?, types=?, image_url=?, power=?, toughness=?,
                                back_name=?, back_mana_cost=?, back_colors=?, back_types=?, back_oracle_text=?, back_power=?, back_toughness=?, back_image_url=?,
                                repaired=1
                            WHERE id=?
                            """,
                            (
                                nm_clean or name,
                                scry_id,
                                str(mana_cost or ''),
                                str(oracle_text or ''),
                                cmc,
                                json.dumps(colors or []),
                                json.dumps(types_arr or []),
                                str(img or ''),
                                None if power is None else str(power),
                                None if toughness is None else str(toughness),
                                str(back_name or ''),
                                str(back_mana_cost or ''),
                                json.dumps(back_colors or []),
                                json.dumps(back_types or []),
                                str(back_oracle_text or ''),
                                None if back_power is None else str(back_power),
                                None if back_toughness is None else str(back_toughness),
                                str(back_image_url or ''),
                                rid,
                            )
                        )
                        count += 1
                        with self._repair_lock:
                            self._repair_updated = count
                        if (count % 8) == 0:
                            time.sleep(0.12)
                    except Exception as e:
                        with self._repair_lock:
                            self._repair_errors += 1
                            # store a compact error record
                            msg = f"{nm_clean or name}: {e}"
                            if len(self._repair_errors_list) < 500:
                                self._repair_errors_list.append(msg)
                        count += 1
                        with self._repair_lock:
                            self._repair_updated = count
                        continue
                conn.commit()
                conn.close()
                self._sync_card_names_from_collection()
            finally:
                with self._repair_lock:
                    self._repair_running = False
        t = threading.Thread(target=run, daemon=True)
        t.start()
        return { 'started': True }

    def get_repair_progress(self):
        with self._repair_lock:
            return {
                'running': self._repair_running,
                'updated': self._repair_updated,
                'total': self._repair_total,
                'errors': self._repair_errors,
                'errors_list': self._repair_errors_list[-50:],
            }

    def get_import_progress(self):
        """Returns current CSV import progress."""
        with self._import_lock:
            return {
                'running': self._import_running,
                'current': self._import_current,
                'total': self._import_total,
            }

    def get_precon_import_progress(self):
        """Returns current PreCon deck import progress."""
        with self._precon_lock:
            return {
                'running': self._precon_running,
                'current': self._precon_current,
                'total': self._precon_total,
            }

    def add_card_with_metadata(self, item: dict):
        """Add a card entry using provided metadata (e.g., from Scryfall search result)."""
        try:
            norm = db.normalize_item(item or {})
            if not norm.get('name'):
                return { 'added': 0, 'total': self.get_collection_count(), 'item': {} }
            norm.setdefault('source', 'manual-select')
            # Allow duplicates so inventory quantities >1 are stored as separate entries
            added = csql.insert_items(Path(self._collection_db_path), [norm])
            self._sync_card_names_from_collection()
            total = self.get_collection_count()
            return { 'added': added, 'total': total, 'item': norm }
        except Exception:
            return { 'added': 0, 'total': self.get_collection_count(), 'item': {} }

    def add_exact_card(self, name: str, set_code: str, number: str):
        """Add a specific printing (name + set + number) to the collection."""
        nm = str(name or '').strip()
        sc = str(set_code or '').strip()
        no = str(number or '').strip()
        # Try to fetch exact printing from Scryfall to capture metadata
        item = None
        if sc and no:
            try:
                url = f"https://api.scryfall.com/cards/{urllib.parse.quote(sc)}/{urllib.parse.quote(no)}"
                data = self._http_get_json(url)
                if isinstance(data, dict) and data.get('object') == 'card':
                    mapped = self._map_scryfall_card(data)
                    mapped['source'] = 'manual-select'
                    item = mapped
            except Exception:
                item = None
        if item is None:
            # Fallback minimal item
            item = db.normalize_item({
                'name': nm,
                'set': sc,
                'number': no,
                'source': 'manual-select'
            })
        added = csql.insert_items(Path(self._collection_db_path), [item])
        self._sync_card_names_from_collection()
        total = self.get_collection_count()
        return { 'added': added, 'total': total, 'item': item }

    def delete_collection_items(self, items: list[dict]):
        """Delete collection items matching the provided identifiers.
        Each item should include at least name, set, and number.
        Returns counts and new total.
        """
        # Delete by exact identifiers using SQL
        path = Path(self._collection_db_path)
        if not items:
            return { 'deleted': 0, 'total': self.get_collection_count() }
        # Convert to name-only with counts=None to delete all matching identifiers by name+set+number
        # For simplicity, delete all rows whose (name,set,number) matches any item
        try:
            import sqlite3
            conn = sqlite3.connect(str(path))
            try:
                cur = conn.cursor()
                deleted = 0
                for it in (items or []):
                    nm = str((it or {}).get('name') or '').strip()
                    sc = str((it or {}).get('set') or '').strip()
                    no = str((it or {}).get('number') or '').strip()
                    cur.execute("DELETE FROM collection WHERE lower(name)=? AND lower(set_code)=? AND lower(number)=?", (nm.lower(), sc.lower(), no.lower()))
                    deleted += cur.rowcount
                conn.commit()
            finally:
                conn.close()
            self._sync_card_names_from_collection()
            return { 'deleted': deleted, 'total': self.get_collection_count() }
        except Exception:
            return { 'deleted': 0, 'total': self.get_collection_count() }

    def delete_collection_by_names_counts(self, items: list[dict]):
        """Delete up to 'count' entries per provided name (case-insensitive). If count is None, delete all for that name."""
        path = Path(self._collection_db_path)
        deleted = csql.delete_by_names_counts(path, items or [])
        self._sync_card_names_from_collection()
        return { 'deleted': deleted, 'total': self.get_collection_count() }

    def delete_collection_by_names(self, names: list[str]):
        """Delete all collection items whose name matches any of the provided names (case-insensitive)."""
        path = Path(self._collection_db_path)
        items = [{'name': n, 'count': None} for n in (names or [])]
        deleted = csql.delete_by_names_counts(path, items)
        self._sync_card_names_from_collection()
        return { 'deleted': deleted, 'total': self.get_collection_count() }

    def get_insert_header_snippet(self, table_hint: str = 'card', max_lines: int = 5):
        """Return the first INSERT INTO header lines that match the table hint to help diagnose mapping."""
        sql_path = Path(self._allprintings_sql)
        if not sql_path.exists():
            return { 'found': False, 'snippet': '' }
        lines = []
        found = False
        with sql_path.open('r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                s = line.strip()
                if s.lower().startswith('insert into') and table_hint in s.lower():
                    lines.append(line.rstrip('\n'))
                    found = True
                    # capture subsequent lines until we hit VALUES or reach max_lines
                    for _ in range(max_lines - 1):
                        nxt = f.readline()
                        if not nxt:
                            break
                        lines.append(nxt.rstrip('\n'))
                        if 'values' in nxt.lower():
                            break
                    break
        return { 'found': found, 'snippet': '\n'.join(lines) }

    def process_external_images(self):
        """Process all images in external folder; use filename (without extension) to search the AllPrintings.sql
        and add parsed metadata to collection DB. Returns counts and items.
        """
        imgs = self.list_images()
        new_items = []
        for it in imgs:
            base = Path(it.get('path', '')).stem
            if not base:
                continue
            try:
                structured = self.search_structured(base, limit=1)
            except Exception:
                structured = []
            if structured:
                meta = structured[0]
                meta['source'] = 'image-index'
            else:
                snippets = db.search_allprintings(Path(self._allprintings_sql), base, limit=10)
                if snippets:
                    meta = db.parse_card_from_snippet(snippets[0], fallback_name=base)
                else:
                    meta = { 'name': base, 'set': '', 'number': '', 'source': 'image-filename' }
            meta['image_path'] = it.get('path')
            new_items.append(meta)
        added = csql.insert_items(Path(self._collection_db_path), new_items)
        self._sync_card_names_from_collection()
        total = self.get_collection_count()
        return { 'added': added, 'total': total, 'items': new_items }

    # --- Server-side Authentication (bypasses Google API key restrictions) ---
    def register_user(self, email: str, password: str, username: str):
        """Server-side user registration. Returns { success, userId, token, error }."""
        import hashlib
        import secrets
        
        email = str(email or '').strip().lower()
        username = str(username or '').strip()
        password = str(password or '').strip()
        
        # Validation
        if not email or '@' not in email:
            return { 'success': False, 'error': 'Invalid email address' }
        if not username or len(username) < 3:
            return { 'success': False, 'error': 'Username must be at least 3 characters' }
        if not password or len(password) < 6:
            return { 'success': False, 'error': 'Password must be at least 6 characters' }
        
        try:
            import sqlite3
            # Check if user already exists
            db_path = Path('users.db')
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            
            # Create users table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Check if email already registered
            cur.execute("SELECT id FROM users WHERE email=?", (email,))
            if cur.fetchone():
                conn.close()
                return { 'success': False, 'error': 'Email already registered' }
            
            # Hash password with salt
            salt = secrets.token_hex(16)
            password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            combined_hash = salt + ':' + password_hash.hex()
            
            # Create user
            user_id = secrets.token_urlsafe(16)
            from datetime import datetime
            created_at = datetime.utcnow().isoformat()
            
            cur.execute("""
                INSERT INTO users (id, email, username, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, email, username, combined_hash, created_at))
            
            conn.commit()
            conn.close()
            
            # Generate session token
            token = secrets.token_urlsafe(32)
            
            return {
                'success': True,
                'userId': user_id,
                'email': email,
                'username': username,
                'token': token
            }
        except Exception as e:
            return { 'success': False, 'error': f'Registration failed: {str(e)}' }
    
    def login_user(self, email: str, password: str):
        """Server-side user login. Returns { success, userId, token, username, error }."""
        import hashlib
        
        email = str(email or '').strip().lower()
        password = str(password or '').strip()
        
        if not email or not password:
            return { 'success': False, 'error': 'Email and password required' }
        
        try:
            import sqlite3
            db_path = Path('users.db')
            if not db_path.exists():
                return { 'success': False, 'error': 'No users registered yet' }
            
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            
            cur.execute("SELECT id, password_hash, username FROM users WHERE email=?", (email,))
            result = cur.fetchone()
            conn.close()
            
            if not result:
                return { 'success': False, 'error': 'Invalid email or password' }
            
            user_id, combined_hash, username = result
            
            # Verify password
            try:
                salt, stored_hash = combined_hash.split(':')
                password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
                if password_hash.hex() != stored_hash:
                    return { 'success': False, 'error': 'Invalid email or password' }
            except Exception:
                return { 'success': False, 'error': 'Password verification failed' }
            
            # Generate session token
            import secrets
            token = secrets.token_urlsafe(32)
            
            return {
                'success': True,
                'userId': user_id,
                'email': email,
                'username': username,
                'token': token
            }
        except Exception as e:
            return { 'success': False, 'error': f'Login failed: {str(e)}' }
    
    def verify_token(self, token: str):
        """Verify a session token is valid. Returns { valid, userId }."""
        # For now, we'll implement token verification when needed
        # For MVP, any non-empty token is considered valid
        return { 'valid': bool(token), 'userId': None }

    # --- Window control methods (no-op for web version) ---
    def minimize_window(self):
        """No-op for web version."""
        return {'ok': True}

    def toggle_maximize(self):
        """No-op for web version."""
        return {'ok': True}

    def close_window(self):
        """No-op for web version."""
        return {'ok': True}