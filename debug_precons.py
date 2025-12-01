import json
from backend import Api

api = Api()

# Test what the API returns
result = api.list_precon_decks('')
print(f"Total items returned: {len(result)}")
print("\nFirst 5 items:")
for i, item in enumerate(result[:5]):
    print(f"\n{i+1}. {item}")
    
# Check if they have 'name' field
if result:
    print(f"\nFirst item keys: {result[0].keys()}")
    print(f"First item name field: '{result[0].get('name')}'")
