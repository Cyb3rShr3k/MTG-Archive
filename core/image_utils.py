# core/image_utils.py
from pathlib import Path
from typing import Iterable, List
import shutil
import io
import os

try:
    import cv2  # optional
except Exception:
    cv2 = None


def import_images_to_folder(paths: Iterable[str], dest_dir: Path) -> List[Path]:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    copied: List[Path] = []
    for p in paths:
        src = Path(p)
        if src.is_file():
            target = dest / src.name
            try:
                shutil.copy2(src, target)
                copied.append(target)
            except Exception:
                # Ignore failures for now
                pass
    return copied


def _preprocess_for_ocr(p: Path):
    """Return a preprocessed PIL image for better OCR.
    Uses OpenCV if available to denoise, grayscale, resize, and threshold.
    Falls back to PIL-only conversion if cv2 is not available.
    """
    from PIL import Image, ImageOps
    try:
        if cv2 is None:
            im = Image.open(str(p)).convert('L')  # grayscale
            # Slight contrast boost
            im = ImageOps.autocontrast(im)
            # Upscale 1.5x for better character shapes
            w, h = im.size
            im = im.resize((int(w*1.5), int(h*1.5)))
            return im
        # Open with OpenCV
        import numpy as np
        img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            # Fallback to PIL
            return Image.open(str(p)).convert('L')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Denoise and enhance edges
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        # Adaptive threshold for varying lighting
        thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 10)
        # Upscale to help OCR
        thr = cv2.resize(thr, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        # Convert back to PIL
        from PIL import Image
        im = Image.fromarray(thr)
        return im
    except Exception:
        # Last resort: raw PIL
        return Image.open(str(p)).convert('L')


def try_ocr(image_path: Path) -> str:
    """Attempt OCR on the given image path using pytesseract if available.
    Returns extracted text or an empty string on failure/unavailability.
    """
    p = Path(image_path)
    try:
        from PIL import Image
        import pytesseract
        # Ensure tesseract.exe is reachable on Windows if not in PATH
        if os.name == 'nt':
            # Hard-pin to requested install path
            try:
                pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
            except Exception:
                pass
            import shutil as _shutil
            if not _shutil.which('tesseract'):
                # Common install locations
                candidates = [
                    r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
                    r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
                ]
                for c in candidates:
                    if Path(c).exists():
                        try:
                            pytesseract.pytesseract.tesseract_cmd = c
                            break
                        except Exception:
                            pass
        # Preprocess for better OCR and run
        im = _preprocess_for_ocr(p)
        if im.mode != 'RGB':
            im = im.convert('RGB')
        # Use a general layout mode suitable for blocks of text
        config = '--oem 3 --psm 6'
        text = pytesseract.image_to_string(im, config=config)
        return text or ''
    except Exception:
        return ''


def detect_tesseract_path() -> str:
    """Return the resolved path to tesseract.exe if found, else empty string.
    Checks current pytesseract config, PATH, and common install locations.
    """
    try:
        import pytesseract
        # If explicitly set
        cmd = getattr(pytesseract.pytesseract, 'tesseract_cmd', '') or ''
        if cmd and Path(cmd).exists():
            return str(Path(cmd))
        # Check PATH
        import shutil as _shutil
        found = _shutil.which('tesseract')
        if found:
            return str(Path(found))
        # Common Windows locations
        if os.name == 'nt':
            candidates = [
                r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
                r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
            ]
            for c in candidates:
                if Path(c).exists():
                    return c
    except Exception:
        pass
    return ''
