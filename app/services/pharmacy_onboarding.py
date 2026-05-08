from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

try:
    from googleapiclient.discovery import build as build_google_service
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    build_google_service = None

from app.config import Settings
from app.sheets import (
    DAILY_LOG,
    DAILY_LOG_HEADERS,
    DAILY_REPORTS,
    DAILY_REPORT_HEADERS,
    MASTER_STOCK,
    MASTER_STOCK_HEADERS,
    REQUEST_LOG,
    REQUEST_LOG_HEADERS,
    TRANSACTIONS,
    TRANSACTION_HEADERS,
    prepare_google_credentials_file,
    validate_service_account_json,
)


INVENTORY_HEADERS = [
    "Drug Name",
    "Stock",
    "Default Cost Price",
    "Default Selling Price",
    "Reorder Level",
    "Default Supplier",
    "Expiry",
    "Notes",
    "Updated At",
]

SALES_HEADERS = [
    "Timestamp",
    "Drug",
    "Quantity",
    "Revenue",
    "Cost",
    "Profit",
    "User",
    "Source Message",
    "Pharmacy ID",
]

RESTOCKS_HEADERS = [
    "Timestamp",
    "Drug",
    "Quantity",
    "Cost",
    "Supplier",
    "User",
    "Source Message",
    "Pharmacy ID",
]

REPORTS_HEADERS = [
    "Date",
    "Revenue",
    "Cost",
    "Profit",
    "Transactions",
    "Low Stock Items",
    "Pharmacy ID",
]

SETTINGS_HEADERS = ["Key", "Value"]

SUPPLIERS_HEADERS = [
    "Supplier ID",
    "Supplier Name",
    "Phone",
    "Location",
    "Notes",
    "Created At",
]

SUPPLIER_PRICES_HEADERS = [
    "Drug Name",
    "Supplier ID",
    "Supplier Name",
    "Cost Price",
    "Last Restock Date",
    "Notes",
]

LOW_STOCK_HEADERS = [
    "Timestamp",
    "Drug Name",
    "Current Stock",
    "Reorder Level",
    "Suggested Supplier",
    "Pharmacy ID",
]

AUDIT_LOG_HEADERS = [
    "Timestamp",
    "Action",
    "User",
    "Source",
    "Details",
    "Pharmacy ID",
]

PHARMACIES_HEADERS = [
    "Pharmacy ID",
    "Pharmacy Name",
    "Owner Name",
    "Phone",
    "Location",
    "Spreadsheet ID",
    "Spreadsheet URL",
    "Created At",
    "Status",
    "Notes",
]

PHASE3_SHEETS: dict[str, list[str]] = {
    "Inventory": INVENTORY_HEADERS,
    "Sales": SALES_HEADERS,
    "Restocks": RESTOCKS_HEADERS,
    "Reports": REPORTS_HEADERS,
    "Settings": SETTINGS_HEADERS,
    "Suppliers": SUPPLIERS_HEADERS,
    "Supplier_Prices": SUPPLIER_PRICES_HEADERS,
    "Low_Stock": LOW_STOCK_HEADERS,
    "Audit_Log": AUDIT_LOG_HEADERS,
}

LEGACY_COMPAT_SHEETS: dict[str, list[str]] = {
    MASTER_STOCK: MASTER_STOCK_HEADERS,
    DAILY_LOG: DAILY_LOG_HEADERS,
    DAILY_REPORTS: DAILY_REPORT_HEADERS,
    TRANSACTIONS: TRANSACTION_HEADERS,
    REQUEST_LOG: REQUEST_LOG_HEADERS,
}

STARTER_INVENTORY = [
    ("Panadol", 20, 5, 10, 5, "Default Supplier"),
    ("Antacid", 15, 8, 15, 5, "Default Supplier"),
    ("Insulin", 5, 300, 500, 2, "Default Supplier"),
]

logger = logging.getLogger("uvicorn.error")
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
SCOPES = [
    SHEETS_SCOPE,
    DRIVE_SCOPE,
    DRIVE_FILE_SCOPE,
]


@dataclass(frozen=True)
class PharmacyPayload:
    pharmacy_name: str
    owner_name: str = ""
    phone: str = ""
    location: str = ""
    notes: str = ""


def generate_pharmacy_id(pharmacy_name: str, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    slug = re.sub(r"[^a-z0-9]+", "_", pharmacy_name.lower()).strip("_")
    slug = slug or "pharmacy"
    return f"{slug}_{now:%Y%m%d}_{uuid4().hex[:6]}"


def local_registry_path() -> Path:
    return Path("data") / "pharmacies_registry.json"


def has_google_credentials(settings: Settings) -> bool:
    raw = (
        os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
        or str(settings.google_service_account_json or "")
    ).strip()
    return raw.startswith("{") or bool(raw and Path(raw).expanduser().exists())


def admin_sheet_id(settings: Settings) -> str:
    return (
        os.environ.get("PHARMAREEN_ADMIN_SHEET_ID")
        or str(settings.pharmareen_admin_sheet_id or "")
    ).strip()


class PharmacyOnboardingService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_pharmacy(self, payload: PharmacyPayload) -> dict[str, Any]:
        pharmacy_name = payload.pharmacy_name.strip()
        if not pharmacy_name:
            raise ValueError("Pharmacy name is required")

        now = datetime.utcnow()
        created_at = now.isoformat(timespec="seconds")
        pharmacy_id = generate_pharmacy_id(pharmacy_name, now=now)

        diagnostics = self.google_diagnostics()
        logger.info(
            "Phase 3 Google diagnostics: google credentials loaded: %s; "
            "admin sheet id loaded: %s; google client initialized: %s; "
            "google-api-python-client installed: %s; "
            "scopes include spreadsheets: %s; scopes include drive: %s",
            "yes" if diagnostics["google_credentials_loaded"] else "no",
            "yes" if diagnostics["admin_sheet_id_loaded"] else "no",
            "yes" if diagnostics["google_client_initialized"] else "no",
            "yes" if diagnostics["google_api_client_installed"] else "no",
            "yes" if diagnostics["credentials_scopes_include_spreadsheets"] else "no",
            "yes" if diagnostics["credentials_scopes_include_drive"] else "no",
        )
        logger.info(
            "Phase 3 live sheet creation attempted: %s",
            "yes" if diagnostics["google_credentials_loaded"] else "no",
        )

        google_error = ""
        try:
            result = self._create_google_sheet(pharmacy_id, payload, created_at)
            status = "google_live"
            message = f"{pharmacy_name} database created successfully"
        except Exception as exc:
            google_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Phase 3 live sheet creation failed: %s", google_error)
            result = {
                "spreadsheet_id": f"local_{pharmacy_id}",
                "spreadsheet_url": f"local://data/pharmacies_registry.json#{pharmacy_id}",
                "tabs": list(PHASE3_SHEETS),
                "local_fallback": True,
                "google_error": google_error,
            }
            status = "local_fallback"
            message = f"{pharmacy_name} saved locally. Connect Google Sheets to create a live database."

        record = {
            "pharmacy_id": pharmacy_id,
            "pharmacy_name": pharmacy_name,
            "owner_name": payload.owner_name.strip(),
            "phone": payload.phone.strip(),
            "location": payload.location.strip(),
            "spreadsheet_id": result["spreadsheet_id"],
            "spreadsheet_url": result["spreadsheet_url"],
            "created_at": created_at,
            "status": status,
            "notes": payload.notes.strip(),
        }
        self._save_registry_record(record)
        response = {
            "ok": True,
            "message": message,
            **record,
            "tabs": result.get("tabs", list(PHASE3_SHEETS)),
            "google_diagnostics": diagnostics,
        }
        if google_error:
            response["google_error"] = google_error
        return response

    def create_pharmacies_bulk(self, payloads: list[PharmacyPayload]) -> dict[str, Any]:
        created: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for payload in payloads:
            try:
                created.append(self.create_pharmacy(payload))
            except Exception as exc:
                failed.append({"pharmacy_name": payload.pharmacy_name, "error": str(exc)})
        return {"ok": not failed, "created": created, "failed": failed}

    def list_pharmacies(self) -> list[dict[str, Any]]:
        if admin_sheet_id(self.settings) and has_google_credentials(self.settings):
            try:
                worksheet = self._admin_worksheet()
                return worksheet.get_all_records()
            except Exception as exc:
                logger.warning("Could not read admin registry sheet: %s: %s", type(exc).__name__, exc)
        return self._read_local_registry()

    def get_pharmacy(self, pharmacy_id: str) -> dict[str, Any] | None:
        wanted = pharmacy_id.strip()
        for record in self.list_pharmacies():
            if str(record.get("Pharmacy ID") or record.get("pharmacy_id") or "").strip() == wanted:
                return normalize_registry_record(record)
        return None

    def _create_google_sheet(self, pharmacy_id: str, payload: PharmacyPayload, created_at: str) -> dict[str, Any]:
        if not has_google_credentials(self.settings):
            raise RuntimeError("Google Sheets credentials are not configured")

        logger.info("Phase 3 live sheet creation executing with Google API")
        spreadsheet = self._create_live_spreadsheet(f"PharMareen - {payload.pharmacy_name.strip()}")
        ensure_spreadsheet_schema(spreadsheet)
        seed_pharmacy_sheet(spreadsheet, pharmacy_id, payload, created_at)
        return {
            "spreadsheet_id": spreadsheet.id,
            "spreadsheet_url": spreadsheet.url,
            "tabs": list(PHASE3_SHEETS),
            "local_fallback": False,
        }

    def _save_registry_record(self, record: dict[str, Any]) -> None:
        if admin_sheet_id(self.settings) and has_google_credentials(self.settings):
            try:
                worksheet = self._admin_worksheet()
                worksheet.append_row(
                    [record.get(key_to_snake(header), record.get(header, "")) for header in PHARMACIES_HEADERS],
                    value_input_option="USER_ENTERED",
                )
                return
            except Exception as exc:
                logger.warning("Could not save admin registry sheet row: %s: %s", type(exc).__name__, exc)
        records = self._read_local_registry()
        records.append(record)
        path = local_registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def _read_local_registry(self) -> list[dict[str, Any]]:
        path = local_registry_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [normalize_registry_record(record) for record in data if isinstance(record, dict)]

    def _admin_worksheet(self):
        spreadsheet = self._gspread_client().open_by_key(admin_sheet_id(self.settings))
        return ensure_worksheet(spreadsheet, "Pharmacies", PHARMACIES_HEADERS)

    def _create_live_spreadsheet(self, title: str):
        credentials = self._google_credentials()
        client = gspread.authorize(credentials)
        logger.info(
            "Phase 3 live sheet creation using scoped credentials: "
            "spreadsheets=%s; drive=%s; drive.file=%s",
            "yes" if SHEETS_SCOPE in (credentials.scopes or []) else "no",
            "yes" if DRIVE_SCOPE in (credentials.scopes or []) else "no",
            "yes" if DRIVE_FILE_SCOPE in (credentials.scopes or []) else "no",
        )

        if build_google_service is not None:
            service = build_google_service(
                "sheets",
                "v4",
                credentials=credentials,
                cache_discovery=False,
            )
            response = (
                service.spreadsheets()
                .create(
                    body={"properties": {"title": title}},
                    fields="spreadsheetId,spreadsheetUrl",
                )
                .execute()
            )
            spreadsheet_id = response.get("spreadsheetId")
            if not spreadsheet_id:
                raise RuntimeError("Google Sheets API did not return a spreadsheet ID")
            return client.open_by_key(spreadsheet_id)

        return client.create(title)

    def _gspread_client(self):
        return gspread.authorize(self._google_credentials())

    def _google_credentials(self):
        raw_credentials = (os.environ.get("GOOGLE_SHEETS_CREDENTIALS") or "").strip()
        configured_value = str(self.settings.google_service_account_json or "").strip()

        if raw_credentials.startswith("{"):
            info = validate_service_account_json(raw_credentials)
            prepare_google_credentials_file(self.settings)
            return Credentials.from_service_account_info(info, scopes=SCOPES)

        if configured_value.startswith("{"):
            info = validate_service_account_json(configured_value)
            prepare_google_credentials_file(self.settings)
            return Credentials.from_service_account_info(info, scopes=SCOPES)

        credential_path = prepare_google_credentials_file(self.settings)
        return Credentials.from_service_account_file(
            str(credential_path),
            scopes=SCOPES,
        )

    def google_diagnostics(self) -> dict[str, bool]:
        client_initialized = False
        scopes_include_spreadsheets = False
        scopes_include_drive = False
        scopes_include_drive_file = False
        if has_google_credentials(self.settings):
            try:
                credentials = self._google_credentials()
                scopes = set(credentials.scopes or [])
                scopes_include_spreadsheets = SHEETS_SCOPE in scopes
                scopes_include_drive = DRIVE_SCOPE in scopes
                scopes_include_drive_file = DRIVE_FILE_SCOPE in scopes
                gspread.authorize(credentials)
                if build_google_service is not None:
                    build_google_service("sheets", "v4", credentials=credentials, cache_discovery=False)
                    build_google_service("drive", "v3", credentials=credentials, cache_discovery=False)
                client_initialized = True
            except Exception as exc:
                logger.warning("Google client initialization failed: %s: %s", type(exc).__name__, exc)

        return {
            "google_credentials_loaded": has_google_credentials(self.settings),
            "admin_sheet_id_loaded": bool(admin_sheet_id(self.settings)),
            "google_client_initialized": client_initialized,
            "google_api_client_installed": build_google_service is not None,
            "credentials_scopes_include_spreadsheets": scopes_include_spreadsheets,
            "credentials_scopes_include_drive": scopes_include_drive,
            "credentials_scopes_include_drive_file": scopes_include_drive_file,
        }


def ensure_spreadsheet_schema(spreadsheet: Any) -> None:
    for title, headers in {**PHASE3_SHEETS, **LEGACY_COMPAT_SHEETS}.items():
        ensure_worksheet(spreadsheet, title, headers)


def ensure_worksheet(spreadsheet: Any, title: str, headers: list[str]):
    try:
        worksheet = spreadsheet.worksheet(title)
    except WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=2000, cols=max(len(headers), 8))
    existing = worksheet.row_values(1)
    if existing[: len(headers)] != headers:
        worksheet.update("A1", [headers])
    return worksheet


def seed_pharmacy_sheet(spreadsheet: Any, pharmacy_id: str, payload: PharmacyPayload, created_at: str) -> None:
    inventory = spreadsheet.worksheet("Inventory")
    master_stock = spreadsheet.worksheet(MASTER_STOCK)
    settings = spreadsheet.worksheet("Settings")
    suppliers = spreadsheet.worksheet("Suppliers")
    supplier_prices = spreadsheet.worksheet("Supplier_Prices")

    timestamp = created_at.replace("T", " ")
    inventory_rows = [
        [name, stock, cost, price, reorder, supplier, "", "", timestamp]
        for name, stock, cost, price, reorder, supplier in STARTER_INVENTORY
    ]
    inventory.append_rows(inventory_rows, value_input_option="USER_ENTERED")
    master_stock.append_rows(
        [[name, price, cost, stock, reorder] for name, stock, cost, price, reorder, _supplier in STARTER_INVENTORY],
        value_input_option="USER_ENTERED",
    )
    settings.append_rows(
        [
            ["pharmacy_id", pharmacy_id],
            ["pharmacy_name", payload.pharmacy_name.strip()],
            ["owner_name", payload.owner_name.strip()],
            ["phone", payload.phone.strip()],
            ["location", payload.location.strip()],
            ["created_at", created_at],
            ["system_version", "phase_3_google_sheets"],
            ["data_mode", "google_sheets"],
        ],
        value_input_option="USER_ENTERED",
    )
    suppliers.append_row(
        ["default_supplier", "Default Supplier", "", payload.location.strip(), "Starter supplier", timestamp],
        value_input_option="USER_ENTERED",
    )
    supplier_prices.append_rows(
        [[name, "default_supplier", "Default Supplier", cost, "", "Starter sample price"] for name, _stock, cost, _price, _reorder, _supplier in STARTER_INVENTORY],
        value_input_option="USER_ENTERED",
    )


def normalize_registry_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "pharmacy_id": str(record.get("pharmacy_id") or record.get("Pharmacy ID") or "").strip(),
        "pharmacy_name": str(record.get("pharmacy_name") or record.get("Pharmacy Name") or "").strip(),
        "owner_name": str(record.get("owner_name") or record.get("Owner Name") or "").strip(),
        "phone": str(record.get("phone") or record.get("Phone") or "").strip(),
        "location": str(record.get("location") or record.get("Location") or "").strip(),
        "spreadsheet_id": str(record.get("spreadsheet_id") or record.get("Spreadsheet ID") or "").strip(),
        "spreadsheet_url": str(record.get("spreadsheet_url") or record.get("Spreadsheet URL") or "").strip(),
        "created_at": str(record.get("created_at") or record.get("Created At") or "").strip(),
        "status": str(record.get("status") or record.get("Status") or "").strip(),
        "notes": str(record.get("notes") or record.get("Notes") or "").strip(),
    }


def key_to_snake(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_")
