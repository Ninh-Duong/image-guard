"""
profiling/visual_analyzer.py - Multi-Signal Visual & Text Composition Analyzer.
Lightweight visual intelligence engine.
Uses RapidOCR (already installed on CPU via ONNX Runtime) and pure NumPy color heuristics
to detect Billboards, Screenshots, Receipts/Documents, and Sunset/Sky when physical COCO objects are absent.
"""
from typing import Dict, Any, List, Optional
import re
import numpy as np
from PIL import Image

# Lazy singleton for RapidOCR
_ocr_engine = None


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except Exception:
            _ocr_engine = False
    return _ocr_engine if _ocr_engine is not False else None


class VisualAnalyzer:
    """Extracts non-object visual and textual cues: Billboards, Screenshots, Documents, Sunsets."""

    COMMERCIAL_KEYWORDS = {
        "cong nghiep", "cong ty", "quang cao", "bien quang cao", "thi cong",
        "hotline", "tel", "lien he", "dich vu", "website", "bourbon",
        "industrial", "garden", "billboard", "advertising", "company", "corp"
    }

    DOCUMENT_KEYWORDS = {
        "hoa don", "thanh toan", "tong tien", "receipt", "bill", "invoice",
        "vnd", "chuyen khoan", "ngan hang", "so tien", "thue", "vat"
    }

    @classmethod
    def analyze(cls, img: Image.Image) -> Dict[str, Any]:
        """
        Runs multi-signal analysis:
        1. Aspect ratio analysis (Screenshots)
        2. Color warmth analysis (Sunsets)
        3. OCR text spotting (Billboards, Advertisements, Documents)
        """
        w, h = img.size
        aspect_ratio = round(h / w if w > 0 else 1.0, 2)
        signals: Dict[str, Any] = {
            "aspect_ratio": aspect_ratio,
            "is_screenshot": False,
            "is_document": False,
            "is_billboard": False,
            "is_sunset": False,
            "extracted_keywords": [],
            "raw_text": "",
        }

        # 1. Color Warmth & Sunset Detection (pure NumPy, 0.5ms)
        try:
            thumb = img.resize((64, 64)).convert("RGB")
            arr = np.array(thumb, dtype=float)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            # Sunset: high red/orange in upper half, red > blue * 1.4
            top_r = r[:32, :]
            top_b = b[:32, :]
            warmth = np.mean(top_r) / (np.mean(top_b) + 1.0)
            if warmth > 1.4 and np.mean(top_r) > 110:
                signals["is_sunset"] = True
        except Exception:
            pass

        # 2. Aspect Ratio heuristic for phone screenshots (9:16 ~ 1.78, 19.5:9 ~ 2.16)
        if aspect_ratio >= 1.70:
            signals["is_screenshot"] = True

        # 3. Text Spotting via RapidOCR (Only ran when needed)
        ocr = _get_ocr()
        if ocr:
            try:
                # Downsample large images for fast text detection
                ocr_img = img
                if max(w, h) > 1024:
                    scale = 1024.0 / max(w, h)
                    ocr_img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)

                results, _ = ocr(np.array(ocr_img))
                if results:
                    lines = [item[1].strip() for item in results if len(item) > 1 and item[1].strip()]
                    full_text = " ".join(lines)
                    text_lower = full_text.lower()
                    signals["raw_text"] = full_text

                    # Extract domains like .com, .vn, www.
                    has_domain = bool(re.search(r'(www\.|https?://|\.(com|vn|net|org|edu))', text_lower))
                    has_phone = bool(re.search(r'(\b0\d{9,10}\b|\b1900\b|\b1800\b|\btel\b)', text_lower))

                    # Check commercial keywords
                    found_comm = [kw for kw in cls.COMMERCIAL_KEYWORDS if kw in text_lower]
                    found_doc = [kw for kw in cls.DOCUMENT_KEYWORDS if kw in text_lower]

                    signals["extracted_keywords"] = found_comm + found_doc

                    if has_domain or has_phone or len(found_comm) >= 1 or "bourbon" in text_lower:
                        signals["is_billboard"] = True
                        signals["is_screenshot"] = False

                    if len(found_doc) >= 1:
                        signals["is_document"] = True
                        signals["is_billboard"] = False

            except Exception:
                pass

        return signals
