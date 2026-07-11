from __future__ import annotations

import hashlib
import io
import re
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from app.services.photo_intake import extract_supplier_invoice_from_text


def scan_invoice_locally(image_bytes: bytes) -> dict[str, Any]:
    fingerprint = hashlib.sha256(image_bytes).hexdigest()
    try:
        import pytesseract
    except ImportError:
        return _failed(fingerprint, "Local invoice reader is not installed.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("L")
            image.thumbnail((1800, 1800))
            image = ImageOps.autocontrast(image)
            image = ImageEnhance.Contrast(image).enhance(1.5)
            visible_text = pytesseract.image_to_string(image, config="--psm 6")
    except Exception:
        return _failed(fingerprint, "I could not read this photo. Try again in good light with the whole page visible.")

    extraction = extract_supplier_invoice_from_text(visible_text)
    table_items = extract_invoice_table_items(visible_text)
    if table_items:
        extraction["items"] = table_items
        extraction["confidence"] = 0.88
        extraction["extraction_status"] = "needs_confirmation"
    extraction.update({
        "fingerprint": fingerprint,
        "ai_used": False,
        "ocr_engine": "local_tesseract",
        "visible_text": visible_text[:8000],
    })
    if not extraction.get("items"):
        extraction["message"] = "I could not find clear medicine rows. Try a clearer photo."
    return extraction


def extract_invoice_table_items(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"^(?P<name>[A-Za-z][A-Za-z -]{2,35})\s+"
        r"(?P<form>cream|pessary|capsule|tablet|suspension|eye drops|ear drops|ointment|gel|injection|inhaler|syrup|solution)\s+"
        r"(?P<unit>tube|pessary|capsule|tablet|bottle|vial|ampoule|inhaler|strip|pack|box)\s+"
        r"(?P<qty>\d+)\s+(?P<cost>[\d,.]+)\s+(?P<total>[\d,.]+)\s+"
        r"(?P<batch>[A-Za-z0-9-]{3,24})\s+(?P<expiry>20\d{2}[-/]\d{2})$",
        flags=re.I,
    )
    for raw_line in text.splitlines():
        line = " ".join(raw_line.replace("|", " ").split())
        match = pattern.match(line)
        if not match:
            continue
        data = match.groupdict()
        rows.append({
            "medicine_name": data["name"].strip(),
            "form": data["form"].lower(),
            "unit": data["unit"].lower(),
            "quantity": int(data["qty"]),
            "unit_cost": float(data["cost"].replace(",", "")),
            "line_total": float(data["total"].replace(",", "")),
            "batch_number": data["batch"],
            "expiry_date": data["expiry"].replace("/", "-"),
            "confidence": 0.9,
        })
    return rows[:50]


def _failed(fingerprint: str, message: str) -> dict[str, Any]:
    return {
        "items": [],
        "confidence": 0.0,
        "extraction_status": "needs_clearer_photo",
        "fingerprint": fingerprint,
        "ai_used": False,
        "ocr_engine": "local_tesseract",
        "message": message,
    }
