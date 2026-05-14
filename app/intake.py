from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from difflib import get_close_matches
from typing import Any, Protocol

from app.domain import Action, ParsedEvent, ParseResult, StockItem
from app.pdf_reports import generate_daily_report_pdf, generate_weekly_report_pdf
from app.reports import ReportMetrics, build_report_metrics, low_stock_from_items, render_daily_summary, top_pairs
from app.services.pharmacy_engine import (
    build_note,
    canonical_unit,
    parse_note_metadata,
    parse_payment_method,
    parse_staff_name,
    parse_trace_modifiers,
    payment_pattern,
    plural_unit,
    strip_modifier_phrases,
    to_base_quantity,
    trace_id,
    unit_pattern,
)
from app.sheets import SHEETS_UNAVAILABLE_MESSAGE, SheetsUnavailableError
from app.utils import format_ksh, normalize_key, now_in_timezone, parse_int, parse_money


UNDERSTAND_ERROR = "\n".join(
    [
        "🤖 I’m not fully sure what you meant.",
        "",
        "Try:",
        "• Panadol 2",
        "• +Panadol 20",
        "• report today",
        "• stock Panadol",
        "",
        "Or type:",
        "help",
    ]
)
SAVE_ERROR = "I could not save this record right now. Please check the Google Sheets connection."
GREETING_TEXT = "\n".join(
    [
        "👋 Welcome to PharMareen.",
        "",
        "You can manage your pharmacy through simple WhatsApp messages.",
        "",
        "Examples:",
        "• Panadol 2",
        "• +Panadol 20",
        "• report today",
        "",
        "Type:",
        "help",
        "",
        "for a quick guide.",
    ]
)
HELP_TEXT = "\n".join(
    [
        "PHARMAREEN QUICK COMMANDS",
        "",
        "Sales:",
        "- Panadol sold 2",
        "- p2",
        "- Insulin sold 1",
        "- sell Panadol",
        "",
        "Stock:",
        "- Panadol stock",
        "- stock p",
        "- low stock",
        "- stock value",
        "",
        "Restock:",
        "- Panadol restock 20",
        "- Panadol +20",
        "- p+20",
        "- Panadol restock 20 cost 2000",
        "",
        "Bonus:",
        "- Panadol restock 20 bonus 5",
        "- Panadol bought 20 plus 5 bonus",
        "",
        "Discount:",
        "- Amoxicillin received 30 paid 2500 discount 300",
        "",
        "Supplier/Expiry:",
        "- Panadol restock 20 supplier DawaPlus expiry Dec 2026",
        "- expiry",
        "- trace Panadol",
        "",
        "Cashier:",
        "- set staff Mary",
        "- cash summary",
        "- staff summary",
        "",
        "Photos:",
        "- Send invoice photo",
        "- Send supplier receipt photo",
        "",
        "Voice:",
        "- Send voice note: Panadol sold two",
        "",
        "Offline mode:",
        "- Save entries in the offline app, then sync",
        "",
        "Late sales:",
        "- later Panadol 5",
        "",
        "Multiple sales:",
        "- Panadol 5, Antacid 3, ORS 2",
    ]
)
AMBIGUOUS_ERROR = (
    "I’m not sure what you mean.\n\n"
    "Did you want to:\n"
    "1. Record a sale\n"
    "2. Add stock\n"
    "3. Check stock\n"
    "4. Get report"
)
ORDERING_TODO_REPLY = (
    "Customer ordering is planned. For now, PharMareen focuses on sales, stock, profit, reports, and no-stock demand."
)
HIGH_VOLUME_REPLY = (
    "No. PharMareen can keep recording many transactions.\n\n"
    "If your pharmacy grows, we can upgrade the storage without changing how you use WhatsApp."
)


class Parser(Protocol):
    def parse_events(self, text: str, master_drug_names: list[str]) -> ParseResult:
        ...


class StockStore(Protocol):
    def list_master_drug_names(self) -> list[str]:
        ...

    def find_stock(self, drug_name: str) -> StockItem | None:
        ...

    def append_daily_log(
        self,
        event: ParsedEvent,
        price: float | None,
        total_value: float | None,
    ) -> None:
        ...

    def update_current_stock(self, stock: StockItem, new_current_stock: int) -> None:
        ...

    def update_current_stock_and_cost(
        self,
        stock: StockItem,
        new_current_stock: int,
        new_cost_price: float | None,
    ) -> None:
        ...

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
    ) -> None:
        ...

    def read_transactions(self, start_date: str, end_date: str | None = None) -> list[dict[str, Any]]:
        ...

    def get_daily_report_text(self, report_date: str) -> str | None:
        ...

    def read_daily_logs(self, report_date: str) -> list[dict]:
        ...

    def list_low_stock_items(self) -> list[StockItem]:
        ...


@dataclass(frozen=True)
class EntryResult:
    logged: bool
    reply: str
    summary_line: str
    category: str = "errors"


@dataclass(frozen=True)
class StockUpdatePlan:
    new_current_stock: int | None
    warning_notes: list[str]
    reply_warnings: list[str]


@dataclass(frozen=True)
class OperatingCommand:
    kind: str
    drug_name: str = ""
    quantity: int = 1
    total_cost: float | None = None
    budgeted_cost: float | None = None
    restock_type: str = "normal"
    ordered_quantity: int | None = None
    bonus_quantity: int = 0
    expected_total_cost: float | None = None
    discount_amount: float = 0
    actual_paid_amount: float | None = None
    supplier: str = ""
    expiry_date: str = ""
    unit: str = ""
    base_quantity: int | None = None
    payment_method: str = ""
    discount: float = 0
    staff_name: str = ""
    batch_number: str = ""
    invoice_number: str = ""
    barcode: str = ""
    trace_id: str = ""
    notes: str = ""
    raw_text: str = ""
    error: str = ""


@dataclass(frozen=True)
class FollowUpPrompt:
    command: OperatingCommand
    question: str


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}

SHORTCUT_DRUGS = {
    "p": "Panadol",
    "pan": "Panadol",
    "para": "Paracetamol",
    "ors": "ORS",
    "a": "Antacid",
    "ant": "Antacid",
    "i": "Insulin",
    "ins": "Insulin",
}


class IntakeService:
    def __init__(
        self,
        parser: Parser,
        store: StockStore,
        timezone: str = "Africa/Nairobi",
        pharmacy_name: str = "PharMareen",
        app_base_url: str | None = None,
        whatsapp_number: str | None = None,
    ):
        self.parser = parser
        self.store = store
        self.timezone = timezone
        self.pharmacy_name = pharmacy_name
        self.app_base_url = clean_app_base_url(app_base_url)
        self.whatsapp_number = clean_whatsapp_number(whatsapp_number)
        self.pending_followups: dict[str, OperatingCommand] = {}
        self.staff_by_conversation: dict[str, str] = {}
        self.last_sale_by_conversation: dict[str, dict[str, Any]] = {}
        self.pending_void_reason: dict[str, dict[str, Any]] = {}
        self.conversions_by_drug: dict[str, dict[str, int]] = {}

    def process_text(self, text: str, conversation_id: str | None = None) -> str:
        text = text.strip()
        if not text:
            return "Please send a short text message or voice note."

        conversation_key = conversation_id or "__default__"
        pending_void = self.pending_void_reason.get(conversation_key)
        if pending_void is not None:
            if normalize_key(text) in {"cancel", "stop"}:
                self.pending_void_reason.pop(conversation_key, None)
                return "No problem. The sale was not voided."
            self.pending_void_reason.pop(conversation_key, None)
            return self._commit_void(pending_void, text, conversation_key)

        pending_followup = self.pending_followups.get(conversation_key)
        if pending_followup is not None:
            completed = complete_followup_command(text, pending_followup)
            if completed is not None:
                self.pending_followups.pop(conversation_key, None)
                return self._process_commands([completed], conversation_key=conversation_key)
            if normalize_key(text) in {"cancel", "stop"}:
                self.pending_followups.pop(conversation_key, None)
                return "No problem. Nothing was saved."
            if parse_operating_commands(text) is not None or is_help_command(text) or is_greeting_command(text):
                self.pending_followups.pop(conversation_key, None)

        if is_greeting_command(text):
            return GREETING_TEXT

        if is_help_command(text):
            return HELP_TEXT

        if is_share_command(text):
            return self._share_reply()

        if is_high_volume_question(text):
            return HIGH_VOLUME_REPLY

        if is_customer_ordering_question(text):
            return ORDERING_TODO_REPLY

        if is_process_batch_command(text):
            return "No saved offline entries yet.\n\nSend sales together like:\nPanadol 2\nAmoxil 1"

        conversion = parse_conversion_command(text)
        if conversion is not None:
            drug_name, strips_per_box, tablets_per_strip = conversion
            self.conversions_by_drug[normalize_key(drug_name)] = {
                "box": strips_per_box * tablets_per_strip,
                "strip": tablets_per_strip,
                "tablet": 1,
                "unit": 1,
                "piece": 1,
                "bottle": 1,
            }
            return "\n".join(
                [
                    f"Conversion saved for {title_drug_name(drug_name)}",
                    f"1 box = {strips_per_box} strips",
                    f"1 strip = {tablets_per_strip} tablets",
                ]
            )

        followup_prompt = parse_followup_prompt(text)
        if followup_prompt is not None:
            self.pending_followups[conversation_key] = followup_prompt.command
            return followup_prompt.question

        if is_profit_today_command(text):
            return self._profit_today_reply()

        if is_cash_summary_command(text):
            return self._cash_summary_reply()

        if is_staff_summary_command(text):
            return self._staff_summary_reply()

        if is_low_stock_command(text):
            return self._low_stock_reply()

        if is_stock_value_command(text):
            return self._stock_value_reply()

        trace_drug_name = parse_trace_command(text)
        if trace_drug_name:
            return self._trace_reply(trace_drug_name)

        expiry_drug_name = parse_expiry_command(text)
        if expiry_drug_name is not None:
            return self._expiry_reply(expiry_drug_name)

        if is_weekly_report_command(text):
            return self._weekly_report_reply()

        stock_drug_name = parse_stock_check_command(text)
        if stock_drug_name:
            return self._stock_check_reply(stock_drug_name)

        if is_today_summary_command(text):
            return self._today_summary_reply()

        report_date = parse_report_command(text, self.timezone)
        if report_date:
            return self._saved_report_reply(report_date)

        commands = parse_operating_commands(text)
        if commands is not None:
            return self._process_commands(commands, conversation_key=conversation_key)

        try:
            master_drug_names = self.store.list_master_drug_names()
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return SAVE_ERROR

        try:
            parsed = self.parser.parse_events(text, master_drug_names)
        except Exception:
            return UNDERSTAND_ERROR

        if parsed.needs_clarification or not parsed.events:
            return parsed.clarification_question or AMBIGUOUS_ERROR

        results = [self._process_event(event) for event in parsed.events]
        if len(results) == 1:
            return results[0].reply

        logged_results = [result for result in results if result.logged]
        if not logged_results:
            return "\n".join(result.reply for result in results)

        lines = [result.summary_line for result in logged_results]
        error_lines = [result.reply for result in results if not result.logged]
        if error_lines:
            lines.extend(error_lines)

        return f"Logged {len(logged_results)} entries:\n\n" + "\n".join(
            f"- {line}" for line in lines
        )

    def _share_reply(self) -> str:
        return "\n".join(
            [
                "📲 Share PharMareen with staff:",
                "",
                "Tap to open WhatsApp:",
                self._whatsapp_start_link(),
            ]
        )

    def _whatsapp_start_link(self) -> str:
        if not self.whatsapp_number:
            return "Ask the pharmacy admin for the PharMareen WhatsApp number."
        return f"https://wa.me/{self.whatsapp_number}?text=start"

    def _saved_report_reply(self, report_date: str) -> str:
        try:
            report_text = self.store.get_daily_report_text(report_date)
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not fetch the report right now. Please check the Google Sheets connection."
        if not report_text:
            return f"No report found for {report_date}."
        return ensure_report_has_pharmacy_name(report_text, self.pharmacy_name)

    def _stock_check_reply(self, drug_name: str) -> str:
        try:
            stock = self._resolve_stock(drug_name)
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return SAVE_ERROR

        if stock is None:
            return f"{drug_name} was not found in inventory. Please add or restock it first."

        try:
            self._append_transaction("stock_check", stock.drug_name, 0, note="Stock checked")
        except Exception:
            pass

        stock_text = str(stock.current_stock) if stock.current_stock is not None else "not set"
        lines = [f"📦 {stock.drug_name} stock: {stock_text}"]
        if stock.selling_price is not None:
            lines.append(f"Price: {format_kes(stock.selling_price)}")
        if stock.reorder_level is not None:
            lines.append(f"Reorder level: {stock.reorder_level}")
        return "\n".join(lines)

    def _low_stock_reply(self) -> str:
        try:
            items = self.store.list_low_stock_items()
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not check low stock right now. Please check the Google Sheets connection."
        if not items:
            return "Low Stock\n\nNo low stock items right now."
        lines = ["Low Stock", ""]
        for item in items[:20]:
            stock_text = item.current_stock if item.current_stock is not None else "not set"
            reorder_text = item.reorder_level if item.reorder_level is not None else "not set"
            lines.append(f"- {item.drug_name}: {stock_text} left, reorder at {reorder_text}")
        return "\n".join(lines)

    def _stock_value_reply(self) -> str:
        try:
            items = self._all_stock_items()
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not calculate stock value right now. Please check the Google Sheets connection."
        cost_value = 0.0
        sales_value = 0.0
        counted = 0
        missing = 0
        for item in items:
            stock_count = item.current_stock
            if stock_count is None:
                missing += 1
                continue
            if item.cost_price is None or item.selling_price is None:
                missing += 1
            if item.cost_price is not None:
                cost_value += stock_count * item.cost_price
            if item.selling_price is not None:
                sales_value += stock_count * item.selling_price
            counted += 1
        lines = [
            "Stock Value",
            "",
            f"Cost value: {format_kes(cost_value)}",
            f"Selling value: {format_kes(sales_value)}",
            f"Potential profit: {format_kes(sales_value - cost_value)}",
            f"Items counted: {counted}",
        ]
        if missing:
            lines.append(f"Missing price/stock data: {missing}")
        return "\n".join(lines)

    def _expiry_reply(self, drug_name: str = "") -> str:
        try:
            list_batches = getattr(self.store, "list_batches", None)
            batches = list_batches(drug_name or None) if list_batches else []
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not check expiry records right now. Please check the Google Sheets connection."
        if not batches:
            target = f" for {drug_name}" if drug_name else ""
            return f"Expiry\n\nNo batch expiry records found{target}."
        try:
            from app.services.batch_service import expiry_status
        except Exception:
            expiry_status = lambda value: "safe"  # noqa: E731
        sorted_batches = sorted(batches, key=lambda batch: getattr(batch, "expiry_sort_key", getattr(batch, "expiry_date", "")))
        lines = ["Expiry", ""]
        for batch in sorted_batches[:20]:
            expiry = getattr(batch, "expiry_date", "") or "not set"
            status = expiry_status(expiry)
            warning = " expired" if status == "expired" else (" near expiry" if status == "near_expiry" else "")
            lines.append(
                f"- {getattr(batch, 'drug_name', drug_name)}: {getattr(batch, 'current_remaining_units', 0)} units exp {expiry}{warning}"
            )
        return "\n".join(lines)

    def _trace_reply(self, drug_name: str) -> str:
        try:
            stock = self._resolve_stock(drug_name)
            list_batches = getattr(self.store, "list_batches", None)
            batches = list_batches(drug_name) if list_batches else []
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not trace that medicine right now. Please check the Google Sheets connection."
        if stock is None and not batches:
            return f"{drug_name} was not found in inventory. Please add or restock it first."
        name = stock.drug_name if stock else title_drug_name(drug_name)
        lines = [f"Trace {name}", ""]
        if stock:
            stock_text = stock.current_stock if stock.current_stock is not None else "not set"
            lines.append(f"Stock: {stock_text}")
            if stock.selling_price is not None:
                lines.append(f"Price: {format_kes(stock.selling_price)}")
        if batches:
            lines.append("Batches:")
            for batch in sorted(batches, key=lambda batch: getattr(batch, "expiry_sort_key", getattr(batch, "expiry_date", "")))[:10]:
                batch_id = getattr(batch, "batch_id", "") or getattr(batch, "manufacturer_batch_number", "") or "batch"
                expiry = getattr(batch, "expiry_date", "") or "not set"
                supplier = getattr(batch, "supplier_name", "") or "not set"
                invoice = getattr(batch, "invoice_number", "") or "not set"
                remaining = getattr(batch, "current_remaining_units", 0)
                lines.append(f"- {batch_id}: {remaining} units, exp {expiry}, supplier {supplier}, invoice {invoice}")
            lines.append("Use earliest expiry first.")
        else:
            lines.append("Batches: none recorded yet.")
        return "\n".join(lines)

    def _today_summary_reply(self) -> str:
        now = now_in_timezone(self.timezone)
        report_date = now.date().isoformat()
        try:
            read_transactions = getattr(self.store, "read_transactions", None)
            transactions = read_transactions(report_date) if read_transactions else []
            logs = self.store.read_daily_logs(report_date)
            low_stock = low_stock_from_items(self.store.list_low_stock_items())
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not prepare today's report right now. Please check the Google Sheets connection."

        metrics = build_transaction_metrics(report_date, transactions, low_stock)
        if not transactions:
            metrics = build_report_metrics(report_date, logs, low_stock)
        report_text = render_whatsapp_report(metrics, "daily")
        payment_section = self._payment_summary_section(transactions)
        if payment_section:
            report_text = f"{report_text}\n\n{payment_section}"
        try:
            pdf_path = generate_daily_report_pdf(
                metrics,
                pharmacy_name=self.pharmacy_name,
                report_time=now.strftime("%H:%M"),
            )
        except Exception:
            return f"{report_text}\n\nPDF report could not be generated on this computer."
        pdf_link = self._public_pdf_link(pdf_path)
        return append_pdf_instruction(report_text, pdf_link, self.can_attach_pdf())

    def _profit_today_reply(self) -> str:
        now = now_in_timezone(self.timezone)
        report_date = now.date().isoformat()
        try:
            transactions = self.store.read_transactions(report_date)
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not calculate profit right now. Please check the Google Sheets connection."

        metrics = build_transaction_metrics(report_date, transactions, [])
        lines = [
            "📊 Profit Today",
            "",
            f"Sales: {format_kes(metrics.total_sales)}",
            f"Cost: {format_kes(metrics.total_cost)}",
            f"Gross Profit: {format_kes(metrics.gross_profit)}",
            f"Items Sold: {metrics.total_items_sold}",
            f"Transactions: {metrics.sale_transactions}",
        ]
        if metrics.missing_profit_data:
            lines.append("")
            lines.append("⚠️ Some items had missing price data, so profit may be incomplete.")
        return "\n".join(lines)

    def _today_profit_line(self) -> str:
        report_date = now_in_timezone(self.timezone).date().isoformat()
        try:
            transactions = self.store.read_transactions(report_date)
        except Exception:
            return ""
        metrics = build_transaction_metrics(report_date, transactions, [])
        return f"📊 Today Profit: {format_kes(metrics.gross_profit)}"

    def _weekly_report_reply(self) -> str:
        today = now_in_timezone(self.timezone).date()
        start_date = today - timedelta(days=6)
        try:
            transactions = self.store.read_transactions(start_date.isoformat(), today.isoformat())
            low_stock = low_stock_from_items(self.store.list_low_stock_items())
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not prepare the weekly report right now. Please check the Google Sheets connection."

        metrics = build_transaction_metrics(f"{start_date.isoformat()} to {today.isoformat()}", transactions, low_stock)
        best_seller = metrics.most_sold[0][0] if metrics.most_sold else "None"
        low_stock_text = ", ".join(item.drug_name for item in metrics.low_stock_warnings) or "None"
        pdf_link = ""
        try:
            pdf_path = generate_weekly_report_pdf(
                metrics,
                pharmacy_name=self.pharmacy_name,
                period_start=start_date.isoformat(),
                period_end=today.isoformat(),
                report_time=now_in_timezone(self.timezone).strftime("%H:%M"),
            )
            pdf_link = self._public_pdf_link(pdf_path)
        except Exception:
            pdf_link = "PDF report could not be generated on this computer."

        lines = render_whatsapp_report(metrics, "weekly").splitlines()
        payment_section = self._payment_summary_section(transactions)
        if payment_section:
            lines.extend(["", payment_section])
        if metrics.missing_profit_data:
            lines.append("")
            lines.append("⚠️ Some items had missing price data, so profit may be incomplete.")
        return append_pdf_instruction("\n".join(lines), pdf_link, self.can_attach_pdf())

    def _payment_summary_section(self, transactions: list[dict[str, Any]]) -> str:
        payment_totals = {"Cash": 0.0, "M-Pesa": 0.0, "Card": 0.0, "Credit": 0.0}
        discounts = 0.0
        for row in transactions:
            if normalize_key(row.get("Type")) not in {"sale", "late sale", "late_sale"}:
                continue
            note_meta = parse_note_metadata(str(row.get("Note") or ""))
            payment = note_meta.get("payment", "Cash")
            payment = "M-Pesa" if normalize_key(payment) in {"mpesa", "m pesa", "m-pesa"} else payment.title()
            payment_totals.setdefault(payment, 0.0)
            payment_totals[payment] += parse_money(row.get("Total Sales")) or 0
            discounts += parse_money(note_meta.get("discount")) or 0
        if not any(payment_totals.values()) and not discounts:
            return ""
        return "\n".join(
            [
                "Payments:",
                f"Cash {format_kes(payment_totals.get('Cash', 0))}",
                f"M-Pesa {format_kes(payment_totals.get('M-Pesa', 0))}",
                f"Card {format_kes(payment_totals.get('Card', 0))}",
                f"Credit {format_kes(payment_totals.get('Credit', 0))}",
                f"Discounts {format_kes(discounts)}",
            ]
        )

    def _public_pdf_link(self, pdf_path) -> str:
        return f"{self.app_base_url}/reports/download/{pdf_path.name}"

    def can_attach_pdf(self) -> bool:
        lower = self.app_base_url.lower()
        return lower.startswith("https://") and "localhost" not in lower and "127.0.0.1" not in lower

    def _process_commands(self, commands: list[OperatingCommand], conversation_key: str = "__default__") -> str:
        results = [self._process_command(command, conversation_key=conversation_key) for command in commands]
        if len(results) == 1:
            return results[0].reply

        groups = {
            "sales": [],
            "late_sales": [],
            "restocks": [],
            "no_stock": [],
            "stock_checks": [],
            "errors": [],
        }
        for result in results:
            if result.category in groups:
                groups[result.category].append(result.summary_line or result.reply)

        lines = ["✅ Batch processed", ""]
        section_titles = [
            ("Sales", "sales"),
            ("Late Sales", "late_sales"),
            ("Restocks", "restocks"),
            ("No Stock", "no_stock"),
        ]
        if groups["stock_checks"]:
            section_titles.append(("Stock Checks", "stock_checks"))
        section_titles.append(("Errors", "errors"))

        for title, key in section_titles:
            lines.append(f"{title}:")
            if groups[key]:
                lines.extend(f"- {item}" for item in groups[key])
            else:
                lines.append("- None")
            if title != section_titles[-1][0]:
                lines.append("")
        return "\n".join(lines)

    def _process_command(self, command: OperatingCommand, conversation_key: str = "__default__") -> EntryResult:
        if command.kind == "error":
            return EntryResult(
                logged=False,
            reply=f'"{command.raw_text}" could not be understood',
            summary_line=f'"{command.raw_text}" could not be understood',
                category="errors",
            )
        if command.kind == "sale":
            return self._process_sale_command(command, is_late=False, conversation_key=conversation_key)
        if command.kind == "late_sale":
            return self._process_sale_command(command, is_late=True, conversation_key=conversation_key)
        if command.kind == "restock":
            return self._process_restock_command(command)
        if command.kind == "set_staff":
            staff_name = command.staff_name or command.drug_name
            self.staff_by_conversation[conversation_key] = staff_name
            return EntryResult(
                logged=True,
                reply=f"Staff set: {staff_name}",
                summary_line=f"Staff set: {staff_name}",
                category="stock_checks",
            )
        if command.kind == "void":
            return self._process_void_command(command, conversation_key=conversation_key)
        if command.kind == "stock_check":
            return EntryResult(
                logged=True,
                reply=self._stock_check_reply(command.drug_name),
                summary_line=f"{command.drug_name} stock checked",
                category="stock_checks",
            )
        if command.kind == "no_stock":
            event = ParsedEvent(command.drug_name, Action.OUT_OF_STOCK, quantity=command.quantity)
            return self._process_missed_demand(event)
        return EntryResult(
            logged=False,
            reply=UNDERSTAND_ERROR,
            summary_line=f'"{command.raw_text}" could not be understood',
            category="errors",
        )

    def _process_event(self, event: ParsedEvent) -> EntryResult:
        if event.needs_clarification or not event.drug_name or event.action is None:
            return EntryResult(
                logged=False,
                reply=event.clarification_question or UNDERSTAND_ERROR,
                summary_line="",
                category="errors",
            )

        if event.action in {Action.SOLD, Action.LATE_SALE}:
            return self._process_sale(event)
        if event.action == Action.RESTOCKED:
            return self._process_restock(event)
        if event.action == Action.OUT_OF_STOCK:
            return self._process_missed_demand(event)
        return self._process_lost_opportunity(event)

    def _process_sale(self, event: ParsedEvent) -> EntryResult:
        return self._record_sale(
            drug_name=event.drug_name,
            quantity=event.quantity,
            is_late=event.action == Action.LATE_SALE,
            note=event.notes,
        )

    def _process_sale_command(self, command: OperatingCommand, is_late: bool, conversation_key: str = "__default__") -> EntryResult:
        note = "Entered later" if is_late else ""
        staff_name = command.staff_name or self.staff_by_conversation.get(conversation_key, "")
        return self._record_sale(
            command.drug_name,
            command.quantity,
            is_late=is_late,
            note=note,
            unit=command.unit,
            base_quantity=command.base_quantity,
            payment_method=command.payment_method,
            discount=command.discount,
            staff_name=staff_name,
            trace_id_value=command.trace_id,
            batch_number=command.batch_number,
            invoice_number=command.invoice_number,
            supplier=command.supplier,
            barcode=command.barcode,
            conversation_key=conversation_key,
        )

    def _record_sale(
        self,
        drug_name: str,
        quantity: int,
        is_late: bool = False,
        note: str = "",
        unit: str = "",
        base_quantity: int | None = None,
        payment_method: str = "",
        discount: float = 0,
        staff_name: str = "",
        trace_id_value: str = "",
        batch_number: str = "",
        invoice_number: str = "",
        supplier: str = "",
        barcode: str = "",
        conversation_key: str = "__default__",
    ) -> EntryResult:
        try:
            stock = self._resolve_stock(drug_name)
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")
        if stock is None:
            return EntryResult(
                logged=False,
                reply=f"{drug_name} was not found in inventory. Please add or restock it first.",
                summary_line="",
                category="errors",
            )

        action = Action.LATE_SALE if is_late else Action.SOLD
        unit = canonical_unit(unit)
        display_quantity = quantity
        base_quantity = self._to_base_quantity(stock.drug_name, quantity, unit) if unit else (base_quantity or to_base_quantity(quantity, unit))
        payment_method = payment_method or "Cash"
        discount = float(discount or 0)
        sale_trace_id = trace_id_value or trace_id("SALE")
        stock_plan = build_stock_update_plan(stock, base_quantity)
        notes = merge_notes(note, stock_plan.warning_notes)
        fefo_reply = ""
        try:
            from app.services.batch_service import BatchService

            deductions = BatchService(self.store).deduct_fefo(stock.drug_name, base_quantity)
            if deductions:
                first_deduction = deductions[0]
                expiry_text = first_deduction.expiry_date or "earliest batch"
                fefo_reply = f"Deducted from earliest expiry batch: {expiry_text}."
                batch_notes = ", ".join(
                    f"{deduction.batch_id}:{deduction.quantity}"
                    for deduction in deductions
                )
                notes = merge_notes(notes, f"Batch deductions: {batch_notes}")
                if not batch_number:
                    batch_number = first_deduction.batch_id
        except Exception:
            fefo_reply = ""
        notes = build_note(
            notes,
            trace_id=sale_trace_id,
            unit=unit or "unit",
            display_quantity=display_quantity,
            base_quantity=base_quantity,
            payment=payment_method,
            discount=discount if discount else "",
            staff=staff_name,
            batch=batch_number,
            invoice=invoice_number,
            supplier=supplier,
            barcode=barcode,
        )
        event = ParsedEvent(stock.drug_name, action, quantity=base_quantity, notes=notes)
        gross_sales = stock.selling_price * base_quantity if stock.selling_price is not None else None
        total_sales = max(gross_sales - discount, 0) if gross_sales is not None else None
        total_cost = stock.cost_price * base_quantity if stock.cost_price is not None else None
        profit = (
            total_sales - total_cost
            if total_sales is not None and total_cost is not None
            else None
        )
        missing_profit_data = stock.selling_price is None or stock.cost_price is None

        try:
            self.store.append_daily_log(event, stock.selling_price, total_sales)
            self._append_transaction(
                "late_sale" if is_late else "sale",
                stock.drug_name,
                base_quantity,
                unit_cost=stock.cost_price,
                unit_selling_price=stock.selling_price,
                total_cost=total_cost,
                total_sales=total_sales,
                profit=profit,
                note=notes,
            )
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")

        if stock_plan.new_current_stock is not None:
            try:
                self.store.update_current_stock(stock, stock_plan.new_current_stock)
            except Exception:
                stock_plan.reply_warnings.append(
                    "Stock level could not be updated because Google Sheets could not be updated."
                )

        if is_late:
            reply_parts = [
                "✅ Late sale recorded",
                f"{event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)}",
            ]
        elif missing_profit_data:
            reply_parts = [
                "⚠️ Sale recorded, but profit not calculated because price data is missing.",
                f"{event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)}",
            ]
        else:
            reply_parts = [
                f"✅ {event.drug_name} x{quantity} recorded",
            ]
        if not is_late and not missing_profit_data:
            reply_parts[0] = f"\u2705 {event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)} recorded"
        if unit and base_quantity != display_quantity:
            reply_parts.append(f"Equivalent: {base_quantity} tablets")
        if stock_plan.new_current_stock is not None:
            suffix = " tablets" if unit else ""
            reply_parts.append(f"Stock left: {stock_plan.new_current_stock}{suffix}")
        else:
            reply_parts.append("Stock left: not set.")
        if fefo_reply:
            reply_parts.append(fefo_reply)
        if payment_method and payment_method != "Cash":
            reply_parts.append(f"Payment: {payment_method}")
        if discount:
            reply_parts.append(f"Discount: {format_kes(discount)}")
        if not is_late and not missing_profit_data:
            reply_parts.append(f"Profit: {format_kes(profit)}")
        reply_parts.append(f"Trace: {sale_trace_id}")
        today_profit_line = self._today_profit_line()
        if today_profit_line:
            reply_parts.append(today_profit_line)
        if stock_plan.reply_warnings:
            reply_parts.extend(stock_plan.reply_warnings)
        reply = "\n".join(reply_parts)
        self.last_sale_by_conversation[conversation_key] = {
            "drug_name": stock.drug_name,
            "quantity": base_quantity,
            "unit": unit,
            "display_quantity": display_quantity,
            "trace_id": sale_trace_id,
            "payment_method": payment_method,
            "discount": discount,
        }

        return EntryResult(
            logged=True,
            reply=reply,
            summary_line=f"{event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)}",
            category="late_sales" if is_late else "sales",
        )

    def _process_restock(self, event: ParsedEvent) -> EntryResult:
        return self._process_restock_command(
            OperatingCommand(
                kind="restock",
                drug_name=event.drug_name,
                quantity=event.quantity,
                raw_text=event.drug_name,
            )
        )

    def _process_restock_command(self, command: OperatingCommand) -> EntryResult:
        try:
            stock = self._resolve_stock(command.drug_name)
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")
        if stock is None:
            return EntryResult(
                logged=False,
                reply=f"{command.drug_name} was not found in inventory. Please add it to Master_Stock first.",
                summary_line="",
                category="errors",
            )

        current_stock = stock.current_stock or 0
        unit = canonical_unit(command.unit)
        display_quantity = command.quantity
        quantity_to_add = self._to_base_quantity(stock.drug_name, command.quantity, unit) if unit else (command.base_quantity or to_base_quantity(command.quantity, unit))
        restock_trace_id = command.trace_id or trace_id("RESTOCK")
        bonus_quantity = max(command.bonus_quantity or 0, 0)
        if command.restock_type == "bonus" and bonus_quantity == 0 and command.total_cost == 0:
            bonus_quantity = command.quantity
            ordered_quantity = command.ordered_quantity if command.ordered_quantity is not None else 0
        else:
            ordered_quantity = command.ordered_quantity if command.ordered_quantity is not None else max(command.quantity - bonus_quantity, 0)
        new_current_stock = current_stock + quantity_to_add
        actual_paid_amount = command.actual_paid_amount if command.actual_paid_amount is not None else command.total_cost
        expected_total_cost = command.expected_total_cost if command.expected_total_cost is not None else command.budgeted_cost
        discount_amount = command.discount_amount or 0
        if actual_paid_amount is None and expected_total_cost is not None and discount_amount:
            actual_paid_amount = max(expected_total_cost - discount_amount, 0)
        total_added_cost = 0 if command.restock_type == "bonus" and actual_paid_amount is None else actual_paid_amount
        new_average_cost = calculate_average_cost(
            current_stock=current_stock,
            current_cost=stock.cost_price,
            added_quantity=quantity_to_add,
            total_added_cost=total_added_cost,
        )
        unit_added_cost = (
            total_added_cost / quantity_to_add
            if total_added_cost is not None and quantity_to_add > 0
            else None
        )
        saved_amount = (
            expected_total_cost - total_added_cost
            if expected_total_cost is not None and total_added_cost is not None
            else discount_amount if discount_amount else None
        )
        note_parts = [f"Restock type: {command.restock_type}."]
        if ordered_quantity or bonus_quantity:
            note_parts.append(f"Ordered quantity {ordered_quantity}. Bonus quantity {bonus_quantity}. Total received {command.quantity}.")
        if total_added_cost is not None:
            note_parts.append(f"Restock total cost {format_kes(total_added_cost)}.")
            note_parts.append(f"Calculated unit cost {format_kes(unit_added_cost)}.")
        if expected_total_cost is not None:
            note_parts.append(f"Budgeted {format_kes(expected_total_cost)}.")
        if discount_amount:
            note_parts.append(f"Discount {format_kes(discount_amount)}.")
        if saved_amount is not None and expected_total_cost is not None:
            note_parts.append(f"Saved {format_kes(saved_amount)}.")
        if command.supplier:
            note_parts.append(f"Supplier: {command.supplier}.")
        if command.expiry_date:
            note_parts.append(f"Expiry: {command.expiry_date}.")
        if command.notes:
            note_parts.append(command.notes)
        notes = build_note(
            " ".join(note_parts),
            trace_id=restock_trace_id,
            unit=unit or "unit",
            display_quantity=display_quantity,
            base_quantity=quantity_to_add,
            supplier=command.supplier,
            invoice=command.invoice_number,
            batch=command.batch_number,
            barcode=command.barcode,
            expiry=command.expiry_date,
        )
        event = ParsedEvent(stock.drug_name, Action.RESTOCKED, quantity=quantity_to_add, notes=notes)

        try:
            if total_added_cost is not None:
                self.store.update_current_stock_and_cost(stock, new_current_stock, new_average_cost)
            else:
                self.store.update_current_stock(stock, new_current_stock)
            self.store.append_daily_log(event, None, None)
            self._append_transaction(
                "restock",
                stock.drug_name,
                quantity_to_add,
                unit_cost=unit_added_cost,
                total_cost=total_added_cost,
                note=notes,
            )
            self._create_batch_if_supported(
                stock.drug_name,
                quantity_to_add,
                command,
                restock_trace_id,
                unit,
                total_added_cost,
                stock.selling_price,
            )
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")

        has_bonus = bonus_quantity > 0
        has_discount = bool(discount_amount) or command.restock_type in {"discount", "bonus_discount"}
        display_text = f"{display_quantity}{unit_suffix(unit, display_quantity)}"
        if has_bonus and ordered_quantity:
            reply_parts = [
                f"\u2705 Restock recorded: {event.drug_name} +{display_text} total. Bought {ordered_quantity} + bonus {bonus_quantity}.",
            ]
        elif has_bonus:
            reply_parts = [f"\u2705 Restock recorded: {event.drug_name} +{display_text} total. Bonus {bonus_quantity}."]
        else:
            reply_parts = [f"\u2705 Restock recorded: {event.drug_name} +{display_text}."]

        if command.restock_type == "bonus" and not ordered_quantity:
            reply_parts.append(f"\u2705 {event.drug_name} bonus +{display_text} added")
        else:
            reply_parts.append(f"\u2705 {event.drug_name} +{display_text} added")
        if unit and quantity_to_add != display_quantity:
            reply_parts.append(f"Equivalent: +{quantity_to_add} tablets")
        if total_added_cost is not None and total_added_cost != 0:
            reply_parts.append(f"Paid: {format_kes(total_added_cost)}")
        if expected_total_cost is not None:
            reply_parts.insert(1, f"Budget: {format_kes(expected_total_cost)}")
        if has_discount and discount_amount:
            if has_bonus:
                reply_parts.append(f"Discount: {format_kes(discount_amount)}.")
            else:
                reply_parts.append(f"Discount noted: {format_kes(discount_amount)}")
        if saved_amount is not None and expected_total_cost is not None:
            reply_parts.append(f"Saved: {format_kes(saved_amount)}")
        if new_average_cost is not None and total_added_cost != 0:
            reply_parts.append(f"Avg cost: {format_kes(new_average_cost)}")
        if command.supplier:
            reply_parts.append(f"Supplier: {command.supplier}")
        if command.expiry_date:
            reply_parts.append(f"Expiry: {command.expiry_date}")
        if command.invoice_number:
            reply_parts.append(f"Invoice: {command.invoice_number}")
        if command.batch_number:
            reply_parts.append(f"Batch: {command.batch_number}")
        reply_parts.append(f"Trace: {restock_trace_id}")
        stock_suffix = " tablets" if unit else ""
        reply_parts.append(f"New stock: {new_current_stock}{stock_suffix}")
        return EntryResult(
            logged=True,
            reply="\n".join(reply_parts),
            summary_line=f"{event.drug_name} +{display_text}",
            category="restocks",
        )

    def _process_missed_demand(self, event: ParsedEvent) -> EntryResult:
        try:
            stock = self._resolve_stock(event.drug_name)
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")
        if stock is not None:
            event = replace(event, drug_name=stock.drug_name)

        try:
            self.store.append_daily_log(event, None, None)
            self._append_transaction(
                "no_stock",
                event.drug_name,
                event.quantity,
                note=event.notes or "Missed demand / no stock",
            )
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")

        return EntryResult(
            logged=True,
            reply=f"📝 {event.drug_name} no-stock request logged",
            summary_line=f"{event.drug_name}",
            category="no_stock",
        )

    def _process_lost_opportunity(self, event: ParsedEvent) -> EntryResult:
        try:
            stock = self._resolve_stock(event.drug_name)
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")
        if stock is not None:
            event = replace(event, drug_name=stock.drug_name)

        try:
            self.store.append_daily_log(event, None, None)
            self._append_transaction(
                "not_sold",
                event.drug_name,
                event.quantity,
                note=event.notes or "Lost opportunity",
            )
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")

        return EntryResult(
            logged=True,
            reply=f"Logged lost opportunity: {event.drug_name}.",
            summary_line=f"{event.drug_name} lost opportunity",
            category="errors",
        )

    def _cash_summary_reply(self) -> str:
        report_date = now_in_timezone(self.timezone).date().isoformat()
        try:
            transactions = self.store.read_transactions(report_date)
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not prepare the cash summary right now. Please check the Google Sheets connection."

        payment_totals = {"Cash": 0.0, "M-Pesa": 0.0, "Card": 0.0, "Credit": 0.0}
        discount_total = 0.0
        total_sales = 0.0
        profit = 0.0
        for row in transactions:
            if normalize_key(row.get("Type")) not in {"sale", "late sale", "late_sale"}:
                continue
            note_meta = parse_note_metadata(str(row.get("Note") or ""))
            payment = note_meta.get("payment", "Cash")
            payment = "M-Pesa" if normalize_key(payment) in {"mpesa", "m pesa", "m-pesa"} else payment.title()
            payment_totals.setdefault(payment, 0.0)
            row_sales = parse_money(row.get("Total Sales")) or 0
            row_profit = parse_money(row.get("Profit")) or 0
            row_discount = parse_money(note_meta.get("discount")) or 0
            payment_totals[payment] += row_sales
            discount_total += row_discount
            total_sales += row_sales
            profit += row_profit

        return "\n".join(
            [
                "💰 Daily Cash Summary",
                "",
                f"Cash: {format_kes(payment_totals.get('Cash', 0))}",
                f"M-Pesa: {format_kes(payment_totals.get('M-Pesa', 0))}",
                f"Card: {format_kes(payment_totals.get('Card', 0))}",
                f"Credit: {format_kes(payment_totals.get('Credit', 0))}",
                f"Discounts: {format_kes(discount_total)}",
                f"Total Sales: {format_kes(total_sales)}",
                f"Profit: {format_kes(profit)}",
            ]
        )

    def _staff_summary_reply(self) -> str:
        report_date = now_in_timezone(self.timezone).date().isoformat()
        try:
            transactions = self.store.read_transactions(report_date)
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not prepare the staff summary right now. Please check the Google Sheets connection."

        staff_totals: dict[str, dict[str, float]] = {}
        for row in transactions:
            if normalize_key(row.get("Type")) not in {"sale", "late sale", "late_sale"}:
                continue
            note_meta = parse_note_metadata(str(row.get("Note") or ""))
            staff = note_meta.get("staff") or "Default"
            bucket = staff_totals.setdefault(staff, {"sales": 0.0, "profit": 0.0, "items": 0.0, "transactions": 0.0})
            bucket["sales"] += parse_money(row.get("Total Sales")) or 0
            bucket["profit"] += parse_money(row.get("Profit")) or 0
            bucket["items"] += parse_int(row.get("Quantity"), default=0) or 0
            bucket["transactions"] += 1
        if not staff_totals:
            return "Staff Summary\n\nNo sales recorded today yet."

        lines = ["Staff Summary", ""]
        for staff, totals in sorted(staff_totals.items()):
            lines.append(
                f"- {staff}: {format_kes(totals['sales'])}, profit {format_kes(totals['profit'])}, "
                f"{int(totals['items'])} items, {int(totals['transactions'])} transactions"
            )
        return "\n".join(lines)

    def _all_stock_items(self) -> list[StockItem]:
        items: list[StockItem] = []
        seen: set[str] = set()
        for name in self.store.list_master_drug_names():
            stock = self.store.find_stock(name)
            if stock is None:
                continue
            key = normalize_key(stock.drug_name)
            if key in seen:
                continue
            seen.add(key)
            items.append(stock)
        return items

    def _to_base_quantity(self, drug_name: str, quantity: int, unit: str) -> int:
        canonical = canonical_unit(unit)
        if not canonical:
            return to_base_quantity(quantity, unit)
        conversion = self.conversions_by_drug.get(normalize_key(drug_name))
        if not conversion:
            return to_base_quantity(quantity, unit)
        return max(int(quantity), 1) * conversion.get(canonical, 1)

    def _process_void_command(self, command: OperatingCommand, conversation_key: str) -> EntryResult:
        sale = self.last_sale_by_conversation.get(conversation_key)
        if sale is None:
            return EntryResult(
                logged=False,
                reply="No recent sale found to void.",
                summary_line="No recent sale found to void",
                category="errors",
            )
        reason = command.notes.strip()
        if not reason:
            self.pending_void_reason[conversation_key] = sale
            return EntryResult(
                logged=False,
                reply="Why are you voiding this sale?",
                summary_line="Void reason needed",
                category="errors",
            )
        reply = self._commit_void(sale, reason, conversation_key)
        return EntryResult(logged=True, reply=reply, summary_line="Void recorded", category="stock_checks")

    def _commit_void(self, sale: dict[str, Any], reason: str, conversation_key: str) -> str:
        drug_name = str(sale.get("drug_name") or "")
        quantity = parse_int(sale.get("quantity"), default=0) or 0
        original_trace_id = str(sale.get("trace_id") or "")
        void_trace_id = trace_id("VOID")
        try:
            stock = self._resolve_stock(drug_name)
            if stock and stock.current_stock is not None:
                self.store.update_current_stock(stock, stock.current_stock + quantity)
            self._append_transaction(
                "void",
                drug_name,
                quantity,
                note=build_note(
                    f"Void reason: {reason}",
                    trace_id=void_trace_id,
                    original_trace_id=original_trace_id,
                    voided="yes",
                ),
            )
        except Exception:
            return "I could not void the sale right now. Please check the connection."
        self.last_sale_by_conversation.pop(conversation_key, None)
        return "\n".join(
            [
                "✅ Sale voided",
                f"{drug_name} x{quantity}",
                f"Reason: {reason}",
                f"Trace: {void_trace_id}",
            ]
        )

    def _create_batch_if_supported(
        self,
        drug_name: str,
        quantity: int,
        command: OperatingCommand,
        restock_trace_id: str,
        unit: str,
        total_added_cost: float | None,
        selling_price: float | None,
    ) -> None:
        if not any([command.expiry_date, command.supplier, command.invoice_number, command.batch_number, command.barcode]):
            return
        try:
            from app.services.batch_service import BatchService

            BatchService(self.store).create_batch(
                {
                    "batch_id": command.batch_number or restock_trace_id,
                    "drug_name": drug_name,
                    "quantity_received": quantity,
                    "current_remaining_units": quantity,
                    "expiry_date": command.expiry_date,
                    "supplier_name": command.supplier,
                    "invoice_number": command.invoice_number,
                    "purchase_cost": total_added_cost,
                    "selling_price": selling_price,
                    "manufacturer_batch_number": command.batch_number,
                    "unit_received": unit or "unit",
                }
            )
        except Exception:
            return

    def _resolve_stock(self, drug_name: str) -> StockItem | None:
        stock = self.store.find_stock(drug_name)
        if stock is not None:
            return stock

        names = self.store.list_master_drug_names()
        normalized_to_name = {normalize_key(name): name for name in names if name.strip()}
        match = get_close_matches(normalize_key(drug_name), list(normalized_to_name.keys()), n=1, cutoff=0.72)
        if not match:
            return None
        return self.store.find_stock(normalized_to_name[match[0]])

    def _append_transaction(
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
    ) -> bool:
        append_transaction = getattr(self.store, "append_transaction", None)
        if append_transaction is None:
            return False
        try:
            append_transaction(
                transaction_type,
                drug_name,
                quantity,
                unit_cost=unit_cost,
                unit_selling_price=unit_selling_price,
                total_cost=total_cost,
                total_sales=total_sales,
                profit=profit,
                note=note,
            )
        except Exception:
            return False
        return True


def build_stock_update_plan(stock: StockItem, quantity: int) -> StockUpdatePlan:
    warning_notes: list[str] = []
    reply_warnings: list[str] = []

    if stock.current_stock is None:
        warning = "Stock level not updated because Current Stock is empty."
        warning_notes.append(warning)
        reply_warnings.append(warning)
        return StockUpdatePlan(None, warning_notes, reply_warnings)

    new_stock = max(stock.current_stock - quantity, 0)
    if stock.current_stock < quantity:
        warning = "Stock may be inaccurate. Sold quantity exceeded recorded stock."
        warning_notes.append(warning)
        reply_warnings.append(warning)

    if stock.reorder_level is not None and new_stock <= stock.reorder_level:
        reply_warnings.append(f"⚠️ LOW STOCK: {stock.drug_name} is at or below reorder level.")

    return StockUpdatePlan(new_stock, warning_notes, reply_warnings)


def unit_suffix(unit: str, quantity: int) -> str:
    canonical = canonical_unit(unit)
    if not canonical:
        return ""
    return f" {plural_unit(canonical, quantity)}"


def merge_notes(existing: str, extra_notes: list[str] | str) -> str:
    notes = [existing.strip()] if existing.strip() else []
    if isinstance(extra_notes, str):
        extra_notes = [extra_notes]
    notes.extend(note for note in extra_notes if note)
    return " ".join(notes)


def is_help_command(text: str) -> bool:
    normalized = normalize_key(text)
    return normalized in {
        "help",
        "start",
        "menu",
        "commands",
        "guide",
        "tutorial",
        "how do i use this",
        "how do i use phar mareen",
        "how do i use pharmareen",
        "what can you do",
    }


def is_greeting_command(text: str) -> bool:
    normalized = normalize_key(text)
    return normalized in {
        "hello",
        "hi",
        "hey",
        "habari",
        "morning",
        "good morning",
        "mambo",
        "sasa",
    }


def is_share_command(text: str) -> bool:
    return normalize_key(text) == "share"


def is_high_volume_question(text: str) -> bool:
    normalized = normalize_key(text)
    return any(
        phrase in normalized
        for phrase in (
            "will it get full",
            "is it full",
            "can it handle many customers",
            "many customers",
        )
    )


def is_customer_ordering_question(text: str) -> bool:
    normalized = normalize_key(text)
    return any(
        phrase in normalized
        for phrase in (
            "customer order",
            "client order",
            "ordering drugs",
            "order drugs for clients",
            "order for customer",
        )
    )


def is_process_batch_command(text: str) -> bool:
    return normalize_key(text) == "process batch"


def parse_conversion_command(text: str) -> tuple[str, int, int] | None:
    match = re.fullmatch(
        r"(.+?)\s+conversion\s+1\s+box\s+(\d+)\s+strips?\s+1\s+strip\s+(\d+)\s+tablets?",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return title_drug_name(match.group(1)), positive_quantity(match.group(2)), positive_quantity(match.group(3))


def parse_stock_check_command(text: str) -> str | None:
    normalized = " ".join(text.strip().lower().split())
    if "no stock" in normalized or "out of stock" in normalized:
        return None
    if re.fullmatch(r"stock\s+.+?\s+\d+", normalized, flags=re.IGNORECASE):
        return None
    if normalized in {"stock", "check stock", "remaining stock"}:
        return None
    natural = re.fullmatch(r"(?:remaining\s+stock|stock\s+remaining)\s+(?:for\s+)?(.+)\??", text.strip(), flags=re.IGNORECASE)
    if natural:
        return natural.group(1).strip() or None
    natural = re.fullmatch(r"(?:remaining|check)\s+(.+)\??", text.strip(), flags=re.IGNORECASE)
    if natural and normalize_key(natural.group(1)) != "stock":
        return natural.group(1).strip() or None
    natural = re.fullmatch(r"(?:what\s+is|what's|check)\s+(.+?)\s+stock\??", text.strip(), flags=re.IGNORECASE)
    if natural:
        return natural.group(1).strip() or None
    match = re.fullmatch(r"(.+?)\s+stock", text.strip(), flags=re.IGNORECASE)
    if not match:
        match = re.fullmatch(r"stock\s+(.+)", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    drug_name = match.group(1).strip()
    return drug_name or None


def is_profit_today_command(text: str) -> bool:
    normalized = normalize_key(text).replace("today's", "today")
    return bool(
        re.fullmatch(r"profit\s+today", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"how\s+much\s+profit\s+today\??", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"today\s+profit", normalized, flags=re.IGNORECASE)
    )


def is_cash_summary_command(text: str) -> bool:
    normalized = normalize_key(text)
    return bool(
        re.fullmatch(r"(?:cash\s+summary|daily\s+cash|payments\s+today|reconciliation\s+today)", normalized, flags=re.IGNORECASE)
    )


def is_staff_summary_command(text: str) -> bool:
    normalized = normalize_key(text)
    return bool(re.fullmatch(r"(?:staff\s+summary|cashier\s+summary|staff\s+today|cashiers?\s+today)", normalized, flags=re.IGNORECASE))


def is_low_stock_command(text: str) -> bool:
    normalized = normalize_key(text)
    return bool(re.fullmatch(r"(?:low\s+stock|show\s+low\s+stock|low\s+stock\s+items|what\s+is\s+low)", normalized, flags=re.IGNORECASE))


def is_stock_value_command(text: str) -> bool:
    normalized = normalize_key(text)
    return bool(re.fullmatch(r"(?:stock\s+value|inventory\s+value|value\s+of\s+stock|stock\s+valuation)", normalized, flags=re.IGNORECASE))


def parse_expiry_command(text: str) -> str | None:
    normalized = normalize_key(text)
    if re.fullmatch(r"(?:expiry|expiring|expiry\s+alerts?|expiring\s+soon)", normalized, flags=re.IGNORECASE):
        return ""
    match = re.fullmatch(r"(?:expiry|expiring|expiring\s+soon)\s+(.+)", text.strip(), flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.fullmatch(r"(.+?)\s+(?:expiry|expiring|expiry\s+status)", text.strip(), flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def parse_trace_command(text: str) -> str | None:
    match = re.fullmatch(r"(?:trace|history)\s+(.+)", text.strip(), flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.fullmatch(r"(.+?)\s+(?:trace|history)", text.strip(), flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def is_weekly_report_command(text: str) -> bool:
    normalized = normalize_key(text)
    return bool(
        re.fullmatch(r"(?:report\s+week|weekly\s+report)", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"show\s+me\s+(?:the\s+)?weekly\s+report", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"week(?:ly)?\s+summary", normalized, flags=re.IGNORECASE)
    )


def is_today_summary_command(text: str) -> bool:
    normalized = normalize_key(text).replace("today's", "today")
    return bool(
        re.fullmatch(r"(?:show\s+)?report(?:\s+today)?|daily\s+report", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"give\s+me\s+(?:today|today\s+report|the\s+daily\s+report)", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"(?:today\s+sales|today\s+report|summary\s+today|today\s+summary)", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"send\s+me\s+(?:the\s+)?daily\s+pdf", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"download\s+today\s+report", normalized, flags=re.IGNORECASE)
    )


def parse_report_command(text: str, timezone: str) -> str | None:
    match = re.fullmatch(
        r"(?:show\s+)?report(?:\s+(today|yesterday|\d{4}-\d{2}-\d{2}))?",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    target = (match.group(1) or "today").lower()
    today = now_in_timezone(timezone).date()
    if target == "today":
        return today.isoformat()
    if target == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    return target


def parse_followup_prompt(text: str) -> FollowUpPrompt | None:
    clean = normalize_natural_text(replace_number_words(text.strip()))
    clean = " ".join(clean.split())
    if not clean or any(separator in clean for separator in [",", "\n"]):
        return None
    if any(character.isdigit() for character in clean):
        return None

    sale_match = re.fullmatch(r"(?:i\s+)?(?:sell|sold|sale)\s+(.+)", clean, flags=re.IGNORECASE)
    if sale_match:
        drug_name = title_drug_name(sale_match.group(1))
        return FollowUpPrompt(
            OperatingCommand(kind="sale", drug_name=drug_name, quantity=0, raw_text=text),
            f"How many {drug_name} were sold?",
        )

    restock_match = re.fullmatch(r"(?:restock|restocked|add|received)\s+(.+)", clean, flags=re.IGNORECASE)
    if not restock_match:
        restock_match = re.fullmatch(r"(.+?)\s+(?:restock|restocked)", clean, flags=re.IGNORECASE)
    if restock_match:
        drug_name = title_drug_name(restock_match.group(1))
        if normalize_key(drug_name) == "stock":
            return FollowUpPrompt(
                OperatingCommand(kind="restock", drug_name="", quantity=0, raw_text=text),
                "Which medicine and how many units were added?\nExample: Panadol restock 20",
            )
        return FollowUpPrompt(
            OperatingCommand(kind="restock", drug_name=drug_name, quantity=0, raw_text=text),
            f"How many {drug_name} were added?",
        )

    if normalize_key(clean) in {"stock", "check stock", "remaining stock"}:
        return FollowUpPrompt(
            OperatingCommand(kind="stock_check", drug_name="", quantity=0, raw_text=text),
            "Which medicine should I check?\nExample: Panadol stock",
        )
    return None


def complete_followup_command(text: str, pending: OperatingCommand) -> OperatingCommand | None:
    clean = normalize_natural_text(replace_number_words(text.strip()))
    clean = " ".join(clean.split())
    if not clean:
        return None
    if pending.kind in {"sale", "restock"}:
        quantity = parse_int(clean, default=None)
        if quantity is not None and quantity > 0 and pending.drug_name:
            return replace(pending, quantity=quantity, raw_text=f"{pending.raw_text} {quantity}".strip())
        if not pending.drug_name:
            parsed = parse_single_operating_command(clean)
            return parsed if parsed and parsed.kind == pending.kind else None
    if pending.kind == "stock_check" and not any(character.isdigit() for character in clean):
        return replace(pending, drug_name=title_drug_name(clean), raw_text=f"{clean} stock")
    return None


def parse_operating_commands(text: str) -> list[OperatingCommand] | None:
    clean_text = normalize_natural_text(replace_number_words(text.strip()))
    if not clean_text:
        return None

    natural_bulk = parse_natural_bulk_commands(clean_text)
    if natural_bulk is not None:
        return natural_bulk

    if "\n" in clean_text:
        return [
            parse_single_operating_command(line.strip())
            or OperatingCommand(kind="error", raw_text=line.strip())
            for line in clean_text.splitlines()
            if line.strip()
        ]

    if "," in clean_text:
        complex_restock = parse_complex_restock_command(clean_text, clean_text)
        if complex_restock is not None:
            return [complex_restock]
        commands: list[OperatingCommand] = []
        for part in clean_text.split(","):
            part = part.strip()
            if not part:
                continue
            commands.append(
                parse_single_operating_command(part)
                or OperatingCommand(kind="error", raw_text=part)
            )
        return commands if commands else None

    command = parse_single_operating_command(clean_text)
    return [command] if command is not None else None


def parse_natural_bulk_commands(text: str) -> list[OperatingCommand] | None:
    late_sale_match = re.fullmatch(
        r"(?:later|late|missed|i\s+missed)\s+(.+)",
        text.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if late_sale_match and "," in late_sale_match.group(1):
        return parse_drug_quantity_list(late_sale_match.group(1), kind="late_sale")

    sale_match = re.fullmatch(r"(?:i\s+)?sold\s+(.+)", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if sale_match and ("," in sale_match.group(1)):
        return parse_drug_quantity_list(sale_match.group(1), kind="sale")

    restock_match = re.fullmatch(r"restocked\s+(.+)", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if restock_match and "," in restock_match.group(1):
        return parse_drug_quantity_list(restock_match.group(1), kind="restock")

    no_stock_match = re.fullmatch(r"no\s+stock\s+(.+)", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    if no_stock_match and "," in no_stock_match.group(1):
        commands = []
        for drug_name in no_stock_match.group(1).split(","):
            drug_name = drug_name.strip()
            if drug_name:
                commands.append(OperatingCommand(kind="no_stock", drug_name=title_drug_name(drug_name), raw_text=drug_name))
        return commands if commands else None
    return None


def parse_drug_quantity_list(text: str, kind: str) -> list[OperatingCommand]:
    commands: list[OperatingCommand] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(.+?)\s+(\d+)", part)
        if not match:
            commands.append(OperatingCommand(kind="error", raw_text=part))
            continue
        commands.append(
            OperatingCommand(
                kind=kind,
                drug_name=title_drug_name(match.group(1)),
                quantity=positive_quantity(match.group(2)),
                raw_text=part,
            )
        )
    return commands


def parse_restock_details(cost_text: str | None, modifier: str | None = None) -> tuple[float | None, str]:
    restock_type = "normal"
    modifier_text = str(modifier or "").strip().lower()
    if modifier_text == "bonus":
        return 0, "bonus"
    if modifier_text in {"disc", "discount", "discounted"}:
        restock_type = "discount"
    return parse_money(cost_text), restock_type


def extract_restock_metadata(clean: str) -> tuple[str, str, str]:
    supplier = ""
    expiry_date = ""
    supplier_match = re.search(r"\bsupplier\s+(.+?)(?=\s+expiry\b|\s+exp\b|$)", clean, flags=re.IGNORECASE)
    if supplier_match:
        supplier = supplier_match.group(1).strip(" ,")
    expiry_match = re.search(r"\b(?:expiry|expires?|exp)\s+(.+)$", clean, flags=re.IGNORECASE)
    if expiry_match:
        expiry_date = expiry_match.group(1).strip(" ,")
    cleaned = re.sub(r"\s+supplier\s+.+?(?=\s+expiry\b|\s+exp\b|$)", "", clean, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:expiry|expires?|exp)\s+.+$", "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()), supplier, expiry_date


def make_restock_command(
    *,
    drug_name: str,
    ordered_quantity: int,
    bonus_quantity: int = 0,
    actual_paid_amount: float | None = None,
    expected_total_cost: float | None = None,
    discount_amount: float | None = None,
    restock_type: str | None = None,
    supplier: str = "",
    expiry_date: str = "",
    raw_text: str = "",
    notes: str = "",
) -> OperatingCommand:
    bonus_quantity = max(int(bonus_quantity or 0), 0)
    ordered_quantity = positive_quantity(ordered_quantity)
    discount_value = parse_money(discount_amount) or 0
    expected_value = parse_money(expected_total_cost)
    paid_value = parse_money(actual_paid_amount)
    if paid_value is None and expected_value is not None and discount_value:
        paid_value = max(expected_value - discount_value, 0)
    total_received = ordered_quantity + bonus_quantity
    if restock_type is None:
        if bonus_quantity and discount_value:
            restock_type = "bonus_discount"
        elif bonus_quantity:
            restock_type = "bonus"
        elif discount_value:
            restock_type = "discount"
        else:
            restock_type = "normal"
    total_cost = 0 if restock_type == "bonus" and paid_value is None else paid_value
    return OperatingCommand(
        kind="restock",
        drug_name=title_drug_name(drug_name),
        quantity=total_received,
        total_cost=total_cost,
        budgeted_cost=expected_value,
        restock_type=restock_type,
        ordered_quantity=ordered_quantity,
        bonus_quantity=bonus_quantity,
        expected_total_cost=expected_value,
        discount_amount=discount_value,
        actual_paid_amount=paid_value,
        supplier=supplier,
        expiry_date=expiry_date,
        notes=notes,
        raw_text=raw_text,
    )


def parse_complex_restock_command(clean: str, raw_text: str) -> OperatingCommand | None:
    detail_clean, supplier, expiry_date = extract_restock_metadata(clean)

    match = re.fullmatch(r"supplier\s+gave\s+(.+?)\s+(\d+),?\s+bonus\s+(\d+)", detail_clean, flags=re.IGNORECASE)
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            bonus_quantity=positive_quantity(match.group(3)),
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

    match = re.fullmatch(r"bought\s+(.+?)\s+(\d+),?\s+paid\s+for\s+(\d+),?\s+bonus\s+(\d+)", detail_clean, flags=re.IGNORECASE)
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            bonus_quantity=positive_quantity(match.group(4)),
            supplier=supplier,
            expiry_date=expiry_date,
            notes=f"Paid for {positive_quantity(match.group(3))} units.",
            raw_text=raw_text,
        )

    match = re.fullmatch(r"(.+?)\s+bought\s+(\d+)\s+plus\s+(\d+)\s+bonus", detail_clean, flags=re.IGNORECASE)
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            bonus_quantity=positive_quantity(match.group(3)),
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

    match = re.fullmatch(
        r"(.+?)\s+(?:restock|restocked|received|bought)\s+(\d+)\s+(?:plus\s+)?bonus\s+(\d+)(?:\s+(?:cost|paid)\s+(\d+(?:\.\d+)?))?(?:\s+discount\s+(\d+(?:\.\d+)?))?",
        detail_clean,
        flags=re.IGNORECASE,
    )
    if match:
        paid_value = parse_money(match.group(4))
        discount_value = parse_money(match.group(5)) or 0
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            bonus_quantity=positive_quantity(match.group(3)),
            actual_paid_amount=paid_value,
            discount_amount=discount_value,
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

    match = re.fullmatch(
        r"(.+?)\s+(?:received|restock|restocked|bought)\s+(\d+)\s+paid\s+(\d+(?:\.\d+)?)(?:\s+discount\s+(\d+(?:\.\d+)?))?",
        detail_clean,
        flags=re.IGNORECASE,
    )
    if match:
        discount_value = parse_money(match.group(4)) or 0
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            actual_paid_amount=parse_money(match.group(3)),
            discount_amount=discount_value,
            restock_type="discount" if discount_value else "normal",
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

    match = re.fullmatch(
        r"(.+?)\s+(?:restock|restocked|received|bought)\s+(\d+)\s+(?:cost|paid)\s+(\d+(?:\.\d+)?)",
        detail_clean,
        flags=re.IGNORECASE,
    )
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            actual_paid_amount=parse_money(match.group(3)),
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

    match = re.fullmatch(r"(.+?)\s+\+(\d+)", detail_clean, flags=re.IGNORECASE)
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

    if supplier or expiry_date:
        match = re.fullmatch(r"(.+?)\s+(?:restock|restocked|received|bought)\s+(\d+)", detail_clean, flags=re.IGNORECASE)
        if match:
            return make_restock_command(
                drug_name=match.group(1),
                ordered_quantity=positive_quantity(match.group(2)),
                supplier=supplier,
                expiry_date=expiry_date,
                raw_text=raw_text,
            )

    return None


def enrich_command_metadata(command: OperatingCommand, raw_text: str) -> OperatingCommand:
    modifiers = parse_trace_modifiers(raw_text)
    return replace(
        command,
        payment_method=command.payment_method or modifiers.payment_method,
        discount=command.discount or modifiers.discount,
        supplier=command.supplier or modifiers.supplier,
        expiry_date=command.expiry_date or modifiers.expiry_date,
        invoice_number=command.invoice_number or modifiers.invoice_number,
        batch_number=command.batch_number or modifiers.batch_number,
        barcode=command.barcode or modifiers.barcode,
    )


def parse_engine_restock_command(clean: str, raw_text: str) -> OperatingCommand | None:
    unit_re = unit_pattern()
    clean_without_modifiers = strip_modifier_phrases(clean)
    patterns = [
        rf"^\+(.+?)\s+(\d+)\s+({unit_re})(?:\s|$)",
        rf"^(.+?)\s+\+(\d+)\s+({unit_re})(?:\s|$)",
        rf"^(?:restock|restocked|add|received|stock)\s+(.+?)\s+(\d+)\s+({unit_re})(?:\s|$)",
        rf"^(.+?)\s+(?:restock|restocked|received|bought)\s+(\d+)\s+({unit_re})(?:\s|$)",
    ]
    for pattern in patterns:
        match = re.match(pattern, clean_without_modifiers, flags=re.IGNORECASE)
        if not match:
            continue
        drug_name = title_drug_name(match.group(1))
        quantity = positive_quantity(match.group(2))
        unit = canonical_unit(match.group(3))
        modifiers = parse_trace_modifiers(clean)
        total_cost = extract_labeled_money(clean, ["cost", "paid", "for"])
        command = OperatingCommand(
            kind="restock",
            drug_name=drug_name,
            quantity=quantity,
            base_quantity=to_base_quantity(quantity, unit),
            total_cost=total_cost,
            unit=unit,
            supplier=modifiers.supplier,
            expiry_date=modifiers.expiry_date,
            invoice_number=modifiers.invoice_number,
            batch_number=modifiers.batch_number,
            barcode=modifiers.barcode,
            raw_text=raw_text,
        )
        return command
    return None


def parse_engine_sale_command(clean: str, raw_text: str) -> OperatingCommand | None:
    if clean.startswith("+"):
        return None
    unit_re = unit_pattern()
    clean_without_modifiers = strip_modifier_phrases(clean)
    patterns = [
        rf"^(?:i\s+)?(?:sold|sell|sale)\s+(\d+)\s+({unit_re})\s+(.+)$",
        rf"^(?:i\s+)?(?:sold|sell|sale)\s+(\d+)\s+(.+?)(?:\s+({unit_re}))?$",
        rf"^(?:i\s+)?(?:sold|sell|sale)\s+(.+?)\s+(\d+)(?:\s+({unit_re}))?$",
        rf"^(.+?)\s+(\d+)\s+({unit_re})$",
        r"^(.+?)\s+x?(\d+)$",
    ]
    for index, pattern in enumerate(patterns):
        match = re.fullmatch(pattern, clean_without_modifiers, flags=re.IGNORECASE)
        if not match:
            continue
        if index == 0:
            quantity = positive_quantity(match.group(1))
            unit = canonical_unit(match.group(2))
            drug_name = title_drug_name(match.group(3))
        elif index == 1:
            quantity = positive_quantity(match.group(1))
            drug_name = title_drug_name(match.group(2))
            unit = canonical_unit(match.group(3) or "")
        else:
            drug_name = title_drug_name(match.group(1))
            quantity = positive_quantity(match.group(2))
            unit = canonical_unit(match.group(3) if match.lastindex and match.lastindex >= 3 else "")
        if not drug_name:
            continue
        modifiers = parse_trace_modifiers(clean)
        return OperatingCommand(
            kind="sale",
            drug_name=drug_name,
            quantity=quantity,
            unit=unit,
            base_quantity=to_base_quantity(quantity, unit),
            payment_method=modifiers.payment_method,
            discount=modifiers.discount,
            supplier=modifiers.supplier,
            invoice_number=modifiers.invoice_number,
            batch_number=modifiers.batch_number,
            barcode=modifiers.barcode,
            raw_text=raw_text,
        )
    return None


def extract_labeled_money(text: str, labels: list[str]) -> float | None:
    for label in labels:
        match = re.search(rf"\b{re.escape(label)}\s+(\d+(?:\.\d+)?)\b", text, flags=re.IGNORECASE)
        if match:
            return parse_money(match.group(1))
    return None


def parse_shortcut_command(clean: str, raw_text: str) -> OperatingCommand | None:
    normalized = normalize_key(clean)
    match = re.fullmatch(r"stock\s+([a-z]+)", normalized, flags=re.IGNORECASE)
    if match and match.group(1) in SHORTCUT_DRUGS:
        return OperatingCommand(kind="stock_check", drug_name=SHORTCUT_DRUGS[match.group(1)], raw_text=raw_text)

    match = re.fullmatch(r"([a-z]+)\s*\+\s*(\d+)", normalized, flags=re.IGNORECASE)
    if match and match.group(1) in SHORTCUT_DRUGS:
        return OperatingCommand(
            kind="restock",
            drug_name=SHORTCUT_DRUGS[match.group(1)],
            quantity=positive_quantity(match.group(2)),
            raw_text=raw_text,
        )

    match = re.fullmatch(r"([a-z]+)\s*x?\s*(\d+)", normalized, flags=re.IGNORECASE)
    if match and match.group(1) in SHORTCUT_DRUGS:
        return OperatingCommand(
            kind="sale",
            drug_name=SHORTCUT_DRUGS[match.group(1)],
            quantity=positive_quantity(match.group(2)),
            raw_text=raw_text,
        )
    return None


def parse_single_operating_command(text: str) -> OperatingCommand | None:
    clean = " ".join(text.strip().split())
    if not clean:
        return None

    shortcut = parse_shortcut_command(clean, text)
    if shortcut is not None:
        return shortcut

    staff_name = parse_staff_name(clean)
    if staff_name:
        return OperatingCommand(kind="set_staff", staff_name=staff_name, raw_text=text)

    void_match = re.fullmatch(r"(?:void|undo|correct)\s+(?:last|sale(?:\s+([A-Za-z0-9_-]+))?)(?:\s+(.+))?", clean, flags=re.IGNORECASE)
    if void_match:
        return OperatingCommand(kind="void", trace_id=void_match.group(1) or "", notes=void_match.group(2) or "", raw_text=text)

    stock_name = parse_stock_check_command(clean)
    if stock_name:
        return OperatingCommand(kind="stock_check", drug_name=title_drug_name(stock_name), raw_text=text)

    engine_restock = parse_engine_restock_command(clean, text)
    if engine_restock is not None:
        return engine_restock

    complex_restock = parse_complex_restock_command(clean, text)
    if complex_restock is not None:
        return enrich_command_metadata(complex_restock, text)

    match = re.fullmatch(r"(?:bonus|free|extra)\s+(.+?)\s+(\d+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=0,
            restock_type="bonus",
            raw_text=text,
        )

    match = re.fullmatch(r"(?:bonus|free|extra)\s+(\d+)\s+(.+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(2)),
            quantity=positive_quantity(match.group(1)),
            total_cost=0,
            restock_type="bonus",
            raw_text=text,
        )

    match = re.fullmatch(r"(\d+)\s+(.+?)\s+(?:bonus|free|extra)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(2)),
            quantity=positive_quantity(match.group(1)),
            total_cost=0,
            restock_type="bonus",
            raw_text=text,
        )

    match = re.fullmatch(r"(.+?)\s+(\d+)\s+(?:bonus|free|extra)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=0,
            restock_type="bonus",
            raw_text=text,
        )

    match = re.fullmatch(
        r"\+(.+?)\s+(\d+)\s+ordered\s+(\d+(?:\.\d+)?)\s+paid\s+(\d+(?:\.\d+)?)(?:\s+(disc|discount|discounted))?",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            budgeted_cost=parse_money(match.group(3)),
            total_cost=parse_money(match.group(4)),
            restock_type="discount",
            raw_text=text,
        )

    match = re.fullmatch(
        r"\+(.+?)\s+(\d+)\s+(?:cost|paid)\s+(\d+(?:\.\d+)?)(?:\s+(disc|discount|discounted))?",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        total_cost, restock_type = parse_restock_details(match.group(3), match.group(4))
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=total_cost,
            restock_type=restock_type,
            raw_text=text,
        )

    match = re.fullmatch(
        r"\+(.+?)\s+(\d+)(?:\s+(\d+(?:\.\d+)?))?(?:\s+(bonus|disc|discount|discounted))?",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        total_cost, restock_type = parse_restock_details(match.group(3), match.group(4))
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=total_cost,
            restock_type=restock_type,
            raw_text=text,
        )

    match = re.fullmatch(
        r"(?:received|stock|add|restock|restocked)\s+(.+?)\s+(\d+)\s+ordered\s+(\d+(?:\.\d+)?)\s+paid\s+(\d+(?:\.\d+)?)",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            budgeted_cost=parse_money(match.group(3)),
            total_cost=parse_money(match.group(4)),
            restock_type="discount",
            raw_text=text,
        )

    match = re.fullmatch(
        r"(?:bought|received)\s+(.+?)\s+(\d+)\s+(?:for|paid|cost)\s+(\d+(?:\.\d+)?)",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=parse_money(match.group(3)),
            raw_text=text,
        )

    match = re.fullmatch(
        r"(?:bought|received)\s+(\d+)\s+(.+?)\s+(?:for|paid|cost)\s+(\d+(?:\.\d+)?)",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(2)),
            quantity=positive_quantity(match.group(1)),
            total_cost=parse_money(match.group(3)),
            raw_text=text,
        )

    match = re.fullmatch(r"(?:add|received|stock|restock|restocked)\s+(\d+)\s+(.+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(2)),
            quantity=positive_quantity(match.group(1)),
            raw_text=text,
        )

    match = re.fullmatch(r"(.+?)\s+(\d+)\s+paid\s+(\d+(?:\.\d+)?)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=parse_money(match.group(3)),
            raw_text=text,
        )

    match = re.fullmatch(r"(?:later|late|missed|i\s+missed)\s+(.+?)\s+(\d+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="late_sale",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            raw_text=text,
        )

    match = re.fullmatch(
        r"(.+?)\s+(?:restock|restocked)\s+(\d+)(?:\s+(\d+(?:\.\d+)?))?(?:\s+(bonus|disc|discount|discounted))?",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        total_cost, restock_type = parse_restock_details(match.group(3), match.group(4))
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=total_cost,
            restock_type=restock_type,
            raw_text=text,
        )

    match = re.fullmatch(
        r"(?:add|received|stock|restock|restocked)\s+(.+?)\s+(\d+)(?:\s+(?:for\s+)?(\d+(?:\.\d+)?))?(?:\s+(bonus|disc|discount|discounted))?",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        total_cost, restock_type = parse_restock_details(match.group(3), match.group(4))
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=total_cost,
            restock_type=restock_type,
            raw_text=text,
        )

    match = re.fullmatch(r"(.+?)\s+(?:is\s+)?(?:no\s+stock|out\s+of\s+stock|not\s+available)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(kind="no_stock", drug_name=title_drug_name(match.group(1)), raw_text=text)

    match = re.fullmatch(r"no\s+stock\s+(.+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(kind="no_stock", drug_name=title_drug_name(match.group(1)), raw_text=text)

    engine_sale = parse_engine_sale_command(clean, text)
    if engine_sale is not None:
        return engine_sale

    match = re.fullmatch(r"(.+?)\s+sold\s+(\d+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="sale",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            raw_text=text,
        )

    match = re.fullmatch(r"(.+?)\s+sold", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="sale",
            drug_name=title_drug_name(match.group(1)),
            quantity=1,
            raw_text=text,
        )

    match = re.fullmatch(r"(?:i\s+)?(?:sold|sell|sale)\s+(\d+)\s+(.+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="sale",
            drug_name=title_drug_name(match.group(2)),
            quantity=positive_quantity(match.group(1)),
            raw_text=text,
        )

    match = re.fullmatch(r"(?:i\s+)?(?:sold|sell|sale)\s+(.+?)\s+(\d+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="sale",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            raw_text=text,
        )

    match = re.fullmatch(r"(.+?)\s+x?(\d+)", clean, flags=re.IGNORECASE)
    if match and not clean.startswith("+"):
        return OperatingCommand(
            kind="sale",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            raw_text=text,
        )

    return None


def positive_quantity(value: Any) -> int:
    quantity = parse_int(value, default=1) or 1
    return quantity if quantity > 0 else 1


def title_drug_name(value: str) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return text
    if any(character.isupper() for character in text[1:]):
        return text
    return text.title()


def replace_number_words(text: str) -> str:
    words = sorted(NUMBER_WORDS, key=len, reverse=True)
    number_pattern = "|".join(re.escape(word) for word in words)
    phrase_pattern = rf"\b(?:{number_pattern})(?:[\s-]+(?:and\s+)?(?:{number_pattern}))*\b"

    def replace_match(match: re.Match[str]) -> str:
        number = parse_number_phrase(match.group(0))
        return str(number) if number is not None else match.group(0)

    return re.sub(phrase_pattern, replace_match, text, flags=re.IGNORECASE)


def parse_number_phrase(phrase: str) -> int | None:
    tokens = re.split(r"[\s-]+", phrase.lower().strip())
    total = 0
    current = 0
    found = False
    for token in tokens:
        if token == "and":
            continue
        if token not in NUMBER_WORDS:
            return None
        found = True
        value = NUMBER_WORDS[token]
        if token == "hundred":
            current = max(current, 1) * value
        elif token == "thousand":
            total += max(current, 1) * value
            current = 0
        else:
            current += value
    if not found:
        return None
    return total + current


def normalize_spoken_command_text(text: str) -> str:
    clean = normalize_natural_text(replace_number_words(text))
    single_line = " ".join(clean.replace(",", " ").split())

    match = re.fullmatch(r"(?:sold|sell|sale)\s+(\d+)\s+(.+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"{title_drug_name(match.group(2))} {positive_quantity(match.group(1))}"

    match = re.fullmatch(r"(?:sell|sale)\s+(.+?)\s+(\d+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"{title_drug_name(match.group(1))} {positive_quantity(match.group(2))}"

    match = re.fullmatch(
        r"ordered\s+(\d+)\s+(.+?)\s+budget\s+(\d+(?:\.\d+)?)\s+paid\s+(\d+(?:\.\d+)?)",
        single_line,
        flags=re.IGNORECASE,
    )
    if match:
        return (
            f"+{title_drug_name(match.group(2))} {positive_quantity(match.group(1))} "
            f"ordered {format_plain_number(parse_money(match.group(3)))} "
            f"paid {format_plain_number(parse_money(match.group(4)))}"
        )

    match = re.fullmatch(
        r"add\s+(.+?)\s+(\d+)\s+ordered\s+(\d+(?:\.\d+)?)\s+paid\s+(\d+(?:\.\d+)?)",
        single_line,
        flags=re.IGNORECASE,
    )
    if match:
        return (
            f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} "
            f"ordered {format_plain_number(parse_money(match.group(3)))} "
            f"paid {format_plain_number(parse_money(match.group(4)))}"
        )

    match = re.fullmatch(
        r"add\s+(.+?)\s+(\d+)\s+paid\s+(\d+(?:\.\d+)?)",
        single_line,
        flags=re.IGNORECASE,
    )
    if match:
        return (
            f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} "
            f"{format_plain_number(parse_money(match.group(3)))}"
        )

    match = re.fullmatch(
        r"(?:bought|received)\s+(\d+)\s+(.+?)\s+(?:for|paid|cost)\s+(\d+(?:\.\d+)?)",
        single_line,
        flags=re.IGNORECASE,
    )
    if match:
        return (
            f"+{title_drug_name(match.group(2))} {positive_quantity(match.group(1))} "
            f"{format_plain_number(parse_money(match.group(3)))}"
        )

    match = re.fullmatch(r"add\s+(.+?)\s+(\d+)\s+bonus", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} bonus"

    match = re.fullmatch(r"(?:bonus|free|extra)\s+(.+?)\s+(\d+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} bonus"

    match = re.fullmatch(r"(?:bonus|free|extra)\s+(\d+)\s+(.+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(2))} {positive_quantity(match.group(1))} bonus"

    match = re.fullmatch(r"(\d+)\s+(.+?)\s+(?:bonus|free|extra)", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(2))} {positive_quantity(match.group(1))} bonus"

    match = re.fullmatch(r"(.+?)\s+(\d+)\s+(?:bonus|free|extra)", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} bonus"

    match = re.fullmatch(r"(?:add|received)\s+(\d+)\s+(.+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(2))} {positive_quantity(match.group(1))}"

    match = re.fullmatch(
        r"(.+?)\s+(\d+)\s+paid\s+(\d+(?:\.\d+)?)",
        single_line,
        flags=re.IGNORECASE,
    )
    if match:
        return (
            f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} "
            f"{format_plain_number(parse_money(match.group(3)))}"
        )

    match = re.fullmatch(r"add\s+(.+?)\s+(\d+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))}"

    return clean


def format_plain_number(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 0.005:
        return str(int(round(value)))
    return str(value)


def normalize_natural_text(text: str) -> str:
    clean = "\n".join(" ".join(line.split()) for line in text.strip().splitlines())
    clean = re.sub(r"^please\s+", "", clean, flags=re.IGNORECASE)
    if "\n" not in clean and re.match(r"^(?:i\s+sold|sold|restocked|no\s+stock)\b", clean, flags=re.IGNORECASE):
        clean = re.sub(r"\s+and\s+", ", ", clean, flags=re.IGNORECASE)
    return clean


def format_kes(amount: float | int | None) -> str:
    amount = float(amount or 0)
    if abs(amount - round(amount)) < 0.005:
        return f"KES {int(round(amount)):,}"
    return f"KES {amount:,.2f}"


def clean_app_base_url(value: str | None) -> str:
    text = str(value or "").strip().rstrip("/")
    lower = text.lower()
    if not text or "your-" in lower or "example.com" in lower:
        return "http://localhost:5000"
    return text


def clean_whatsapp_number(value: str | None) -> str:
    text = str(value or "").replace("whatsapp:", "").strip()
    return re.sub(r"\D", "", text)


def calculate_average_cost(
    current_stock: int,
    current_cost: float | None,
    added_quantity: int,
    total_added_cost: float | None,
) -> float | None:
    if total_added_cost is None or added_quantity <= 0:
        return current_cost
    if current_stock <= 0 or current_cost is None:
        return total_added_cost / added_quantity
    return ((current_stock * current_cost) + total_added_cost) / (current_stock + added_quantity)


def build_transaction_metrics(
    report_date: str,
    transactions: list[dict[str, Any]],
    low_stock_warnings,
) -> ReportMetrics:
    total_sales = 0.0
    total_cost = 0.0
    gross_profit = 0.0
    total_items_sold = 0
    sale_transactions = 0
    sold_counter: Counter[str] = Counter()
    requested_counter: Counter[str] = Counter()
    missed_counter: Counter[str] = Counter()
    restock_counter: Counter[str] = Counter()
    not_sold_counter: Counter[str] = Counter()
    missing_profit_data = False
    late_sale_transactions = 0
    peak_blocks: dict[int, dict[str, int]] = {}

    for row in transactions:
        drug_name = str(row.get("Drug") or "").strip()
        if not drug_name:
            continue
        transaction_type = normalize_key(row.get("Type"))
        quantity = parse_int(row.get("Quantity"), default=1) or 1

        if transaction_type in {"sale", "late sale", "late_sale"}:
            sale_transactions += 1
            if transaction_type in {"late sale", "late_sale"}:
                late_sale_transactions += 1
            total_items_sold += quantity
            sold_counter[drug_name] += quantity
            requested_counter[drug_name] += quantity
            block = two_hour_block_from_timestamp(row.get("Timestamp"))
            if block is not None:
                peak_blocks.setdefault(block, {"transactions": 0, "items": 0})
                peak_blocks[block]["transactions"] += 1
                peak_blocks[block]["items"] += quantity
            row_sales = parse_money(row.get("Total Sales"))
            row_cost = parse_money(row.get("Total Cost"))
            row_profit = parse_money(row.get("Profit"))
            if row_sales is None or row_cost is None or row_profit is None:
                missing_profit_data = True
            total_sales += row_sales or 0
            total_cost += row_cost or 0
            gross_profit += row_profit or 0
        elif transaction_type == "restock":
            restock_counter[drug_name] += quantity
        elif transaction_type in {"no stock", "no_stock", "out of stock"}:
            missed_counter[drug_name] += quantity
            requested_counter[drug_name] += quantity
        elif transaction_type in {"not sold", "not_sold"}:
            not_sold_counter[drug_name] += quantity
            requested_counter[drug_name] += quantity

    peak_time, peak_sales_count, peak_items_sold = summarize_peak_block(peak_blocks)
    return ReportMetrics(
        report_date=report_date,
        total_sales=total_sales,
        total_items_sold=total_items_sold,
        sale_transactions=sale_transactions,
        most_requested=top_pairs(requested_counter, limit=5),
        most_sold=top_pairs(sold_counter, limit=5),
        missed_sales=top_pairs(missed_counter, limit=5),
        not_sold=top_pairs(not_sold_counter, limit=5),
        low_stock_warnings=low_stock_warnings or [],
        peak_activity_time=peak_time,
        total_cost=total_cost,
        gross_profit=gross_profit,
        restocks=top_pairs(restock_counter, limit=5),
        missing_profit_data=missing_profit_data,
        late_sale_transactions=late_sale_transactions,
        peak_sales_count=peak_sales_count,
        peak_items_sold=peak_items_sold,
    )


def two_hour_block_from_timestamp(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace(" ", "T"))
    except ValueError:
        time_text = text.split(" ", maxsplit=1)[-1]
        try:
            hour = int(time_text.split(":", maxsplit=1)[0])
        except ValueError:
            return None
    else:
        hour = parsed.hour
    return (hour // 2) * 2 if 0 <= hour <= 23 else None


def summarize_peak_block(blocks: dict[int, dict[str, int]]) -> tuple[str, int, int]:
    if not blocks:
        return "Not enough data yet", 0, 0
    block, counts = sorted(
        blocks.items(),
        key=lambda item: (-item[1]["transactions"], -item[1]["items"], item[0]),
    )[0]
    return format_two_hour_block(block), counts["transactions"], counts["items"]


def format_two_hour_block(start_hour: int) -> str:
    return f"{format_hour_label(start_hour)} - {format_hour_label((start_hour + 2) % 24)}"


def format_hour_label(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    value = hour % 12
    if value == 0:
        value = 12
    return f"{value}{suffix}"


def render_whatsapp_report(metrics: ReportMetrics, report_type: str) -> str:
    title = "📅 Weekly Report" if report_type == "weekly" else "📊 Daily Report"
    best_seller = metrics.most_sold[0][0] if metrics.most_sold else "None"
    low_stock = ", ".join(item.drug_name for item in metrics.low_stock_warnings) or "None"
    return "\n".join(
        [
            title,
            "",
            f"Sales: {format_kes(metrics.total_sales)}",
            f"Cost: {format_kes(metrics.total_cost)}",
            f"Profit: {format_kes(metrics.gross_profit)}",
            f"Items Sold: {metrics.total_items_sold}",
            f"Transactions: {metrics.sale_transactions}",
            f"Best Seller: {best_seller}",
            f"Peak Time: {metrics.peak_activity_time}",
            f"Low Stock: {low_stock}",
        ]
    )


def append_pdf_instruction(report_text: str, pdf_link: str, can_attach: bool) -> str:
    if can_attach:
        return f"{report_text}\n\n📎 PDF report attached below.\n{pdf_link}"
    return f"{report_text}\n\n📄 PDF report:\nTap here to download: {pdf_link}"


def ensure_report_has_pharmacy_name(report_text: str, pharmacy_name: str) -> str:
    clean_report = report_text.strip()
    first_line = clean_report.splitlines()[0].strip() if clean_report else ""
    if first_line.startswith("Zilla Pharmacy"):
        clean_report = clean_report.replace("Zilla Pharmacy", pharmacy_name, 1)
        first_line = clean_report.splitlines()[0].strip() if clean_report else ""
    if first_line == pharmacy_name or first_line.startswith(f"{pharmacy_name} "):
        return clean_report
    return f"{pharmacy_name}\n{clean_report}"


def compact_low_stock(items) -> str:
    if not items:
        return "None."
    return ", ".join(
        f"{item.drug_name} ({item.current_stock})"
        for item in items
    )
