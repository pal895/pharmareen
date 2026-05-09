from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

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
