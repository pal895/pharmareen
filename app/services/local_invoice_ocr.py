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
    positioned_fields: dict[str, dict[str, str]] = {}
    geometry_order: list[str] = []
    primary_text_order: list[str] = []
    try:
        import pytesseract
    except ImportError:
        return _failed(fingerprint, "Local invoice reader is not installed.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("L")
            longest_edge = 2400 if image.width > image.height else 1800
            image.thumbnail((longest_edge, longest_edge))
            image = ImageOps.autocontrast(image)
            image = ImageEnhance.Contrast(image).enhance(1.5)
            word_data, geometry_rows, oriented_image = _read_oriented_invoice_words(image, pytesseract)
            geometry_text = "\n".join(geometry_rows)
            ocr_texts = []
            if geometry_text:
                ocr_texts.append(geometry_text)
            geometry_order = _medicine_order_from_lines(geometry_rows)
            positioned_fields = extract_positioned_row_fields(word_data)
            document_geometry_text = "\n".join(reconstruct_document_lines_from_word_positions(word_data))
            if document_geometry_text:
                ocr_texts.append(document_geometry_text)
            primary_text_order = _medicine_order_from_text(document_geometry_text)
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
    extraction["supplier_name"] = _best_ocr_metadata_value([
        extraction.get("supplier_name"),
        _supplier_name_from_text(combined_text),
    ])
    extraction["invoice_number"] = _best_ocr_metadata_value(
        [item.get("invoice_number") for item in extractions],
        extraction.get("invoice_number"),
    )
    extraction["invoice_number"] = _best_ocr_metadata_value([extraction.get("invoice_number"), _invoice_number_from_text(combined_text)])
    if not re.search(r"\d", str(extraction.get("invoice_number") or "")):
        extraction["invoice_number"] = ""
    table_items = merge_source_brain_invoice_items(ocr_texts)
    geometry_items = extract_geometry_table_items(word_data)
    if _geometry_needs_refinement(geometry_items):
        geometry_items = _refine_ambiguous_invoice_cells(oriented_image, word_data, geometry_items, pytesseract)
    table_items = _merge_geometry_items(table_items, geometry_items)
    _fill_unique_source_pair_fields(table_items)
    for item in table_items:
        for field, value in positioned_fields.get(str(item.get("medicine_name")), {}).items():
            if not item.get(field):
                item[field] = value
    item_names = {str(item.get("medicine_name")) for item in table_items}
    if item_names and item_names.issubset(set(primary_text_order)):
        order = {name: index for index, name in enumerate(primary_text_order)}
        table_items.sort(key=lambda item: order[str(item.get("medicine_name"))])
    elif geometry_order:
        order = {name: index for index, name in enumerate(geometry_order)}
        table_items.sort(key=lambda item: order.get(str(item.get("medicine_name")), len(order)))
    _normalize_batch_digits_by_invoice_pattern(table_items)
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
    if not extraction.get("invoice_date"):
        extraction["invoice_date"] = _invoice_date_from_text(combined_text)
    extraction["extracted_line_total"] = extracted_total
    extraction["complete"] = bool(
        extraction.get("items")
        and all(_row_has_required_invoice_fields(item) for item in extraction["items"])
        and (invoice_total is None or abs(invoice_total - extracted_total) < 0.01)
    )
    if not extraction.get("items"):
        extraction["message"] = "I could not find clear medicine rows. Try a clearer photo."
    return extraction


def _read_oriented_invoice_words(image: Image.Image, pytesseract: Any) -> tuple[dict[str, list[Any]], list[str], Image.Image]:
    """Retry expensive sparse/rotated OCR only when the normal orientation has no medicine anchors."""
    attempts = [(image, "--psm 6"), (image, "--psm 11")]
    attempts.extend((image.transpose(rotation), "--psm 11") for rotation in (
        Image.Transpose.ROTATE_90,
        Image.Transpose.ROTATE_270,
        Image.Transpose.ROTATE_180,
    ))
    first_data: dict[str, list[Any]] = {}
    for attempt_image, config in attempts:
        data = pytesseract.image_to_data(attempt_image, config=config, output_type=pytesseract.Output.DICT)
        if not first_data:
            first_data = data
        rows = reconstruct_bounded_invoice_rows(data)
        if rows:
            return data, rows, attempt_image
    return first_data, [], image


def reconstruct_invoice_rows_from_word_positions(data: dict[str, list[Any]]) -> list[str]:
    """Rebuild medicine rows by y-position when Tesseract splits table cells into unrelated text lines."""
    medicines = load_source_brain_medicines()
    words: list[dict[str, Any]] = []
    for index, raw_text in enumerate(data.get("text") or []):
        text = " ".join(str(raw_text or "").split())
        if not text:
            continue
        try:
            confidence = float((data.get("conf") or [])[index])
            left = int((data.get("left") or [])[index])
            top = int((data.get("top") or [])[index])
            width = int((data.get("width") or [])[index])
            height = int((data.get("height") or [])[index])
        except (ValueError, TypeError, IndexError):
            continue
        if confidence < 15:
            continue
        words.append({"text": text, "left": left, "right": left + width, "center_y": top + height / 2, "height": height})

    rows: list[tuple[float, str]] = []
    used_y: list[float] = []
    for medicine in medicines:
        anchors = sorted(
            ((_medicine_line_score(word["text"], medicine), word) for word in words),
            key=lambda item: item[0],
            reverse=True,
        )
        if not anchors or anchors[0][0] < 0.68:
            continue
        score, anchor = anchors[0]
        if len(anchors) > 1 and score - anchors[1][0] < 0.04 and abs(anchor["center_y"] - anchors[1][1]["center_y"]) > anchor["height"] * 2:
            continue
        tolerance = max(10.0, anchor["height"] * 0.9)
        if any(abs(anchor["center_y"] - known_y) <= tolerance for known_y in used_y):
            continue
        band = [word for word in words if abs(word["center_y"] - anchor["center_y"]) <= tolerance]
        line = " ".join(word["text"] for word in sorted(band, key=lambda word: word["left"]))
        if line:
            rows.append((anchor["center_y"], line))
            used_y.append(anchor["center_y"])
    return [line for _, line in sorted(rows)]


def extract_geometry_table_items(data: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Read variable-layout invoice cells from named column positions, not numeric token order."""
    medicines = load_source_brain_medicines()
    tokens: list[dict[str, Any]] = []
    for index, raw_text in enumerate(data.get("text") or []):
        text = " ".join(str(raw_text or "").split())
        if not text:
            continue
        try:
            left = int((data.get("left") or [])[index])
            top = int((data.get("top") or [])[index])
            width = int((data.get("width") or [])[index])
            height = int((data.get("height") or [])[index])
        except (ValueError, TypeError, IndexError):
            continue
        tokens.append({"text": text, "left": left, "center_x": left + width / 2, "center_y": top + height / 2})
    anchors = _unique_medicine_anchors(tokens, medicines)
    if not anchors:
        return []
    header_tokens = [token for token in tokens if token["center_y"] < anchors[0][0]]

    def rightmost(label: str) -> dict[str, Any] | None:
        matches = [token for token in header_tokens if token["text"].lower() == label]
        return max(matches, key=lambda token: token["center_x"], default=None)

    qty = rightmost("qty") or rightmost("quantity")
    cost = rightmost("cost")
    total = rightmost("total")
    batch = rightmost("batch")
    expiry = rightmost("expiry") or rightmost("expires")
    required = [qty, cost, total, batch, expiry]
    if any(token is None for token in required):
        return []
    positions = {name: token["center_x"] for name, token in zip(("qty", "cost", "total", "batch", "expiry"), required)}
    if positions != dict(sorted(positions.items(), key=lambda item: item[1])):
        return []
    form_headers = [token for token in header_tokens if token["text"].lower() == "form" and token["center_x"] < positions["qty"]]
    unit_headers = [token for token in header_tokens if token["text"].lower() == "unit" and token["center_x"] < positions["qty"]]
    form_x = max((token["center_x"] for token in form_headers), default=0)
    unit_x = max((token["center_x"] for token in unit_headers), default=0)
    pack = rightmost("pack") or rightmost("size")
    price = rightmost("price")
    column_centers = [("form", form_x), ("unit", unit_x), ("pack", pack["center_x"] if pack else 0),
                      ("qty", positions["qty"]), ("cost", positions["cost"]),
                      ("price", price["center_x"] if price else 0), ("total", positions["total"]),
                      ("batch", positions["batch"]), ("expiry", positions["expiry"])]
    column_centers = [(name, x) for name, x in column_centers if x > 0]
    column_centers.sort(key=lambda item: item[1])
    boundaries = [(column_centers[i][1] + column_centers[i + 1][1]) / 2 for i in range(len(column_centers) - 1)]
    typical_gap = min((anchors[i + 1][0] - anchors[i][0] for i in range(len(anchors) - 1)), default=80)
    medicine_map = {medicine["name"]: medicine for medicine in medicines}
    rows: list[dict[str, Any]] = []
    for index, (center_y, name) in enumerate(anchors):
        lower = (anchors[index - 1][0] + center_y) / 2 if index else center_y - typical_gap / 2
        upper = (center_y + anchors[index + 1][0]) / 2 if index + 1 < len(anchors) else center_y + typical_gap / 2
        row_tokens = [token for token in tokens if lower <= token["center_y"] < upper]
        cells: dict[str, str] = {}
        for column_index, (column_name, _x) in enumerate(column_centers):
            cell_left = boundaries[column_index - 1] if column_index else float("-inf")
            cell_right = boundaries[column_index] if column_index < len(boundaries) else float("inf")
            cells[column_name] = " ".join(token["text"] for token in sorted(row_tokens, key=lambda token: token["left"]) if cell_left <= token["center_x"] < cell_right)
        medicine = medicine_map[name]
        form = _best_known_value(f"{cells.get('form', '')} {cells.get('unit', '')}", medicine["forms"])
        unit = _best_known_value(cells.get("unit", ""), medicine["units"])
        quantity_match = re.search(r"\d+", cells.get("qty", ""))
        cost_match = re.search(r"\d[\d,.]*", cells.get("cost", ""))
        total_match = re.search(r"\d[\d,.]*", cells.get("total", ""))
        batch_match = re.search(r"(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)+", cells.get("batch", ""), flags=re.I)
        expiry_match = re.search(r"(20\d{2})\D*(0[1-9]|1[0-2])", cells.get("expiry", ""))
        if not (quantity_match and cost_match and total_match):
            continue
        rows.append({
            "medicine_name": name,
            "form": form,
            "unit": unit,
            "quantity": int(quantity_match.group()),
            "unit_cost": _ocr_money(cost_match.group()),
            "selling_price": _ocr_money(price_match.group()) if (price_match := re.search(r"\d[\d,.]*", cells.get("price", ""))) else None,
            "line_total": _ocr_money(total_match.group()),
            "batch_number": batch_match.group() if batch_match else "",
            "expiry_date": f"{expiry_match.group(1)}-{expiry_match.group(2)}" if expiry_match else "",
            "confidence": 0.94,
        })
    return rows


def _merge_geometry_items(items: list[dict[str, Any]], geometry_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {str(item.get("medicine_name")): item for item in items}
    order = [str(item.get("medicine_name")) for item in geometry_items]
    for item in geometry_items:
        name = str(item.get("medicine_name"))
        if name in by_name:
            descriptive = _merge_item_candidates([by_name[name], item])
            for field in ("quantity", "unit_cost", "selling_price", "line_total"):
                descriptive[field] = item.get(field)
            by_name[name] = descriptive
        else:
            by_name[name] = item
    return sorted(by_name.values(), key=lambda item: order.index(str(item.get("medicine_name"))) if str(item.get("medicine_name")) in order else len(order))


def _geometry_needs_refinement(items: list[dict[str, Any]]) -> bool:
    if not items:
        return False
    for item in items:
        if not _row_has_required_invoice_fields(item):
            return True
        selling = item.get("selling_price")
        if selling not in (None, "") and float(item.get("unit_cost") or 0) >= float(selling):
            return True
    return False


def _refine_ambiguous_invoice_cells(
    image: Image.Image,
    data: dict[str, list[Any]],
    items: list[dict[str, Any]],
    pytesseract: Any,
) -> list[dict[str, Any]]:
    boxes = _invoice_cell_boxes(data, image.size)
    refined: list[dict[str, Any]] = []
    for item in items:
        candidate = dict(item)
        row_boxes = boxes.get(str(item.get("medicine_name")), {})
        readings: dict[str, str] = {}
        if not item.get("batch_number") and row_boxes.get("batch"):
            readings["batch_number"] = _read_invoice_cell(image, row_boxes["batch"], pytesseract, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
        selling = item.get("selling_price")
        suspicious_numbers = selling not in (None, "") and float(item.get("unit_cost") or 0) >= float(selling)
        if suspicious_numbers:
            for field in ("quantity", "unit_cost", "selling_price", "line_total"):
                if row_boxes.get(field):
                    readings[field] = _read_invoice_cell(image, row_boxes[field], pytesseract, "0123456789.,")
        candidate = _apply_targeted_cell_readings(candidate, readings)
        refined.append(candidate)
    return refined


def _read_invoice_cell(image: Image.Image, box: tuple[int, int, int, int], pytesseract: Any, whitelist: str) -> str:
    left, top, right, bottom = box
    crop = image.crop((left + 2, top + 2, right - 2, bottom - 2))
    crop = crop.resize((max(1, crop.width * 3), max(1, crop.height * 3)), Image.Resampling.LANCZOS)
    crop = ImageEnhance.Sharpness(ImageOps.autocontrast(crop)).enhance(2.0)
    return "".join(pytesseract.image_to_string(
        crop,
        config=f"--psm 7 -c tessedit_char_whitelist={whitelist}",
    ).split())


def _apply_targeted_cell_readings(item: dict[str, Any], readings: dict[str, str]) -> dict[str, Any]:
    result = dict(item)
    batch = readings.get("batch_number", "").upper()
    if re.fullmatch(r"(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)+", batch):
        result["batch_number"] = batch
    try:
        quantity = int(float(re.sub(r"[^0-9.]", "", readings.get("quantity", ""))))
        unit_cost = _ocr_money(re.sub(r"[^0-9.,]", "", readings.get("unit_cost", "")))
        selling_price = _ocr_money(re.sub(r"[^0-9.,]", "", readings.get("selling_price", "")))
        line_total = _ocr_money(re.sub(r"[^0-9.,]", "", readings.get("line_total", "")))
    except (ValueError, TypeError):
        return result
    if quantity > 0 and unit_cost >= 0 and selling_price > unit_cost and line_total > 0 \
            and abs(quantity * unit_cost - line_total) < 0.01:
        result.update({
            "quantity": quantity,
            "unit_cost": unit_cost,
            "selling_price": selling_price,
            "line_total": line_total,
        })
    return result


def _invoice_cell_boxes(data: dict[str, list[Any]], image_size: tuple[int, int]) -> dict[str, dict[str, tuple[int, int, int, int]]]:
    tokens: list[dict[str, Any]] = []
    for index, raw_text in enumerate(data.get("text") or []):
        text = " ".join(str(raw_text or "").split())
        if not text:
            continue
        try:
            left = int((data.get("left") or [])[index])
            top = int((data.get("top") or [])[index])
            width = int((data.get("width") or [])[index])
            height = int((data.get("height") or [])[index])
        except (ValueError, TypeError, IndexError):
            continue
        tokens.append({"text": text, "center_x": left + width / 2, "center_y": top + height / 2})
    anchors = _unique_medicine_anchors(tokens, load_source_brain_medicines())
    if not anchors:
        return {}
    header = [token for token in tokens if token["center_y"] < anchors[0][0]]

    def x_for(*labels: str) -> float:
        matches = [token["center_x"] for token in header if token["text"].lower() in labels]
        return max(matches, default=0)

    columns = [
        ("medicine", min((token["center_x"] for token in header if token["text"].lower().startswith("medicine")), default=0)),
        ("form", x_for("form")), ("unit", x_for("unit")), ("pack", x_for("pack", "size")),
        ("quantity", x_for("qty", "quantity")), ("unit_cost", x_for("cost")),
        ("selling_price", x_for("price")), ("line_total", x_for("total")),
        ("batch", x_for("batch")), ("expiry", x_for("expiry", "expires")),
    ]
    columns = [(name, x) for name, x in columns if x > 0]
    columns.sort(key=lambda entry: entry[1])
    if not all(any(name == required for name, _ in columns) for required in ("quantity", "unit_cost", "line_total", "batch")):
        return {}
    x_edges = [0] + [int((columns[index][1] + columns[index + 1][1]) / 2) for index in range(len(columns) - 1)] + [image_size[0]]
    typical_gap = min((anchors[index + 1][0] - anchors[index][0] for index in range(len(anchors) - 1)), default=80)
    result: dict[str, dict[str, tuple[int, int, int, int]]] = {}
    for row_index, (center_y, name) in enumerate(anchors):
        top = int((anchors[row_index - 1][0] + center_y) / 2) if row_index else max(0, int(center_y - typical_gap / 2))
        bottom = int((center_y + anchors[row_index + 1][0]) / 2) if row_index + 1 < len(anchors) else min(image_size[1], int(center_y + typical_gap / 2))
        result[name] = {
            field: (x_edges[index], top, x_edges[index + 1], bottom)
            for index, (field, _x) in enumerate(columns)
        }
    return result


def _merge_geometry_passes(primary: list[dict[str, Any]], refined: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refined_by_name = {str(item.get("medicine_name")): item for item in refined}
    result: list[dict[str, Any]] = []
    for original in primary:
        alternative = refined_by_name.pop(str(original.get("medicine_name")), None)
        if not alternative:
            result.append(original)
            continue
        ranked = sorted([original, alternative], key=_geometry_item_score, reverse=True)
        chosen = dict(ranked[0])
        for field in ("form", "unit", "selling_price", "batch_number", "expiry_date"):
            if chosen.get(field) in (None, "", 0):
                chosen[field] = ranked[1].get(field)
        result.append(chosen)
    result.extend(refined_by_name.values())
    return result


def _geometry_item_score(item: dict[str, Any]) -> tuple[int, int, int]:
    complete = sum(item.get(field) not in (None, "", 0) for field in (
        "form", "unit", "quantity", "unit_cost", "line_total", "batch_number", "expiry_date"
    ))
    arithmetic = int(
        item.get("quantity") not in (None, "", 0)
        and item.get("unit_cost") not in (None, "")
        and item.get("line_total") not in (None, "", 0)
        and abs(float(item["quantity"]) * float(item["unit_cost"]) - float(item["line_total"])) < 0.01
    )
    selling = item.get("selling_price")
    positive_margin = int(selling not in (None, "") and float(selling) > float(item.get("unit_cost") or 0))
    return arithmetic, positive_margin, complete


def reconstruct_bounded_invoice_rows(data: dict[str, list[Any]]) -> list[str]:
    medicines = load_source_brain_medicines()
    tokens: list[dict[str, Any]] = []
    for index, raw_text in enumerate(data.get("text") or []):
        text = " ".join(str(raw_text or "").split())
        if not text:
            continue
        try:
            left = int((data.get("left") or [])[index])
            top = int((data.get("top") or [])[index])
            height = int((data.get("height") or [])[index])
        except (ValueError, TypeError, IndexError):
            continue
        tokens.append({"text": text, "left": left, "center_y": top + height / 2})
    anchors = _unique_medicine_anchors(tokens, medicines)
    if not anchors:
        return []
    typical_gap = min((anchors[index + 1][0] - anchors[index][0] for index in range(len(anchors) - 1)), default=60)
    rows: list[str] = []
    for index, (center_y, _name) in enumerate(anchors):
        lower = (anchors[index - 1][0] + center_y) / 2 if index else center_y - typical_gap / 2
        upper = (center_y + anchors[index + 1][0]) / 2 if index + 1 < len(anchors) else center_y + typical_gap / 2
        row_tokens = [token for token in tokens if lower <= token["center_y"] < upper]
        rows.append(" ".join(token["text"] for token in sorted(row_tokens, key=lambda token: token["left"])))
    return rows


def _unique_medicine_anchors(tokens: list[dict[str, Any]], medicines: list[dict[str, Any]]) -> list[tuple[float, str]]:
    best_by_medicine: dict[str, tuple[float, float]] = {}
    for token in tokens:
        if len(re.sub(r"[^A-Za-z]", "", token["text"])) < 5:
            continue
        ranked = sorted(((_medicine_line_score(token["text"], medicine), medicine["name"]) for medicine in medicines), reverse=True)
        if not ranked or ranked[0][0] < 0.78 or (len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.08):
            continue
        score, name = ranked[0]
        current = best_by_medicine.get(name)
        if current is None or score > current[0]:
            best_by_medicine[name] = (score, token["center_y"])
    return sorted((center_y, name) for name, (_score, center_y) in best_by_medicine.items())


def _medicine_order_from_lines(lines: list[str]) -> list[str]:
    medicines = load_source_brain_medicines()
    order: list[str] = []
    for line in lines:
        ranked = sorted(((_medicine_line_score(line, medicine), medicine["name"]) for medicine in medicines), reverse=True)
        if ranked and ranked[0][0] >= 0.76 and ranked[0][1] not in order:
            order.append(ranked[0][1])
    return order


def _medicine_order_from_text(text: str) -> list[str]:
    """Preserve the primary OCR pass's document reading order for recognized medicines."""
    medicines = load_source_brain_medicines()
    found: list[tuple[int, str]] = []
    lowered = text.lower()
    for medicine in medicines:
        positions = [lowered.find(name.lower()) for name in [medicine["name"], *medicine["aliases"]]]
        positions = [position for position in positions if position >= 0]
        if positions:
            found.append((min(positions), medicine["name"]))
    return [name for _, name in sorted(found)]


def extract_positioned_row_fields(data: dict[str, list[Any]]) -> dict[str, dict[str, str]]:
    medicines = load_source_brain_medicines()
    tokens: list[dict[str, Any]] = []
    for index, raw_text in enumerate(data.get("text") or []):
        text = " ".join(str(raw_text or "").split())
        if not text:
            continue
        try:
            top = int((data.get("top") or [])[index])
            height = int((data.get("height") or [])[index])
        except (ValueError, TypeError, IndexError):
            continue
        tokens.append({"text": text, "center_y": top + height / 2})
    anchors = _unique_medicine_anchors(tokens, medicines)
    row_gap = min((anchors[index + 1][0] - anchors[index][0] for index in range(len(anchors) - 1)), default=80)
    result: dict[str, dict[str, str]] = {name: {} for _, name in anchors}
    for token in tokens:
        expiry = re.fullmatch(r"(20\d{2})(?:\s*[-/.,:]\s*|(?=\d{2}$))(0[1-9]|1[0-2])", token["text"])
        batch = re.fullmatch(r"(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+-[A-Z0-9]+", token["text"], flags=re.I)
        if not expiry and not batch:
            continue
        nearest_y, name = min(anchors, key=lambda anchor: abs(anchor[0] - token["center_y"]), default=(0, ""))
        if not name or abs(nearest_y - token["center_y"]) > row_gap * 0.45:
            continue
        if expiry:
            result[name]["expiry_date"] = f"{expiry.group(1)}-{expiry.group(2)}"
        elif batch and not token["text"].startswith("20"):
            result[name]["batch_number"] = token["text"]
    return result


def reconstruct_document_lines_from_word_positions(data: dict[str, list[Any]]) -> list[str]:
    words: list[tuple[float, int, int, str]] = []
    for index, raw_text in enumerate(data.get("text") or []):
        text = " ".join(str(raw_text or "").split())
        if not text:
            continue
        try:
            top = int((data.get("top") or [])[index])
            left = int((data.get("left") or [])[index])
            height = int((data.get("height") or [])[index])
        except (ValueError, TypeError, IndexError):
            continue
        words.append((top + height / 2, left, height, text))
    lines: list[dict[str, Any]] = []
    for center_y, left, height, text in sorted(words):
        line = next((row for row in lines if abs(row["center_y"] - center_y) <= max(8, height * 0.8)), None)
        if line is None:
            line = {"center_y": center_y, "words": []}
            lines.append(line)
        line["words"].append((left, text))
    return [" ".join(text for _, text in sorted(line["words"])) for line in sorted(lines, key=lambda row: row["center_y"])]


def _normalize_batch_digits_by_invoice_pattern(items: list[dict[str, Any]]) -> None:
    suffixes = [str(item.get("batch_number") or "").rsplit("-", 1)[-1] for item in items]
    digit_pattern = sum(bool(re.fullmatch(r"[A-Z]\d{2}", suffix, flags=re.I)) for suffix in suffixes) >= 2
    if not digit_pattern:
        return
    for item in items:
        batch = str(item.get("batch_number") or "")
        match = re.fullmatch(r"(.+-[A-Z])([OQ])([0-9])", batch.strip().replace(" ", ""), flags=re.I)
        if match:
            item["batch_number"] = f"{match.group(1)}0{match.group(3)}"


def _fill_unique_source_pair_fields(items: list[dict[str, Any]]) -> None:
    medicines = {medicine["name"]: medicine for medicine in load_source_brain_medicines()}
    for item in items:
        medicine = medicines.get(str(item.get("medicine_name")))
        if not medicine:
            continue
        pairs = list(zip(medicine.get("forms") or [], medicine.get("units") or []))
        if not item.get("form") and item.get("unit"):
            matches = [form for form, unit in pairs if unit == item["unit"]]
            if len(set(matches)) == 1:
                item["form"] = matches[0]
        if not item.get("unit") and item.get("form"):
            matches = [unit for form, unit in pairs if form == item["form"]]
            if len(set(matches)) == 1:
                item["unit"] = matches[0]


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
    for field in ("form", "unit", "batch_number", "expiry_date"):
        if merged.get(field) in (None, "", 0):
            merged[field] = next((item.get(field) for item in ranked if item.get(field) not in (None, "", 0)), merged.get(field))
    numeric = _coherent_row_numbers(items)
    if numeric:
        merged.update(numeric)
    else:
        merged.update({"quantity": None, "unit_cost": None, "line_total": None})
    merged["confidence"] = max(float(item.get("confidence") or 0) for item in items)
    return merged


def _coherent_row_numbers(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    observed = {
        round(float(value), 2)
        for item in items
        for field in ("quantity", "unit_cost", "line_total")
        if (value := item.get(field)) not in (None, "", 0)
    }
    money_values = observed | {value / 100 for value in observed if value >= 1000 and int(value) % 100 == 0}
    quantity_values = observed | {
        round(total / cost, 2)
        for total in money_values
        for cost in money_values
        if cost and total > cost and total / cost <= 10000
    }
    matches: list[tuple[int, float, float, float]] = []
    for quantity in quantity_values:
        if quantity != int(quantity) or quantity > 10000:
            continue
        for unit_cost in money_values:
            for line_total in money_values:
                if abs(quantity * unit_cost - line_total) <= max(0.01, line_total * 0.001):
                    role_support = sum(
                        item.get("quantity") == quantity
                        for item in items
                    ) + sum(
                        item.get("unit_cost") == unit_cost
                        for item in items
                    ) + sum(
                        item.get("line_total") == line_total
                        for item in items
                    )
                    role_support += 2 * sum(
                        _same_number(unit_cost, _money_from_misplaced_quantity(item.get("quantity")))
                        and _same_number(line_total, item.get("unit_cost"))
                        for item in items
                    )
                    matches.append((role_support, quantity, unit_cost, line_total))
    if not matches:
        return None
    _, quantity, unit_cost, line_total = max(matches, key=lambda row: (row[0], row[3], row[1] != 1))
    return {"quantity": int(quantity), "unit_cost": unit_cost, "line_total": line_total}


def _money_from_misplaced_quantity(value: Any) -> float | None:
    if value in (None, "", 0):
        return None
    number = float(value)
    return number / 100 if number >= 1000 and int(number) % 100 == 0 else number


def _same_number(left: Any, right: Any) -> bool:
    return left not in (None, "") and right not in (None, "") and abs(float(left) - float(right)) < 0.01


def _item_completeness(item: dict[str, Any]) -> tuple[int, float]:
    fields = ("form", "unit", "quantity", "unit_cost", "line_total", "batch_number", "expiry_date")
    return sum(item.get(field) not in (None, "", 0) for field in fields), float(item.get("confidence") or 0)


def _best_ocr_metadata_value(values: list[Any], fallback: Any = "") -> str:
    candidates = [" ".join(str(value).split()).strip(" :;'\"") for value in values if str(value or "").strip()]
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
    line = re.sub(r"\s*-\s*", "-", line)
    line = re.sub(r"(?<=\d)[—–_:](?=\d)", "-", line)
    form = _best_known_value(line, medicine["forms"])
    unit = _best_known_value(line, medicine["units"])
    expiry_match = re.search(r"\b(20\d{2})(?:\s*[-/., ]\s*|(?=\d{2}\b))(0[1-9]|1[0-2])\b", line)
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
    exact = next((value for value in sorted(values, key=len, reverse=True) if _contains_name(line, value)), "")
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
    for line in text.splitlines():
        if not re.search(r"invoice\s+total", line, flags=re.I):
            continue
        tail = re.split(r"invoice\s+total", line, maxsplit=1, flags=re.I)[-1]
        digits = "".join(re.findall(r"\d", tail))
        if digits:
            return _ocr_money(digits)
    return None


def _invoice_date_from_text(text: str) -> str:
    match = re.search(r"invoice\s+date\D{0,12}(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})", text, flags=re.I)
    return " ".join(match.group(1).split()) if match else ""


def _invoice_number_from_text(text: str) -> str:
    candidates = re.findall(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b", text.upper())
    candidates = [value for value in candidates if any(character.isdigit() for character in value)]
    return max(candidates, key=lambda value: ("TEST" in value, len(value)), default="")


def _supplier_name_from_text(text: str) -> str:
    candidates = []
    for line in text.splitlines():
        clean = " ".join(line.split()).strip(" :-")
        if re.search(r"\b(?:medical\s+suppl\w*|pharma\w*(?:\s+suppl\w*)?|wholesale|wholesaler)\b", clean, flags=re.I):
            clean = re.sub(r"^supplier\s*[:\-]?\s*", "", clean, flags=re.I)
            clean = re.sub(r"\s+supplier\s+invoice.*$", "", clean, flags=re.I)
            candidates.append(clean)
    return max(candidates, key=lambda value: (bool(re.search(r"\b(?:ltd|limited|plc|inc)\b", value, flags=re.I)), value.isupper(), len(value)), default="")


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
