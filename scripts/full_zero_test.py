from __future__ import annotations

import subprocess
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
from app.sheets import MASTER_STOCK, GoogleSheetsStore
from app.utils import normalize_key


APP_EXE = Path(r"C:\Program Files (x86)\ZillaPharmacy\ZillaPharmacyApp.exe")
BASE_URL = "http://localhost:8000"


class ZeroTest:
    def __init__(self) -> None:
        self.ready = True
        self.before_rows: list[dict[str, Any]] = []

    def run(self) -> int:
        self.check_app_start()
        self.check_health()
        store = self.check_google_sheets()
        logging_already_checked = False
        if store is not None:
            try:
                self.prepare_stock(store)
                self.before_rows = store.read_daily_logs(date.today().isoformat())
            except Exception as exc:
                self.pass_fail("GOOGLE SHEET LOGGING", False, f"Could not prepare stock test data: {exc}")
                logging_already_checked = True
                store = None

        sale_response = self.post_and_check(
            label="SALE TEST",
            message="Panadol 2",
            required=["✅ Panadol x2 recorded", "Stock left: 42", "Profit:"],
        )
        stock_response = self.post_and_check(
            label="STOCK TEST",
            message="Panadol stock",
            required=["📦 Panadol stock: 42", "Price: KES 220", "Reorder level: 10"],
        )
        restock_response = self.post_and_check(
            label="RESTOCK TEST",
            message="+Panadol 20",
            required=["✅ Panadol +20 added", "New stock: 62"],
        )
        missed_response = self.post_and_check(
            label="MISSED DEMAND TEST",
            message="Insulin no stock",
            required=["📝 Insulin no-stock request logged"],
        )
        low_stock_response = self.post_and_check(
            label="LOW STOCK TEST",
            message="Insulin sold 1",
            required=["✅ Insulin x1 recorded", "Stock left: 2", "LOW STOCK"],
        )
        report_response = self.post_and_check(
            label="REPORT TEST",
            message="report today",
            required=[
                "Daily Report",
                "Sales:",
                "Cost:",
                "Profit:",
                "Items Sold:",
                "Transactions:",
                "Low Stock:",
                "Best Seller:",
                "PDF report:",
            ],
        )

        twilio_ok = any(
            "<Response><Message>" in response
            for response in [
                sale_response,
                stock_response,
                restock_response,
                missed_response,
                low_stock_response,
                report_response,
            ]
        )
        self.pass_fail("TWILIO WEBHOOK TEST", twilio_ok, "Webhook did not return TwiML XML.")

        if store is not None:
            self.check_google_sheet_logging(store)
        elif not logging_already_checked:
            self.pass_fail("GOOGLE SHEET LOGGING", False, "Google Sheets was not available.")

        print(f"FINAL RESULT: {'READY' if self.ready else 'NOT READY'}")
        return 0 if self.ready else 1

    def check_app_start(self) -> None:
        if not APP_EXE.exists():
            self.pass_fail("APP START", False, f"Installed app not found: {APP_EXE}")
            return

        if self.health_ok(wait_seconds=2):
            self.pass_fail("APP START", True)
            return

        try:
            creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                [str(APP_EXE)],
                cwd=str(APP_EXE.parent),
                creationflags=creationflags,
            )
        except Exception as exc:
            self.pass_fail("APP START", False, f"Could not start app: {exc}")
            return

        started = self.health_ok(wait_seconds=90)
        self.pass_fail("APP START", started, "App did not answer /health after starting.")

    def check_health(self) -> None:
        self.pass_fail("APP HEALTH", self.health_ok(wait_seconds=5), "/health did not return ok.")

    def check_google_sheets(self) -> GoogleSheetsStore | None:
        try:
            body = http_get(f"{BASE_URL}/test", timeout=15)
            app_sheets_ok = '"status":"ok"' in body.replace(" ", "")
        except Exception:
            app_sheets_ok = False

        try:
            store = GoogleSheetsStore(get_settings())
            local_sheets_ok = store.is_available
        except Exception:
            store = None
            local_sheets_ok = False

        self.pass_fail(
            "GOOGLE SHEETS",
            app_sheets_ok and local_sheets_ok,
            "Google Sheets is not connected.",
        )
        return store if local_sheets_ok else None

    def prepare_stock(self, store: GoogleSheetsStore) -> None:
        self.set_stock(store, "Panadol", current_stock=44, reorder_level=10)
        self.set_stock(store, "Insulin", current_stock=3, reorder_level=3)

    def set_stock(self, store: GoogleSheetsStore, drug_name: str, current_stock: int, reorder_level: int) -> None:
        stock = store.find_stock(drug_name)
        if stock is None or stock.row_number is None:
            raise RuntimeError(f"{drug_name} was not found in Master_Stock. Run seed_prices.bat first.")
        if stock.selling_price is None:
            raise RuntimeError(f"{drug_name} has no selling price in Master_Stock.")

        worksheet = store.spreadsheet.worksheet(MASTER_STOCK)
        worksheet.update(
            range_name=f"D{stock.row_number}:E{stock.row_number}",
            values=[[current_stock, reorder_level]],
            value_input_option="USER_ENTERED",
        )

    def post_and_check(self, label: str, message: str, required: list[str]) -> str:
        try:
            response = post_whatsapp(message)
        except Exception as exc:
            self.pass_fail(label, False, str(exc))
            return ""

        ok = all(text in response for text in required)
        missing = [text for text in required if text not in response]
        self.pass_fail(label, ok, f"Missing: {', '.join(missing)}")
        return response

    def check_google_sheet_logging(self, store: GoogleSheetsStore) -> None:
        try:
            today = date.today().isoformat()
            after_rows = store.read_daily_logs(today)
            new_rows = after_rows[len(self.before_rows) :]

            checks = [
                row_exists(new_rows, "Panadol", "Sold", 2),
                row_exists(new_rows, "Panadol", "Restocked", 20),
                row_exists(new_rows, "Insulin", "Out of Stock", 1),
                row_exists(new_rows, "Insulin", "Sold", 1),
            ]

            panadol = store.find_stock("Panadol")
            insulin = store.find_stock("Insulin")
            checks.append(panadol is not None and panadol.current_stock == 62)
            checks.append(insulin is not None and insulin.current_stock == 2)
            self.pass_fail("GOOGLE SHEET LOGGING", all(checks), "Expected rows or final stock values were not found.")
        except Exception as exc:
            self.pass_fail("GOOGLE SHEET LOGGING", False, str(exc))

    def health_ok(self, wait_seconds: int) -> bool:
        deadline = time.time() + wait_seconds
        while time.time() <= deadline:
            try:
                body = http_get(f"{BASE_URL}/health", timeout=5)
                if '"status":"ok"' in body.replace(" ", ""):
                    return True
            except Exception:
                pass
            time.sleep(3)
        return False

    def pass_fail(self, label: str, ok: bool, detail: str = "") -> None:
        if ok:
            print(f"{label}: PASS")
            return
        self.ready = False
        print(f"{label}: FAIL")
        if detail:
            print(f"{label} DETAIL: {detail}")


def post_whatsapp(message: str) -> str:
    data = urllib.parse.urlencode(
        {
            "Body": message,
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+14155238886",
            "MessageSid": f"SM-ZERO-{int(time.time() * 1000)}",
            "NumMedia": "0",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/webhooks/twilio/whatsapp",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {body}")
        return body


def http_get(url: str, timeout: int) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def row_exists(rows: list[dict[str, Any]], drug_name: str, action: str, quantity: int) -> bool:
    for row in rows:
        if normalize_key(row.get("Drug Name")) != normalize_key(drug_name):
            continue
        if normalize_key(row.get("Action")) != normalize_key(action):
            continue
        try:
            row_quantity = int(float(str(row.get("Quantity") or 0)))
        except ValueError:
            row_quantity = 0
        if row_quantity == quantity:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(ZeroTest().run())
