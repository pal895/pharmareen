from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SALE_LEDGER_PATH = Path(__file__).resolve().parent.parent / "training" / "sale_ledger.json"


@dataclass(frozen=True)
class SaleLookupResult:
    found: bool
    message: str
    record: dict[str, Any] | None = None


class DailySaleLedger:
    def __init__(
        self,
        path: str | Path | None = None,
        pharmacy_id: str = "default",
    ) -> None:
        self.path = Path(path or DEFAULT_SALE_LEDGER_PATH)
        self.pharmacy_id = pharmacy_id or "default"

    def preview_next_sale_number(self, sale_date: str) -> int:
        day = self._day(sale_date)
        return int(day.get("last_sale_number", 0)) + 1

    def record_sale(
        self,
        sale_date: str,
        *,
        drug_name: str,
        quantity: int,
        price: float | None,
        total_value: float | None,
        notes: str = "",
        payment: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        source: str | None = None,
        sale_number: int | None = None,
    ) -> dict[str, Any]:
        data = self._load()
        day = self._day(sale_date, data=data)
        number = sale_number or int(day.get("last_sale_number", 0)) + 1
        day["last_sale_number"] = max(int(day.get("last_sale_number", 0)), number)
        original = {
            "sale_number": number,
            "date": sale_date,
            "drug_name": drug_name,
            "quantity": quantity,
            "price": price,
            "total_value": total_value,
            "payment": payment,
            "notes": notes,
            "status": "active",
        }
        record = {
            "sale_number": number,
            "date": sale_date,
            "drug_name": drug_name,
            "quantity": quantity,
            "price": price,
            "total_value": total_value,
            "payment": payment,
            "notes": notes,
            "status": "active",
            "actor_id": actor_id,
            "actor_role": actor_role,
            "source": source,
            "corrections": [],
            "audit": [
                {
                    "type": "created",
                    "actor_id": actor_id,
                    "actor_role": actor_role,
                    "source": source,
                    "record": original,
                }
            ],
        }
        day.setdefault("sales", {})[str(number)] = record
        self._save(data)
        return record

    def get_sale(self, sale_date: str, sale_number: int) -> SaleLookupResult:
        record = self._sale_record(sale_date, sale_number)
        if record is None:
            return SaleLookupResult(False, f"Sale #{sale_number} was not found for {sale_date}.")
        return SaleLookupResult(True, format_sale_record(record), record)

    def undo_sale(
        self,
        sale_date: str,
        sale_number: int,
        *,
        actor_id: str | None = None,
        actor_role: str | None = None,
        reason: str = "",
    ) -> SaleLookupResult:
        data = self._load()
        record = self._sale_record(sale_date, sale_number, data=data)
        if record is None:
            return SaleLookupResult(False, f"Sale #{sale_number} was not found for {sale_date}.")
        if record.get("status") == "undone":
            return SaleLookupResult(False, f"Sale #{sale_number} is already undone.", record)

        record["status"] = "undone"
        record.setdefault("audit", []).append(
            {
                "type": "undone",
                "actor_id": actor_id,
                "actor_role": actor_role,
                "reason": reason,
                "reversal": {
                    "sale_number": sale_number,
                    "drug_name": record.get("drug_name"),
                    "quantity": record.get("quantity"),
                    "total_value": record.get("total_value"),
                    "payment": record.get("payment"),
                },
            }
        )
        self._save(data)
        return SaleLookupResult(True, f"Undone sale #{sale_number}: {record['drug_name']} x{record['quantity']}.", record)

    def undo_last_sale(
        self,
        sale_date: str,
        *,
        actor_id: str | None = None,
        actor_role: str | None = None,
        reason: str = "",
    ) -> SaleLookupResult:
        sale_number = self.latest_active_sale_number(sale_date)
        if sale_number is None:
            return SaleLookupResult(False, f"No active sale found for {sale_date}.")
        return self.undo_sale(sale_date, sale_number, actor_id=actor_id, actor_role=actor_role, reason=reason)

    def correct_sale(
        self,
        sale_date: str,
        sale_number: int,
        updates: dict[str, Any],
        *,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> SaleLookupResult:
        data = self._load()
        record = self._sale_record(sale_date, sale_number, data=data)
        if record is None:
            return SaleLookupResult(False, f"Sale #{sale_number} was not found for {sale_date}.")
        if record.get("status") == "undone":
            return SaleLookupResult(False, f"Sale #{sale_number} is undone and cannot be corrected.", record)
        if not updates:
            return SaleLookupResult(False, f"No correction details found for sale #{sale_number}.", record)

        clean_updates = {
            key: value
            for key, value in updates.items()
            if key in {"drug_name", "quantity", "payment", "price", "total_value", "notes"}
        }
        if not clean_updates:
            return SaleLookupResult(False, f"No supported correction details found for sale #{sale_number}.", record)

        if "quantity" in clean_updates and "total_value" not in clean_updates:
            price = clean_updates.get("price", record.get("price"))
            if price is not None:
                clean_updates["total_value"] = float(price) * int(clean_updates["quantity"])
        if "price" in clean_updates and "total_value" not in clean_updates:
            clean_updates["total_value"] = float(clean_updates["price"]) * int(record.get("quantity") or 1)

        before = {key: record.get(key) for key in clean_updates}
        record.update(clean_updates)
        record.setdefault("corrections", []).append(
            {
                "actor_id": actor_id,
                "actor_role": actor_role,
                "before": before,
                "after": clean_updates,
            }
        )
        record.setdefault("audit", []).append(
            {
                "type": "corrected",
                "actor_id": actor_id,
                "actor_role": actor_role,
                "updates": clean_updates,
            }
        )
        self._save(data)
        return SaleLookupResult(True, f"Corrected sale #{sale_number}: {format_updates(clean_updates)}.", record)

    def latest_active_sale_number(self, sale_date: str) -> int | None:
        sales = self._day(sale_date).get("sales", {})
        active_numbers = [
            int(number)
            for number, record in sales.items()
            if isinstance(record, dict) and record.get("status") != "undone"
        ]
        return max(active_numbers) if active_numbers else None

    def sale_count(self, sale_date: str, *, include_undone: bool = False) -> int:
        sales = self._day(sale_date).get("sales", {})
        if include_undone:
            return len(sales)
        return sum(1 for record in sales.values() if record.get("status") != "undone")

    def finance_summary(self, sale_date: str) -> dict[str, Any]:
        sales = self._day(sale_date).get("sales", {})
        payment_totals = {"cash": 0.0, "mpesa": 0.0, "credit": 0.0, "unknown": 0.0}
        total_sales = 0.0
        total_items = 0
        active_sales = 0
        sale_rows: list[dict[str, Any]] = []

        for record in sales.values():
            if not isinstance(record, dict) or record.get("status") == "undone":
                continue
            active_sales += 1
            quantity = int(record.get("quantity") or 0)
            total_value = float(record.get("total_value") or 0)
            payment = str(record.get("payment") or "unknown").lower()
            if payment not in payment_totals:
                payment = "unknown"
            total_items += quantity
            total_sales += total_value
            payment_totals[payment] += total_value
            sale_rows.append(record)

        return {
            "date": sale_date,
            "active_sales": active_sales,
            "total_sales": total_sales,
            "total_items": total_items,
            "payment_totals": payment_totals,
            "sales": sale_rows,
        }

    def _sale_record(
        self,
        sale_date: str,
        sale_number: int,
        *,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        day = self._day(sale_date, data=data)
        record = day.get("sales", {}).get(str(sale_number))
        return record if isinstance(record, dict) else None

    def _day(self, sale_date: str, *, data: dict[str, Any] | None = None) -> dict[str, Any]:
        ledger = data if data is not None else self._load()
        pharmacy = ledger.setdefault("pharmacies", {}).setdefault(self.pharmacy_id, {"dates": {}})
        return pharmacy.setdefault("dates", {}).setdefault(
            sale_date,
            {
                "last_sale_number": 0,
                "sales": {},
            },
        )

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "pharmacies": {}}
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return {"version": 1, "pharmacies": {}}
        data = json.loads(text)
        if not isinstance(data, dict):
            return {"version": 1, "pharmacies": {}}
        data.setdefault("version", 1)
        data.setdefault("pharmacies", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(self.path)


def extract_sale_number(notes: str) -> int | None:
    match = re.search(r"\b(?:target sale|sale)\s*[:#]?\s*(\d+)\b", str(notes or ""), flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def wants_last_sale(notes: str) -> bool:
    return bool(re.search(r"\blast\s+sale\b|\btarget sale\s*:\s*last\b", str(notes or ""), flags=re.IGNORECASE))


def extract_sale_correction_updates(notes: str) -> dict[str, Any]:
    text = str(notes or "")
    updates: dict[str, Any] = {}
    payment_match = re.search(r"\bpayment\s*:\s*(cash|m-?pesa|mpesa|credit)\b", text, flags=re.IGNORECASE)
    if payment_match:
        payment = payment_match.group(1).lower().replace("-", "")
        updates["payment"] = "mpesa" if payment == "mpesa" else payment
    quantity_match = re.search(r"\bquantity\s*:\s*(\d+)\b", text, flags=re.IGNORECASE)
    if quantity_match:
        updates["quantity"] = int(quantity_match.group(1))
    medicine_match = re.search(r"\bmedicine\s*:\s*([^;]+)", text, flags=re.IGNORECASE)
    if medicine_match:
        updates["drug_name"] = " ".join(medicine_match.group(1).strip().split())
    return updates


def sale_number_note(sale_number: int) -> str:
    return f"Sale #{sale_number}"


def payment_from_notes(notes: str) -> str | None:
    match = re.search(r"\bPayment:\s*(Cash|M-Pesa|Credit)\b", str(notes or ""), flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).lower()
    return "mpesa" if value in {"m-pesa", "mpesa"} else value


def format_sale_record(record: dict[str, Any]) -> str:
    number = record.get("sale_number")
    status = record.get("status", "active")
    drug_name = record.get("drug_name", "")
    quantity = record.get("quantity", "")
    payment = record.get("payment") or "unknown payment"
    return f"Sale #{number}: {drug_name} x{quantity}, {payment}, status {status}."


def format_updates(updates: dict[str, Any]) -> str:
    labels = []
    for key, value in updates.items():
        label = key.replace("_", " ")
        labels.append(f"{label}={value}")
    return ", ".join(labels)
