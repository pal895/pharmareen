from __future__ import annotations

import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.sheets import MASTER_STOCK, GoogleSheetsStore


BASE_URL = "http://localhost:8000"


def main() -> None:
    assert_health()
    store = GoogleSheetsStore(get_settings())
    if not store.is_available:
        fail("Google Sheets is not available. Check service-account.json and .env.")

    prepare_stock(store, "Panadol", current_stock=44, reorder_level=10)

    help_response = post_whatsapp("help")
    assert_contains(help_response, "Welcome to PharMareen", "help header")
    assert_contains(help_response, "Panadol 2", "help sale example")
    assert_contains(help_response, "Panadol stock", "help stock example")
    print("HELP TEST OK")

    stock_response = post_whatsapp("Panadol stock")
    assert_contains(stock_response, "Panadol stock: 44", "stock count")
    assert_contains(stock_response, "Price: KES 220", "stock price")
    assert_contains(stock_response, "Reorder level: 10", "stock reorder level")
    print("STOCK CHECK TEST OK")

    report_response = post_whatsapp("report today")
    assert_contains(report_response, "Daily Report", "daily report heading")
    assert_contains(report_response, "Sales:", "daily report sales")
    assert_contains(report_response, "Profit:", "daily report profit")
    assert_contains(report_response, "PDF report:", "daily report pdf")
    print("DAILY REPORT TEST OK")

    sale_response = post_whatsapp("Panadol sold 2")
    assert_contains(sale_response, "Panadol x2 recorded", "sale confirmation")
    assert_contains(sale_response, "Stock left: 42", "sale stock left")
    print("SALE STILL WORKS OK")

    restock_response = post_whatsapp("Panadol restock 20")
    assert_contains(restock_response, "Panadol +20 added", "restock confirmation")
    assert_contains(restock_response, "New stock: 62", "restock new stock")
    print("RESTOCK STILL WORKS OK")

    print("PHARMACY BOT READY")


def assert_health() -> None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            if response.status != 200 or '"ok"' not in body:
                fail(f"App health failed: HTTP {response.status} {body}")
    except Exception as exc:
        fail(f"App health failed. Start PharMareen first. Error: {exc}")


def post_whatsapp(message: str) -> str:
    data = urllib.parse.urlencode(
        {
            "Body": message,
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+14155238886",
            "MessageSid": f"SM-READY-{int(time.time() * 1000)}",
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


def assert_contains(response: str, expected: str, label: str) -> None:
    if expected not in response:
        fail(f"Missing {label}. Expected '{expected}' in response: {response}")


def fail(message: str) -> None:
    print(f"FAILED: {message}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
