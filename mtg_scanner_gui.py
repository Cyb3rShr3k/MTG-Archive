import sys
import re
import requests
import webbrowser
import json
import os
import difflib
import base64
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QTextEdit, QLabel, QFileDialog, QInputDialog, QComboBox, QDialog, QDialogButtonBox,
    QCheckBox, QProgressBar, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)
from PySide6.QtGui import QPixmap, QColor, QCursor
from PySide6.QtCore import Qt, QPoint

# --- Backend imports ---
from pathlib import Path
from core.collection_sql import insert_items, ensure_db
import json
from enrich import enrich_card
from core.image_utils import detect_tesseract_path

# Initialize DB
ensure_db(Path('collection.db'))

CONFIG_FILE = "config.json"
OCR_SPACE_API_KEY = "K89950406288957"

# ---------------- OCR & Preprocessing ----------------
def preprocess_image(image_path):
    try:
        img = Image.open(image_path)
        # Convert to RGB if needed (fixes PNG issues)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.convert("L")  # Convert to grayscale
        img = img.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2)
        return img
    except Exception as e:
        print(f"Image preprocessing error: {e}")
        return None

def extract_card_text(image_path, apply_enhancements=True, progress_callback=None):
    try:
        if progress_callback:
            progress_callback(10)
        
        img = preprocess_image(image_path) if apply_enhancements else Image.open(image_path)
        
        if img is None:
            print("Failed to preprocess image")
            if progress_callback:
                progress_callback(0)
            return None, None

        width, height = img.size
        crop_height = int(height * 0.10)
        img = img.crop((0, 0, width, crop_height))

        if progress_callback:
            progress_callback(50)
        
        # Convert to RGB before passing to Tesseract (fixes PNG compatibility issues)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        raw_text = pytesseract.image_to_string(img)
        if progress_callback:
            progress_callback(80)

        cleaned = re.sub(r"\{[A-Z0-9]+\}", "", raw_text)
        cleaned = re.sub(r'[^A-Za-z0-9,\-\s]', '', cleaned)
        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]

        card_name = lines[0] if lines else None
        if progress_callback:
            progress_callback(100)
        return card_name, raw_text
    except Exception as e:
        print(f"OCR error: {e}")
        if progress_callback:
            progress_callback(0)
        return None, None

def fuzzy_correct_name(name):
    try:
        url = f"https://api.scryfall.com/cards/named?fuzzy={name}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("name")
    except Exception as e:
        print(f"Scryfall fuzzy correction error: {e}")
    return None

def extract_card_metadata_with_ocr_api(image_path):
    """Use OCR.space API to extract text from card image, then enrich with Scryfall."""
    try:
        # OCR.space API endpoint
        url = "https://api.ocr.space/parse/image"
        
        with open(image_path, 'rb') as image_file:
            payload = {
                'apikey': OCR_SPACE_API_KEY,
                'language': 'eng',
                'isOverlayRequired': False,
                'detectOrientation': True,
                'scale': True,
                'OCREngine': 2  # Engine 2 is more accurate
            }
            
            files = {'file': image_file}
            
            response = requests.post(url, data=payload, files=files)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('IsErroredOnProcessing'):
                    error_msg = result.get('ErrorMessage', ['Unknown error'])[0]
                    print(f"OCR.space API error: {error_msg}")
                    return {"error": "ocr_processing_error", "message": error_msg}
                
                # Extract text from OCR result
                parsed_text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                
                if not parsed_text:
                    return {"error": "no_text", "message": "No text detected in image"}
                
                # Extract card name from the first lines
                lines = [line.strip() for line in parsed_text.split('\n') if line.strip()]
                card_name = lines[0] if lines else None
                
                if not card_name:
                    return {"error": "no_card_name", "message": "Could not extract card name"}
                
                # Clean card name
                card_name = re.sub(r'[^A-Za-z0-9,\-\s\']', '', card_name).strip()
                
                # Try to get full metadata from Scryfall using the card name
                try:
                    scryfall_url = f"https://api.scryfall.com/cards/named?fuzzy={card_name}"
                    scryfall_response = requests.get(scryfall_url)
                    
                    if scryfall_response.status_code == 200:
                        scryfall_data = scryfall_response.json()
                        
                        # Build comprehensive metadata
                        metadata = {
                            "card_name": scryfall_data.get("name", card_name),
                            "mana_cost": scryfall_data.get("mana_cost", "N/A"),
                            "type_line": scryfall_data.get("type_line", "N/A"),
                            "oracle_text": scryfall_data.get("oracle_text", "N/A"),
                            "power": scryfall_data.get("power"),
                            "toughness": scryfall_data.get("toughness"),
                            "artist": scryfall_data.get("artist", "N/A"),
                            "set_name": scryfall_data.get("set_name", "N/A"),
                            "collector_number": scryfall_data.get("collector_number", "N/A"),
                            "rarity": scryfall_data.get("rarity", "N/A"),
                            "ocr_text": parsed_text,
                            "source": "OCR.space + Scryfall"
                        }
                        
                        return metadata
                    else:
                        # Return OCR text only if Scryfall fails
                        return {
                            "card_name": card_name,
                            "ocr_text": parsed_text,
                            "source": "OCR.space only",
                            "note": "Could not enrich with Scryfall data"
                        }
                        
                except Exception as scryfall_error:
                    print(f"Scryfall enrichment error: {scryfall_error}")
                    return {
                        "card_name": card_name,
                        "ocr_text": parsed_text,
                        "source": "OCR.space only",
                        "error": "scryfall_failed"
                    }
            else:
                return {"error": "api_error", "message": f"API returned status {response.status_code}"}
                
    except Exception as e:
        print(f"OCR.space API error: {e}")
        return {"error": "exception", "message": str(e)}









# ---------------- Main App ----------------
class MTGScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MTG Card Image Processor")
        self.setGeometry(200, 200, 800, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Cinzel', serif;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 10px;
                font-family: 'Cinzel', serif;
                font-size: 11pt;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QTextEdit {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
            QProgressBar {
                background-color: #3e3e42;
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                font-family: 'Cinzel', serif;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
                border-radius: 3px;
            }
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                gridline-color: #3e3e42;
                font-family: 'Cinzel', serif;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #094771;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #3e3e42;
                font-family: 'Cinzel', serif;
                font-weight: bold;
            }
        """)

        self.status_label = QLabel("Ready - Load images to process", self)
        self.status_label.setAlignment(Qt.AlignCenter)

        self.load_button = QPushButton("📂 Load Single Image")
        self.load_folder_button = QPushButton("📁 Load Folder (Batch Process)")
        self.ocr_api_button = QPushButton("🚀 Smart OCR (OCR.space + Scryfall)")
        self.clear_button = QPushButton("🗑️ Clear All Images")

        # Table for batch file view with file size - ALWAYS visible
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels(["Filename", "Size", "OCR Status", "Card Name", "DB Status"])
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.itemEntered.connect(self.on_table_hover)
        self.file_table.viewport().installEventFilter(self)  # Install event filter to detect mouse leave
        self.file_table.setMouseTracking(True)
        self.file_table.setMinimumHeight(200)

        # Hover preview tooltip
        self.hover_preview = QLabel(self)
        self.hover_preview.setWindowFlags(Qt.ToolTip)
        self.hover_preview.setStyleSheet("border: 2px solid #007acc; background-color: #1e1e1e;")
        self.hover_preview.hide()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.load_button)
        layout.addWidget(self.load_folder_button)
        layout.addWidget(self.file_table)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.ocr_api_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.output_text)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.load_button.clicked.connect(self.load_image)
        self.load_folder_button.clicked.connect(self.load_folder)
        self.ocr_api_button.clicked.connect(self.extract_with_ocr_api)
        self.clear_button.clicked.connect(self.clear_all_images)

        self.last_image = None
        self.last_card_name = None
        self.last_ocr_api_data = None
        self.current_folder_images = []
        self.current_image_index = 0

    def clear_all_images(self):
        """Clear all loaded images from the table and reset state."""
        self.file_table.setRowCount(0)
        self.current_folder_images = []
        self.current_image_index = 0
        self.progress_bar.setValue(0)
        self.output_text.append("🗑️ Cleared all loaded images")
        self.status_label.setText("Ready - Load images to process")

    def update_image_preview(self, image_path):
        pixmap = QPixmap(image_path)
        if pixmap.width() > 400:
            pixmap = pixmap.scaled(400, 200, Qt.KeepAspectRatio)
        self.image_preview.setPixmap(pixmap)



    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Card Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            # Add to batch list
            self.current_folder_images.append(file_path)
            
            # Add row to table
            row_idx = self.file_table.rowCount()
            self.file_table.setRowCount(row_idx + 1)
            
            filename_item = QTableWidgetItem(os.path.basename(file_path))
            filename_item.setData(Qt.UserRole, file_path)  # Store full path
            
            # Get file size
            file_size = os.path.getsize(file_path)
            size_kb = file_size / 1024
            size_mb = size_kb / 1024
            if size_mb >= 1:
                size_str = f"{size_mb:.2f} MB"
            else:
                size_str = f"{size_kb:.1f} KB"
            size_item = QTableWidgetItem(size_str)
            
            ocr_status_item = QTableWidgetItem("⏳ Pending")
            card_name_item = QTableWidgetItem("-")
            db_status_item = QTableWidgetItem("⏳ Pending")
            
            self.file_table.setItem(row_idx, 0, filename_item)
            self.file_table.setItem(row_idx, 1, size_item)
            self.file_table.setItem(row_idx, 2, ocr_status_item)
            self.file_table.setItem(row_idx, 3, card_name_item)
            self.file_table.setItem(row_idx, 4, db_status_item)
            
            self.output_text.append(f"Loaded image: {os.path.basename(file_path)} ({size_str})")
            self.status_label.setText(f"{len(self.current_folder_images)} image(s) loaded - Load more or click Smart OCR")

    def load_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder with Card Images")
        if folder_path:
            # Find all image files in folder
            import glob
            image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']
            new_images = []
            for ext in image_extensions:
                new_images.extend(glob.glob(os.path.join(folder_path, ext)))
            
            # Remove duplicates (case-insensitive check)
            new_images = list(set(new_images))
            new_images.sort()  # Sort for consistent ordering
            
            if new_images:
                # Add to existing list
                start_idx = len(self.current_folder_images)
                self.current_folder_images.extend(new_images)
                
                # Add rows to table
                for img_path in new_images:
                    row_idx = self.file_table.rowCount()
                    self.file_table.setRowCount(row_idx + 1)
                    
                    filename_item = QTableWidgetItem(os.path.basename(img_path))
                    filename_item.setData(Qt.UserRole, img_path)  # Store full path
                    
                    # Get file size
                    file_size = os.path.getsize(img_path)
                    size_kb = file_size / 1024
                    size_mb = size_kb / 1024
                    if size_mb >= 1:
                        size_str = f"{size_mb:.2f} MB"
                    else:
                        size_str = f"{size_kb:.1f} KB"
                    size_item = QTableWidgetItem(size_str)
                    
                    ocr_status_item = QTableWidgetItem("⏳ Pending")
                    card_name_item = QTableWidgetItem("-")
                    db_status_item = QTableWidgetItem("⏳ Pending")
                    
                    self.file_table.setItem(row_idx, 0, filename_item)
                    self.file_table.setItem(row_idx, 1, size_item)
                    self.file_table.setItem(row_idx, 2, ocr_status_item)
                    self.file_table.setItem(row_idx, 3, card_name_item)
                    self.file_table.setItem(row_idx, 4, db_status_item)
                
                self.output_text.append(f"📁 Loaded {len(new_images)} images from folder")
                self.output_text.append("Ready to process. Click Smart OCR to begin batch processing.")
                self.status_label.setText(f"{len(self.current_folder_images)} total image(s) - Click Smart OCR to start")
            else:
                self.output_text.append("No image files found in selected folder")
                self.status_label.setText("No images found")

    def on_table_hover(self, item):
        """Show image preview when hovering over table row."""
        row = item.row()
        img_path = self.file_table.item(row, 0).data(Qt.UserRole)
        
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            # Scale to reasonable preview size
            pixmap = pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.hover_preview.setPixmap(pixmap)
            self.hover_preview.adjustSize()
            
            # Position near cursor using QCursor.pos()
            cursor_pos = QCursor.pos()
            self.hover_preview.move(cursor_pos.x() + 20, cursor_pos.y() + 20)
            self.hover_preview.show()
        else:
            self.hover_preview.hide()

    def eventFilter(self, obj, event):
        """Event filter to hide hover preview when mouse leaves table."""
        if obj == self.file_table.viewport():
            if event.type() == event.Type.Leave:
                self.hover_preview.hide()
        return super().eventFilter(obj, event)

    def extract_with_ocr_api(self):
        # Check if there are any images to process
        if not self.current_folder_images:
            self.output_text.append("No images loaded for OCR extraction!")
            return
        
        # Batch mode - process all images
        total = len(self.current_folder_images)
        skipped_files = []  # Track files skipped due to size
        self.output_text.append(f"\n🚀 Starting batch processing of {total} images...\n")
        self.output_text.append("─" * 50)
        
        for idx, img_path in enumerate(self.current_folder_images):
            self.current_image_index = idx
            self.last_image = img_path
            
            # Check file size (skip if over 1MB)
            file_size = os.path.getsize(img_path)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 1.0:
                # Skip this file
                filename = os.path.basename(img_path)
                skipped_files.append(f"{filename} ({file_size_mb:.2f} MB)")
                
                ocr_item = self.file_table.item(idx, 2)
                if ocr_item:
                    ocr_item.setText("⚠️ Skipped")
                card_item = self.file_table.item(idx, 3)
                if card_item:
                    card_item.setText("File too large")
                db_item = self.file_table.item(idx, 4)
                if db_item:
                    db_item.setText("-")
                
                self.output_text.append(f"\n[{idx + 1}/{total}] ⚠️ Skipped (too large): {filename}")
                
                # Update progress
                progress = int(((idx + 1) / total) * 100)
                self.progress_bar.setValue(progress)
                QApplication.processEvents()
                continue
            
            # Update table status
            ocr_status_item = self.file_table.item(idx, 2)
            if ocr_status_item:
                ocr_status_item.setText("⏳ Processing...")
            QApplication.processEvents()  # Update UI
            
            # Update progress
            progress = int((idx / total) * 100)
            self.progress_bar.setValue(progress)
            self.status_label.setText(f"Processing {idx + 1}/{total}: {os.path.basename(img_path)}")
            
            self.output_text.append(f"\n[{idx + 1}/{total}] Processing: {os.path.basename(img_path)}")
            
            metadata = extract_card_metadata_with_ocr_api(img_path)
            
            if metadata and not metadata.get('error'):
                card_name = metadata.get("card_name", "Unknown")
                
                ocr_item = self.file_table.item(idx, 2)
                if ocr_item:
                    ocr_item.setText("✅ Done")
                name_item = self.file_table.item(idx, 3)
                if name_item:
                    name_item.setText(card_name)
                
                self.output_text.append(f"   ✅ Identified: {card_name}")
                
                # Insert into database
                try:
                    db_status_item = self.file_table.item(idx, 4)
                    if db_status_item:
                        db_status_item.setText("💾 Saving...")
                    QApplication.processEvents()  # Update UI
                    
                    card_item = {
                        'name': card_name,
                        'set': metadata.get('set', ''),
                        'number': metadata.get('collector_number', ''),
                        'colors': metadata.get('colors', []),
                        'types': metadata.get('type_line', '').split(' — ')[0].split() if metadata.get('type_line') else [],
                        'cmc': metadata.get('cmc'),
                        'power': metadata.get('power'),
                        'toughness': metadata.get('toughness'),
                        'text': metadata.get('oracle_text', ''),
                        'image_path': None,
                        'image_url': metadata.get('image_uris', {}).get('normal') if isinstance(metadata.get('image_uris'), dict) else None,
                        'source': ''  # Blank source for scanner-imported cards
                    }
                    insert_items(Path('collection.db'), [card_item])
                    
                    db_item = self.file_table.item(idx, 4)
                    if db_item:
                        db_item.setText("✅ Saved")
                    self.output_text.append(f"   💾 Saved to database")
                except Exception as db_error:
                    db_item = self.file_table.item(idx, 4)
                    if db_item:
                        db_item.setText("❌ Error")
                    self.output_text.append(f"   ⚠️ DB error: {db_error}")
            else:
                error_msg = metadata.get('message', 'Unknown error') if metadata else 'No response'
                
                ocr_item = self.file_table.item(idx, 2)
                if ocr_item:
                    ocr_item.setText("❌ Failed")
                name_item = self.file_table.item(idx, 3)
                if name_item:
                    name_item.setText(f"Error: {error_msg[:30]}")
                db_item = self.file_table.item(idx, 4)
                if db_item:
                    db_item.setText("-")
                
                self.output_text.append(f"   ❌ Failed: {error_msg}")
            
            QApplication.processEvents()  # Update UI
        
        self.progress_bar.setValue(100)
        self.output_text.append("\n" + "─" * 50)
        self.output_text.append("🎉 Batch processing complete!")
        
        # Report skipped files
        if skipped_files:
            self.output_text.append(f"\n⚠️ {len(skipped_files)} file(s) skipped due to file size > 1MB:")
            for skipped in skipped_files:
                self.output_text.append(f"   • {skipped}")
            self.output_text.append("\nPlease reduce image file sizes and try again.")
            self.status_label.setText(f"✅ Completed - {len(skipped_files)} skipped")
        else:
            self.status_label.setText(f"✅ Completed all {total} images")

    def display_metadata(self, metadata):
        """Display extracted metadata in output box."""
        self.output_text.append("\n✅ OCR.space Extraction Results:")
        self.output_text.append(f"Card Name: {metadata.get('card_name', 'N/A')}")
        self.output_text.append(f"Mana Cost: {metadata.get('mana_cost', 'N/A')}")
        self.output_text.append(f"Type: {metadata.get('type_line', 'N/A')}")
        self.output_text.append(f"Oracle Text: {metadata.get('oracle_text', 'N/A')}")
        
        if metadata.get('power') and metadata.get('toughness'):
            self.output_text.append(f"P/T: {metadata.get('power')}/{metadata.get('toughness')}")
        
        self.output_text.append(f"Artist: {metadata.get('artist', 'N/A')}")
        self.output_text.append(f"Set: {metadata.get('set_name', 'N/A')}")
        self.output_text.append(f"Collector #: {metadata.get('collector_number', 'N/A')}")
        
        if metadata.get('rarity'):
            self.output_text.append(f"Rarity: {metadata.get('rarity', 'N/A')}")
        
        self.output_text.append(f"\n📊 Data source: {metadata.get('source', 'OCR.space')}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MTGScannerApp()
    window.show()
    sys.exit(app.exec())