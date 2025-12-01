import json
from backend import Api

api = Api()
result = api.list_precon_decks('')

# Convert to JSON format
with open('g:\\PyWeb\\precon_decks.json', 'w') as f:
    json.dump(result, f, indent=2)

print(f"Saved {len(result)} precons to precon_decks.json")
