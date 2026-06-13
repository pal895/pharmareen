from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.services.pharmacy_alias_store import PharmacyAliasStore
from app.utils import normalize_key, parse_int, parse_money


CATALOG_IMPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "pharmacy_catalog_imports"


@dataclass(frozen=True)
class BulkMedicineRecord:
    name: str
    aliases: tuple[str, ...] = ()
    forms: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    pack_sizes: tuple[str, ...] = ()
    category: str = ""
    selling_price: float | None = None
    cost_price: float | None = None
    current_stock: int | None = None
    reorder_level: int | None = None

    def as_catalog_metadata(self) -> dict[str, Any]:
        return {
            "drug_name": self.name,
            "aliases": list(self.aliases),
            "dosage_forms": list(self.forms),
            "units": list(self.units),
            "pack_sizes": list(self.pack_sizes),
            "packaging": list(self.pack_sizes),
            "category": self.category,
            "source": "Pharmacy owner import",
        }


FIELD_ALIASES = {
    "name": "name",
    "drug": "name",
    "drugname": "name",
    "medicine": "name",
    "medicinename": "name",
    "item": "name",
    "alias": "aliases",
    "aliases": "aliases",
    "aka": "aliases",
    "shortcut": "aliases",
    "shortcuts": "aliases",
    "form": "forms",
    "forms": "forms",
    "dosageform": "forms",
    "dosageforms": "forms",
    "unit": "units",
    "units": "units",
    "pack": "pack_sizes",
    "packs": "pack_sizes",
    "packsize": "pack_sizes",
    "packsizes": "pack_sizes",
    "packaging": "pack_sizes",
    "category": "category",
    "class": "category",
    "price": "selling_price",
    "sellingprice": "selling_price",
    "cost": "cost_price",
    "costprice": "cost_price",
    "stock": "current_stock",
    "currentstock": "current_stock",
    "quantity": "current_stock",
    "qty": "current_stock",
    "reorder": "reorder_level",
    "reorderlevel": "reorder_level",
    "minimumstock": "reorder_level",
}


def parse_bulk_medicine_payload(payload: dict[str, Any]) -> list[BulkMedicineRecord]:
    raw_medicines = payload.get("medicines")
    if isinstance(raw_medicines, list):
        return [
            record
            for item in raw_medicines
            if (record := normalize_medicine_record(item)) is not None
        ]
    text = str(payload.get("text") or payload.get("bulk_text") or "").strip()
    if not text:
        return []
    records: list[BulkMedicineRecord] = []
    for line in text.splitlines():
        record = parse_medicine_line(line)
        if record is not None:
            records.append(record)
    return records


def parse_medicine_line(line: str) -> BulkMedicineRecord | None:
    clean = str(line or "").strip()
    if not clean or clean.startswith("#"):
        return None
    if clean.startswith("{"):
        try:
            parsed = json.loads(clean)
        except ValueError:
            parsed = None
        return normalize_medicine_record(parsed) if isinstance(parsed, dict) else None

    if "|" in clean:
        parts = [part.strip() for part in clean.split("|") if part.strip()]
    elif ";" in clean and re.search(r"[:=]", clean):
        parts = [part.strip() for part in clean.split(";") if part.strip()]
    else:
        columns = [part.strip() for part in clean.split(",") if part.strip()]
        if not columns:
            return None
        mapped: dict[str, Any] = {"name": columns[0]}
        ordered_fields = ["aliases", "forms", "units", "pack_sizes", "category"]
        for field, value in zip(ordered_fields, columns[1:]):
            mapped[field] = value
        return normalize_medicine_record(mapped)

    mapped: dict[str, Any] = {}
    for index, part in enumerate(parts):
        if re.search(r"[:=]", part):
            key, value = re.split(r"[:=]", part, maxsplit=1)
            field = FIELD_ALIASES.get(normalize_key(key))
            if field:
                mapped[field] = value.strip()
        elif index == 0 and "name" not in mapped:
            mapped["name"] = part
    return normalize_medicine_record(mapped)


def normalize_medicine_record(item: Any) -> BulkMedicineRecord | None:
    if isinstance(item, str):
        return parse_medicine_line(item)
    if not isinstance(item, dict):
        return None
    normalized: dict[str, Any] = {}
    for key, value in item.items():
        field = FIELD_ALIASES.get(normalize_key(key), key)
        normalized[field] = value

    name = " ".join(str(normalized.get("name") or "").strip().split())
    if not name:
        return None
    return BulkMedicineRecord(
        name=name,
        aliases=tuple(_clean_list(normalized.get("aliases"))),
        forms=tuple(_clean_list(normalized.get("forms"))),
        units=tuple(_clean_list(normalized.get("units"))),
        pack_sizes=tuple(_clean_list(normalized.get("pack_sizes"))),
        category=str(normalized.get("category") or "").strip(),
        selling_price=parse_money(normalized.get("selling_price")),
        cost_price=parse_money(normalized.get("cost_price")),
        current_stock=parse_int(normalized.get("current_stock"), default=None),
        reorder_level=parse_int(normalized.get("reorder_level"), default=None),
    )


def import_pharmacy_medicines(
    payload: dict[str, Any],
    *,
    store: Any,
    pharmacy_id: str,
    alias_store: PharmacyAliasStore | None = None,
    audit_dir: Path | None = None,
) -> dict[str, Any]:
    records = parse_bulk_medicine_payload(payload)
    pharmacy_key = normalize_key(pharmacy_id) or "default"
    alias_store = alias_store or PharmacyAliasStore()
    audit_path = save_pharmacy_catalog_snapshot(
        pharmacy_key,
        records,
        audit_dir=audit_dir or CATALOG_IMPORT_DIR,
    )

    sheets_available = bool(getattr(store, "is_available", True))
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    stock_names = [record.name for record in records]
    for record in records:
        row = asdict(record)
        row["sheet_status"] = "skipped_unavailable"
        if sheets_available:
            try:
                add_stock = getattr(store, "add_stock_item")
                add_stock(
                    record.name,
                    selling_price=record.selling_price,
                    cost_price=record.cost_price,
                    current_stock=record.current_stock or 0,
                    reorder_level=record.reorder_level or 5,
                )
                upsert_metadata = getattr(store, "upsert_medicine_catalog_record", None)
                if callable(upsert_metadata):
                    upsert_metadata(record.as_catalog_metadata())
                row["sheet_status"] = "written"
            except Exception as exc:
                row["sheet_status"] = "error"
                row["error"] = exc.__class__.__name__
                skipped.append(row)
                continue
        for alias in record.aliases:
            alias_store.observe(
                pharmacy_key,
                alias,
                record.name,
                confirmed=True,
                owner_approved=True,
                inventory_names=stock_names,
            )
        imported.append(row)

    return {
        "status": "ok",
        "ai_used": False,
        "pharmacy_id": pharmacy_id,
        "records_received": len(records),
        "records_imported": len(imported),
        "records_failed": len(skipped),
        "sheets_available": sheets_available,
        "audit_path": str(audit_path),
        "imported": imported,
        "failed": skipped,
    }


def save_pharmacy_catalog_snapshot(
    pharmacy_id: str,
    records: Iterable[BulkMedicineRecord],
    *,
    audit_dir: Path,
) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"{normalize_key(pharmacy_id) or 'default'}.json"
    payload = {
        "pharmacy_id": pharmacy_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "medicines": [asdict(record) for record in records],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = re.split(r"[,;/]+", str(value))
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in raw_values:
        text = " ".join(str(raw or "").strip().split())
        key = normalize_key(text)
        if key and key not in seen:
            seen.add(key)
            cleaned.append(text)
    return cleaned
