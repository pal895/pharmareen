from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.sheets import GoogleSheetsStore, MASTER_STOCK, MASTER_STOCK_HEADERS
from app.utils import normalize_key


TEST_PRICE_ROWS = [
    ["Panadol", 220, 140, 30, 10],
    ["Paracetamol", 150, 100, 40, 10],
    ["Cough Syrup", 350, 250, 15, 5],
    ["Amoxicillin", 500, 360, 20, 5],
    ["Amoxyl", 450, 320, 20, 5],
    ["Vitamin C", 100, 60, 50, 15],
    ["Insulin", 1200, 950, 5, 2],
    ["Asthma Inhaler", 900, 700, 6, 2],
    ["Malaria Tablets", 650, 480, 12, 4],
    ["ORS", 80, 50, 30, 10],
    ["Ibuprofen", 180, 120, 25, 8],
    ["Antacid", 250, 170, 20, 6],
    ["Glucose", 150, 90, 30, 10],
    ["Cetirizine", 120, 80, 25, 8],
    ["Metformin", 300, 220, 15, 5],
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Master_Stock with sample testing prices only."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing sample rows during testing.",
    )
    args = parser.parse_args()

    settings = get_settings()
    store = GoogleSheetsStore(settings)
    store.ensure_schema()
    worksheet = store.spreadsheet.worksheet(MASTER_STOCK)

    added, skipped, updated = seed_master_stock(worksheet, overwrite=args.overwrite)
    print(f"Added {added} test drugs, skipped {skipped} existing drugs, updated {updated} drugs.")
    print("These are sample testing prices only. Please adjust Master_Stock before real use.")


def seed_master_stock(worksheet: Any, overwrite: bool = False) -> tuple[int, int, int]:
    ensure_headers(worksheet)
    existing_rows = existing_drug_rows(worksheet)

    added = 0
    skipped = 0
    updated = 0

    for row in TEST_PRICE_ROWS:
        drug_name = row[0]
        existing_row_number = existing_rows.get(normalize_key(drug_name))

        if existing_row_number is None:
            worksheet.append_row(row, value_input_option="USER_ENTERED")
            added += 1
            continue

        if overwrite:
            worksheet.update(
                range_name=f"A{existing_row_number}:E{existing_row_number}",
                values=[row],
                value_input_option="USER_ENTERED",
            )
            updated += 1
        else:
            skipped += 1

    return added, skipped, updated


def ensure_headers(worksheet: Any) -> None:
    existing_headers = worksheet.row_values(1)
    if existing_headers[: len(MASTER_STOCK_HEADERS)] != MASTER_STOCK_HEADERS:
        worksheet.update(range_name="A1", values=[MASTER_STOCK_HEADERS])


def existing_drug_rows(worksheet: Any) -> dict[str, int]:
    if hasattr(worksheet, "get_all_values"):
        values = worksheet.get_all_values()
        return {
            normalize_key(row[0]): row_number
            for row_number, row in enumerate(values[1:], start=2)
            if row and str(row[0]).strip()
        }

    records = worksheet.get_all_records()
    rows: dict[str, int] = {}
    for row_number, record in enumerate(records, start=2):
        drug_name = str(record.get("Drug Name") or "").strip()
        if drug_name:
            rows[normalize_key(drug_name)] = row_number
    return rows


if __name__ == "__main__":
    main()
