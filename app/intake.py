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
from app.sheets import SHEETS_UNAVAILABLE_MESSAGE, SheetsUnavailableError
from app.utils import format_ksh, normalize_key, now_in_timezone, parse_int, parse_money


UNDERSTAND_ERROR = "I didn’t understand that yet.\n\nTry:\nPanadol 2\n+Panadol 20\nreport today"
SAVE_ERROR = "I could not save this record right now. Please check the Google Sheets connection."
HELP_TEXT = "\n".join(
    [
        "👋 PharMareen Quick Commands",
        "",
        "Sell:",
        "Panadol 2",
        "Panadol two",
        "",
        "Restock:",
        "+Panadol 20",
        "add Panadol 20",
        "",
        "Bonus/free stock:",
        "bonus Panadol 5",
        "+Panadol 5 bonus",
        "",
        "Discount / paid less:",
        "+Panadol 20 paid 1800",
        "+Panadol 20 ordered 2000 paid 1800",
        "",
        "Check:",
        "Panadol stock",
        "",
        "Reports:",
        "profit today",
        "report today",
        "report week",
        "",
        "Voice:",
        'Say: "Panadol two"',
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
    raw_text: str = ""
    error: str = ""


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

    def process_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "Please send a short text message or voice note."

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

        if is_profit_today_command(text):
            return self._profit_today_reply()

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
            return self._process_commands(commands)

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
        if metrics.missing_profit_data:
            lines.append("")
            lines.append("⚠️ Some items had missing price data, so profit may be incomplete.")
        return append_pdf_instruction("\n".join(lines), pdf_link, self.can_attach_pdf())

    def _public_pdf_link(self, pdf_path) -> str:
        return f"{self.app_base_url}/reports/download/{pdf_path.name}"

    def can_attach_pdf(self) -> bool:
        lower = self.app_base_url.lower()
        return lower.startswith("https://") and "localhost" not in lower and "127.0.0.1" not in lower

    def _process_commands(self, commands: list[OperatingCommand]) -> str:
        results = [self._process_command(command) for command in commands]
        if len(results) == 1 and results[0].category != "errors":
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

    def _process_command(self, command: OperatingCommand) -> EntryResult:
        if command.kind == "error":
            return EntryResult(
                logged=False,
            reply=f'"{command.raw_text}" could not be understood',
            summary_line=f'"{command.raw_text}" could not be understood',
                category="errors",
            )
        if command.kind == "sale":
            return self._process_sale_command(command, is_late=False)
        if command.kind == "late_sale":
            return self._process_sale_command(command, is_late=True)
        if command.kind == "restock":
            return self._process_restock_command(command)
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

    def _process_sale_command(self, command: OperatingCommand, is_late: bool) -> EntryResult:
        note = "Entered later" if is_late else ""
        return self._record_sale(command.drug_name, command.quantity, is_late=is_late, note=note)

    def _record_sale(self, drug_name: str, quantity: int, is_late: bool = False, note: str = "") -> EntryResult:
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
        stock_plan = build_stock_update_plan(stock, quantity)
        notes = merge_notes(note, stock_plan.warning_notes)
        event = ParsedEvent(stock.drug_name, action, quantity=quantity, notes=notes)
        total_sales = stock.selling_price * quantity if stock.selling_price is not None else None
        total_cost = stock.cost_price * quantity if stock.cost_price is not None else None
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
                quantity,
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
                f"{event.drug_name} x{quantity}",
            ]
        elif missing_profit_data:
            reply_parts = [
                "⚠️ Sale recorded, but profit not calculated because price data is missing.",
                f"{event.drug_name} x{quantity}",
            ]
        else:
            reply_parts = [
                f"✅ {event.drug_name} x{quantity} recorded",
            ]
        if stock_plan.new_current_stock is not None:
            reply_parts.append(f"Stock left: {stock_plan.new_current_stock}")
        else:
            reply_parts.append("Stock left: not set.")
        if not is_late and not missing_profit_data:
            reply_parts.append(f"Profit: {format_kes(profit)}")
        today_profit_line = self._today_profit_line()
        if today_profit_line:
            reply_parts.append(today_profit_line)
        if stock_plan.reply_warnings:
            reply_parts.extend(stock_plan.reply_warnings)
        reply = "\n".join(reply_parts)

        return EntryResult(
            logged=True,
            reply=reply,
            summary_line=f"{event.drug_name} x{quantity}",
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
        new_current_stock = current_stock + command.quantity
        total_added_cost = 0 if command.restock_type == "bonus" else command.total_cost
        new_average_cost = calculate_average_cost(
            current_stock=current_stock,
            current_cost=stock.cost_price,
            added_quantity=command.quantity,
            total_added_cost=total_added_cost,
        )
        unit_added_cost = (
            total_added_cost / command.quantity
            if total_added_cost is not None and command.quantity > 0
            else None
        )
        saved_amount = (
            command.budgeted_cost - total_added_cost
            if command.budgeted_cost is not None and total_added_cost is not None
            else None
        )
        notes = f"Restock type: {command.restock_type}."
        if total_added_cost is not None:
            notes = (
                f"Restock type: {command.restock_type}. "
                f"Restock total cost {format_kes(total_added_cost)}. "
                f"Calculated unit cost {format_kes(unit_added_cost)}."
            )
        if command.budgeted_cost is not None and total_added_cost is not None:
            notes = (
                f"Restock type: {command.restock_type}. "
                f"Budgeted {format_kes(command.budgeted_cost)}. "
                f"Paid {format_kes(total_added_cost)}. "
                f"Saved {format_kes(saved_amount)}. "
                f"Calculated unit cost {format_kes(unit_added_cost)}."
            )
        event = ParsedEvent(stock.drug_name, Action.RESTOCKED, quantity=command.quantity, notes=notes)

        try:
            if total_added_cost is not None:
                self.store.update_current_stock_and_cost(stock, new_current_stock, new_average_cost)
            else:
                self.store.update_current_stock(stock, new_current_stock)
            self.store.append_daily_log(event, None, None)
            self._append_transaction(
                "restock",
                stock.drug_name,
                command.quantity,
                unit_cost=unit_added_cost,
                total_cost=total_added_cost,
                note=notes,
            )
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")

        if command.restock_type == "bonus":
            reply_parts = [
                f"✅ {event.drug_name} bonus +{command.quantity} added",
            ]
        else:
            reply_parts = [f"✅ {event.drug_name} +{command.quantity} added"]
        if command.restock_type != "bonus" and total_added_cost is not None:
            reply_parts.append(f"Paid: {format_kes(total_added_cost)}")
        if command.budgeted_cost is not None and command.restock_type != "bonus":
            if command.budgeted_cost is not None:
                reply_parts.insert(1, f"Budget: {format_kes(command.budgeted_cost)}")
            if saved_amount is not None:
                reply_parts.append(f"Saved: {format_kes(saved_amount)}")
        if new_average_cost is not None and command.restock_type != "bonus":
            reply_parts.append(f"Avg cost: {format_kes(new_average_cost)}")
        reply_parts.append(f"New stock: {new_current_stock}")
        return EntryResult(
            logged=True,
            reply="\n".join(reply_parts),
            summary_line=f"{event.drug_name} +{command.quantity}",
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


def merge_notes(existing: str, extra_notes: list[str]) -> str:
    notes = [existing.strip()] if existing.strip() else []
    notes.extend(note for note in extra_notes if note)
    return " ".join(notes)


def is_help_command(text: str) -> bool:
    return text.strip().lower() in {"help", "start"}


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


def parse_stock_check_command(text: str) -> str | None:
    normalized = " ".join(text.strip().lower().split())
    if "no stock" in normalized or "out of stock" in normalized:
        return None
    if re.fullmatch(r"stock\s+.+?\s+\d+", normalized, flags=re.IGNORECASE):
        return None
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


def is_weekly_report_command(text: str) -> bool:
    normalized = normalize_key(text)
    return bool(
        re.fullmatch(r"(?:report\s+week|weekly\s+report)", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"show\s+me\s+(?:the\s+)?weekly\s+report", normalized, flags=re.IGNORECASE)
    )


def is_today_summary_command(text: str) -> bool:
    normalized = normalize_key(text).replace("today's", "today")
    return bool(
        re.fullmatch(r"(?:show\s+)?report(?:\s+today)?|daily\s+report", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"give\s+me\s+(?:today|today\s+report|the\s+daily\s+report)", normalized, flags=re.IGNORECASE)
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


def parse_single_operating_command(text: str) -> OperatingCommand | None:
    clean = " ".join(text.strip().split())
    if not clean:
        return None

    stock_name = parse_stock_check_command(clean)
    if stock_name:
        return OperatingCommand(kind="stock_check", drug_name=title_drug_name(stock_name), raw_text=text)

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

    match = re.fullmatch(r"(.+?)\s+(\d+)\s+paid\s+(\d+(?:\.\d+)?)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="restock",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            total_cost=parse_money(match.group(3)),
            raw_text=text,
        )

    match = re.fullmatch(r"(?:later|missed|i\s+missed)\s+(.+?)\s+(\d+)", clean, flags=re.IGNORECASE)
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

    match = re.fullmatch(r"(.+?)\s+sold\s+(\d+)", clean, flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="sale",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
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
    single_line = " ".join(clean.split())

    match = re.fullmatch(r"(?:sell|sale)\s+(.+?)\s+(\d+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"{title_drug_name(match.group(1))} {positive_quantity(match.group(2))}"

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

    match = re.fullmatch(r"add\s+(.+?)\s+(\d+)\s+bonus", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} bonus"

    match = re.fullmatch(r"(?:bonus|free|extra)\s+(.+?)\s+(\d+)", single_line, flags=re.IGNORECASE)
    if match:
        return f"+{title_drug_name(match.group(1))} {positive_quantity(match.group(2))} bonus"

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
