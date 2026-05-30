from __future__ import annotations

from app.services.medicine_catalog import (
    catalog_entries_payload,
    catalog_unique_aliases,
    load_catalog_metadata,
    match_local_medicine,
    search_catalog_entries,
)


def test_catalog_is_repo_backed_and_contains_expandable_pharmacy_metadata():
    entries = {item["canonical_name"]: item for item in catalog_entries_payload()}

    assert {"Panadol", "Paracetamol", "Piriton", "Amoxyl", "Amoxicillin", "ORS", "Glucose", "Belladonna", "Vitcobin", "Milk"} <= set(entries)
    assert "pnadol" in entries["Panadol"]["misspellings"]
    assert "strip" in entries["Panadol"]["units"]
    assert entries["Panadol"]["category"] == "pain/fever"


def test_kenya_catalog_has_official_product_scale_and_required_schema():
    entries = catalog_entries_payload()
    metadata = load_catalog_metadata()
    required_categories = {
        "pain/fever",
        "antibiotics",
        "malaria",
        "cough/cold",
        "allergy",
        "stomach/ulcer",
        "diarrhea/ORS",
        "vitamins",
        "antifungals",
        "skin creams",
        "eye/ear medicines",
        "diabetes",
        "hypertension",
        "asthma",
        "antiseptics",
        "dewormers",
        "pregnancy supplements",
        "baby medicines",
        "family planning",
        "emergency medicines",
        "nutrition",
        "injections",
        "OTC/common counter medicines",
    }

    assert len(entries) >= 2000
    assert metadata["ppb_registered_product_count"] >= 2000
    assert metadata["catalog_entry_count"] == len(entries)
    assert required_categories <= set(metadata["categories"])
    assert any("products.pharmacyboardkenya.org" in source.get("url", "") for source in metadata["sources"])
    assert any("kemsa.go.ke" in source.get("url", "") for source in metadata["sources"])
    for entry in entries:
        assert {
            "canonical_name",
            "generic_name",
            "aliases",
            "brand_names",
            "misspellings",
            "shorthand",
            "units",
            "category",
            "dosage_forms",
        } <= set(entry)


def test_catalog_search_finds_registered_kenyan_brand_locally():
    matches = search_catalog_entries("Paralife", limit=10)

    assert any(match["canonical_name"].lower().startswith("paralife") for match in matches)
    assert all(match["ai_used"] is False for match in matches)


def test_catalog_matcher_prioritizes_inventory_and_corrects_typos_locally():
    match = match_local_medicine("pnadol", inventory_names=["Panadol", "Glucose", "ORS"])

    assert match.canonical_name == "Panadol"
    assert match.in_inventory is True
    assert match.source in {"catalog_alias", "fuzzy"}


def test_catalog_matcher_asks_when_amox_is_ambiguous_in_live_inventory():
    match = match_local_medicine("amox", inventory_names=["Amoxyl", "Amoxicillin"])

    assert match.ambiguous is True
    assert set(match.choices) == {"Amoxyl", "Amoxicillin"}


def test_catalog_matcher_resolves_amox_when_pharmacy_has_only_one_clear_item():
    match = match_local_medicine("amox", inventory_names=["Amoxyl", "Panadol"])

    assert match.canonical_name == "Amoxyl"
    assert match.in_inventory is True


def test_catalog_matcher_recognizes_unstocked_item_without_pretending_it_is_inventory():
    match = match_local_medicine("vit kobin", inventory_names=["Panadol"])

    assert match.canonical_name == "Vitcobin"
    assert match.in_inventory is False


def test_offline_alias_payload_only_exports_unambiguous_live_inventory_aliases():
    aliases = catalog_unique_aliases(["Panadol", "Amoxyl", "Amoxicillin", "ORS"])

    assert aliases["pnadol"] == "Panadol"
    assert aliases["ors"] == "ORS"
    assert "amox" not in aliases
