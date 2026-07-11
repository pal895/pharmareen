from __future__ import annotations

import hashlib
import io
import json
import re
from difflib import SequenceMatcher
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
            threshold = image.point(lambda value: 255 if value > 165 else 0)
            ocr_texts = [
                pytesseract.image_to_string(image, config="--psm 4"),
                pytesseract.image_to_string(image, config="--psm 6"),
                pytesseract.image_to_string(threshold, config="--psm 6"),
            ]
            visible_text = max(ocr_texts, key=len, default="")
    except Exception:
        return _failed(fingerprint, "I could not read this photo. Try again in good light with the whole page visible.")

    combined_text = "\n".join(ocr_texts)
    extractions = [extract_supplier_invoice_from_text(text) for text in ocr_texts]
    extraction = extract_supplier_invoice_from_text(combined_text)
    extraction["supplier_name"] = _best_ocr_metadata_value(
        [item.get("supplier_name") for item in extractions],
        extraction.get("supplier_name"),
    )
    extraction["invoice_number"] = _best_ocr_metadata_value(
        [item.get("invoice_number") for item in extractions],
        extraction.get("invoice_number"),
    )
    table_items = merge_source_brain_invoice_items(ocr_texts)
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
    invoice_total = _invoice_total_from_text(combined_text)
    extracted_total = sum(float(item.get("line_total") or 0) for item in extraction.get("items") or [])
    extraction["invoice_total"] = invoice_total
    extraction["extracted_line_total"] = extracted_total
    extraction["complete"] = bool(
        extraction.get("items")
        and all(_row_has_required_invoice_fields(item) for item in extraction["items"])
        and (invoice_total is None or abs(invoice_total - extracted_total) < 0.01)
    )
    if not extraction.get("items"):
        extraction["message"] = "I could not find clear medicine rows. Try a clearer photo."
    return extraction


def merge_source_brain_invoice_items(texts: list[str]) -> list[dict[str, Any]]:
    """Merge complementary deterministic OCR passes without duplicating medicines."""
    candidates: dict[str, list[dict[str, Any]]] = {}
    for text in texts:
        for item in extract_source_brain_invoice_items(text):
            candidates.setdefault(str(item["medicine_name"]), []).append(item)
    return [_merge_item_candidates(items) for items in candidates.values()]


def _merge_item_candidates(items: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(items, key=_item_completeness, reverse=True)
    merged = dict(ranked[0])
    for field in ("form", "unit", "quantity", "unit_cost", "line_total", "batch_number", "expiry_date"):
        if merged.get(field) in (None, "", 0):
            merged[field] = next((item.get(field) for item in ranked if item.get(field) not in (None, "", 0)), merged.get(field))
    merged["confidence"] = max(float(item.get("confidence") or 0) for item in items)
    return merged


def _item_completeness(item: dict[str, Any]) -> tuple[int, float]:
    fields = ("form", "unit", "quantity", "unit_cost", "line_total", "batch_number", "expiry_date")
    return sum(item.get(field) not in (None, "", 0) for field in fields), float(item.get("confidence") or 0)


def _best_ocr_metadata_value(values: list[Any], fallback: Any = "") -> str:
    candidates = [" ".join(str(value).split()) for value in values if str(value or "").strip()]
    if not candidates:
        return str(fallback or "").strip()

    def quality(value: str) -> tuple[int, int, int]:
        isolated_letters = len(re.findall(r"\b[A-Za-z]\b", value))
        readable_words = len(re.findall(r"\b[A-Za-z]{3,}\b", value))
        return -isolated_letters, readable_words, len(value)

    return max(candidates, key=quality)


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
    used_medicines: set[str] = set()
    for line in normalized_lines:
        ranked = sorted(
            ((_medicine_line_score(line, medicine), medicine) for medicine in medicines),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, medicine = ranked[0]
        next_score = ranked[1][0] if len(ranked) > 1 else 0.0
        if best_score < 0.76 or best_score - next_score < 0.08 or medicine["name"] in used_medicines:
            continue
        row = _parse_source_brain_row(line, medicine)
        if row:
            rows.append(row)
            used_medicines.add(medicine["name"])
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


def _medicine_line_score(line: str, medicine: dict[str, Any]) -> float:
    words = re.findall(r"[A-Za-z]+", line.lower())
    if not words:
        return 0.0
    scores: list[float] = []
    for name in [medicine["name"], *medicine["aliases"]]:
        target_words = re.findall(r"[A-Za-z]+", name.lower())
        if not target_words:
            continue
        target = "".join(target_words)
        width = len(target_words)
        for start in range(min(3, len(words))):
            candidate = "".join(words[start:start + width])
            if candidate:
                scores.append(SequenceMatcher(None, target, candidate).ratio())
    return max(scores, default=0.0)


def _parse_source_brain_row(line: str, medicine: dict[str, Any]) -> dict[str, Any] | None:
    line = re.sub(r"(?<=\d)[—–_:](?=\d)", "-", line)
    form = _best_known_value(line, medicine["forms"])
    unit = _best_known_value(line, medicine["units"])
    expiry_match = re.search(r"\b(20\d{2})\s*[-/., ]\s*(0[1-9]|1[0-2])\b", line)
    batch_match = re.search(r"\b(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)+\b", line, flags=re.I)
    clean = line
    for value in [medicine["name"], *medicine["aliases"], form, unit]:
        if value:
            clean = re.sub(re.escape(value), " ", clean, count=1, flags=re.I)
    if expiry_match:
        clean = clean.replace(expiry_match.group(0), " ")
    if batch_match:
        clean = clean.replace(batch_match.group(0), " ")
    numbers = re.findall(r"\b\d[\d,]*(?:\.\d{2})?\b", clean)
    if not numbers:
        return None
    quantity = int(float(numbers[0].replace(",", "")))
    if quantity <= 0 or quantity > 100000:
        return None
    unit_cost = _ocr_money(numbers[1]) if len(numbers) > 1 else None
    line_total = _ocr_money(numbers[2]) if len(numbers) > 2 else None
    return {
        "medicine_name": medicine["name"],
        "form": form,
        "unit": unit,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "line_total": line_total,
        "batch_number": batch_match.group(0) if batch_match else "",
        "expiry_date": f"{expiry_match.group(1)}-{expiry_match.group(2)}" if expiry_match else "",
        "confidence": 0.92 if form and unit and batch_match and expiry_match else 0.78,
    }


def _ocr_money(token: str) -> float:
    compact = token.replace(",", "")
    value = float(compact)
    if "." not in compact and len(compact) >= 3 and compact.endswith("00"):
        return value / 100
    return value


def _best_known_value(line: str, values: list[str]) -> str:
    exact = next((value for value in values if _contains_name(line, value)), "")
    if exact:
        return exact
    singular_line = re.sub(r"\bdrops\b", "drop", line.lower())
    singular = next((value for value in values if _contains_name(singular_line, re.sub(r"\bdrops\b", "drop", value.lower()))), "")
    if singular:
        return singular
    words = re.findall(r"[A-Za-z]+", singular_line)
    ranked: list[tuple[float, str]] = []
    for value in values:
        target_words = re.findall(r"[A-Za-z]+", re.sub(r"\bdrops\b", "drop", value.lower()))
        width = len(target_words)
        target = "".join(target_words)
        score = max((SequenceMatcher(None, target, "".join(words[i:i + width])).ratio() for i in range(len(words))), default=0.0)
        ranked.append((score, value))
    ranked.sort(reverse=True)
    if ranked and ranked[0][0] >= 0.78 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.08):
        return ranked[0][1]
    return ""


def _invoice_total_from_text(text: str) -> float | None:
    match = re.search(r"invoice\s+total\D{0,20}(?:KES|KSH)?\s*([\d,]+(?:\.\d{2})?)", text, flags=re.I)
    return float(match.group(1).replace(",", "")) if match else None


def _row_has_required_invoice_fields(item: dict[str, Any]) -> bool:
    return all([
        item.get("medicine_name"),
        item.get("form"),
        item.get("unit"),
        item.get("quantity"),
        item.get("unit_cost") is not None,
        item.get("batch_number"),
        item.get("expiry_date"),
    ])


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
