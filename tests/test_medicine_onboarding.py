from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from app.services.medicine_onboarding import import_pharmacy_medicines, parse_bulk_medicine_payload


class FakeCatalogStore:
    is_available = True

    def __init__(self) -> None:
        self.stock_items: list[dict] = []
        self.catalog_records: list[dict] = []

    def add_stock_item(
        self,
        drug_name,
        *,
        selling_price=None,
        cost_price=None,
        current_stock=0,
        reorder_level=5,
    ):
        self.stock_items.append(
            {
                "drug_name": drug_name,
                "selling_price": selling_price,
                "cost_price": cost_price,
                "current_stock": current_stock,
                "reorder_level": reorder_level,
            }
        )

    def upsert_medicine_catalog_record(self, record):
        self.catalog_records.append(record)


def test_parse_bulk_medicine_payload_supports_forms_units_aliases():
    records = parse_bulk_medicine_payload(
        {
            "text": "\n".join(
                [
                    "Panadol | aliases: pndo; paracetamol | form: tablet/syrup | unit: tabs, bottle | pack: 10x10 | category: pain",
                    "Amoxicillin, amox, capsule, caps, 500mg, antibiotic",
                ]
            )
        }
    )

    assert [record.name for record in records] == ["Panadol", "Amoxicillin"]
    assert records[0].aliases == ("pndo", "paracetamol")
    assert records[0].forms == ("tablet", "syrup")
    assert records[0].units == ("tabs", "bottle")
    assert records[1].aliases == ("amox",)


def test_import_pharmacy_medicines_writes_stock_catalog_and_alias_memory(monkeypatch):
    artifact_root = Path("pytest_tmp_medicine_onboarding") / uuid4().hex
    alias_path = artifact_root / "aliases.json"
    monkeypatch.setenv("PHARMAREEN_ALIAS_STORE_PATH", str(alias_path))
    store = FakeCatalogStore()
    try:
        result = import_pharmacy_medicines(
            {
                "medicines": [
                    {
                        "name": "Cetirizine",
                        "aliases": ["cetz", "allergy"],
                        "forms": ["tablet", "syrup"],
                        "units": ["tabs", "bottle"],
                        "pack_sizes": ["10s"],
                        "selling_price": 20,
                        "stock": 15,
                    }
                ]
            },
            store=store,
            pharmacy_id="Zuri Chemist",
            audit_dir=artifact_root / "catalog_audit",
        )

        assert result["status"] == "ok"
        assert result["ai_used"] is False
        assert result["records_imported"] == 1
        assert store.stock_items[0]["drug_name"] == "Cetirizine"
        assert store.stock_items[0]["current_stock"] == 15
        assert store.catalog_records[0]["aliases"] == ["cetz", "allergy"]
        assert store.catalog_records[0]["dosage_forms"] == ["tablet", "syrup"]
        assert store.catalog_records[0]["pack_sizes"] == ["10s"]
        assert alias_path.exists()
    finally:
        shutil.rmtree(artifact_root, ignore_errors=True)
