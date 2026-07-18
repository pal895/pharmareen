from __future__ import annotations

import io
import re
from typing import Any

from PIL import Image, ImageEnhance, ImageOps


def scan_stock_fix_evidence_locally(image_bytes: bytes) -> dict[str, Any]:
    """Read one medicine package locally; never infer a stock count from the image."""
    import pytesseract

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        if max(image.size) > 1800:
            image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(image)
        enhanced = ImageEnhance.Sharpness(ImageOps.autocontrast(gray)).enhance(1.8)
        binary = enhanced.point(lambda value: 255 if value >= 155 else 0)
        readings = [
            pytesseract.image_to_string(enhanced, config="--psm 6"),
            pytesseract.image_to_string(enhanced, config="--psm 11"),
            pytesseract.image_to_string(binary, config="--psm 11"),
        ]

    visible_text = merge_ocr_readings(readings)
    compact = re.sub(r"\s+", " ", visible_text)
    strength = (re.search(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml)\b", compact, re.I) or [None, "", ""])
    batch = re.search(r"\b(?:batch|lot)\s*(?:no\.?|number|#|:)?\s*([A-Z0-9-]{3,})", compact, re.I)
    expiry = re.search(r"\b(?:exp(?:iry)?|expires?)\s*(?:date|:)?\s*(20\d{2})[-/. ](0?[1-9]|1[0-2])", compact, re.I)
    form = next((word for word in ("tablet", "capsule", "syrup", "cream", "ointment", "injection") if re.search(rf"\b{word}s?\b", compact, re.I)), "")
    return {
        "visible_text": visible_text,
        "strength": f"{strength[1]} {strength[2].lower()}" if strength[1] else "",
        "form": form,
        "unit": form,
        "batch": batch.group(1).upper() if batch else "",
        "expiry": f"{expiry.group(1)}-{int(expiry.group(2)):02d}" if expiry else "",
        "confidence": 0.9 if visible_text else 0.0,
        "ocr_engine": "local_tesseract",
        "ai_used": False,
    }


def merge_ocr_readings(readings: list[str]) -> str:
    """Keep complementary OCR evidence instead of discarding every pass but the longest."""
    unique_lines: list[str] = []
    seen: set[str] = set()
    for reading in readings:
        for raw_line in str(reading or "").splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            key = re.sub(r"[^a-z0-9]", "", line.lower())
            if not key or key in seen:
                continue
            seen.add(key)
            unique_lines.append(line)
    return "\n".join(unique_lines)
