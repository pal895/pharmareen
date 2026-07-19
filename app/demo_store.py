from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from app.domain import Action, ParsedEvent, StockItem
from app.utils import normalize_key, now_in_timezone


class DemoPharmacyStore:
    """Small in-memory store for safe MVP demos when Google Sheets is absent."""

    is_available = False
    is_demo = True

    def __init__(self, settings):
        self.settings = settings
        self._stock: dict[str, StockItem] = {}
        self._daily_logs: list[dict[str, Any]] = []
        self._transactions: list[dict[str, Any]] = []
        self._daily_reports: dict[str, str] = {}
        self._request_log: list[dict[str, Any]] = []
        self._batches: list[Any] = []
        self._seed_stock()

    def _seed_stock(self) -> None:
        samples = [
            StockItem("Panadol", 220, 140, 30, 10, 1),
            StockItem("Paracetamol", 150, 100, 40, 10, 2),
            StockItem("Cough Syrup", 350, 250, 15, 5, 3),
            StockItem("Amoxil", 450, 320, 20, 5, 4),
            StockItem("Amoxicillin", 500, 360, 20, 5, 5),
            StockItem("Vitamin C", 100, 60, 50, 15, 6),
            StockItem("Insulin", 1200, 950, 5, 2, 7),
            StockItem("ORS", 80, 50, 30, 10, 8),
            StockItem("Antacid", 250, 170, 20, 6, 9),
        ]
        self._stock = {normalize_key(item.drug_name): item for item in samples}

    def ensure_schema(self) -> None:
        return None

    def list_master_drug_names(self) -> list[str]:
        return [item.drug_name for item in self._stock.values()]

    def find_stock(self, drug_name: str) -> StockItem | None:
        item = self._stock.get(normalize_key(drug_name))
        return deepcopy(item) if item else None

    def update_current_stock(self, stock: StockItem, new_current_stock: int) -> None:
        key = normalize_key(stock.drug_name)
        current = self._stock.get(key)
        if not current:
            return
        self._stock[key] = StockItem(
            current.drug_name,
            current.selling_price,
            current.cost_price,
            max(0, int(new_current_stock)),
            current.reorder_level,
            current.row_number,
        )

    def update_current_stock_and_cost(
        self,
        stock: StockItem,
        new_current_stock: int,
        new_cost_price: float | None,
    ) -> None:
        key = normalize_key(stock.drug_name)
        current = self._stock.get(key)
        if not current:
            return
        self._stock[key] = StockItem(
            current.drug_name,
            current.selling_price,
            current.cost_price if new_cost_price is None else new_cost_price,
            max(0, int(new_current_stock)),
            current.reorder_level,
            current.row_number,
        )

    def add_stock_item(
        self,
        drug_name: str,
        selling_price: float | None = None,
        cost_price: float | None = None,
        current_stock: int = 0,
        reorder_level: int = 5,
    ) -> StockItem:
        clean_name = " ".join(str(drug_name or "").split())
        if not clean_name:
            raise ValueError("Missing medicine name")
        key = normalize_key(clean_name)
        existing = self._stock.get(key)
        if existing:
            return deepcopy(existing)
        item = StockItem(
            clean_name,
            selling_price,
            cost_price,
            max(0, int(current_stock or 0)),
            max(0, int(reorder_level or 0)),
            len(self._stock) + 1,
        )
        self._stock[key] = item
        return deepcopy(item)

    def append_daily_log(
        self,
        event: ParsedEvent,
        price: float | None,
        total_value: float | None,
        created_at: datetime | None = None,
    ) -> None:
        created_at = created_at or now_in_timezone(self.settings.timezone)
        self._daily_logs.append(
            {
                "Date": created_at.date().isoformat(),
                "Time": created_at.strftime("%H:%M:%S"),
                "Drug Name": event.drug_name,
                "Action": event.action.value if event.action else "",
                "Quantity": event.quantity,
                "Price": "" if price is None else price,
                "Total Value": "" if total_value is None else total_value,
                "Notes": event.notes,
            }
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
        self._transactions.append(
            {
                "Timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Date": created_at.date().isoformat(),
                "Type": transaction_type,
                "Drug": drug_name,
                "Quantity": quantity,
                "Unit Cost": "" if unit_cost is None else unit_cost,
                "Unit Selling Price": "" if unit_selling_price is None else unit_selling_price,
                "Total Cost": "" if total_cost is None else total_cost,
                "Total Sales": "" if total_sales is None else total_sales,
                "Profit": "" if profit is None else profit,
                "Note": note,
            }
        )

    def read_daily_logs(self, report_date: str) -> list[dict[str, Any]]:
        return [row.copy() for row in self._daily_logs if str(row.get("Date")) == report_date]

    def read_transactions(self, start_date: str, end_date: str | None = None) -> list[dict[str, Any]]:
        end_date = end_date or start_date
        return [
            row.copy()
            for row in self._transactions
            if start_date <= str(row.get("Date") or "") <= end_date
        ]

    def read_report_source_records(self, start_date: str, end_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        logs = [row.copy() for row in self._daily_logs if start_date <= str(row.get("Date") or "") <= end_date]
        return logs, self.read_transactions(start_date, end_date)

    def list_low_stock_items(self) -> list[StockItem]:
        return [
            deepcopy(item)
            for item in self._stock.values()
            if item.current_stock is not None
            and item.reorder_level is not None
            and item.current_stock <= item.reorder_level
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
        self._request_log.append(
            {
                "Timestamp": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Sender": sender,
                "Message Type": message_type,
                "Success": "yes" if success else "no",
                "Error Reason": error_reason,
            }
        )

    def append_daily_report(self, report_row: dict[str, Any]) -> None:
        date_text = str(report_row.get("Date") or "")
        full_text = str(report_row.get("Full Report Text") or "")
        if date_text and full_text:
            self._daily_reports[date_text] = full_text

    def get_daily_report_text(self, report_date: str) -> str | None:
        return self._daily_reports.get(report_date)

    # Extra no-op methods used by Day 2/3 services in demo mode.
    def append_batch(self, batch: Any) -> None:
        self._batches.append(deepcopy(batch))

    def list_batches(self, drug_name: str | None = None) -> list[Any]:
        if not drug_name:
            return deepcopy(self._batches)
        wanted = normalize_key(drug_name)
        return [deepcopy(batch) for batch in self._batches if normalize_key(getattr(batch, "drug_name", "")) == wanted]

    def update_batch_remaining(self, batch_id: str, remaining_units: int) -> None:
        for batch in self._batches:
            if getattr(batch, "batch_id", "") == batch_id:
                batch.current_remaining_units = max(int(remaining_units), 0)
                return

    def append_issue(self, payload: dict[str, Any]) -> None:
        return None

    def append_return(self, payload: dict[str, Any]) -> None:
        return None

    def append_import_review(self, phone: str, extraction: Any, raw: dict[str, Any] | None = None) -> None:
        return None
