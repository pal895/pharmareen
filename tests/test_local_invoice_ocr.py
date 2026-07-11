from app.services.local_invoice_ocr import _best_ocr_metadata_value, merge_source_brain_invoice_items


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
