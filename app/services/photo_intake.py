from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.operational_intelligence import MediaClassification, classify_media_input

PHOTO_UPLOAD_RELATIVE_DIR = Path("data") / "photo_uploads"
PHOTO_LOG_RELATIVE_PATH = Path("data") / "photo_intake_log.jsonl"

INVOICE_EXTRACTION_SCHEMA: dict[str, Any] = {
    "drug_name": None,
    "quantity": None,
    "ordered_quantity": None,
    "bonus_quantity": 0,
    "total_received_quantity": None,
    "buying_price": None,
    "expected_total_cost": None,
    "discount_amount": 0,
    "actual_paid_amount": None,
    "supplier": None,
    "expiry_date": None,
    "notes": "",
    "confidence": 0.0,
    "extraction_status": "waiting_for_openai_credits",
}

SUPPLIER_INVOICE_EXTRACTION_SCHEMA: dict[str, Any] = {
    "document_type": None,
    "supplier_name": None,
    "invoice_number": None,
    "date": None,
    "items": [],
    "confidence": 0.0,
    "extraction_status": "needs_review",
    "requires_confirmation": True,
    "notes": "",
}

PHOTO_JOB_STATUSES = {"completed", "needs_review", "failed"}

GOOGLE_SHEETS_PREPARATION: dict[str, list[str]] = {
    "Invoices": [
        "Timestamp",
        "Sender",
        "Message ID",
        "File Path",
        "Drug Name",
        "Ordered Quantity",
        "Bonus Quantity",
        "Total Received Quantity",
        "Buying Price",
        "Expected Total Cost",
        "Discount Amount",
        "Actual Paid Amount",
        "Supplier",
        "Expiry Date",
        "Confidence",
        "Extraction Status",
        "Notes",
    ],
    "Stock_Intake": [
        "Timestamp",
        "Drug Name",
        "Ordered Quantity",
        "Bonus Quantity",
        "Total Received Quantity",
        "Buying Price",
        "Expected Total Cost",
        "Discount Amount",
        "Actual Paid Amount",
        "Supplier",
        "Expiry Date",
        "Source Photo",
        "Processing Status",
    ],
    "Supplier_Logs": [
        "Timestamp",
        "Supplier",
        "Invoice File",
        "Detected Items",
        "Bonus/Discount Notes",
        "Processing Status",
        "Notes",
    ],
    "Expiry_Tracking": [
        "Timestamp",
        "Drug Name",
        "Batch",
        "Expiry Date",
        "Ordered Quantity",
        "Bonus Quantity",
        "Total Received Quantity",
        "Source Photo",
        "Status",
    ],
}

IMAGE_EXTENSION_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def ensure_photo_intake_dirs(project_root: Path) -> dict[str, Path]:
    upload_dir = project_root / PHOTO_UPLOAD_RELATIVE_DIR
    log_path = project_root / PHOTO_LOG_RELATIVE_PATH
    upload_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return {"upload_dir": upload_dir, "log_path": log_path}


def mask_sender_for_storage(sender: str) -> str:
    digits = re.sub(r"\D+", "", sender or "")
    if len(digits) >= 8:
        return f"{digits[:4]}xxxx{digits[-4:]}"
    if digits:
        return f"sender_{digits[-4:]}"
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", sender or "").strip("_")
    return (cleaned[:32] or "unknown_sender").lower()


def _safe_token(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value or "").strip("_")
    return cleaned[:48] or fallback


def image_extension(media_type: str) -> str:
    return IMAGE_EXTENSION_BY_MIME.get((media_type or "").split(";")[0].strip().lower(), ".img")


def build_invoice_extraction_placeholder(extraction_status: str = "waiting_for_openai_credits") -> dict[str, Any]:
    result = dict(INVOICE_EXTRACTION_SCHEMA)
    result["extraction_status"] = extraction_status
    ordered_quantity = result.get("ordered_quantity") or 0
    bonus_quantity = result.get("bonus_quantity") or 0
    result["total_received_quantity"] = ordered_quantity + bonus_quantity if ordered_quantity or bonus_quantity else None
    expected_total_cost = result.get("expected_total_cost")
    discount_amount = result.get("discount_amount") or 0
    if result.get("actual_paid_amount") is None and expected_total_cost is not None and discount_amount:
        result["actual_paid_amount"] = expected_total_cost - discount_amount
    return result


def classify_photo_for_intake(
    *,
    filename: str = "",
    caption: str = "",
    purpose: str = "",
    media_type: str = "",
    quality_hint: str = "",
    ocr_text: str = "",
) -> dict[str, Any]:
    classification = classify_media_input(
        filename=filename,
        caption=caption,
        purpose=purpose,
        content_type=media_type,
        quality_hint=quality_hint,
        ocr_text=ocr_text,
    )
    return {
        "media_kind": classification.media_kind,
        "label": classification.label,
        "confidence": classification.confidence,
        "processing_status": classification.processing_status,
        "user_message": classification.user_message,
        "extraction_target": classification.extraction_target,
        "needs_ai": classification.needs_ai,
        "evidence": list(classification.evidence),
    }


def build_media_job_placeholder(classification: MediaClassification | dict[str, Any]) -> dict[str, Any]:
    if isinstance(classification, MediaClassification):
        media_kind = classification.media_kind
        status = classification.processing_status
        label = classification.label
        target = classification.extraction_target
        confidence = classification.confidence
        message = classification.user_message
    else:
        media_kind = str(classification.get("media_kind") or "unknown_photo")
        status = str(classification.get("processing_status") or "needs_review")
        label = str(classification.get("label") or "unknown photo")
        target = str(classification.get("extraction_target") or "unknown_review")
        confidence = float(classification.get("confidence") or 0.0)
        message = str(classification.get("user_message") or "Photo received safely.")
    if status not in PHOTO_JOB_STATUSES:
        status = "needs_review"
    return {
        "media_kind": media_kind,
        "label": label,
        "confidence": confidence,
        "processing_status": status,
        "extraction_target": target,
        "requires_confirmation": media_kind in {"supplier_invoice", "supplier_receipt", "handwritten_invoice", "delivery_note"},
        "user_message": message,
    }


def extract_supplier_invoice_from_text(visible_text: str, *, document_type: str = "supplier_invoice") -> dict[str, Any]:
    """Small deterministic extraction used for tests and review scaffolding.

    Real OCR/vision can populate the same shape later. This function never marks
    stock ready for automatic update; the owner must confirm first.
    """

    result = dict(SUPPLIER_INVOICE_EXTRACTION_SCHEMA)
    result["document_type"] = document_type
    text = " ".join((visible_text or "").split())
    if not text:
        result["extraction_status"] = "needs_review"
        result["notes"] = "No readable text was supplied."
        return result

    supplier_match = re.search(
        r"(?:supplier|from|vendor)\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 &.'-]{2,40}?)(?=\s+(?:invoice|inv|date|receipt|delivery\s*note)\b|$)",
        text,
        flags=re.I,
    )
    invoice_match = re.search(r"\b(?:invoice|inv|receipt|delivery\s*note)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Za-z0-9_-]{3,24})", text, flags=re.I)
    date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b", text, flags=re.I)
    if supplier_match:
        result["supplier_name"] = supplier_match.group(1).strip(" -")
    if invoice_match:
        result["invoice_number"] = invoice_match.group(1).strip(" -")
    if date_match:
        result["date"] = date_match.group(1)

    item_pattern = re.compile(
        r"\b([A-Z][A-Za-z][A-Za-z -]{1,30}?)\s+(\d+)\s*(boxes|box|packs|pack|strips|strip|tabs|tablets|tablet|bottles|bottle|units|pcs|pieces)?"
        r"(?:\s+(?:bonus|free)\s+(\d+))?"
        r"(?:\s+(?:cost|price|kes|ksh)\s*([0-9,.]+))?",
        flags=re.I,
    )
    items: list[dict[str, Any]] = []
    for match in item_pattern.finditer(text):
        name = match.group(1).strip(" -")
        name_key = name.lower()
        if name_key in {"supplier", "invoice", "receipt", "delivery note", "date", "inv"}:
            continue
        if any(token in name_key.split() for token in ["supplier", "invoice", "receipt", "date", "inv"]):
            continue
        quantity = int(match.group(2))
        bonus = int(match.group(4) or 0)
        cost_text = (match.group(5) or "").replace(",", "")
        items.append(
            {
                "medicine_name": name,
                "quantity": quantity,
                "unit": match.group(3) or "",
                "bonus_quantity": bonus,
                "total_received_quantity": quantity + bonus,
                "unit_cost": float(cost_text) if cost_text else None,
                "expiry_date": None,
                "batch_number": None,
                "confidence": 0.72 if name and quantity else 0.4,
            }
        )

    result["items"] = items[:25]
    result["confidence"] = 0.82 if result["supplier_name"] and result["invoice_number"] and items else (0.6 if items else 0.35)
    result["extraction_status"] = "needs_confirmation" if items else "needs_review"
    result["notes"] = "Owner confirmation required before stock update."
    return result


def stock_shelf_photo_summary(classification: dict[str, Any] | MediaClassification) -> dict[str, Any]:
    kind = classification.media_kind if isinstance(classification, MediaClassification) else str(classification.get("media_kind") or "")
    if kind != "pharmacy_stock_shelf_photo":
        return {"can_count_safely": False, "message": "Photo saved safely for review."}
    return {
        "can_count_safely": False,
        "message": "Stock photo received. I can see medicines, but I cannot count safely from this image.",
        "suggested_next_step": "Confirm quantities or scan barcode.",
    }


def save_photo_upload(
    project_root: Path,
    *,
    sender: str,
    message_id: str,
    media_type: str,
    image_bytes: bytes,
    timestamp: str | None = None,
) -> dict[str, Any]:
    paths = ensure_photo_intake_dirs(project_root)
    timestamp_value = timestamp or datetime.now().isoformat(timespec="seconds")
    compact_timestamp = re.sub(r"[^0-9T]+", "", timestamp_value.replace(":", "").replace("-", ""))[:20]
    sender_slug = mask_sender_for_storage(sender)
    message_slug = _safe_token(message_id, "photo")
    file_name = f"{compact_timestamp}_{sender_slug}_{message_slug}{image_extension(media_type)}"
    file_path = paths["upload_dir"] / file_name
    file_path.write_bytes(image_bytes)
    relative_file_path = file_path.relative_to(project_root).as_posix()
    return {
        "timestamp": timestamp_value,
        "sender": sender_slug,
        "message_id": message_id,
        "media_type": media_type,
        "file_path": str(file_path),
        "relative_file_path": relative_file_path,
        "byte_count": len(image_bytes),
        "processing_status": "stored",
    }


def append_photo_intake_log(project_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    paths = ensure_photo_intake_dirs(project_root)
    with paths["log_path"].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return {**record, "log_path": str(paths["log_path"])}


def read_photo_intake_stats(project_root: Path) -> dict[str, Any]:
    log_path = project_root / PHOTO_LOG_RELATIVE_PATH
    if not log_path.exists():
        return {"images_received_count": 0, "last_uploaded_image": None}

    count = 0
    last_record: dict[str, Any] | None = None
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            count += 1
            try:
                last_record = json.loads(line)
            except json.JSONDecodeError:
                last_record = {"raw": line}
    return {
        "images_received_count": count,
        "last_uploaded_image": last_record,
    }


def google_sheets_preparation_helpers() -> dict[str, list[str]]:
    return {sheet: list(headers) for sheet, headers in GOOGLE_SHEETS_PREPARATION.items()}
