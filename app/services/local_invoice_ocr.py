from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
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
    table_items = extract_source_brain_invoice_items(visible_text)
    if table_items:
        extraction["items"] = table_items
        extraction["confidence"] = 0.88
        extraction["extraction_status"] = "needs_confirmation"
    else:
        extraction["items"] = []
        extraction["confidence"] = 0.0
        extraction["extraction_status"] = "needs_clearer_photo"
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


def extract_source_brain_invoice_items(text: str) -> list[dict[str, Any]]:
    medicines = load_source_brain_medicines()
    rows: list[dict[str, Any]] = []
    normalized_lines = [" ".join(line.replace("|", " ").split()) for line in text.splitlines()]
    for medicine in medicines:
        aliases = [medicine["name"], *medicine["aliases"]]
        matched_line = next((line for line in normalized_lines if any(_contains_name(line, alias) for alias in aliases)), "")
        if not matched_line:
            continue
        row = _parse_source_brain_row(matched_line, medicine)
        if row:
            rows.append(row)
    return rows[:50]


def load_source_brain_medicines() -> list[dict[str, Any]]:
    source_path = Path(__file__).resolve().parents[2] / "ms20-main-app" / "src" / "data" / "sourceMedicines.js"
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError:
        return []
    pattern = re.compile(r'medicine\("([^"]+)",\s*\[([^\]]*)\],\s*\[([^\]]*)\],\s*\[([^\]]*)\]\)')
    medicines: list[dict[str, Any]] = []
    for name, aliases, forms, units in pattern.findall(source):
        medicines.append({
            "name": name,
            "aliases": json.loads(f"[{aliases}]") if aliases.strip() else [],
            "forms": json.loads(f"[{forms}]") if forms.strip() else [],
            "units": json.loads(f"[{units}]") if units.strip() else [],
        })
    return medicines


def _contains_name(line: str, name: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", line, flags=re.I))


def _parse_source_brain_row(line: str, medicine: dict[str, Any]) -> dict[str, Any] | None:
    form = next((value for value in medicine["forms"] if _contains_name(line, value)), "")
    unit = next((value for value in medicine["units"] if _contains_name(line, value)), "")
    expiry_match = re.search(r"\b(20\d{2})[-/](0[1-9]|1[0-2])\b", line)
    batch_match = re.search(r"\b(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)+\b", line, flags=re.I)
    clean = line
    for value in [medicine["name"], *medicine["aliases"], form, unit]:
        if value:
            clean = re.sub(re.escape(value), " ", clean, count=1, flags=re.I)
    if expiry_match:
        clean = clean.replace(expiry_match.group(0), " ")
    if batch_match:
        clean = clean.replace(batch_match.group(0), " ")
    numbers = [value.replace(",", "") for value in re.findall(r"\b\d[\d,]*(?:\.\d{2})?\b", clean)]
    if not numbers:
        return None
    quantity = int(float(numbers[0]))
    if quantity <= 0 or quantity > 100000:
        return None
    unit_cost = float(numbers[1]) if len(numbers) > 1 else None
    line_total = float(numbers[2]) if len(numbers) > 2 else None
    return {
        "medicine_name": medicine["name"],
        "form": form,
        "unit": unit,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "line_total": line_total,
        "batch_number": batch_match.group(0) if batch_match else "",
        "expiry_date": expiry_match.group(0).replace("/", "-") if expiry_match else "",
        "confidence": 0.92 if form and unit and batch_match and expiry_match else 0.78,
    }


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
