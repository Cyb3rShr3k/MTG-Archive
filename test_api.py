from backend import Api
import json

api = Api()

# Test 1: List all precons
print("Test 1: List all precons (no query)")
result1 = api.list_precon_decks('')
print(f"Total: {len(result1)}")

# Test 2: Search for a specific deck
print("\nTest 2: Search for 'graveyard'")
result2 = api.list_precon_decks('graveyard')
print(f"Found: {len(result2)}")
for deck in result2:
    print(f"  - {deck['name']}")

# Test 3: Check if sorting
print("\nTest 3: First 20 decks (to check if they're sorted)")
for i, deck in enumerate(result1[:20]):
    print(f"{i+1}. {deck['name']}")
