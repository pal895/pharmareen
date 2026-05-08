from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.ai import AIService
from app.config import Settings
from app.demo_store import DemoPharmacyStore
from app.intake import IntakeService
from app.routes import admin
from app.services.pharmacy_onboarding import (
    PHASE3_SHEETS,
    PharmacyOnboardingService,
    PharmacyPayload,
    ensure_spreadsheet_schema,
    generate_pharmacy_id,
)


class FakeWorksheet:
    def __init__(self, title: str):
        self.title = title
        self.rows: list[list[object]] = []

    def row_values(self, row: int) -> list[object]:
        if row == 1 and self.rows:
            return self.rows[0]
        return []

    def update(self, _range: str, values: list[list[object]]) -> None:
        if self.rows:
            self.rows[0] = values[0]
        else:
            self.rows.append(values[0])

    def append_rows(self, rows: list[list[object]], value_input_option: str = "") -> None:
        self.rows.extend(rows)

    def append_row(self, row: list[object], value_input_option: str = "") -> None:
        self.rows.append(row)


class FakeSpreadsheet:
    def __init__(self):
        self.worksheets: dict[str, FakeWorksheet] = {}

    def worksheet(self, title: str) -> FakeWorksheet:
        from gspread.exceptions import WorksheetNotFound

        if title not in self.worksheets:
            raise WorksheetNotFound(title)
        return self.worksheets[title]

    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeWorksheet:
        worksheet = FakeWorksheet(title)
        self.worksheets[title] = worksheet
        return worksheet


def test_pharmacy_id_generation_is_stable_shape():
    pharmacy_id = generate_pharmacy_id("ABC Pharmacy")

    assert pharmacy_id.startswith("abc_pharmacy_")
    assert len(pharmacy_id.split("_")[-1]) == 6


def test_phase3_sheet_structure_creation():
    spreadsheet = FakeSpreadsheet()

    ensure_spreadsheet_schema(spreadsheet)

    for title, headers in PHASE3_SHEETS.items():
        assert title in spreadsheet.worksheets
        assert spreadsheet.worksheets[title].rows[0] == headers
    assert "Suppliers" in spreadsheet.worksheets
    assert "Supplier_Prices" in spreadsheet.worksheets
    assert "Master_Stock" in spreadsheet.worksheets


def test_single_pharmacy_onboarding_uses_local_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = PharmacyOnboardingService(Settings(_env_file=None, GOOGLE_SERVICE_ACCOUNT_JSON=""))

    result = service.create_pharmacy(
        PharmacyPayload(
            pharmacy_name="ABC Pharmacy",
            owner_name="Mary",
            phone="0712345678",
            location="Nairobi",
            notes="Pilot",
        )
    )

    assert result["ok"] is True
    assert result["pharmacy_id"].startswith("abc_pharmacy_")
    assert result["spreadsheet_id"].startswith("local_")
    assert result["status"] == "local_fallback"
    assert "google_error" in result
    assert Path("data/pharmacies_registry.json").exists()


def test_single_pharmacy_onboarding_reports_google_live(monkeypatch):
    service = PharmacyOnboardingService(Settings(_env_file=None, GOOGLE_SERVICE_ACCOUNT_JSON=""))

    def fake_create_google_sheet(pharmacy_id, payload, created_at):
        return {
            "spreadsheet_id": "live-sheet-123",
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/live-sheet-123",
            "tabs": list(PHASE3_SHEETS),
        }

    saved: list[dict[str, object]] = []
    monkeypatch.setattr(service, "_create_google_sheet", fake_create_google_sheet)
    monkeypatch.setattr(service, "_save_registry_record", lambda record: saved.append(record))

    result = service.create_pharmacy(PharmacyPayload("Live Pharmacy", "Samuel", "0712222222", "Nairobi"))

    assert result["ok"] is True
    assert result["status"] == "google_live"
    assert result["spreadsheet_id"] == "live-sheet-123"
    assert result["spreadsheet_url"].startswith("https://docs.google.com/spreadsheets/d/")
    assert saved[0]["status"] == "google_live"


def test_bulk_pharmacy_onboarding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = PharmacyOnboardingService(Settings(_env_file=None, GOOGLE_SERVICE_ACCOUNT_JSON=""))

    result = service.create_pharmacies_bulk(
        [
            PharmacyPayload("Greenleaf Pharmacy", "John", "0722333444", "Kiambu"),
            PharmacyPayload("Towncare Pharmacy", "Ann", "0799888777", "Nakuru"),
        ]
    )

    assert result["ok"] is True
    assert len(result["created"]) == 2
    assert result["failed"] == []
    assert len(service.list_pharmacies()) == 2


def test_admin_routes_create_list_and_show_pharmacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(admin, "get_settings", lambda: Settings(_env_file=None, GOOGLE_SERVICE_ACCOUNT_JSON=""))

    with TestClient(main.app) as client:
        page = client.get("/admin/onboard")
        created = client.post(
            "/admin/create-pharmacy",
            json={
                "pharmacy_name": "ABC Pharmacy",
                "owner_name": "Mary",
                "phone": "0712345678",
                "location": "Nairobi",
                "notes": "Pilot",
            },
        )
        listed = client.get("/admin/pharmacies")
        pharmacy_id = created.json()["pharmacy_id"]
        shown = client.get(f"/admin/pharmacy/{pharmacy_id}")
        placeholder = client.post("/admin/photo-onboard-placeholder")

    assert page.status_code == 200
    assert "PharMareen Pharmacy Onboarding" in page.text
    assert created.status_code == 200
    assert created.json()["ok"] is True
    assert listed.json()["pharmacies"]
    assert shown.json()["pharmacy"]["pharmacy_id"] == pharmacy_id
    assert placeholder.json()["ok"] is True


def test_existing_commands_update_inventory_sales_restocks_and_report(monkeypatch):
    settings = Settings(_env_file=None, DEMO_MODE=True)
    store = DemoPharmacyStore(settings)
    service = IntakeService(AIService(settings), store, timezone=settings.timezone)

    stock_before = service.process_text("Panadol stock")
    sale = service.process_text("Panadol 2")
    stock_after = service.process_text("Panadol stock")
    restock = service.process_text("Panadol restock 20")
    batch = service.process_text("Panadol 2, Antacid 1")
    report = service.process_text("report today")

    assert "Panadol" in stock_before
    assert "Panadol" in sale and "Stock left" in sale
    assert "28" in stock_after
    assert "added" in restock.lower() or "Restock" in restock
    assert "Batch processed" in batch
    assert "Daily Report" in report
    assert store.read_transactions("2099-01-01") == []
