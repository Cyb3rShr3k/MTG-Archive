# Preconstructed Commander Decks

This folder is for storing preconstructed Commander deck JSON files.

## Format

Each deck should be a JSON file with this structure:

```json
{
  "name": "Deck Name",
  "commander": "Commander Card Name",
  "cards": [
    {
      "name": "Card Name",
      "quantity": 1,
      "scryfall_id": "uuid-here"
    }
  ]
}
```

## Adding Decks

1. Export deck lists from sources like EDHREC, Scryfall, or Moxfield
2. Convert to the JSON format above
3. Place in this folder
4. Optionally add a matching image file (same name as JSON but .png/.jpg)

The application will automatically detect and list all JSON files in this directory when you use the "Import Precon Deck" feature.
