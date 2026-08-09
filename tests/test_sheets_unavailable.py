from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings
from app.sheets import (
    GoogleSheetsStore,
    INVENTORY,
    MASTER_STOCK,
    SHEETS_UNAVAILABLE_MESSAGE,
    SheetsUnavailableError,
    prepare_google_credentials_file,
)


class UnavailableStore:
    is_available = False

    def ensure_schema(self) -> None:
        return None


class FailingReportService:
    def generate_daily_report(self, report_date, send_whatsapp=True):
        raise SheetsUnavailableError(SHEETS_UNAVAILABLE_MESSAGE)


class FakeSettings:
    timezone = "Africa/Nairobi"
    report_trigger_token = None
    pharmareen_default_pharmacy_id = ""


class FakeWorksheet:
    def __init__(self, values):
        self.values = values
        self.updated_cells = []

    def get_all_values(self):
        return self.values

    def row_values(self, row):
        if row <= 0 or row > len(self.values):
            return []
        return self.values[row - 1]

    def update_cell(self, row, column, value):
        self.updated_cells.append((row, column, value))
        while len(self.values) < row:
            self.values.append([])
        while len(self.values[row - 1]) < column:
            self.values[row - 1].append("")
        self.values[row - 1][column - 1] = value

    def append_row(self, row, value_input_option=None):
        self.values.append(list(row))

    def update(self, cell, rows):
        row_number = int(str(cell).lstrip("A"))
        while len(self.values) < row_number:
            self.values.append([])
        self.values[row_number - 1] = list(rows[0])


class FakeSpreadsheet:
    def __init__(self, worksheets):
        self.worksheets = worksheets

    def worksheet(self, title):
        return self.worksheets[title]


def make_settings(service_account_path: str) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test-openai-key",
        openai_parse_model="gpt-5",
        google_sheets_spreadsheet_id="test-sheet",
        google_service_account_json=service_account_path,
        whatsapp_number="254100000000",
        owner_whatsapp_to="whatsapp:+20000000000",
    )


def make_fake_sheet_store(worksheets) -> GoogleSheetsStore:
    store = object.__new__(GoogleSheetsStore)
    store.spreadsheet = FakeSpreadsheet(worksheets)
    store.settings = FakeSettings()
    store.unavailable_message = SHEETS_UNAVAILABLE_MESSAGE
    return store


def test_operations_catalog_resume_reads_pharmacy_inventory_when_master_stock_is_empty():
    store = make_fake_sheet_store({
        MASTER_STOCK: FakeWorksheet([["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"]]),
        "pharmacy-a_inventory": FakeWorksheet([
            ["Drug", "Stock", "Selling Price", "Cost Price", "Low Stock Alert Level"],
            ["Ibuprofen", "13", "18", "10", "5"],
        ]),
        INVENTORY: FakeWorksheet([["Drug", "Stock", "Selling Price"]]),
    })

    assert store.list_pharmacy_catalog_records("pharmacy-a") == [{
        "name": "Ibuprofen",
        "strength": "",
        "forms": [],
        "units": [],
        "sellingPrice": 18.0,
        "costPrice": 10.0,
        "stockLeft": 13,
        "reorderLevel": 5,
        "supplier": "",
        "barcode": "",
        "batches": [],
        "shelf": "",
    }]


def test_operations_catalog_resume_does_not_read_another_pharmacy_inventory():
    store = make_fake_sheet_store({
        MASTER_STOCK: FakeWorksheet([["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"]]),
        "pharmacy-a_inventory": FakeWorksheet([["Drug", "Stock", "Selling Price"]]),
        "pharmacy-b_inventory": FakeWorksheet([
            ["Drug", "Stock", "Selling Price"],
            ["Private B Medicine", "4", "20"],
        ]),
        INVENTORY: FakeWorksheet([["Drug", "Stock", "Selling Price"]]),
    })

    assert store.list_pharmacy_catalog_records("pharmacy-a") == []


def test_ms20_operations_state_round_trips_as_durable_pharmacy_scoped_truth():
    from app.sheets import MS20_OPERATIONS_STATE, MS20_OPERATIONS_STATE_HEADERS

    store = make_fake_sheet_store({
        MS20_OPERATIONS_STATE: FakeWorksheet([MS20_OPERATIONS_STATE_HEADERS]),
    })
    saved = store.save_ms20_operations_state(
        "pharmacy-a",
        {"name": "Afya Pharmacy", "owner": "Mary", "branch": "Main", "location": "Nairobi"},
        [{"name": "Ibuprofen", "stockLeft": 13}],
    )

    assert saved["initialized"] is True
    assert saved["pharmacy_name"] == "Afya Pharmacy"
    assert saved["catalog"] == [{"name": "Ibuprofen", "stockLeft": 13}]
    assert store.get_ms20_operations_state("pharmacy-b") is None


@pytest.mark.parametrize("file_contents", ["", "{not-json"])
def test_store_starts_unavailable_for_empty_or_invalid_service_account(file_contents, tmp_path):
    service_account = tmp_path / f"service-account-{uuid4().hex}.json"
    service_account.write_text(file_contents, encoding="utf-8")

    store = GoogleSheetsStore(make_settings(str(service_account)))

    assert store.is_available is False
    with pytest.raises(SheetsUnavailableError, match="Google Sheets is not configured"):
        store.list_master_drug_names()
    service_account.unlink(missing_ok=True)


def test_store_starts_unavailable_for_missing_service_account(tmp_path):
    missing_service_account = tmp_path / f"missing-service-account-{uuid4().hex}.json"

    store = GoogleSheetsStore(make_settings(str(missing_service_account)))

    assert store.is_available is False
    with pytest.raises(SheetsUnavailableError, match="Google Sheets is not configured"):
        store.read_daily_logs("2026-04-27")


def test_google_sheets_credentials_env_is_written_to_service_account_file(tmp_path, monkeypatch):
    credentials_json = """
    {
      "type": "service_account",
      "project_id": "test-project",
      "private_key_id": "test-key-id",
      "private_key": "-----BEGIN PRIVATE KEY-----\\nTEST\\n-----END PRIVATE KEY-----\\n",
      "client_email": "test@example.iam.gserviceaccount.com",
      "client_id": "123456789",
      "token_uri": "https://oauth2.googleapis.com/token"
    }
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS", credentials_json)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")

    path = prepare_google_credentials_file(make_settings("./service-account.json"))

    assert path == tmp_path / "service-account.json"
    assert path.exists()
    written = path.read_text(encoding="utf-8")
    assert "test@example.iam.gserviceaccount.com" in written
    assert "private_key" in written


def test_google_sheets_credentials_env_invalid_json_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS", "{not-json")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")

    with pytest.raises(ValueError, match="not valid JSON"):
        prepare_google_credentials_file(make_settings("./service-account.json"))


def test_find_stock_prefers_inventory_zero_for_stock_safety():
    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    inventory = FakeWorksheet(
        [
            ["Drug", "Stock", "Cost Price", "Selling Price", "Average Cost", "Low Stock Alert Level", "Last Updated"],
            ["ORS", "0", "50", "80", "", "10", ""],
        ]
    )
    store = make_fake_sheet_store({MASTER_STOCK: master, INVENTORY: inventory})

    stock = store.find_stock("ORS")

    assert stock is not None
    assert stock.current_stock == 0
    assert stock.selling_price == 80
    assert stock.cost_price == 50
    assert stock.reorder_level == 10


def test_find_stock_prefers_default_pharmacy_inventory_zero_for_stock_safety():
    class DefaultPharmacySettings(FakeSettings):
        pharmareen_default_pharmacy_id = "abc_pharmacy"

    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    global_inventory = FakeWorksheet(
        [
            ["Drug", "Stock", "Cost Price", "Selling Price", "Average Cost", "Low Stock Alert Level", "Last Updated"],
            ["ORS", "2", "50", "80", "", "10", ""],
        ]
    )
    pharmacy_inventory = FakeWorksheet(
        [
            ["Drug Name", "Stock", "Default Cost Price", "Default Selling Price", "Reorder Level", "Default Supplier", "Expiry", "Notes", "Updated At"],
            ["ORS", "0", "50", "80", "10", "", "", "", ""],
        ]
    )
    store = make_fake_sheet_store(
        {MASTER_STOCK: master, INVENTORY: global_inventory, "abc_pharmacy_inventory": pharmacy_inventory}
    )
    store.settings = DefaultPharmacySettings()

    stock = store.find_stock("ORS")

    assert stock is not None
    assert stock.current_stock == 0
    assert stock.reorder_level == 10


def test_find_stock_sees_prefixed_inventory_zero_even_without_default_pharmacy_setting():
    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    global_inventory = FakeWorksheet(
        [
            ["Drug", "Stock", "Cost Price", "Selling Price", "Average Cost", "Low Stock Alert Level", "Last Updated"],
            ["ORS", "2", "50", "80", "", "10", ""],
        ]
    )
    live_pharmacy_inventory = FakeWorksheet(
        [
            ["Drug Name", "Stock", "Default Cost Price", "Default Selling Price", "Reorder Level"],
            ["ORS", "0", "50", "80", "10"],
        ]
    )
    store = make_fake_sheet_store(
        {
            MASTER_STOCK: master,
            INVENTORY: global_inventory,
            "real_pharmacy_inventory": live_pharmacy_inventory,
        }
    )

    stock = store.find_stock("ORS")
    safety_stock = store.find_stock_for_safety("ORS")

    assert stock is not None
    assert stock.current_stock == 0
    assert safety_stock is not None
    assert safety_stock.current_stock == 0


def test_find_stock_reads_nonstandard_inventory_title_and_headers_for_safety():
    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    live_inventory = FakeWorksheet(
        [
            ["Medicine", "Quantity", "Unit Cost", "Price", "Min Stock"],
            ["ORS", "0", "50", "80", "10"],
        ]
    )
    store = make_fake_sheet_store({MASTER_STOCK: master, "Main Pharmacy Inventory": live_inventory})

    stock = store.find_stock("ORS")
    safety_stock = store.find_stock_for_safety("ORS")

    assert stock is not None
    assert stock.current_stock == 0
    assert stock.selling_price == 80
    assert stock.cost_price == 50
    assert stock.reorder_level == 10
    assert safety_stock is not None
    assert safety_stock.current_stock == 0


def test_find_stock_reads_legacy_stock_sheet_when_inventory_name_is_missing():
    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    stock_sheet = FakeWorksheet(
        [
            ["Item Name", "Available Stock", "Unit Cost", "Unit Price", "Minimum Stock"],
            ["ORS", "0", "50", "80", "10"],
        ]
    )
    store = make_fake_sheet_store({MASTER_STOCK: master, "Stock": stock_sheet})

    stock = store.find_stock_for_safety("ORS")

    assert stock is not None
    assert stock.current_stock == 0
    assert stock.selling_price == 80


def test_update_current_stock_updates_master_stock_and_inventory_tabs():
    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    inventory = FakeWorksheet(
        [
            ["Drug", "Stock", "Cost Price", "Selling Price", "Average Cost", "Low Stock Alert Level", "Last Updated"],
            ["ORS", "0", "50", "80", "", "10", ""],
        ]
    )
    store = make_fake_sheet_store({MASTER_STOCK: master, INVENTORY: inventory})
    stock = store.find_stock("ORS")

    store.update_current_stock(stock, 0)

    assert master.updated_cells == [(2, 4, 0)]
    assert inventory.updated_cells == [(2, 2, 0)]


def test_update_current_stock_updates_default_pharmacy_inventory_tab():
    class DefaultPharmacySettings(FakeSettings):
        pharmareen_default_pharmacy_id = "abc_pharmacy"

    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    global_inventory = FakeWorksheet(
        [
            ["Drug", "Stock", "Cost Price", "Selling Price", "Average Cost", "Low Stock Alert Level", "Last Updated"],
            ["ORS", "2", "50", "80", "", "10", ""],
        ]
    )
    pharmacy_inventory = FakeWorksheet(
        [
            ["Drug Name", "Stock", "Default Cost Price", "Default Selling Price", "Reorder Level", "Default Supplier", "Expiry", "Notes", "Updated At"],
            ["ORS", "0", "50", "80", "10", "", "", "", ""],
        ]
    )
    store = make_fake_sheet_store(
        {MASTER_STOCK: master, INVENTORY: global_inventory, "abc_pharmacy_inventory": pharmacy_inventory}
    )
    store.settings = DefaultPharmacySettings()
    stock = store.find_stock("ORS")

    store.update_current_stock(stock, 0)

    assert master.updated_cells == [(2, 4, 0)]
    assert pharmacy_inventory.updated_cells == [(2, 2, 0)]
    assert global_inventory.updated_cells == [(2, 2, 0)]


def test_update_current_stock_updates_nonstandard_inventory_quantity_column():
    master = FakeWorksheet(
        [
            ["Drug Name", "Selling Price", "Cost Price", "Current Stock", "Reorder Level"],
            ["ORS", "80", "50", "2", "10"],
        ]
    )
    live_inventory = FakeWorksheet(
        [
            ["Medicine", "Quantity", "Unit Cost", "Price", "Min Stock"],
            ["ORS", "0", "50", "80", "10"],
        ]
    )
    store = make_fake_sheet_store({MASTER_STOCK: master, "Main Pharmacy Inventory": live_inventory})
    stock = store.find_stock("ORS")

    store.update_current_stock(stock, 0)

    assert master.updated_cells == [(2, 4, 0)]
    assert live_inventory.updated_cells == [(2, 2, 0)]


def test_health_and_test_endpoint_work_when_sheets_are_unavailable(monkeypatch):
    monkeypatch.setattr(main, "get_sheet_store", lambda: UnavailableStore())

    with TestClient(main.app) as client:
        health_response = client.get("/health")
        test_response = client.get("/test")

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert test_response.status_code == 200
    assert test_response.json()["message"] == SHEETS_UNAVAILABLE_MESSAGE


def test_daily_report_endpoint_returns_clear_message_when_sheets_are_unavailable(monkeypatch):
    monkeypatch.setattr(main, "get_sheet_store", lambda: UnavailableStore())
    monkeypatch.setattr(main, "get_report_service", lambda: FailingReportService())
    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())

    with TestClient(main.app) as client:
        response = client.post("/reports/daily?send_whatsapp=false")

    assert response.status_code == 503
    assert response.json() == {"detail": SHEETS_UNAVAILABLE_MESSAGE}
