#!/usr/bin/env python3
"""
Test commander saving to database
"""

import sqlite3
from pathlib import Path

def test_commander_in_db():
    """Check what's actually in the database commander column"""
    db_path = Path("collection.db")
    
    if not db_path.exists():
        print("❌ collection.db not found")
        return
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    print("Checking commander column in decks table...")
    
    # Get all decks with their commander info
    cur.execute("SELECT id, name, deck_type, commander FROM decks ORDER BY name")
    decks = cur.fetchall()
    
    print(f"\nFound {len(decks)} decks:")
    for deck in decks:
        deck_id, name, deck_type, commander = deck
        commander_display = f"'{commander}'" if commander else "(empty)"
        print(f"  - {name} (Type: {deck_type or 'None'}) - Commander: {commander_display}")
    
    # Check for any recent deck imports
    print(f"\nRecent decks (checking for test imports):")
    cur.execute("SELECT name, commander, created_at FROM decks ORDER BY created_at DESC LIMIT 3")
    recent = cur.fetchall()
    
    for deck in recent:
        name, commander, created_at = deck
        commander_display = f"'{commander}'" if commander else "(empty)"
        print(f"  - {name} - Commander: {commander_display} (Created: {created_at})")
    
    conn.close()

def test_save_deck_directly():
    """Test the save_deck function directly"""
    from core import collection_sql as csql
    
    db_path = Path("collection.db")
    
    print("\nTesting save_deck function directly...")
    
    # Test saving a deck with commander
    test_deck_name = "Test Commander Save"
    test_commander = "Jace, the Mind Sculptor"
    test_items = [{"name": "Lightning Bolt", "count": 4}]
    
    csql.save_deck(
        db_path, 
        test_deck_name, 
        test_items, 
        deck_type="Commander", 
        deck_colors=["U", "R"], 
        commander=test_commander
    )
    
    print(f"Saved test deck: {test_deck_name} with commander: {test_commander}")
    
    # Verify it was saved
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name, commander FROM decks WHERE name = ?", (test_deck_name,))
    result = cur.fetchone()
    conn.close()
    
    if result:
        saved_name, saved_commander = result
        print(f"✅ Verified: {saved_name} has commander: '{saved_commander}'")
        if saved_commander == test_commander:
            print("✅ Commander saved correctly!")
        else:
            print(f"❌ Commander mismatch. Expected: '{test_commander}', Got: '{saved_commander}'")
    else:
        print("❌ Test deck not found")

if __name__ == "__main__":
    test_commander_in_db()
    test_save_deck_directly()