from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.main as main
from app.domain import StockItem
from app.intake import IntakeService
from app.pdf_reports import generate_daily_report_pdf, generate_weekly_report_pdf
from app.reports import LowStockWarning, ReportMetrics


class FakeParser:
    def parse_events(self, text, master_drug_names):
        raise AssertionError("Rule parser should handle this proof.")


class FakeStore:
    def __init__(self):
        self.stocks = {
            "panadol": StockItem("Panadol", selling_price=220, cost_price=140, current_stock=100, reorder_level=10),
            "amoxyl": StockItem("Amoxyl", selling_price=450, cost_price=320, current_stock=50, reorder_level=5),
            "insulin": StockItem("Insulin", selling_price=1200, cost_price=950, current_stock=20, reorder_level=5),
            "cetirizine": StockItem("Cetirizine", selling_price=120, cost_price=80, current_stock=40, reorder_level=8),
        }
        self.logs = []
        self.transactions = []
        self.reports = {}

    def list_master_drug_names(self):
        return [item.drug_name for item in self.stocks.values()]

    def find_stock(self, drug_name):
        return self.stocks.get(str(drug_name).lower())

    def append_daily_log(self, event, price, total_value):
        self.logs.append(event)

    def update_current_stock(self, stock, new_current_stock):
        self.stocks[stock.drug_name.lower()] = StockItem(
            stock.drug_name, stock.selling_price, stock.cost_price, new_current_stock, stock.reorder_level
        )

    def update_current_stock_and_cost(self, stock, new_current_stock, new_cost_price):
        self.stocks[stock.drug_name.lower()] = StockItem(
            stock.drug_name, stock.selling_price, new_cost_price, new_current_stock, stock.reorder_level
        )

    def append_transaction(self, transaction_type, drug_name, quantity, **kwargs):
        self.transactions.append(
            {
                "Timestamp": "2026-04-30 16:15:00",
                "Date": "today",
                "Type": transaction_type,
                "Drug": drug_name,
                "Quantity": quantity,
                "Total Sales": kwargs.get("total_sales") or "",
                "Total Cost": kwargs.get("total_cost") or "",
                "Profit": kwargs.get("profit") or "",
            }
        )

    def read_transactions(self, start_date, end_date=None):
        return self.transactions

    def read_daily_logs(self, report_date):
        return []

    def list_low_stock_items(self):
        return [item for item in self.stocks.values() if item.current_stock is not None and item.reorder_level is not None and item.current_stock <= item.reorder_level]

    def get_daily_report_text(self, report_date):
        return self.reports.get(report_date)


class FakeWhatsApp:
    async def download_media(self, media_url):
        return b"audio"


class FakeTranscription:
    is_available = True

    def __init__(self, text):
        self.text = text

    def transcribe_audio(self, audio_bytes, content_type):
        return self.text


class FakeIntake:
    def __init__(self, reply):
        self.reply = reply
        self.received = ""

    def process_text(self, text):
        self.received = text
        return self.reply


def main_check() -> int:
    ok = True
    ok &= check("health endpoint", check_health())
    ok &= check("production webhook route", check_webhook_route())
    ok &= check("report today summary", check_intake_contains("report today", "📊 Daily Report"))
    ok &= check("report today PDF generated", check_pdf("daily"))
    ok &= check("report today PDF media attachment payload", check_media_payload())
    ok &= check("report today PDF fallback link", check_fallback_link())
    ok &= check("report week summary", check_intake_contains("report week", "📅 Weekly Report"))
    ok &= check("report week PDF generated", check_pdf("weekly"))
    ok &= check("peak time appears", check_intake_contains("report week", "Peak Time:"))
    ok &= check("voice clear transcript processed", check_voice_clear())
    ok &= check("voice unclear transcript asks confirmation", check_voice_unclear())
    ok &= check("yes confirmation processes pending voice command", check_voice_yes())
    ok &= check("natural language commands work", check_natural_commands())
    ok &= check("help/start works", check_intake_contains("start", "PharMareen Help"))
    ok &= check("share command works", check_intake_contains("share", "wa.me"))
    ok &= check("50-line batch works", check_fifty_line_batch())
    ok &= check("will it get full response works", check_intake_contains("will it get full", "many transactions"))
    ok &= check("old commands still work", check_intake_contains("Panadol sold 2", "Panadol x2 recorded"))
    ok &= check("no-stock logging works", check_intake_contains("Insulin no stock", "no-stock request logged"))
    ok &= check("late sales work", check_intake_contains("later Panadol 3", "Late sale recorded"))
    ok &= check("restock with cost works", check_intake_contains("+Panadol 20 2000", "Avg cost"))
    print(f"FINAL RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def service() -> IntakeService:
    return IntakeService(FakeParser(), FakeStore(), app_base_url="https://reports.pharmareen.app", whatsapp_number="whatsapp:+14155238886")


def check_health() -> bool:
    with TestClient(main.app) as client:
        return client.get("/health").json().get("version") == "day-2"


def check_webhook_route() -> bool:
    fake = FakeIntake("✅ Panadol x2 recorded")
    old = main.get_intake_service
    main.get_intake_service = lambda: fake
    try:
        with TestClient(main.app) as client:
            response = client.post("/webhook/whatsapp", data={"Body": "Panadol 2", "From": "whatsapp:+254700000000", "MessageSid": "SMCHECKROUTE"})
        return response.status_code == 200 and "<Response>" in response.text
    finally:
        main.get_intake_service = old


def check_intake_contains(message: str, expected: str) -> bool:
    return expected in service().process_text(message)


def check_pdf(kind: str) -> bool:
    metrics = ReportMetrics(
        report_date="2026-04-30",
        total_sales=440,
        total_items_sold=2,
        sale_transactions=1,
        most_requested=[("Panadol", 2)],
        most_sold=[("Panadol", 2)],
        missed_sales=[],
        not_sold=[],
        low_stock_warnings=[LowStockWarning("Insulin", 2, 5)],
        peak_activity_time="4PM - 6PM",
        total_cost=280,
        gross_profit=160,
        peak_sales_count=1,
        peak_items_sold=2,
    )
    if kind == "weekly":
        path = generate_weekly_report_pdf(metrics, "PharMareen", "2026-04-24", "2026-04-30", "18:00")
    else:
        path = generate_daily_report_pdf(metrics, "PharMareen", "18:00")
    return path.exists() and path.read_bytes().startswith(b"%PDF")


def check_media_payload() -> bool:
    fake = FakeIntake("📊 Daily Report\n\n📎 PDF report attached below.\nhttps://reports.pharmareen.app/reports/download/report.pdf")
    old = main.get_intake_service
    main.get_intake_service = lambda: fake
    try:
        with TestClient(main.app) as client:
            response = client.post("/webhook/whatsapp", data={"Body": "report today", "From": "whatsapp:+254700000000", "MessageSid": "SMCHECKMEDIA"})
        return "<Media>https://reports.pharmareen.app/reports/download/report.pdf</Media>" in response.text
    finally:
        main.get_intake_service = old


def check_fallback_link() -> bool:
    return "Tap here to download:" in IntakeService(FakeParser(), FakeStore(), app_base_url="http://localhost:8000").process_text("report today")


def check_voice_clear() -> bool:
    return voice_post("Panadol two, later Cetrizine three", "Records updated")


def check_voice_unclear() -> bool:
    return voice_post("maybe panadol", "not fully sure")


def check_voice_yes() -> bool:
    fake = FakeIntake("✅ Panadol x2 recorded")
    old_whatsapp = main.get_whatsapp_client
    old_transcription = main.get_transcription_service
    old_intake = main.get_intake_service
    main.pending_voice_confirmations.clear()
    main.get_whatsapp_client = lambda: FakeWhatsApp()
    main.get_transcription_service = lambda: FakeTranscription("maybe panadol")
    main.get_intake_service = lambda: fake
    try:
        with TestClient(main.app) as client:
            client.post("/webhook/whatsapp", data={"NumMedia": "1", "MediaContentType0": "audio/ogg", "MediaUrl0": "https://example.com/a.ogg", "From": "whatsapp:+254700000100", "MessageSid": "SMCHECKYES1"})
            response = client.post("/webhook/whatsapp", data={"Body": "yes", "From": "whatsapp:+254700000100", "MessageSid": "SMCHECKYES2"})
        return "Confirmed. Records updated" in response.text and fake.received == "maybe panadol"
    finally:
        main.get_whatsapp_client = old_whatsapp
        main.get_transcription_service = old_transcription
        main.get_intake_service = old_intake


def voice_post(transcript: str, expected: str) -> bool:
    old_whatsapp = main.get_whatsapp_client
    old_transcription = main.get_transcription_service
    main.get_whatsapp_client = lambda: FakeWhatsApp()
    main.get_transcription_service = lambda: FakeTranscription(transcript)
    try:
        with TestClient(main.app) as client:
            response = client.post("/webhook/whatsapp", data={"NumMedia": "1", "MediaContentType0": "audio/ogg", "MediaUrl0": "https://example.com/a.ogg", "From": "whatsapp:+254700000099", "MessageSid": f"SMCHECKVOICE{abs(hash(transcript))}"})
        return expected in response.text
    finally:
        main.get_whatsapp_client = old_whatsapp
        main.get_transcription_service = old_transcription


def check_natural_commands() -> bool:
    s = service()
    checks = [
        "Panadol x2" in s.process_text("I sold Panadol 2 and Amoxil 1"),
        "Panadol +20 added" in s.process_text("Add Panadol 20"),
        "Avg cost" in s.process_text("Restock Panadol 20 for 2000"),
        "📊 Daily Report" in s.process_text("Give me today's report"),
        "📦 Panadol stock" in s.process_text("What is Panadol stock?"),
    ]
    return all(checks)


def check_fifty_line_batch() -> bool:
    return "Errors:\n- None" in service().process_text("\n".join("Panadol 1" for _ in range(50)))


def check(label: str, passed: bool) -> bool:
    print(f"{label}: {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    raise SystemExit(main_check())
