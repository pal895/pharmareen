from __future__ import annotations

import time

from app.services.medicine_catalog import (
    catalog_entries_payload,
    catalog_unique_aliases,
    load_catalog_metadata,
    match_local_medicine,
    medicine_match_snapshot,
    migrate_catalog_record,
    search_catalog_entries,
)
from app.services.pharmacy_alias_store import PharmacyAliasStore


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
            "strengths",
            "packaging",
            "manufacturer_importer",
            "ppb_registration_number",
            "source",
            "source_last_updated",
            "human_or_veterinary",
            "otc_or_prescription",
            "combination_medicine_components",
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


def test_catalog_migration_upgrades_old_rows_without_breaking_existing_snapshots():
    migrated = migrate_catalog_record(
        {
            "canonical_name": "Sample Tabs",
            "category": "pain relief",
            "units": ["tab", "amp", "inj", "syr", "susp"],
            "sources": ["Legacy import"],
            "registration_numbers": ["PPB-1"],
        }
    )

    assert migrated["category"] == "pain/fever"
    assert migrated["units"] == ("tablet", "ampoule", "injection", "syrup", "suspension")
    assert migrated["source"] == "Legacy import"
    assert migrated["ppb_registration_number"] == "PPB-1"
    assert migrated["human_or_veterinary"] == "unknown"


def test_official_catalog_rows_include_relationship_metadata():
    entries = catalog_entries_payload()
    official = [entry for entry in entries if entry["ppb_registration_number"]]

    assert len(official) >= 2000
    assert all(entry["source"] == "PPB registered products public registry" for entry in official)
    assert all(entry["otc_or_prescription"] == "unknown" for entry in official)
    assert any(entry["manufacturer_importer"] for entry in official)
    assert any(entry["strengths"] for entry in official)
    assert any(entry["packaging"] for entry in official)
    assert any(entry["combination_medicine_components"] for entry in official)


def test_local_match_telemetry_proves_zero_ai_route():
    match = match_local_medicine("pnadol", inventory_names=["Panadol", "ORS"])
    snapshot = medicine_match_snapshot()

    assert match.canonical_name == "Panadol"
    assert snapshot["ai_used"] is False
    assert snapshot["recent"][-1]["source"] in {"catalog_alias", "fuzzy"}
    assert snapshot["recent"][-1]["ai_used"] is False


def test_hot_local_match_stays_fast_enough_for_rush_hour():
    match_local_medicine("pnadol", inventory_names=["Panadol", "Glucose", "ORS"])
    started = time.perf_counter()
    for _ in range(100):
        match_local_medicine("pnadol", inventory_names=["Panadol", "Glucose", "ORS"])
    average_ms = (time.perf_counter() - started) * 1000 / 100

    assert average_ms < 10


def test_pharmacy_alias_store_persists_only_safe_confirmed_shortcuts(tmp_path):
    store = PharmacyAliasStore(tmp_path / "aliases.json", short_alias_threshold=2)

    first = store.observe("demo pharmacy", "pd", "Panadol", confirmed=True, inventory_names=["Panadol"])
    second = store.observe("demo pharmacy", "pd", "Panadol", confirmed=True, inventory_names=["Panadol"])

    assert first["accepted"] is False
    assert second["accepted"] is True
    assert store.accepted_aliases("demo pharmacy") == {"pd": "Panadol"}


def test_pharmacy_alias_store_does_not_learn_ambiguous_shortcut_without_owner_approval(tmp_path):
    store = PharmacyAliasStore(tmp_path / "aliases.json")

    result = store.observe(
        "demo pharmacy",
        "p",
        "Panadol",
        confirmed=True,
        inventory_names=["Panadol", "Piriton", "Paracetamol"],
    )

    assert result["accepted"] is False
    assert result["needs_review"] is True
    assert result["reason"] == "inventory ambiguity"
