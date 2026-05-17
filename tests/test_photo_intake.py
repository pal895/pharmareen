from __future__ import annotations

import json

from app.services.photo_intake import (
    build_invoice_extraction_placeholder,
    build_media_job_placeholder,
    classify_photo_for_intake,
    extract_supplier_invoice_from_text,
    google_sheets_preparation_helpers,
    read_photo_intake_stats,
    save_photo_upload,
    append_photo_intake_log,
    stock_shelf_photo_summary,
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


def test_media_classifier_identifies_supplier_documents_before_extraction():
    invoice = classify_photo_for_intake(filename="INV123.jpg", caption="supplier invoice MedCare Panadol 20 boxes")
    receipt = classify_photo_for_intake(filename="receipt.jpg", caption="supplier receipt paid 2500")
    delivery = classify_photo_for_intake(filename="delivery-note.jpg", caption="delivery note stock imefika")

    assert invoice["media_kind"] == "supplier_invoice"
    assert invoice["processing_status"] == "needs_review"
    assert invoice["needs_ai"] is True
    assert "supplier invoice" in invoice["user_message"]
    assert receipt["media_kind"] == "supplier_receipt"
    assert delivery["media_kind"] == "delivery_note"


def test_media_classifier_handles_stock_pack_barcode_blurry_and_random_safely():
    shelf = classify_photo_for_intake(filename="shelf.jpg", caption="stock shelf photo Panadol ORS")
    pack = classify_photo_for_intake(filename="pack.jpg", caption="medicine pack label")
    barcode = classify_photo_for_intake(filename="barcode.jpg", caption="barcode 9789914441314")
    blurry = classify_photo_for_intake(filename="invoice.jpg", caption="blurry invoice poor lighting")
    random = classify_photo_for_intake(filename="family.jpg", caption="family photo")

    assert shelf["media_kind"] == "pharmacy_stock_shelf_photo"
    assert pack["media_kind"] == "medicine_pack_photo"
    assert barcode["media_kind"] == "barcode_photo"
    assert barcode["processing_status"] == "completed"
    assert blurry["media_kind"] == "blurry_unclear_photo"
    assert "retake closer" in blurry["user_message"]
    assert random["media_kind"] == "random_non_pharmacy_photo"


def test_media_job_placeholder_never_updates_stock_without_confirmation():
    classification = classify_photo_for_intake(caption="supplier invoice MedCare Panadol 20 boxes")
    job = build_media_job_placeholder(classification)

    assert job["processing_status"] == "needs_review"
    assert job["requires_confirmation"] is True
    assert job["extraction_target"] == "invoice_items"


def test_supplier_invoice_text_extraction_schema_requires_confirmation():
    extraction = extract_supplier_invoice_from_text(
        "Supplier: MedCare Invoice INV123 Date 12/05/2026 Panadol 20 boxes bonus 5 cost 2000 Amoxyl 10 packs"
    )

    assert extraction["document_type"] == "supplier_invoice"
    assert extraction["supplier_name"] == "MedCare"
    assert extraction["invoice_number"] == "INV123"
    assert extraction["items"][0]["medicine_name"] == "Panadol"
    assert extraction["items"][0]["quantity"] == 20
    assert extraction["items"][0]["bonus_quantity"] == 5
    assert extraction["items"][0]["total_received_quantity"] == 25
    assert extraction["requires_confirmation"] is True
    assert extraction["extraction_status"] == "needs_confirmation"


def test_stock_shelf_photo_summary_refuses_unsafe_counts():
    classification = classify_photo_for_intake(caption="stock shelf photo Panadol and ORS")
    summary = stock_shelf_photo_summary(classification)

    assert summary["can_count_safely"] is False
    assert "cannot count safely" in summary["message"]
