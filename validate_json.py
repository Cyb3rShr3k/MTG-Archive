import json

with open('precon_decks.json', 'r') as f:
    data = json.load(f)

print(f'✓ Valid JSON with {len(data)} precons')
print(f'First deck: {data[0]["name"]}')
print(f'Last deck: {data[-1]["name"]}')
print(f'\nSample decks:')
for i, deck in enumerate(data[::30]):  # Every 30th deck
    print(f'  {i*30 + 1}. {deck["name"]}')
