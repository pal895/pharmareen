from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

from app.utils import normalize_key, parse_int, parse_money


@dataclass
class BatchRecord:
    batch_id: str
    drug_name: str
    quantity_received: int
    current_remaining_units: int
    expiry_date: str = ""
    supplier_name: str = ""
    invoice_number: str = ""
    purchase_cost: float | None = None
    selling_price: float | None = None
    manufacturer_batch_number: str = ""
    recorded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds"))

    @property
    def expiry_sort_key(self) -> str:
        return self.expiry_date or "9999-12-31"


@dataclass(frozen=True)
class SaleDeduction:
    batch_id: str
    quantity: int
    expiry_date: str


class BatchStore(Protocol):
    def append_batch(self, batch: BatchRecord) -> None:
        ...

    def list_batches(self, drug_name: str | None = None) -> list[BatchRecord]:
        ...

    def update_batch_remaining(self, batch_id: str, remaining_units: int) -> None:
        ...

    def append_issue_log(self, row: dict[str, Any]) -> None:
        ...

    def append_return_log(self, row: dict[str, Any]) -> None:
        ...


class InMemoryBatchStore:
    def __init__(self):
        self.batches: list[BatchRecord] = []
        self.issues: list[dict[str, Any]] = []
        self.returns: list[dict[str, Any]] = []

    def append_batch(self, batch: BatchRecord) -> None:
        self.batches.append(batch)

    def list_batches(self, drug_name: str | None = None) -> list[BatchRecord]:
        if not drug_name:
            return list(self.batches)
        wanted = normalize_key(drug_name)
        return [batch for batch in self.batches if normalize_key(batch.drug_name) == wanted]

    def update_batch_remaining(self, batch_id: str, remaining_units: int) -> None:
        for batch in self.batches:
            if batch.batch_id == batch_id:
                batch.current_remaining_units = max(remaining_units, 0)
                return

    def append_issue_log(self, row: dict[str, Any]) -> None:
        self.issues.append(row)

    def append_return_log(self, row: dict[str, Any]) -> None:
        self.returns.append(row)


class BatchService:
    def __init__(self, store: BatchStore):
        self.store = store

    def create_batch(self, data: dict[str, Any]) -> BatchRecord:
        drug_name = str(data.get("drug_name") or data.get("Drug Name") or "").strip().title()
        quantity = positive_int(data.get("quantity_received") or data.get("quantity") or data.get("Quantity"), 1)
        batch = BatchRecord(
            batch_id=str(data.get("batch_id") or f"BATCH-{int(datetime.utcnow().timestamp() * 1000)}"),
            drug_name=drug_name,
            quantity_received=quantity,
            current_remaining_units=positive_int(data.get("current_remaining_units"), quantity),
            expiry_date=normalize_expiry(data.get("expiry_date") or data.get("expiry")),
            supplier_name=str(data.get("supplier_name") or data.get("supplier") or "").strip(),
            invoice_number=str(data.get("invoice_number") or data.get("invoice") or "").strip(),
            purchase_cost=parse_money(data.get("purchase_cost") or data.get("cost")),
            selling_price=parse_money(data.get("selling_price") or data.get("price")),
            manufacturer_batch_number=str(data.get("manufacturer_batch_number") or data.get("batch_number") or "").strip(),
        )
        self.store.append_batch(batch)
        return batch

    def deduct_fefo(self, drug_name: str, quantity: int) -> list[SaleDeduction]:
        remaining = positive_int(quantity, 1)
        deductions: list[SaleDeduction] = []
        batches = sorted(
            [batch for batch in self.store.list_batches(drug_name) if batch.current_remaining_units > 0],
            key=lambda batch: batch.expiry_sort_key,
        )
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.current_remaining_units, remaining)
            self.store.update_batch_remaining(batch.batch_id, batch.current_remaining_units - take)
            deductions.append(SaleDeduction(batch.batch_id, take, batch.expiry_date))
            remaining -= take
        return deductions

    def drug_card(self, drug_name: str, stock: Any | None = None) -> str:
        batches = sorted(self.store.list_batches(drug_name), key=lambda batch: batch.expiry_sort_key)
        lines = [str(drug_name).strip().title()]
        if stock is not None:
            stock_text = stock.current_stock if stock.current_stock is not None else "not set"
            lines.append(f"Stock: {stock_text}")
            if stock.reorder_level is not None and stock.current_stock is not None and stock.current_stock <= stock.reorder_level:
                lines.append("Low stock warning")
        if batches:
            lines.append("Batches:")
            for batch in batches[:5]:
                expiry = batch.expiry_date or "expiry not set"
                warning = " near expiry" if expiry_status(expiry) == "near_expiry" else ""
                lines.append(f"- {batch.current_remaining_units} units exp {expiry}{warning}")
            lines.append(f"Suggested action: Sell {batches[0].expiry_date or 'earliest'} batch first.")
        else:
            lines.append("Batches: none recorded yet")
        return "\n".join(lines)

    def record_issue(self, payload: dict[str, Any]) -> None:
        self.store.append_issue_log(payload)

    def record_return(self, payload: dict[str, Any]) -> None:
        self.store.append_return_log(payload)


def positive_int(value: Any, default: int) -> int:
    parsed = parse_int(value, default=default)
    return parsed if parsed and parsed > 0 else default


def normalize_expiry(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date().isoformat() if fmt == "%Y-%m-%d" else parsed.strftime("%Y-%m-01")
        except ValueError:
            continue
    return text


def expiry_status(expiry_date: str) -> str:
    try:
        expiry = datetime.fromisoformat(expiry_date.replace("/", "-")).date()
    except ValueError:
        return "safe"
    days = (expiry - date.today()).days
    if days < 0:
        return "expired"
    if days <= 90:
        return "near_expiry"
    return "safe"
