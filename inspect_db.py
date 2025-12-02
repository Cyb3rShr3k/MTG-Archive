import sqlite3

conn = sqlite3.connect('web/decklist_cards.db')
cursor = conn.cursor()

# Get table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', tables)

# Get info about each table
for table in tables:
    table_name = table[0]
    print(f'\n--- {table_name} ---')
    cursor.execute(f'PRAGMA table_info({table_name})')
    columns = cursor.fetchall()
    print('Columns:')
    for col in columns:
        print(f'  {col}')
    
    # Count rows
    cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    count = cursor.fetchone()[0]
    print(f'Total rows: {count}')
    
    # Get sample if it's the cards table
    if 'cards' in table_name.lower():
        cursor.execute(f'SELECT * FROM {table_name} LIMIT 3')
        rows = cursor.fetchall()
        print('Sample data:')
        for row in rows:
            print(f'  {row}')
        
        # Get distinct deck_ids
        cursor.execute(f'SELECT DISTINCT deck_id FROM {table_name} LIMIT 10')
        deck_ids = cursor.fetchall()
        print('Sample deck_ids:')
        for did in deck_ids:
            print(f'  {did[0]}')

conn.close()
