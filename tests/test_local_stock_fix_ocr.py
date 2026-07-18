from app.services.local_stock_fix_ocr import merge_ocr_readings


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
