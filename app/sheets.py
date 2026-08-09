from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

from app.config import Settings
from app.domain import ParsedEvent, StockItem
from app.services.medicine_catalog import match_local_medicine, search_catalog_entries
from app.utils import normalize_key, parse_int, parse_money, now_in_timezone


MASTER_STOCK = "Master_Stock"
DAILY_LOG = "Daily_Log"
DAILY_REPORTS = "Daily_Reports"
INVENTORY = "Inventory"
TRANSACTIONS = "Transactions"
REQUEST_LOG = "Request_Log"
BATCHES = "Batches"
SALES_LOG = "Sales_Log"
RESTOCK_LOG = "Restock_Log"
ISSUE_LOG = "Issue_Log"
RETURNS_LOG = "Returns_Log"
SUPPLIERS = "Suppliers"
IMPORT_REVIEW_QUEUE = "Import_Review_Queue"
OFFLINE_SYNC_LOG = "Offline_Sync_Log"
MEDICINE_CATALOG_METADATA = "Medicine_Catalog_Metadata"

REPORT_SOURCE_CACHE_TTL_SECONDS = 600.0
REPORT_SOURCE_REFRESH_SECONDS = 300.0
REPORT_SOURCE_CACHE_MAX_ROWS = 100000
PHARMACIES = "Pharmacies"
MS20_OPERATIONS_STATE = "MS20_Operations_State"
MS20_OPERATIONS_STATE_HEADERS = [
    "Pharmacy ID", "Initialized", "Pharmacy Name", "Owner Name", "Branch",
    "Location", "Payments", "Catalog JSON", "Updated At",
]

SHEETS_UNAVAILABLE_MESSAGE = (
    "Google Sheets is not configured. Add a valid service-account.json to enable logging."
)

logger = logging.getLogger(__name__)

STOCK_NAME_HEADERS = [
    "Drug",
    "Drug Name",
    "Medicine",
    "Medicine Name",
    "Item",
    "Item Name",
    "Product",
    "Product Name",
    "Name",
]

STOCK_QUANTITY_HEADERS = [
    "Stock",
    "Current Stock",
    "Current Stock Level",
    "Quantity",
    "Qty",
    "On Hand",
    "Available",
    "Available Stock",
    "Balance",
    "Stock Left",
]

STOCK_COST_HEADERS = [
    "Cost Price",
    "Default Cost Price",
    "Buying Price",
    "Unit Cost",
    "Average Cost",
]

STOCK_SELLING_HEADERS = [
    "Selling Price",
    "Default Selling Price",
    "Price",
    "Unit Price",
]

STOCK_REORDER_HEADERS = [
    "Low Stock Alert Level",
    "Reorder Level",
    "Minimum Stock",
    "Min Stock",
    "Restock Level",
]

INVENTORY_TITLE_BLOCKLIST = {
    "audit",
    "dailylog",
    "dailyreports",
    "importreview",
    "issued",
    "issuelog",
    "log",
    "lowstock",
    "offline",
    "report",
    "request",
    "restocklog",
    "return",
    "saleslog",
    "settings",
    "supplier",
    "transaction",
}


def record_text_value(record: dict[str, Any], aliases: list[str]) -> str:
    for alias in aliases:
        value = record.get(alias)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def record_int_value(record: dict[str, Any], aliases: list[str]) -> int | None:
    for alias in aliases:
        value = parse_int(record.get(alias), default=None)
        if value is not None:
            return value
    return None


def record_money_value(record: dict[str, Any], aliases: list[str]) -> float | None:
    for alias in aliases:
        value = parse_money(record.get(alias))
        if value is not None:
            return value
    return None


def metadata_text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def metadata_values(value: Any) -> list[str]:
    return [item.strip() for item in metadata_text_value(value).split(",") if item.strip()]


def first_metadata_value(value: Any) -> str:
    return next(iter(metadata_values(value)), "")


def is_inventory_worksheet_title(title: str) -> bool:
    clean_title = str(title or "").strip()
    if not clean_title:
        return False
    key = normalize_key(clean_title)
    if key == normalize_key(INVENTORY):
        return True
    if key == normalize_key(MASTER_STOCK):
        return False
    if key.endswith("inventory"):
        return True
    if key in {"stock", "stocks", "stocklist", "currentstock", "pharmacystock"}:
        return True
    if "inventory" not in key and "stock" not in key:
        return False
    return not any(blocked in key for blocked in INVENTORY_TITLE_BLOCKLIST)


class SheetsUnavailableError(RuntimeError):
    pass

MASTER_STOCK_HEADERS = [
    "Drug Name",
    "Selling Price",
    "Cost Price",
    "Current Stock",
    "Reorder Level",
]

DAILY_LOG_HEADERS = [
    "Date",
    "Time",
    "Drug Name",
    "Action",
    "Quantity",
    "Price",
    "Total Value",
    "Notes",
]

DAILY_REPORT_HEADERS = [
    "Date",
    "Total Sales",
    "Total Cost",
    "Gross Profit",
    "Total Items Sold",
    "Sale Transactions",
    "Most Requested Drugs",
    "Most Sold Drugs",
    "Missed Sales",
    "Restocks Today",
    "Low Stock Warnings",
    "AI Recommendation Summary",
    "Full Report Text",
]

INVENTORY_HEADERS = [
    "Drug",
    "Stock",
    "Cost Price",
    "Selling Price",
    "Average Cost",
    "Low Stock Alert Level",
    "Last Updated",
]

TRANSACTION_HEADERS = [
    "Timestamp",
    "Date",
    "Type",
    "Drug",
    "Quantity",
    "Unit Cost",
    "Unit Selling Price",
    "Total Cost",
    "Total Sales",
    "Profit",
    "Note",
]

REQUEST_LOG_HEADERS = [
    "Timestamp",
    "Sender",
    "Message Type",
    "Success",
    "Error Reason",
]

BATCH_HEADERS = [
    "batch_id",
    "drug_id",
    "drug_name",
    "generic_name",
    "brand_name",
    "category",
    "strength",
    "form",
    "pack_type",
    "units_per_pack",
    "units_per_strip",
    "quantity_received",
    "unit_received",
    "converted_total_units",
    "current_remaining_units",
    "minimum_stock_level",
    "expiry_date",
    "days_to_expiry",
    "expiry_status",
    "supplier_name",
    "invoice_number",
    "purchase_date",
    "delivery_date",
    "purchase_cost",
    "selling_price",
    "payment_status",
    "manufacturer_batch_number",
    "received_by",
    "entered_by",
    "recorded_at",
    "stock_location",
    "return_status",
    "return_quantity",
    "return_reason",
    "bad_drug_flag",
    "damaged_flag",
    "expired_flag",
    "supplier_contacted",
    "return_date",
    "refund_or_replacement_status",
]

SALES_LOG_HEADERS = [
    "sale_id",
    "drug_name",
    "quantity_sold",
    "unit_sold",
    "batch_id",
    "sold_by",
    "sold_at",
    "stock_before",
    "stock_after",
    "sale_amount",
]

RESTOCK_LOG_HEADERS = [
    "restock_id",
    "drug_name",
    "quantity_received",
    "unit_received",
    "expiry_date",
    "supplier_name",
    "invoice_number",
    "purchase_cost",
    "batch_id",
    "recorded_at",
    "note",
]

ISSUE_LOG_HEADERS = [
    "issue_id",
    "drug_name",
    "batch_id",
    "issue_type",
    "quantity",
    "supplier_name",
    "invoice_number",
    "reported_by",
    "reported_at",
    "status",
    "note",
]

RETURNS_LOG_HEADERS = [
    "return_id",
    "drug_name",
    "batch_id",
    "quantity",
    "return_reason",
    "supplier_name",
    "return_date",
    "refund_or_replacement_status",
    "note",
]

SUPPLIER_HEADERS = [
    "supplier_name",
    "contact",
    "supplier_reliability_score",
    "return_frequency",
    "last_updated",
]

IMPORT_REVIEW_HEADERS = [
    "Timestamp",
    "Sender",
    "Status",
    "Extracted Items",
    "Confidence",
    "Raw",
]

OFFLINE_SYNC_HEADERS = [
    "action_id",
    "action_type",
    "drug_name",
    "quantity",
    "created_by",
    "created_at",
    "sync_status",
    "retry_count",
    "last_error",
    "source",
]

MEDICINE_CATALOG_METADATA_HEADERS = [
    "Drug Name",
    "Generic Name",
    "Brand Names",
    "Aliases",
    "Category",
    "Strengths",
    "Dosage Forms",
    "Units",
    "Manufacturer/Importer",
    "PPB Registration Number",
    "Pack Sizes",
    "Source",
    "Last Updated",
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
    "Phone Number",
    "Timezone",
    "Currency",
    "Active",
    "Updated At",
]


class GoogleSheetsStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.spreadsheet = None
        self.unavailable_message = SHEETS_UNAVAILABLE_MESSAGE

        try:
            credential_path = prepare_google_credentials_file(settings)
            credentials = self._load_credentials(str(credential_path))
            client = gspread.authorize(credentials)
            self.spreadsheet = client.open_by_key(settings.google_sheets_spreadsheet_id)
            logger.info("Google Sheets connected successfully")
            self._ensure_report_cache_state()
        except Exception as exc:
            logger.warning("Google Sheets is unavailable: %s", exc)

    @property
    def is_available(self) -> bool:
        return self.spreadsheet is not None

    def ensure_schema(self) -> None:
        if not self.is_available:
            return
        self._ensure_worksheet(MASTER_STOCK, MASTER_STOCK_HEADERS, rows=2000)
        self._ensure_worksheet(DAILY_LOG, DAILY_LOG_HEADERS, rows=10000)
        self._ensure_worksheet(DAILY_REPORTS, DAILY_REPORT_HEADERS, rows=1000)
        self._ensure_worksheet(INVENTORY, INVENTORY_HEADERS, rows=2000)
        self._ensure_worksheet(TRANSACTIONS, TRANSACTION_HEADERS, rows=10000)
        self._ensure_worksheet(REQUEST_LOG, REQUEST_LOG_HEADERS, rows=10000)
        self._ensure_worksheet(BATCHES, BATCH_HEADERS, rows=10000)
        self._ensure_worksheet(SALES_LOG, SALES_LOG_HEADERS, rows=10000)
        self._ensure_worksheet(RESTOCK_LOG, RESTOCK_LOG_HEADERS, rows=10000)
        self._ensure_worksheet(ISSUE_LOG, ISSUE_LOG_HEADERS, rows=10000)
        self._ensure_worksheet(RETURNS_LOG, RETURNS_LOG_HEADERS, rows=10000)
        self._ensure_worksheet(SUPPLIERS, SUPPLIER_HEADERS, rows=1000)
        self._ensure_worksheet(IMPORT_REVIEW_QUEUE, IMPORT_REVIEW_HEADERS, rows=10000)
        self._ensure_worksheet(OFFLINE_SYNC_LOG, OFFLINE_SYNC_HEADERS, rows=10000)
        self._ensure_worksheet(MEDICINE_CATALOG_METADATA, MEDICINE_CATALOG_METADATA_HEADERS, rows=3000)
        self._ensure_worksheet(PHARMACIES, PHARMACIES_HEADERS, rows=2000)
        self._ensure_worksheet(MS20_OPERATIONS_STATE, MS20_OPERATIONS_STATE_HEADERS, rows=2000)

    def list_master_drug_names(self) -> list[str]:
        return [
            str(record.get("Drug Name") or "").strip()
            for record, _row_number in self._master_records_with_rows()
            if str(record.get("Drug Name") or "").strip()
        ]

    def find_stock(self, drug_name: str) -> StockItem | None:
        return self._find_stock_from_sources(drug_name, include_all_inventory=True)

    def find_stock_for_safety(self, drug_name: str, pharmacy_id: str | None = None) -> StockItem | None:
        """Read stock using the safest known value across trusted stock tabs.

        This is intentionally read-only. Live offline sync can include a
        pharmacy_id, but deployed phones can also have stale or blank IDs; we
        include every *_inventory tab so stale Master_Stock cannot override a
        newer pharmacy inventory showing zero stock.
        """
        return self._find_stock_from_sources(
            drug_name,
            pharmacy_id=pharmacy_id,
            include_all_inventory=True,
        )

    def _find_stock_from_sources(
        self,
        drug_name: str,
        *,
        pharmacy_id: str | None = None,
        include_all_inventory: bool = False,
    ) -> StockItem | None:
        wanted = normalize_key(drug_name)
        if not wanted:
            return None

        inventory_records = self._find_inventory_stock_records(
            wanted,
            pharmacy_id=pharmacy_id,
            include_all=include_all_inventory,
        )
        for record, row_number in self._master_records_with_rows():
            name = str(record.get("Drug Name") or "").strip()
            if normalize_key(name) != wanted:
                continue
            inventory = inventory_records[0][1] if inventory_records else {}
            master_stock = parse_int(record.get("Current Stock"), default=None)
            inventory_stocks = [
                record_int_value(item, STOCK_QUANTITY_HEADERS)
                for _title, item, _row in inventory_records
            ]
            inventory_stocks = [value for value in inventory_stocks if value is not None]
            stock_values = ([master_stock] if master_stock is not None else []) + inventory_stocks
            reorder_level = parse_int(record.get("Reorder Level"), default=None)

            return StockItem(
                drug_name=name,
                selling_price=parse_money(record.get("Selling Price")) or record_money_value(inventory, STOCK_SELLING_HEADERS),
                cost_price=parse_money(record.get("Cost Price")) or record_money_value(inventory, STOCK_COST_HEADERS),
                current_stock=min(stock_values) if stock_values else None,
                reorder_level=reorder_level
                if reorder_level is not None
                else record_int_value(inventory, STOCK_REORDER_HEADERS),
                row_number=row_number,
            )
        if inventory_records:
            _title, record, _row_number = inventory_records[0]
            name = record_text_value(record, STOCK_NAME_HEADERS)
            stock_values = [
                record_int_value(item, STOCK_QUANTITY_HEADERS)
                for _title, item, _row in inventory_records
            ]
            stock_values = [value for value in stock_values if value is not None]
            return StockItem(
                drug_name=name,
                selling_price=record_money_value(record, STOCK_SELLING_HEADERS),
                cost_price=record_money_value(record, STOCK_COST_HEADERS),
                current_stock=min(stock_values) if stock_values else None,
                reorder_level=record_int_value(record, STOCK_REORDER_HEADERS),
                row_number=None,
            )
        return None

    def update_current_stock(self, stock: StockItem, new_current_stock: int) -> None:
        if stock.row_number is not None:
            current_stock_column = MASTER_STOCK_HEADERS.index("Current Stock") + 1
            self._worksheet(MASTER_STOCK).update_cell(
                stock.row_number,
                current_stock_column,
                new_current_stock,
            )
        self._update_inventory_columns(stock.drug_name, {"Stock": new_current_stock})

    def update_current_stock_and_cost(
        self,
        stock: StockItem,
        new_current_stock: int,
        new_cost_price: float | None,
    ) -> None:
        if stock.row_number is not None:
            worksheet = self._worksheet(MASTER_STOCK)
            current_stock_column = MASTER_STOCK_HEADERS.index("Current Stock") + 1
            worksheet.update_cell(stock.row_number, current_stock_column, new_current_stock)

            if new_cost_price is not None:
                cost_price_column = MASTER_STOCK_HEADERS.index("Cost Price") + 1
                worksheet.update_cell(stock.row_number, cost_price_column, new_cost_price)
        inventory_updates: dict[str, Any] = {"Stock": new_current_stock}
        if new_cost_price is not None:
            inventory_updates["Cost Price"] = new_cost_price
        self._update_inventory_columns(stock.drug_name, inventory_updates)

    def add_stock_item(
        self,
        drug_name: str,
        selling_price: float | None = None,
        cost_price: float | None = None,
        current_stock: int = 0,
        reorder_level: int = 5,
    ) -> None:
        name = " ".join(str(drug_name or "").strip().split())
        if not name:
            raise ValueError("Missing medicine name")
        existing = self.find_stock(name)
        if existing is not None:
            self.update_current_stock_and_cost(existing, int(current_stock or existing.current_stock or 0), cost_price)
            return
        self._worksheet(MASTER_STOCK).append_row(
            [
                name,
                "" if selling_price is None else selling_price,
                "" if cost_price is None else cost_price,
                int(current_stock or 0),
                int(reorder_level or 5),
            ],
            value_input_option="USER_ENTERED",
        )
        self._worksheet(INVENTORY).append_row(
            [
                name,
                int(current_stock or 0),
                "" if cost_price is None else cost_price,
                "" if selling_price is None else selling_price,
                "" if cost_price is None else cost_price,
                int(reorder_level or 5),
                now_in_timezone(self.settings.timezone).strftime("%Y-%m-%d %H:%M:%S"),
            ],
            value_input_option="USER_ENTERED",
        )
        self.upsert_medicine_catalog_metadata(name)

    def upsert_medicine_catalog_record(self, record: dict[str, Any]) -> None:
        """Save owner-imported catalog metadata without touching legacy stock columns."""
        name = " ".join(
            str(record.get("drug_name") or record.get("name") or record.get("Drug Name") or "").strip().split()
        )
        if not name:
            return
        row = [
            name,
            metadata_text_value(record.get("generic_name")),
            metadata_text_value(record.get("brand_names")),
            metadata_text_value(record.get("aliases")),
            metadata_text_value(record.get("category")),
            metadata_text_value(record.get("strengths")),
            metadata_text_value(record.get("dosage_forms") or record.get("forms")),
            metadata_text_value(record.get("units")),
            metadata_text_value(record.get("manufacturer_importer")),
            metadata_text_value(record.get("ppb_registration_number")),
            metadata_text_value(record.get("pack_sizes") or record.get("packaging")),
            metadata_text_value(record.get("source")) or "Pharmacy owner import",
            now_in_timezone(self.settings.timezone).strftime("%Y-%m-%d %H:%M:%S"),
        ]

    def list_pharmacy_catalog_records(self, pharmacy_id: str | None = None) -> list[dict[str, Any]]:
        """Return durable pharmacy catalog truth for authenticated Main App resume."""
        metadata_by_name: dict[str, dict[str, Any]] = {}
        try:
            for record in self._worksheet(MEDICINE_CATALOG_METADATA).get_all_records():
                name = str(record.get("Drug Name") or "").strip()
                if name:
                    metadata_by_name[normalize_key(name)] = record
        except Exception:
            logger.warning("Medicine catalog metadata could not be read for operations resume", exc_info=True)
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        names = self.list_master_drug_names()
        # Older Main App onboarding and the live stock workflows persist the
        # pharmacy's operational catalog in Inventory (or <pharmacy>_inventory),
        # while Master_Stock can legitimately be empty.  Authentication must
        # therefore resume from both durable representations.  Keep this read
        # pharmacy-scoped; the broad include_all safety lookup is deliberately
        # not used here because it could pull another tenant's inventory into
        # an authenticated bootstrap response.
        for _title, inventory_record, _row_number in self._inventory_records_with_rows(
            pharmacy_id=pharmacy_id,
            include_all=False,
        ):
            inventory_name = record_text_value(inventory_record, STOCK_NAME_HEADERS)
            if inventory_name:
                names.append(inventory_name)
        for name in names:
            identity = normalize_key(name)
            if not identity or identity in seen:
                continue
            seen.add(identity)
            stock = self._find_stock_from_sources(
                name,
                pharmacy_id=pharmacy_id,
                include_all_inventory=False,
            )
            metadata = metadata_by_name.get(identity, {})
            records.append({
                "name": name,
                "strength": first_metadata_value(metadata.get("Strengths")),
                "forms": metadata_values(metadata.get("Dosage Forms")),
                "units": metadata_values(metadata.get("Units")),
                "sellingPrice": stock.selling_price if stock else None,
                "costPrice": stock.cost_price if stock else None,
                "stockLeft": stock.current_stock if stock else None,
                "reorderLevel": stock.reorder_level if stock else None,
                "supplier": "",
                "barcode": "",
                "batches": [],
                "shelf": "",
            })
        return records
        self._upsert_medicine_catalog_row(name, row)

    def get_ms20_operations_state(self, pharmacy_id: str) -> dict[str, Any] | None:
        wanted = str(pharmacy_id or "").strip()
        if not wanted:
            return None
        try:
            rows = self._worksheet(MS20_OPERATIONS_STATE).get_all_values()
        except (WorksheetNotFound, KeyError):
            return None
        for row in rows[1:]:
            if not row or str(row[0] or "").strip() != wanted:
                continue
            try:
                catalog = json.loads(row[7] if len(row) > 7 else "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                catalog = []
            return {
                "initialized": str(row[1] if len(row) > 1 else "").strip().lower() in {"true", "yes", "1"},
                "pharmacy_name": str(row[2] if len(row) > 2 else "").strip(),
                "owner_name": str(row[3] if len(row) > 3 else "").strip(),
                "branch": str(row[4] if len(row) > 4 else "").strip(),
                "location": str(row[5] if len(row) > 5 else "").strip(),
                "payments": str(row[6] if len(row) > 6 else "").strip(),
                "catalog": catalog if isinstance(catalog, list) else [],
            }
        return None

    def save_ms20_operations_state(
        self, pharmacy_id: str, profile: dict[str, Any], catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        wanted = str(pharmacy_id or "").strip()
        if not wanted:
            raise ValueError("Missing pharmacy identity")
        clean_catalog = [dict(item) for item in catalog[:500] if isinstance(item, dict) and str(item.get("name") or "").strip()]
        row = [
            wanted, "true", str(profile.get("name") or "").strip(),
            str(profile.get("owner") or "").strip(), str(profile.get("branch") or "Main").strip(),
            str(profile.get("location") or "Kenya").strip(),
            str(profile.get("payments") or "cash, mpesa, credit").strip(),
            json.dumps(clean_catalog, ensure_ascii=False, separators=(",", ":")),
            now_in_timezone(self.settings.timezone).strftime("%Y-%m-%d %H:%M:%S"),
        ]
        worksheet = self._worksheet(MS20_OPERATIONS_STATE)
        rows = worksheet.get_all_values()
        for row_number, existing in enumerate(rows[1:], start=2):
            if existing and str(existing[0] or "").strip() == wanted:
                worksheet.update(f"A{row_number}", [row])
                return self.get_ms20_operations_state(wanted) or {}
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return self.get_ms20_operations_state(wanted) or {}

    def upsert_medicine_catalog_metadata(self, drug_name: str) -> None:
        """Keep onboarding metadata separate so legacy stock columns stay stable."""
        try:
            match = match_local_medicine(drug_name)
            query = match.canonical_name or drug_name
            matches = search_catalog_entries(query, limit=5)
            entry = next(
                (
                    item for item in matches
                    if normalize_key(item.get("canonical_name")) == normalize_key(query)
                ),
                matches[0] if matches else {},
            )
            if not entry:
                return
            row = [
                drug_name,
                entry.get("generic_name", ""),
                ", ".join(entry.get("brand_names", [])),
                ", ".join(entry.get("aliases", [])),
                entry.get("category", ""),
                ", ".join(entry.get("strengths", [])),
                ", ".join(entry.get("dosage_forms", [])),
                ", ".join(entry.get("units", [])),
                ", ".join(entry.get("manufacturer_importer", [])),
                entry.get("ppb_registration_number", ""),
                "",
                entry.get("source", "") or "Local Kenya medicine brain",
                now_in_timezone(self.settings.timezone).strftime("%Y-%m-%d %H:%M:%S"),
            ]
            self._upsert_medicine_catalog_row(drug_name, row)
        except Exception:
            logger.warning("Medicine metadata could not be saved for %s", drug_name, exc_info=True)

    def _upsert_medicine_catalog_row(self, drug_name: str, row: list[Any]) -> None:
        worksheet = self._worksheet(MEDICINE_CATALOG_METADATA)
        records = worksheet.get_all_values()
        for row_number, existing in enumerate(records[1:], start=2):
            if existing and normalize_key(existing[0]) == normalize_key(drug_name):
                worksheet.update(f"A{row_number}", [row])
                return
        worksheet.append_row(row, value_input_option="USER_ENTERED")

    def list_low_stock_items(self) -> list[StockItem]:
        low_stock: list[StockItem] = []
        for record, row_number in self._master_records_with_rows():
            name = str(record.get("Drug Name") or "").strip()
            current_stock = parse_int(record.get("Current Stock"), default=None)
            reorder_level = parse_int(record.get("Reorder Level"), default=None)
            if not name or current_stock is None or reorder_level is None:
                continue
            if current_stock <= reorder_level:
                low_stock.append(
                    StockItem(
                        drug_name=name,
                        selling_price=parse_money(record.get("Selling Price")),
                        cost_price=parse_money(record.get("Cost Price")),
                        current_stock=current_stock,
                        reorder_level=reorder_level,
                        row_number=row_number,
                    )
                )
        return low_stock

    def append_daily_log(
        self,
        event: ParsedEvent,
        price: float | None,
        total_value: float | None,
        created_at: datetime | None = None,
    ) -> None:
        created_at = created_at or now_in_timezone(self.settings.timezone)
        worksheet = self._worksheet(DAILY_LOG)
        values = [
            created_at.date().isoformat(),
            created_at.strftime("%H:%M:%S"),
            event.drug_name,
            event.action.value if event.action else "",
            event.quantity,
            "" if price is None else price,
            "" if total_value is None else total_value,
            event.notes,
        ]
        worksheet.append_row(
            values,
            value_input_option="USER_ENTERED",
        )
        self._append_report_source_cache("logs", dict(zip(DAILY_LOG_HEADERS, values)))

    def append_transaction(
        self,
        transaction_type: str,
        drug_name: str,
        quantity: int,
        unit_cost: float | None = None,
        unit_selling_price: float | None = None,
        total_cost: float | None = None,
        total_sales: float | None = None,
        profit: float | None = None,
        note: str = "",
        created_at: datetime | None = None,
    ) -> None:
        created_at = created_at or now_in_timezone(self.settings.timezone)
        worksheet = self._worksheet(TRANSACTIONS)
        values = [
            created_at.strftime("%Y-%m-%d %H:%M:%S"),
            created_at.date().isoformat(),
            transaction_type,
            drug_name,
            quantity,
            "" if unit_cost is None else unit_cost,
            "" if unit_selling_price is None else unit_selling_price,
            "" if total_cost is None else total_cost,
            "" if total_sales is None else total_sales,
            "" if profit is None else profit,
            note,
        ]
        worksheet.append_row(
            values,
            value_input_option="USER_ENTERED",
        )
        self._append_report_source_cache("transactions", dict(zip(TRANSACTION_HEADERS, values)))

    def read_daily_logs(self, report_date: str) -> list[dict[str, Any]]:
        records, _transactions = self._report_source_records()
        return [
            record.copy()
            for record in records
            if str(record.get("Date") or "").strip() == report_date
        ]

    def read_report_source_records(self, start_date: str, end_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Read one shared pharmacy-scoped source snapshot and filter it locally."""
        logs, transactions = self._report_source_records()
        return (
            [row.copy() for row in logs if start_date <= str(row.get("Date") or "").strip() <= end_date],
            [row.copy() for row in transactions if start_date <= str(row.get("Date") or "").strip() <= end_date],
        )

    def _fetch_report_source_records(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Fetch both canonical report sources in exactly one Sheets API call."""
        response = self._require_spreadsheet().values_batch_get(
            ranges=[f"'{DAILY_LOG}'", f"'{TRANSACTIONS}'"]
        )
        ranges = response.get("valueRanges") or []

        def records(index: int, expected_headers: list[str]) -> list[dict[str, Any]]:
            values = (ranges[index].get("values") if index < len(ranges) else None) or []
            if not values:
                return []
            headers = [str(value).strip() for value in values[0]]
            if not headers:
                headers = expected_headers
            return [dict(zip(headers, [*row, *([""] * max(0, len(headers) - len(row)))])) for row in values[1:]]

        return records(0, DAILY_LOG_HEADERS), records(1, TRANSACTION_HEADERS)

    def _ensure_report_cache_state(self) -> None:
        if hasattr(self, "_report_cache_condition"):
            return
        self._report_cache_condition = threading.Condition(threading.RLock())
        self._report_cache_snapshot: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None
        self._report_cache_loaded_at = 0.0
        self._report_cache_loading = False
        self._report_cache_warmup_started = False
        self._report_cache_hits = 0
        self._report_cache_misses = 0

    def _report_source_records(self, *, force_refresh: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        self._ensure_report_cache_state()
        condition = self._report_cache_condition
        with condition:
            if not force_refresh and self._report_cache_snapshot is not None and time.monotonic() - self._report_cache_loaded_at < REPORT_SOURCE_CACHE_TTL_SECONDS:
                self._report_cache_hits += 1
                return self._report_cache_snapshot
            if self._report_cache_loading:
                if self._report_cache_snapshot is not None:
                    self._report_cache_hits += 1
                    return self._report_cache_snapshot
                condition.wait_for(lambda: not self._report_cache_loading, timeout=30.0)
                if self._report_cache_snapshot is not None:
                    return self._report_cache_snapshot
            self._report_cache_loading = True
            self._report_cache_misses += 1
        try:
            snapshot = self._fetch_report_source_records()
            if len(snapshot[0]) + len(snapshot[1]) > REPORT_SOURCE_CACHE_MAX_ROWS:
                logger.warning("Report source snapshot exceeds bounded cache size; serving without retention")
                return snapshot
            with condition:
                self._report_cache_snapshot = snapshot
                self._report_cache_loaded_at = time.monotonic()
            return snapshot
        finally:
            with condition:
                self._report_cache_loading = False
                condition.notify_all()

    def start_report_source_warmup(self) -> None:
        self._ensure_report_cache_state()
        with self._report_cache_condition:
            if self._report_cache_warmup_started or not self.is_available:
                return
            self._report_cache_warmup_started = True
        threading.Thread(target=self._report_source_refresh_loop, name="report-source-warmup", daemon=True).start()

    def _report_source_refresh_loop(self) -> None:
        while True:
            self._warm_report_source_cache()
            time.sleep(REPORT_SOURCE_REFRESH_SECONDS)

    def _warm_report_source_cache(self) -> None:
        try:
            logs, transactions = self._report_source_records(force_refresh=True)
            logger.info("Report source snapshot warmed: logs=%s transactions=%s", len(logs), len(transactions))
            print(f"REPORT_SOURCE_SNAPSHOT_WARMED logs={len(logs)} transactions={len(transactions)}", flush=True)
        except Exception:
            logger.exception("Report source warmup failed; requests will use the authoritative fallback")

    def report_source_cache_status(self) -> dict[str, Any]:
        self._ensure_report_cache_state()
        with self._report_cache_condition:
            logs, transactions = self._report_cache_snapshot or ([], [])
            age_seconds = None if self._report_cache_snapshot is None else round(max(0.0, time.monotonic() - self._report_cache_loaded_at), 3)
            return {
                "ready": self._report_cache_snapshot is not None,
                "loading": self._report_cache_loading,
                "log_rows": len(logs),
                "transaction_rows": len(transactions),
                "age_seconds": age_seconds,
                "hits": self._report_cache_hits,
                "misses": self._report_cache_misses,
                "max_rows": REPORT_SOURCE_CACHE_MAX_ROWS,
            }

    def _append_report_source_cache(self, source: str, row: dict[str, Any]) -> None:
        self._ensure_report_cache_state()
        with self._report_cache_condition:
            if self._report_cache_snapshot is None:
                return
            logs, transactions = self._report_cache_snapshot
            target = logs if source == "logs" else transactions
            if len(logs) + len(transactions) >= REPORT_SOURCE_CACHE_MAX_ROWS:
                self._report_cache_snapshot = None
                self._report_cache_loaded_at = 0.0
                return
            target.append(row)
            self._report_cache_loaded_at = time.monotonic()

    def read_transactions(self, start_date: str, end_date: str | None = None) -> list[dict[str, Any]]:
        end_date = end_date or start_date
        _logs, records = self._report_source_records()
        return [
            record.copy()
            for record in records
            if start_date <= str(record.get("Date") or "").strip() <= end_date
        ]

    def append_request_log(
        self,
        sender: str,
        message_type: str,
        success: bool,
        error_reason: str = "",
        created_at: datetime | None = None,
    ) -> None:
        created_at = created_at or now_in_timezone(self.settings.timezone)
        self._worksheet(REQUEST_LOG).append_row(
            [
                created_at.strftime("%Y-%m-%d %H:%M:%S"),
                sender,
                message_type,
                "yes" if success else "no",
                error_reason,
            ],
            value_input_option="USER_ENTERED",
        )

    def append_daily_report(self, report_row: dict[str, Any]) -> None:
        worksheet = self._worksheet(DAILY_REPORTS)
        worksheet.append_row(
            [report_row.get(header, "") for header in DAILY_REPORT_HEADERS],
            value_input_option="USER_ENTERED",
        )

    def append_batch(self, batch: Any) -> None:
        row = {
            "batch_id": batch.batch_id,
            "drug_name": batch.drug_name,
            "quantity_received": batch.quantity_received,
            "converted_total_units": batch.quantity_received,
            "current_remaining_units": batch.current_remaining_units,
            "expiry_date": batch.expiry_date,
            "expiry_status": "safe",
            "supplier_name": batch.supplier_name,
            "invoice_number": batch.invoice_number,
            "purchase_cost": "" if batch.purchase_cost is None else batch.purchase_cost,
            "selling_price": "" if batch.selling_price is None else batch.selling_price,
            "manufacturer_batch_number": batch.manufacturer_batch_number,
            "recorded_at": batch.recorded_at,
            "stock_location": "shelf",
            "return_status": "none",
        }
        self._worksheet(BATCHES).append_row(
            [serialize_cell(row.get(header, "")) for header in BATCH_HEADERS],
            value_input_option="USER_ENTERED",
        )

    def list_batches(self, drug_name: str | None = None) -> list[Any]:
        from app.services.batch_service import BatchRecord

        wanted = normalize_key(drug_name)
        batches: list[BatchRecord] = []
        for record in self._records(BATCHES, BATCH_HEADERS):
            name = str(record.get("drug_name") or "").strip()
            if wanted and normalize_key(name) != wanted:
                continue
            batches.append(
                BatchRecord(
                    batch_id=str(record.get("batch_id") or "").strip(),
                    drug_name=name,
                    quantity_received=parse_int(record.get("quantity_received"), default=0) or 0,
                    current_remaining_units=parse_int(record.get("current_remaining_units"), default=0) or 0,
                    expiry_date=str(record.get("expiry_date") or "").strip(),
                    supplier_name=str(record.get("supplier_name") or "").strip(),
                    invoice_number=str(record.get("invoice_number") or "").strip(),
                    purchase_cost=parse_money(record.get("purchase_cost")),
                    selling_price=parse_money(record.get("selling_price")),
                    manufacturer_batch_number=str(record.get("manufacturer_batch_number") or "").strip(),
                    recorded_at=str(record.get("recorded_at") or "").strip(),
                )
            )
        return batches

    def update_batch_remaining(self, batch_id: str, remaining_units: int) -> None:
        for record, row_number in self._records_with_rows(BATCHES, BATCH_HEADERS):
            if str(record.get("batch_id") or "").strip() != batch_id:
                continue
            column = BATCH_HEADERS.index("current_remaining_units") + 1
            self._worksheet(BATCHES).update_cell(row_number, column, max(remaining_units, 0))
            return

    def append_issue_log(self, row: dict[str, Any]) -> None:
        self._worksheet(ISSUE_LOG).append_row(
            [serialize_cell(row.get(header, "")) for header in ISSUE_LOG_HEADERS],
            value_input_option="USER_ENTERED",
        )

    def append_return_log(self, row: dict[str, Any]) -> None:
        self._worksheet(RETURNS_LOG).append_row(
            [serialize_cell(row.get(header, "")) for header in RETURNS_LOG_HEADERS],
            value_input_option="USER_ENTERED",
        )

    def append_import_review(self, row: dict[str, Any]) -> None:
        created_at = now_in_timezone(self.settings.timezone)
        full_row = {"Timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"), **row}
        self._worksheet(IMPORT_REVIEW_QUEUE).append_row(
            [serialize_cell(full_row.get(header, "")) for header in IMPORT_REVIEW_HEADERS],
            value_input_option="USER_ENTERED",
        )

    def append_offline_sync_log(self, row: dict[str, Any]) -> None:
        self._worksheet(OFFLINE_SYNC_LOG).append_row(
            [serialize_cell(row.get(header, "")) for header in OFFLINE_SYNC_HEADERS],
            value_input_option="USER_ENTERED",
        )

    def find_offline_sync_action(self, action_id: str) -> dict[str, Any] | None:
        wanted = str(action_id or "").strip()
        if not wanted:
            return None
        for record in reversed(self._records(OFFLINE_SYNC_LOG, OFFLINE_SYNC_HEADERS)):
            if str(record.get("action_id") or "").strip() == wanted:
                return record
        return None

    def get_daily_report_text(self, report_date: str) -> str | None:
        records = self._records(DAILY_REPORTS, DAILY_REPORT_HEADERS)
        for record in reversed(records):
            if str(record.get("Date") or "").strip() != report_date:
                continue
            report_text = str(record.get("Full Report Text") or "").strip()
            return report_text or None
        return None

    def _master_records_with_rows(self) -> list[tuple[dict[str, Any], int]]:
        return self._records_with_rows(MASTER_STOCK, MASTER_STOCK_HEADERS)

    def _inventory_titles(self, pharmacy_id: str | None = None, include_all: bool = False) -> list[str]:
        titles: list[str] = []
        requested_pharmacy_id = str(pharmacy_id or "").strip()
        default_pharmacy_id = str(getattr(self.settings, "pharmareen_default_pharmacy_id", "") or "").strip()
        for candidate in [requested_pharmacy_id, default_pharmacy_id]:
            if candidate:
                titles.append(f"{candidate}_inventory")
        titles.append(INVENTORY)
        if include_all:
            titles.extend(self._all_inventory_worksheet_titles())
        unique: list[str] = []
        seen: set[str] = set()
        for title in titles:
            if title not in seen:
                seen.add(title)
                unique.append(title)
        return unique

    def _all_inventory_worksheet_titles(self) -> list[str]:
        try:
            spreadsheet = self._require_spreadsheet()
        except SheetsUnavailableError:
            return []
        worksheets_attr = getattr(spreadsheet, "worksheets", None)
        if isinstance(worksheets_attr, dict):
            candidates = worksheets_attr.keys()
        elif callable(worksheets_attr):
            try:
                candidates = [getattr(worksheet, "title", "") for worksheet in worksheets_attr()]
            except Exception:
                candidates = []
        else:
            candidates = []
        titles: list[str] = []
        for title in candidates:
            clean_title = str(title or "").strip()
            if is_inventory_worksheet_title(clean_title) and clean_title not in {INVENTORY, MASTER_STOCK}:
                titles.append(clean_title)
        return titles

    def _inventory_records_with_rows(
        self,
        pharmacy_id: str | None = None,
        include_all: bool = False,
    ) -> list[tuple[str, dict[str, Any], int]]:
        records: list[tuple[str, dict[str, Any], int]] = []
        for title in self._inventory_titles(pharmacy_id=pharmacy_id, include_all=include_all):
            try:
                worksheet = self._worksheet(title)
                values = worksheet.get_all_values()
            except (WorksheetNotFound, KeyError):
                continue
            if not values:
                continue
            headers = [str(header or "").strip() for header in values[0]]
            for row_number, row in enumerate(values[1:], start=2):
                if not any(str(cell).strip() for cell in row):
                    continue
                record = {
                    header: row[index] if index < len(row) else ""
                    for index, header in enumerate(headers)
                    if header
                }
                name = record_text_value(record, STOCK_NAME_HEADERS)
                if name:
                    record.setdefault("Drug", name)
                    record.setdefault("Drug Name", name)
                stock_value = record_int_value(record, STOCK_QUANTITY_HEADERS)
                if stock_value is not None:
                    record.setdefault("Stock", stock_value)
                    record.setdefault("Current Stock", stock_value)
                cost_price = record_money_value(record, STOCK_COST_HEADERS)
                if cost_price is not None:
                    record.setdefault("Cost Price", cost_price)
                selling_price = record_money_value(record, STOCK_SELLING_HEADERS)
                if selling_price is not None:
                    record.setdefault("Selling Price", selling_price)
                reorder_level = record_int_value(record, STOCK_REORDER_HEADERS)
                if reorder_level is not None:
                    record.setdefault("Low Stock Alert Level", reorder_level)
                records.append((title, record, row_number))
        return records

    def _find_inventory_stock_records(
        self,
        wanted_key: str,
        pharmacy_id: str | None = None,
        include_all: bool = False,
    ) -> list[tuple[str, dict[str, Any], int]]:
        matches: list[tuple[str, dict[str, Any], int]] = []
        for title, record, row_number in self._inventory_records_with_rows(
            pharmacy_id=pharmacy_id,
            include_all=include_all,
        ):
            name = record_text_value(record, STOCK_NAME_HEADERS)
            if normalize_key(name) == wanted_key:
                matches.append((title, record, row_number))
        return matches

    def _update_inventory_columns(self, drug_name: str, updates: dict[str, Any]) -> None:
        wanted = normalize_key(drug_name)
        if not wanted:
            return
        matches = self._find_inventory_stock_records(wanted, include_all=True)
        if not matches:
            return
        header_aliases = {
            "Stock": STOCK_QUANTITY_HEADERS,
            "Cost Price": STOCK_COST_HEADERS,
            "Selling Price": STOCK_SELLING_HEADERS,
        }
        for title, _record, row_number in matches:
            worksheet = self._worksheet(title)
            headers = [str(header or "").strip() for header in worksheet.row_values(1)]
            for header, value in updates.items():
                aliases = header_aliases.get(header, [header])
                column = next((headers.index(alias) + 1 for alias in aliases if alias in headers), None)
                if column:
                    worksheet.update_cell(row_number, column, value)

    def _records(self, title: str, headers: list[str]) -> list[dict[str, Any]]:
        return [record for record, _row_number in self._records_with_rows(title, headers)]

    def _records_with_rows(self, title: str, headers: list[str]) -> list[tuple[dict[str, Any], int]]:
        worksheet = self._worksheet(title)
        values = worksheet.get_all_values()
        records: list[tuple[dict[str, Any], int]] = []

        for row_number, row in enumerate(values[1:], start=2):
            if not any(str(cell).strip() for cell in row[: len(headers)]):
                continue
            record = {
                header: row[index] if index < len(row) else ""
                for index, header in enumerate(headers)
            }
            records.append((record, row_number))

        return records

    def _worksheet(self, title: str):
        return self._require_spreadsheet().worksheet(title)

    def _ensure_worksheet(self, title: str, headers: list[str], rows: int):
        spreadsheet = self._require_spreadsheet()
        try:
            worksheet = spreadsheet.worksheet(title)
        except WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=title,
                rows=rows,
                cols=max(len(headers), 8),
            )

        existing = worksheet.row_values(1)
        if existing[: len(headers)] != headers:
            worksheet.update("A1", [headers])
        return worksheet

    def _require_spreadsheet(self):
        if self.spreadsheet is None:
            raise SheetsUnavailableError(self.unavailable_message)
        return self.spreadsheet

    @staticmethod
    def _load_credentials(value: str) -> Credentials:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        stripped = value.strip()

        if stripped.startswith("{"):
            info = json.loads(stripped)
            return Credentials.from_service_account_info(info, scopes=scopes)

        path = Path(stripped).expanduser()
        return Credentials.from_service_account_file(path, scopes=scopes)


def prepare_google_credentials_file(settings: Settings) -> Path:
    """Create a service-account.json file from env JSON when provided.

    Replit and Render store credentials as environment variables. The app
    materializes that JSON into a local file so Google auth can use the same
    file-based flow everywhere without printing secrets.
    """
    raw_credentials = (os.environ.get("GOOGLE_SHEETS_CREDENTIALS") or "").strip()
    configured_value = str(settings.google_service_account_json or "").strip()

    if raw_credentials.startswith("{"):
        info = validate_service_account_json(raw_credentials)
        output_path = service_account_output_path()
        write_service_account_file(output_path, info)
        return output_path

    if configured_value.startswith("{"):
        info = validate_service_account_json(configured_value)
        output_path = service_account_output_path()
        write_service_account_file(output_path, info)
        return output_path

    path_value = raw_credentials or configured_value or "service-account.json"
    return Path(path_value).expanduser()


def validate_service_account_json(raw_credentials: str) -> dict[str, Any]:
    try:
        info = json.loads(raw_credentials)
    except json.JSONDecodeError as exc:
        raise ValueError("GOOGLE_SHEETS_CREDENTIALS is not valid JSON") from exc

    if not isinstance(info, dict):
        raise ValueError("GOOGLE_SHEETS_CREDENTIALS must be a JSON object")

    required_keys = {"type", "client_email", "private_key"}
    missing = sorted(key for key in required_keys if not info.get(key))
    if missing:
        raise ValueError("GOOGLE_SHEETS_CREDENTIALS is missing required service account fields")
    return info


def service_account_output_path() -> Path:
    configured = (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "service-account.json").strip()
    path = Path(configured).expanduser()
    if path.name != "service-account.json":
        path = path / "service-account.json" if path.suffix == "" else Path("service-account.json")
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def write_service_account_file(path: Path, info: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(info), encoding="utf-8")
        logger.info("Google Sheets credentials file prepared: %s", path.name)
        return
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "service-account.json"
        fallback.write_text(json.dumps(info), encoding="utf-8")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(fallback)
        logger.info("Google Sheets credentials file prepared: %s", fallback.name)


def serialize_cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return value
