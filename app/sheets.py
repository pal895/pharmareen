from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

from app.config import Settings
from app.domain import ParsedEvent, StockItem
from app.utils import normalize_key, parse_int, parse_money, now_in_timezone


MASTER_STOCK = "Master_Stock"
DAILY_LOG = "Daily_Log"
DAILY_REPORTS = "Daily_Reports"
INVENTORY = "Inventory"
TRANSACTIONS = "Transactions"
REQUEST_LOG = "Request_Log"

SHEETS_UNAVAILABLE_MESSAGE = (
    "Google Sheets is not configured. Add a valid service-account.json to enable logging."
)

logger = logging.getLogger(__name__)


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

    def list_master_drug_names(self) -> list[str]:
        return [
            str(record.get("Drug Name") or "").strip()
            for record, _row_number in self._master_records_with_rows()
            if str(record.get("Drug Name") or "").strip()
        ]

    def find_stock(self, drug_name: str) -> StockItem | None:
        wanted = normalize_key(drug_name)
        if not wanted:
            return None

        for record, row_number in self._master_records_with_rows():
            name = str(record.get("Drug Name") or "").strip()
            if normalize_key(name) != wanted:
                continue

            return StockItem(
                drug_name=name,
                selling_price=parse_money(record.get("Selling Price")),
                cost_price=parse_money(record.get("Cost Price")),
                current_stock=parse_int(record.get("Current Stock"), default=None),
                reorder_level=parse_int(record.get("Reorder Level"), default=None),
                row_number=row_number,
            )
        return None

    def update_current_stock(self, stock: StockItem, new_current_stock: int) -> None:
        if stock.row_number is None:
            return
        current_stock_column = MASTER_STOCK_HEADERS.index("Current Stock") + 1
        self._worksheet(MASTER_STOCK).update_cell(
            stock.row_number,
            current_stock_column,
            new_current_stock,
        )

    def update_current_stock_and_cost(
        self,
        stock: StockItem,
        new_current_stock: int,
        new_cost_price: float | None,
    ) -> None:
        if stock.row_number is None:
            return

        worksheet = self._worksheet(MASTER_STOCK)
        current_stock_column = MASTER_STOCK_HEADERS.index("Current Stock") + 1
        worksheet.update_cell(stock.row_number, current_stock_column, new_current_stock)

        if new_cost_price is not None:
            cost_price_column = MASTER_STOCK_HEADERS.index("Cost Price") + 1
            worksheet.update_cell(stock.row_number, cost_price_column, new_cost_price)

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
        worksheet.append_row(
            [
                created_at.date().isoformat(),
                created_at.strftime("%H:%M:%S"),
                event.drug_name,
                event.action.value if event.action else "",
                event.quantity,
                "" if price is None else price,
                "" if total_value is None else total_value,
                event.notes,
            ],
            value_input_option="USER_ENTERED",
        )

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
        worksheet.append_row(
            [
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
            ],
            value_input_option="USER_ENTERED",
        )

    def read_daily_logs(self, report_date: str) -> list[dict[str, Any]]:
        records = self._records(DAILY_LOG, DAILY_LOG_HEADERS)
        return [
            record
            for record in records
            if str(record.get("Date") or "").strip() == report_date
        ]

    def read_transactions(self, start_date: str, end_date: str | None = None) -> list[dict[str, Any]]:
        end_date = end_date or start_date
        try:
            records = self._records(TRANSACTIONS, TRANSACTION_HEADERS)
        except WorksheetNotFound:
            return []
        return [
            record
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
