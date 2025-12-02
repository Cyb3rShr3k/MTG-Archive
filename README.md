# MTG Archive

A web-based Magic: The Gathering card collection manager and deck builder with multiple import methods and user authentication.

## ✨ Features

- 📚 **Collection Management** - Add, search, and organize your Magic card collection
- 📤 **Multiple Import Methods**:
  - Manual entry with Scryfall integration
  - CSV bulk import for large collections
  - OCR scanning for card images
- 🎴 **Deck Building** - Create and manage multiple deck lists
  - Mana curve visualization
  - Preconstructed deck library
  - Commander format support
- 👤 **Multi-User Support** - User authentication with isolated collections
- 📊 **Card Database** - Integrated Scryfall card database integration
- 🎨 **Professional UI** - HTML5up Editorial template with responsive design
- 🌐 **Web-Based** - No installation required, runs in any browser

## 🚀 Quick Start

### Requirements
- Python 3.11 or higher
- pip (Python package manager)
- Modern web browser

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Cyb3rShr3k/MTG-Archive.git
   cd MTG-Archive
   ```

2. **Create virtual environment** (recommended)
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

5. **Open in browser**
   Navigate to: `http://localhost:5000`

## 📁 File Structure

```
├── main.py                 # Flask server entry point
├── backend.py              # Core API and collection methods
├── requirements.txt        # Python dependencies
├── Procfile               # Deployment config (Heroku/Render)
├── render.yaml            # Render deployment config
├── core/                  
│   ├── card_index.py      # Card search and indexing
│   ├── collection_sql.py  # SQLite database management
│   ├── user_auth.py       # User authentication
│   └── ...
├── web/                   # Frontend files
│   ├── index.html         # Dashboard
│   ├── login.html         # Login page
│   ├── register.html      # Registration
│   ├── card_addition.html # Card import
│   ├── deckbuilding.html  # Deck manager
│   ├── api.js             # API proxy
│   ├── shared-nav.js      # Navigation component
│   └── assets/            # Images, icons
└── HTML5up/               # Editorial template assets
```

## 📖 Usage

### Add Cards to Collection
1. Click "Add Cards" on dashboard
2. Choose import method:
   - **Manual**: Type card names (e.g., "3 Sol Ring")
   - **CSV**: Upload bulk data
   - **OCR**: Scan card images
3. Cards are validated against Scryfall database
4. View updated collection table

### Build Decks
1. Go to "Deck Building"
2. Create new deck or import precon
3. Search collection and add cards
4. View mana curve
5. Save deck list

### Create Account
1. Register on `/register` page
2. Login to access your personal collection
3. Each user has isolated data

## 🔗 API Endpoints

### Authentication
```
POST /api/register       - Create account
POST /api/login          - Login user
POST /api/logout         - Logout
GET  /api/current_user   - Get user info
```

### Collection
```
GET  /api/get_collection_items    - List cards
POST /api/add_card                - Add card
POST /api/add_card_with_metadata  - Add with Scryfall data
GET  /api/search_collection       - Search cards
```

### Decks
```
POST /api/create_deck        - Create deck
GET  /api/list_decks         - List decks
GET  /api/get_deck_cards     - Get deck contents
POST /api/update_deck        - Modify deck
DELETE /api/delete_deck      - Delete deck
GET  /api/get_precon_decks   - List precons
```

## 🌐 Deployment

### Render (Recommended)
1. Push to GitHub
2. Connect repo to [Render.com](https://render.com)
3. Deploy (auto-detected from `render.yaml`)

### Railway
1. Push to GitHub
2. Connect repo to [Railway.app](https://railway.app)
3. Deploy from dashboard

### Local Development
```bash
pip install flask-reload
python -m flask --app main run --reload
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

## Support the Project

If you find MTG Archive useful, consider supporting its development:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support%20Development-orange?style=for-the-badge&logo=buy-me-a-coffee)](https://www.buymeacoffee.com/yourusername)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue?style=for-the-badge&logo=paypal)](https://paypal.me/yourusername)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-red?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/yourusername)

Your support helps with:
- 🚀 Development of new features
- 🐛 Bug fixes and improvements
- 📚 Documentation and tutorials
- ☁️ Server costs for hosting services

Every contribution is appreciated and helps keep this project active!

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
#   G i t H u b   A c t i o n s   T e s t   -   2 0 2 5 - 1 2 - 0 2   1 0 : 0 5 : 3 1  
 