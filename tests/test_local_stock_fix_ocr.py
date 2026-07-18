import io
import sys
from types import SimpleNamespace

from PIL import Image

from app.services.local_stock_fix_ocr import merge_ocr_readings, scan_stock_fix_evidence_locally


def test_stock_fix_ocr_preserves_complementary_medicine_evidence() -> None:
    merged = merge_ocr_readings(
        [
            "400 mg\nTABLETS\n20 tablets\nBatch MET-400C\nEXP 2029-03",
            "METRONIDAZOLE\n400 mg\nTABLETS",
        ]
    )

    assert "METRONIDAZOLE" in merged
    assert "Batch MET-400C" in merged
    assert merged.count("400 mg") == 1


def test_stock_fix_ocr_ignores_blank_and_duplicate_lines() -> None:
    assert merge_ocr_readings([" Prednisolone  ", "\nPREDNISOLONE\n", ""]) == "Prednisolone"


def test_package_region_can_recover_name_missed_by_whole_frame(monkeypatch) -> None:
    readings = iter([
        "Stock Fix instructions\n400 mg",
        "20 tablets",
        "Batch MET-400C\nEXP 2029-03",
        "TABLETS",
        "METRONIDAZOLE\n400 mg",
    ])
    fake_tesseract = SimpleNamespace(image_to_string=lambda *_args, **_kwargs: next(readings))
    monkeypatch.setitem(sys.modules, "pytesseract", fake_tesseract)
    image_bytes = io.BytesIO()
    Image.new("RGB", (600, 900), "white").save(image_bytes, format="JPEG")

    result = scan_stock_fix_evidence_locally(image_bytes.getvalue())

    assert "METRONIDAZOLE" in result["visible_text"]
    assert result["strength"] == "400 mg"
    assert result["batch"] == "MET-400C"
    assert result["expiry"] == "2029-03"
