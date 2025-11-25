# MTG Archive

A comprehensive Magic: The Gathering collection manager and deck builder with OCR scanning capabilities.

## Features

- 📸 **OCR Card Scanning** - Scan physical cards using OCR technology
- 📚 **Collection Management** - Track your card collection with detailed information
- 🎴 **Deck Builder** - Build and manage decks with drag-and-drop interface
- ⚔️ **Commander Format Support** - Full Commander/EDH deck building with format rules enforcement
- 🔍 **Advanced Search** - Search and filter your collection by various criteria
- 📊 **Card Database** - Integrated Scryfall card database
- 🖼️ **Card Images** - View high-quality card images
- 📋 **Deck Import** - Import preconstructed Commander decks

## Commander Deck Rules

The deck builder automatically enforces Commander format rules:
- ✅ Only 1 copy of each card (except basic lands)
- ✅ Unlimited basic lands (Plains, Island, Swamp, Mountain, Forest, Wastes, Snow-Covered variants)
- ✅ Commander selection from legendary creatures
- ✅ Visual indicators for Commander decks
- ✅ Automatic validation when adding cards

## Installation

### Requirements
- Windows 7 SP1 or later
- Python 3.10 or higher
- Internet connection (for card database)

### Quick Install

1. Download `MTG_Archive_Setup.exe` from the [Releases](https://github.com/yourusername/mtg-archive/releases) page
2. Run the installer
3. Follow the installation wizard:
   - Python will be checked (download link provided if not installed)
   - Optional: Enter your Scryfall API key
   - Dependencies will be installed automatically
4. Launch from Start Menu or Desktop shortcut

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mtg-archive.git
cd mtg-archive
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

## Building the Installer

To build the Windows installer yourself:

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php)
2. Run the build script:
```batch
build_inno_installer.bat
```
3. Find the installer in `dist\MTG_Archive_Setup.exe`

See [INSTALLER_SETUP.md](INSTALLER_SETUP.md) for detailed instructions.

## Usage

### Collection Management
- Add cards manually or via OCR scanning
- View card details and images
- Track card quantities and conditions
- Search and filter your collection

### Deck Building
- Create new decks (Standard or Commander format)
- Drag cards from collection to deck
- Visual deck statistics
- Save and load decks
- Import preconstructed Commander decks

### Commander Decks
1. Create a new Commander deck
2. Select your commander (legendary creature)
3. Add cards - the system enforces the 1-copy rule automatically
4. Basic lands can be added in any quantity

## Project Structure

```
mtg-archive/
├── main.py                    # Application entry point
├── backend.py                 # API backend server
├── mtg_scanner_gui.py        # GUI and OCR functionality
├── enrich.py                 # Card data enrichment
├── requirements.txt          # Python dependencies
├── core/                     # Core modules
│   ├── collection_sql.py     # Database operations
│   ├── card_index.py         # Card indexing
│   ├── db.py                 # Database management
│   └── ...
├── web/                      # Web interface
│   ├── index.html
│   ├── deckbuilding.html
│   ├── style.css
│   └── assets/
└── MTG_Archive_Setup.iss     # Installer script
```

## Technologies

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite
- **OCR**: OCR.space API
- **Card Data**: Scryfall API
- **Installer**: Inno Setup

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter issues:
1. Ensure Python 3.10+ is installed and in PATH
2. Check that all dependencies are installed: `pip install -r requirements.txt`
3. For installer issues, see [INSTALLER_SETUP.md](INSTALLER_SETUP.md)
4. Open an issue on GitHub with details

## Acknowledgments

- Card data provided by [Scryfall](https://scryfall.com/)
- OCR powered by [OCR.space](https://ocr.space/)
- Magic: The Gathering is a trademark of Wizards of the Coast LLC

---

**Note**: This is an unofficial fan project and is not affiliated with or endorsed by Wizards of the Coast.
