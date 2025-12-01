from backend import Api

api = Api()
result = api.list_precon_decks('')
print(f'Total precons: {len(result)}')
print('\nFirst 10 precons:')
for i, deck in enumerate(result[:10]):
    print(f'{i+1}. {deck["name"]}')
    
# Test a search
print('\n\nSearching for "Graveyard":')
result2 = api.list_precon_decks('Graveyard')
for deck in result2:
    print(f'  - {deck["name"]}')
