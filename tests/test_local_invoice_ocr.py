from app.services.local_invoice_ocr import _best_ocr_metadata_value, _coherent_row_numbers, _ocr_money, merge_source_brain_invoice_items, reconstruct_invoice_rows_from_word_positions


def test_multiple_ocr_passes_merge_all_canonical_invoice_rows_and_fields():
    passes = [
        "Acyclovir cream 12 180.00 2,160.00 ACY-T01 2028-06\n"
        "Clotrimazole pessary pessary 20 95.00 1,900.00 CLO-P02 2028-09\n"
        "Doxycycline 50 18.00 900.00 DOX-C03 2027-12",
        "Acyclovir cream tube 12 180.00 2,160.00 ACY-T01 2028-06\n"
        "Doxycycline capsule capsule 50 18.00 900.00 DOX-C03 2027-12\n"
        "Chloramphenicol eye drops bottle 15 140.00 2,100.00 CHL-E04 2027-10",
    ]

    rows = merge_source_brain_invoice_items(passes)
    by_name = {row["medicine_name"]: row for row in rows}

    assert set(by_name) == {"Acyclovir", "Clotrimazole", "Doxycycline", "Chloramphenicol"}
    assert by_name["Acyclovir"]["form"] == "cream"
    assert by_name["Acyclovir"]["unit"] == "tube"
    assert by_name["Doxycycline"]["form"] == "capsule"
    assert by_name["Doxycycline"]["unit"] == "capsule"
    assert by_name["Chloramphenicol"]["line_total"] == 2100.0


def test_supplier_metadata_prefers_readable_pass_over_fragmented_ocr():
    assert _best_ocr_metadata_value([
        "Af k M Supplies Ltd",
        "AfyaLink Medical Supplies Ltd",
    ]) == "AfyaLink Medical Supplies Ltd"


def test_ocr_money_restores_dropped_printed_decimal_places():
    assert _ocr_money("18000") == 180.0
    assert _ocr_money("9500") == 95.0
    assert _ocr_money("18.00") == 18.0
    assert _ocr_money("140") == 140.0


def test_numeric_columns_are_reconstructed_by_invoice_arithmetic():
    candidates = [
        {"quantity": 9500, "unit_cost": 1900, "line_total": None},
        {"quantity": 20, "unit_cost": 95, "line_total": 1900},
    ]
    assert _coherent_row_numbers(candidates) == {
        "quantity": 20,
        "unit_cost": 95.0,
        "line_total": 1900.0,
    }

    assert _coherent_row_numbers([{
        "quantity": 1800,
        "unit_cost": 900,
        "line_total": 1,
    }]) == {"quantity": 50, "unit_cost": 18.0, "line_total": 900.0}
    assert _coherent_row_numbers([{
        "quantity": 140,
        "unit_cost": 2100,
        "line_total": 202710,
    }]) == {"quantity": 15, "unit_cost": 140.0, "line_total": 2100.0}


def test_invoice_endpoint_returns_safe_json_when_reader_throws(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    main.main_app_invoice_ocr_cache.clear()
    monkeypatch.setattr(main, "scan_invoice_locally", lambda _data: (_ for _ in ()).throw(RuntimeError("ocr failure")))
    with TestClient(main.app) as client:
        response = client.post("/api/ms20/invoice-scan", files={"file": ("invoice.jpg", b"image", "image/jpeg")})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["complete"] is False
    assert response.json()["message"] == "I could not finish reading this invoice. Please scan it again."


def test_table_cells_are_rebuilt_from_word_coordinates_not_ocr_line_order():
    words = ["Acyclovir", "cream", "tube", "12", "180.00", "2,160.00", "ACY-T01", "2028-06"]
    data = {
        "text": words,
        "conf": [90] * len(words),
        "left": [10, 120, 190, 250, 300, 390, 490, 570],
        "top": [100, 102, 99, 101, 100, 103, 98, 101],
        "width": [80, 50, 40, 20, 60, 70, 60, 60],
        "height": [20] * len(words),
    }
    assert reconstruct_invoice_rows_from_word_positions(data) == [
        "Acyclovir cream tube 12 180.00 2,160.00 ACY-T01 2028-06"
    ]
