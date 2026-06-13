from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from gspread.exceptions import WorksheetNotFound


PHARMACY_REGISTRY_SHEET = "Pharmacies"
PHARMACY_REGISTRY_HEADERS = [
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

ACTIVE_STATUSES = {"active", "approved", "approved_provisioned", "google_live", "ready", "provisioned"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegistryWriteResult:
    accepted: bool
    record: dict[str, str]
    created: bool
    message: str
    error: str = ""


def phone_digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def display_phone(value: Any) -> str:
    digits = phone_digits(value)
    return f"+{digits}" if digits else ""


def registry_phone_key(value: Any) -> str:
    return phone_digits(value)


def normalize_registry_record(record: dict[str, Any]) -> dict[str, str]:
    phone = str(record.get("phone_number") or record.get("Phone Number") or record.get("phone") or record.get("Phone") or "").strip()
    active = str(record.get("active") or record.get("Active") or "").strip()
    status = str(record.get("status") or record.get("Status") or "").strip()
    return {
        "pharmacy_id": str(record.get("pharmacy_id") or record.get("Pharmacy ID") or "").strip(),
        "pharmacy_name": str(record.get("pharmacy_name") or record.get("Pharmacy Name") or "").strip(),
        "owner_name": str(record.get("owner_name") or record.get("Owner Name") or "").strip(),
        "phone_number": phone,
        "phone": phone,
        "location": str(record.get("location") or record.get("Location") or "").strip(),
        "timezone": str(record.get("timezone") or record.get("Timezone") or "Africa/Nairobi").strip(),
        "currency": str(record.get("currency") or record.get("Currency") or "KES").strip(),
        "status": status or "active",
        "active": active or "yes",
        "created_at": str(record.get("created_at") or record.get("Created At") or "").strip(),
        "updated_at": str(record.get("updated_at") or record.get("Updated At") or "").strip(),
        "spreadsheet_id": str(record.get("spreadsheet_id") or record.get("Spreadsheet ID") or "").strip(),
        "spreadsheet_url": str(record.get("spreadsheet_url") or record.get("Spreadsheet URL") or "").strip(),
        "notes": str(record.get("notes") or record.get("Notes") or "").strip(),
    }


def registry_record_is_active(record: dict[str, Any]) -> bool:
    normalized = normalize_registry_record(record)
    active_text = normalized["active"].lower()
    status_text = normalized["status"].lower()
    if active_text in {"no", "false", "0", "inactive", "disabled", "deactivated"}:
        return False
    return status_text in ACTIVE_STATUSES


def pharmacy_id_for_name(pharmacy_name: str, phone_number: str = "") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(pharmacy_name or "").lower()).strip("_")
    slug = slug or "pharmacy"
    suffix_source = phone_digits(phone_number)[-4:] or uuid4().hex[:4]
    return f"{slug}_{suffix_source}_{uuid4().hex[:6]}"


class GoogleSheetsPharmacyRegistry:
    def __init__(
        self,
        store: Any,
        *,
        timezone_name: str = "Africa/Nairobi",
        currency: str = "KES",
    ) -> None:
        self.store = store
        self.timezone_name = timezone_name
        self.currency = currency
        self.last_error = ""

    @property
    def is_available(self) -> bool:
        return bool(getattr(self.store, "is_available", False) and getattr(self.store, "spreadsheet", None))

    def ensure_schema(self) -> bool:
        if not self.is_available:
            self.last_error = "google_sheets_store_unavailable"
            return False
        self._worksheet()
        return True

    def find_by_phone(self, phone_number: Any, *, active_only: bool = True) -> dict[str, str] | None:
        wanted = registry_phone_key(phone_number)
        if not wanted:
            return None
        for record in self.list_records():
            if registry_phone_key(record.get("phone_number") or record.get("phone")) != wanted:
                continue
            if active_only and not registry_record_is_active(record):
                continue
            return normalize_registry_record(record)
        return None

    def list_records(self) -> list[dict[str, str]]:
        if not self.is_available:
            self.last_error = "google_sheets_store_unavailable"
            return []
        worksheet = self._worksheet()
        records = worksheet_records(worksheet)
        return [normalize_registry_record(record) for record in records]

    def register_pharmacy(self, details: dict[str, Any]) -> RegistryWriteResult:
        if not self.is_available:
            error = "google_sheets_store_unavailable"
            self.last_error = error
            logger.warning("PHARMACY_REGISTRY_WRITE_FAILED normalized_phone=%s reason=%s", registry_phone_key(details.get("phone_number") or details.get("phone")), error)
            return RegistryWriteResult(False, {}, False, "Google Sheets registry is not available.", error)

        phone = display_phone(details.get("phone_number") or details.get("phone"))
        existing = self.find_by_phone(phone, active_only=False)
        if existing:
            logger.info("PHARMACY_REGISTRY_DUPLICATE normalized_phone=%s pharmacy_id=%s", registry_phone_key(phone), existing.get("pharmacy_id", ""))
            return RegistryWriteResult(True, existing, False, "Pharmacy phone is already registered.")

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        pharmacy_name = str(details.get("pharmacy_name") or "").strip()
        owner_name = str(details.get("owner_name") or "").strip()
        record = {
            "pharmacy_id": str(details.get("pharmacy_id") or pharmacy_id_for_name(pharmacy_name, phone)),
            "pharmacy_name": pharmacy_name,
            "owner_name": owner_name,
            "phone": phone,
            "phone_number": phone,
            "location": str(details.get("location") or "").strip(),
            "spreadsheet_id": str(details.get("spreadsheet_id") or getattr(getattr(self.store, "spreadsheet", None), "id", "") or "").strip(),
            "spreadsheet_url": str(details.get("spreadsheet_url") or getattr(getattr(self.store, "spreadsheet", None), "url", "") or "").strip(),
            "created_at": str(details.get("created_at") or now),
            "updated_at": now,
            "status": str(details.get("status") or "active").strip(),
            "active": str(details.get("active") or "yes").strip(),
            "timezone": str(details.get("timezone") or self.timezone_name).strip(),
            "currency": str(details.get("currency") or self.currency).strip(),
            "notes": str(details.get("notes") or "registered_by_live_onboarding").strip(),
        }
        worksheet = self._worksheet()
        worksheet.append_row(row_for_registry_record(record), value_input_option="USER_ENTERED")
        self.last_error = ""
        logger.info("PHARMACY_REGISTRY_WRITE_SUCCESS normalized_phone=%s pharmacy_id=%s", registry_phone_key(phone), record["pharmacy_id"])
        return RegistryWriteResult(True, normalize_registry_record(record), True, "Pharmacy registered.")

    def _worksheet(self):
        spreadsheet = getattr(self.store, "spreadsheet", None)
        if spreadsheet is None:
            raise RuntimeError("Google Sheets store is unavailable")
        try:
            worksheet = spreadsheet.worksheet(PHARMACY_REGISTRY_SHEET)
        except WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=PHARMACY_REGISTRY_SHEET,
                rows=2000,
                cols=max(len(PHARMACY_REGISTRY_HEADERS), 8),
            )
        existing = worksheet.row_values(1)
        if existing[: len(PHARMACY_REGISTRY_HEADERS)] != PHARMACY_REGISTRY_HEADERS:
            worksheet.update("A1", [PHARMACY_REGISTRY_HEADERS])
        return worksheet


def worksheet_records(worksheet: Any) -> list[dict[str, Any]]:
    get_all_records = getattr(worksheet, "get_all_records", None)
    if callable(get_all_records):
        return [record for record in get_all_records() if isinstance(record, dict)]
    values = worksheet.get_all_values()
    if not values:
        return []
    headers = [str(header or "").strip() for header in values[0]]
    records: list[dict[str, Any]] = []
    for row in values[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        records.append({header: row[index] if index < len(row) else "" for index, header in enumerate(headers) if header})
    return records


def row_for_registry_record(record: dict[str, Any]) -> list[str]:
    return [
        str(record.get("pharmacy_id") or ""),
        str(record.get("pharmacy_name") or ""),
        str(record.get("owner_name") or ""),
        str(record.get("phone") or record.get("phone_number") or ""),
        str(record.get("location") or ""),
        str(record.get("spreadsheet_id") or ""),
        str(record.get("spreadsheet_url") or ""),
        str(record.get("created_at") or ""),
        str(record.get("status") or ""),
        str(record.get("notes") or ""),
        str(record.get("phone_number") or record.get("phone") or ""),
        str(record.get("timezone") or ""),
        str(record.get("currency") or ""),
        str(record.get("active") or ""),
        str(record.get("updated_at") or ""),
    ]
