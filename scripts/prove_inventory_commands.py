from __future__ import annotations

import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.sheets import DAILY_LOG, MASTER_STOCK, GoogleSheetsStore
from app.utils import normalize_key


BASE_URL = "http://localhost:8000"


def main() -> None:
    assert_health()
    store = GoogleSheetsStore(get_settings())
    if not store.is_available:
        fail("Google Sheets is not available. Check service-account.json and .env.")

    prepare_stock(store, "Panadol", current_stock=26, reorder_level=10)
    prepare_stock(store, "Insulin", current_stock=3, reorder_level=3)

    sale_response = post_whatsapp("Panadol sold 2")
    assert_contains(sale_response, "Panadol x2 recorded", "sale confirmation")
    assert_contains(sale_response, "Stock left: 24", "sale stock left")
    print("SALE TEST OK")

    restock_response = post_whatsapp("Panadol restock 20")
    assert_contains(restock_response, "Panadol +20 added", "restock confirmation")
    assert_contains(restock_response, "New stock: 44", "restock new stock")
    print("RESTOCK TEST OK")

    missed_response = post_whatsapp("Insulin no stock")
    assert_contains(missed_response, "Insulin no-stock request logged", "missed demand confirmation")
    print("MISSED DEMAND TEST OK")

    low_stock_response = post_whatsapp("Insulin sold 1")
    assert_contains(low_stock_response, "Insulin x1 recorded", "low stock sale confirmation")
    assert_contains(low_stock_response, "Stock left: 2", "low stock remaining stock")
    assert_contains(low_stock_response, "LOW STOCK", "low stock warning")
    print("LOW STOCK WARNING TEST OK")

    verify_google_sheets(store)
    print("GOOGLE SHEETS LOGGING OK")


def assert_health() -> None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            if response.status != 200 or '"ok"' not in body:
                fail(f"App health failed: HTTP {response.status} {body}")
    except Exception as exc:
        fail(f"App health failed. Start PharMareen first. Error: {exc}")
    print("APP HEALTH OK")


def post_whatsapp(message: str) -> str:
    data = urllib.parse.urlencode(
        {
            "Body": message,
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+14155238886",
            "MessageSid": f"SM-PROOF-{int(time.time() * 1000)}",
            "NumMedia": "0",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/webhooks/twilio/whatsapp",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status != 200:
            fail(f"Webhook returned HTTP {response.status}: {body}")
        print(f"{message} -> {body}")
        return body


def prepare_stock(store: GoogleSheetsStore, drug_name: str, current_stock: int, reorder_level: int) -> None:
    stock = store.find_stock(drug_name)
    if stock is None or stock.row_number is None:
        fail(f"{drug_name} was not found in Master_Stock. Run seed_prices.bat first.")

    worksheet = store.spreadsheet.worksheet(MASTER_STOCK)
    worksheet.update(
        range_name=f"D{stock.row_number}:E{stock.row_number}",
        values=[[current_stock, reorder_level]],
        value_input_option="USER_ENTERED",
    )


def verify_google_sheets(store: GoogleSheetsStore) -> None:
    today = date.today().isoformat()
    today_rows = store.read_daily_logs(today)

    assert_log_exists(today_rows, "Panadol", "Sold", 2)
    assert_log_exists(today_rows, "Panadol", "Restocked", 20)
    assert_log_exists(today_rows, "Insulin", "Out of Stock", 1)
    assert_log_exists(today_rows, "Insulin", "Sold", 1)

    panadol = stock_item(store, "Panadol")
    insulin = stock_item(store, "Insulin")
    if int(panadol.current_stock or 0) != 44:
        fail(f"Expected Panadol stock 44, got {panadol.current_stock}")
    if int(insulin.current_stock or 0) != 2:
        fail(f"Expected Insulin stock 2, got {insulin.current_stock}")


def assert_log_exists(rows: list[dict[str, Any]], drug_name: str, action: str, quantity: int) -> None:
    for row in reversed(rows):
        if normalize_key(row.get("Drug Name")) != normalize_key(drug_name):
            continue
        if normalize_key(row.get("Action")) != normalize_key(action):
            continue
        if int(row.get("Quantity") or 0) == quantity:
            return
    fail(f"Missing Daily_Log row: {drug_name} {action} {quantity}")


def stock_item(store: GoogleSheetsStore, drug_name: str):
    stock = store.find_stock(drug_name)
    if stock is not None:
        return stock
    fail(f"Missing Master_Stock row: {drug_name}")


def assert_contains(response: str, expected: str, label: str) -> None:
    if expected not in response:
        fail(f"Missing {label}. Expected '{expected}' in response: {response}")


def fail(message: str) -> None:
    print(f"FAILED: {message}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
