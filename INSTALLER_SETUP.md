# MTG Archive - Inno Setup Installer

This installer uses Inno Setup to create a professional Windows installer for MTG Archive.

## Prerequisites

1. **Inno Setup 6** - Download and install from:
   - https://jrsoftware.org/isdl.php
   - Use default installation path: `C:\Program Files (x86)\Inno Setup 6\`

## Building the Installer

### Option 1: Using the Build Script (Recommended)

Simply double-click or run:
```batch
build_inno_installer.bat
```

The script will:
- Check if Inno Setup is installed
- Verify required files exist
- Compile the installer
- Report success/failure

### Option 2: Manual Compilation

1. Right-click `MTG_Archive_Setup.iss`
2. Select "Compile" from the context menu (if Inno Setup is installed)

Or use the Inno Setup IDE:
1. Open Inno Setup Compiler
2. File → Open → Select `MTG_Archive_Setup.iss`
3. Build → Compile

## Output

The compiled installer will be created at:
```
dist\MTG_Archive_Setup.exe
```

## Installer Features

The installer includes:

### ✅ Python Detection
- Checks for Python 3.10 or higher
- Provides download link if not found
- Validates Python installation

### ✅ API Key Configuration
- Custom wizard page for Scryfall API key
- Input validation
- Optional but recommended

### ✅ Automatic Dependency Installation
- Installs all required Python packages
- Uses pip install with requirements.txt
- Shows progress during installation

### ✅ Desktop Integration
- Creates Start Menu shortcuts
- Optional Desktop shortcut
- Creates launcher batch file with API key

### ✅ Professional Experience
- Modern wizard interface
- Progress indicators
- Proper uninstall support

## Distribution

Once built, `MTG_Archive_Setup.exe` can be distributed to users. The installer:
- Requires ~20MB disk space for installation
- Works on Windows 7 SP1 and later
- Does not require administrator rights (user install)

## Troubleshooting

### "Inno Setup not found"
- Install Inno Setup from https://jrsoftware.org/isdl.php
- Use default installation path
- Restart command prompt/PowerShell

### "MTG_Archive_Setup.iss not found"
- Run build script from project root directory
- Ensure .iss file is in the same folder

### Icon not found error
- Verify `assets/icons/mtg-color-wheel.png` exists
- Check file path in MTG_Archive_Setup.iss (line ~25)

## File Structure Required

The installer expects this structure:
```
PyWeb/
├── MTG_Archive_Setup.iss       # Inno Setup script
├── build_inno_installer.bat    # Build script
├── LICENSE.txt                  # License file
├── requirements.txt             # Python dependencies
├── main.py                      # Application entry point
├── backend.py
├── mtg_scanner_gui.py
├── core/                        # Core modules
│   ├── __init__.py
│   ├── collection_sql.py
│   └── ...
├── web/                         # Web assets
│   ├── index.html
│   ├── deckbuilding.html
│   └── ...
└── assets/                      # Assets and data
    ├── icons/
    │   └── mtg-color-wheel.png
    └── AllDeckFiles/
```

## Differences from PyInstaller

**Inno Setup Advantages:**
- ✅ More reliable than PyInstaller single-file executables
- ✅ Proper Windows installer experience
- ✅ Better dependency management
- ✅ Smaller download size
- ✅ Easier to update and maintain

**Inno Setup Approach:**
- Installs actual Python files (not bundled)
- Manages dependencies via pip
- Creates launcher scripts
- Better for Python applications with many dependencies

## Support

If users encounter issues:
1. Ensure Python 3.10+ is installed
2. Run installer as administrator (if permission issues)
3. Check Windows Defender/antivirus isn't blocking
4. Verify disk space available (~100MB for Python + dependencies)
