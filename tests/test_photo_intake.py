from __future__ import annotations

import json

from app.services.photo_intake import (
    build_invoice_extraction_placeholder,
    google_sheets_preparation_helpers,
    read_photo_intake_stats,
    save_photo_upload,
    append_photo_intake_log,
)


def test_photo_upload_is_saved_with_sender_timestamp_name(tmp_path):
    upload = save_photo_upload(
        tmp_path,
        sender="254700000000@s.whatsapp.net",
        message_id="wamid.TEST/123",
        media_type="image/png",
        image_bytes=b"png-bytes",
        timestamp="2026-05-09T12:30:00+03:00",
    )

    assert upload["relative_file_path"].startswith("data/photo_uploads/")
    assert upload["relative_file_path"].endswith(".png")
    assert "2547xxxx0000" in upload["relative_file_path"]
    saved_path = tmp_path / upload["relative_file_path"]
    assert saved_path.read_bytes() == b"png-bytes"


def test_photo_intake_log_records_status_and_last_upload(tmp_path):
    record = {
        "sender": "2547******00",
        "timestamp": "2026-05-09T12:30:00+03:00",
        "media_type": "image/jpeg",
        "file_path": "data/photo_uploads/example.jpg",
        "message_id": "wamid.example",
        "processing_status": "waiting_for_openai_credits",
    }

    append_photo_intake_log(tmp_path, record)
    stats = read_photo_intake_stats(tmp_path)

    assert stats["images_received_count"] == 1
    assert stats["last_uploaded_image"]["message_id"] == "wamid.example"
    log_line = (tmp_path / "data" / "photo_intake_log.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(log_line)["processing_status"] == "waiting_for_openai_credits"


def test_invoice_extraction_placeholder_schema():
    extraction = build_invoice_extraction_placeholder()

    assert set(extraction) == {
        "drug_name",
        "quantity",
        "ordered_quantity",
        "bonus_quantity",
        "total_received_quantity",
        "buying_price",
        "expected_total_cost",
        "discount_amount",
        "actual_paid_amount",
        "supplier",
        "expiry_date",
        "notes",
        "confidence",
        "extraction_status",
    }
    assert extraction["confidence"] == 0.0
    assert extraction["bonus_quantity"] == 0
    assert extraction["discount_amount"] == 0
    assert extraction["extraction_status"] == "waiting_for_openai_credits"

def test_google_sheets_preparation_helpers_include_phase5_tabs():
    helpers = google_sheets_preparation_helpers()

    assert "Invoices" in helpers
    assert "Stock_Intake" in helpers
    assert "Supplier_Logs" in helpers
    assert "Expiry_Tracking" in helpers
    assert "Drug Name" in helpers["Invoices"]
    assert "Bonus Quantity" in helpers["Invoices"]
    assert "Actual Paid Amount" in helpers["Stock_Intake"]
    assert "Expiry Date" in helpers["Expiry_Tracking"]
