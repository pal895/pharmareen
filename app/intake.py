from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote

from app.domain import Action, ParsedEvent, ParseResult, StockItem
from app.pdf_reports import generate_daily_report_pdf, generate_weekly_report_pdf
from app.reports import ReportMetrics, build_report_metrics, low_stock_from_items, render_daily_summary, top_pairs
from app.services.pharmacy_engine import (
    build_note,
    canonical_unit,
    parse_note_metadata,
    parse_discount_percent,
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
from app.ai import log_ai_route_decision
from app.services.medicine_catalog import match_local_medicine
from app.services.operational_intelligence import OperationalMemory, classify_local_intent, decide_ai_route, log_edge_case
from app.services.pharmacy_alias_store import PharmacyAliasStore
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
        "Stock checks:",
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

    def add_stock_item(
        self,
        drug_name: str,
        selling_price: float | None = None,
        cost_price: float | None = None,
        current_stock: int = 0,
        reorder_level: int = 5,
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
    discount_percent: float = 0
    staff_name: str = ""
    batch_number: str = ""
    invoice_number: str = ""
    barcode: str = ""
    trace_id: str = ""
    notes: str = ""
    raw_text: str = ""
    error: str = ""
    target_day: str = ""


@dataclass(frozen=True)
class FollowUpPrompt:
    command: OperatingCommand
    question: str


@dataclass(frozen=True)
class DrugResolution:
    drug_name: str = ""
    question: str = ""


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
    "moja": 1,
    "mbili": 2,
    "bili": 2,
    "billi": 2,
    "billy": 2,
    "tatu": 3,
    "nne": 4,
    "ine": 4,
    "tano": 5,
    "sita": 6,
    "saba": 7,
    "nane": 8,
    "tisa": 9,
    "kumi": 10,
    "ishirini": 20,
    "thelathini": 30,
    "arobaini": 40,
    "hamsini": 50,
}

SHORTCUT_DRUGS = {
    "p": "Panadol",
    "pan": "Panadol",
    "para": "Paracetamol",
    "ors": "ORS",
    "a": "Antacid",
    "ant": "Antacid",
    "amoxil": "Amoxyl",
    "i": "Insulin",
    "ins": "Insulin",
}

PAYMENT_SPLIT_NOTE_KEYS = {
    "payment_cash": "Cash",
    "payment_mpesa": "M-Pesa",
    "payment_card": "Card",
    "payment_credit": "Credit",
}


def medicine_choice_question(typed: str, choices: list[str]) -> str:
    clean_choices = []
    seen = set()
    for choice in choices:
        key = normalize_key(choice)
        if not key or key in seen:
            continue
        seen.add(key)
        clean_choices.append(title_drug_name(choice))
    if not clean_choices:
        return f'I’m not sure which medicine "{typed}" means.\nPlease type the full medicine name.'
    return "\n".join(
        [
            f'I’m not sure which medicine "{typed}" means.',
            "",
            "Did you mean:",
            *[f"{index}. {choice}" for index, choice in enumerate(clean_choices, start=1)],
        ]
    )


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
        self.pending_selector_confirmations: dict[str, OperatingCommand] = {}
        self.staff_by_conversation: dict[str, str] = {}
        self.last_sale_by_conversation: dict[str, dict[str, Any]] = {}
        self.pending_void_reason: dict[str, dict[str, Any]] = {}
        self.pending_void_confirmation: dict[str, dict[str, Any]] = {}
        self.pending_repeat_confirmation: dict[str, str] = {}
        self.conversions_by_drug: dict[str, dict[str, int]] = {}
        self.pharmacy_alias_store = PharmacyAliasStore()
        self.pharmacy_learning_key = normalize_key(pharmacy_name) or "default"
        self.aliases_by_key = self._load_pharmacy_aliases()
        self.receipt_printing_enabled = False
        self.operational_memory = OperationalMemory()

    def process_text(self, text: str, conversation_id: str | None = None) -> str:
        text = text.strip()
        if not text:
            return "Please send a short text message or voice note."
        text = expand_compact_pharmacy_text(text)

        conversation_key = conversation_id or "__default__"
        route_decision = decide_ai_route(text=text)
        log_ai_route_decision(
            text=text,
            route=route_decision.route,
            used_ai=route_decision.use_ai,
            reason=route_decision.reason,
        )

        pending_repeat = self.pending_repeat_confirmation.get(conversation_key)
        if pending_repeat is not None:
            response_key = normalize_key(text)
            if response_key in {"yes", "y", "confirm", "ndio", "sawa"}:
                self.pending_repeat_confirmation.pop(conversation_key, None)
                return self.process_text(pending_repeat, conversation_id=conversation_key)
            if response_key in {"cancel", "stop", "no", "hapana"}:
                self.pending_repeat_confirmation.pop(conversation_key, None)
                return "No problem. Nothing was saved."
            self.pending_repeat_confirmation.pop(conversation_key, None)
        pending_selector = self.pending_selector_confirmations.get(conversation_key)
        if pending_selector is not None:
            response_key = normalize_key(text)
            if response_key in {"yes", "y", "confirm", "ndio", "sawa"}:
                self.pending_selector_confirmations.pop(conversation_key, None)
                return self._process_commands([pending_selector], conversation_key=conversation_key)
            if response_key in {"cancel", "stop", "no", "hapana"}:
                self.pending_selector_confirmations.pop(conversation_key, None)
                return "No problem. Nothing was saved."
            updated_selector = self._update_selector_choice(text, pending_selector)
            if updated_selector is not None:
                self.pending_selector_confirmations[conversation_key] = updated_selector
                return self._selector_approval_reply(updated_selector, ready_to_confirm=True)
            self.pending_selector_confirmations.pop(conversation_key, None)
        pending_void_confirmation = self.pending_void_confirmation.get(conversation_key)
        if pending_void_confirmation is not None:
            response_key = normalize_key(text)
            if response_key in {"yes", "y", "confirm", "ndio", "sawa"}:
                self.pending_void_confirmation.pop(conversation_key, None)
                return self._commit_void(pending_void_confirmation, "Confirmed by user", conversation_key)
            if response_key in {"cancel", "stop", "no", "hapana"}:
                self.pending_void_confirmation.pop(conversation_key, None)
                return "No problem. The sale was not undone."
            return "Reply YES to undo the last sale, or CANCEL."

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

        if is_unsafe_undo_number_command(text):
            return "Which sale should I undo? Send undo last sale or cancel TX-1046."

        selector_reply = self._medicine_selector_reply(text, conversation_key)
        if selector_reply:
            return selector_reply

        if is_details_last_command(text):
            return self._details_last_reply(conversation_key)

        memory_reference_reply = self._memory_reference_reply(text, conversation_key)
        if memory_reference_reply:
            return memory_reference_reply

        receipt_setting = parse_receipt_setting_command(text)
        if receipt_setting is not None:
            self.receipt_printing_enabled = receipt_setting
            if receipt_setting and not receipt_printer_available():
                return "Receipt printing is now ON.\n🧾 Digital receipt ready — printer not detected."
            return f"Receipt printing is now {'ON' if receipt_setting else 'OFF'}."

        if is_print_receipt_last_command(text):
            return self._receipt_last_reply(conversation_key)

        payment_correction = parse_payment_correction_command(text)
        if payment_correction is not None:
            return self._payment_correction_reply(
                payment_correction[0],
                payment_correction[1],
                conversation_key,
            )

        quantity_correction = parse_quantity_correction_command(text)
        if quantity_correction is not None:
            return self._quantity_correction_reply(quantity_correction, conversation_key)

        replacement = parse_replace_last_sale_command(text)
        if replacement is not None:
            return self._replace_last_sale_reply(replacement, conversation_key)

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

        if is_cash_summary_command(text):
            return self._cash_summary_reply()

        if is_staff_summary_command(text):
            return self._staff_summary_reply()

        if is_low_stock_command(text):
            return self._low_stock_reply()

        if is_stock_value_command(text):
            return self._stock_value_reply()

        commands = parse_operating_commands(text)
        if commands is not None:
            return self._process_commands(commands, conversation_key=conversation_key)

        analytics_intent = parse_analytics_command(text)
        if analytics_intent is not None:
            if analytics_intent.get("type") == "low_stock":
                return self._low_stock_reply()
            return self._analytics_reply(analytics_intent)

        followup_prompt = parse_followup_prompt(text)
        if followup_prompt is not None:
            self.pending_followups[conversation_key] = followup_prompt.command
            return followup_prompt.question

        if is_profit_today_command(text):
            return self._profit_today_reply()

        if is_best_seller_command(text):
            return self._best_seller_reply(text)

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

        try:
            master_drug_names = self.store.list_master_drug_names()
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return SAVE_ERROR

        if route_decision.route == "clarify" and self.parser.__class__.__name__ == "AIService":
            guessed_intent, confidence = classify_local_intent(text)
            log_edge_case(
                text=text,
                sender=conversation_key,
                guessed_intent=guessed_intent,
                confidence=confidence,
                context={"route": route_decision.route, "reason": route_decision.reason},
                ai_fallback_used=False,
                final_outcome="local_safe_clarification",
            )
            return AMBIGUOUS_ERROR

        try:
            parsed = self.parser.parse_events(text, master_drug_names)
        except Exception as exc:
            guessed_intent, confidence = classify_local_intent(text)
            log_edge_case(
                text=text,
                sender=conversation_key,
                guessed_intent=guessed_intent,
                confidence=confidence,
                context={"parser": self.parser.__class__.__name__, "error": exc.__class__.__name__},
                ai_fallback_used=self.parser.__class__.__name__ == "AIService",
                final_outcome="parser_exception",
            )
            return UNDERSTAND_ERROR

        if parsed.needs_clarification or not parsed.events:
            guessed_intent, confidence = classify_local_intent(text)
            log_edge_case(
                text=text,
                sender=conversation_key,
                guessed_intent=guessed_intent,
                confidence=confidence,
                context={"question": parsed.clarification_question or ""},
                ai_fallback_used=self.parser.__class__.__name__ == "AIService",
                final_outcome="clarification",
            )
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

    def _memory_reference_reply(self, text: str, conversation_key: str) -> str:
        normalized = normalize_key(text)
        if normalized in {"same as last", "same kama jana", "same as yesterday", "same again", "rudia ile", "repeat last", "repeat last please"}:
            last = self.operational_memory.resolve_reference(conversation_key, text)
            if last:
                drug = str(last.get("drug_name") or "medicine")
                quantity = parse_int(last.get("display_quantity"), default=parse_int(last.get("quantity"), default=1)) or 1
                payment = str(last.get("payment_method") or "Cash")
                self.pending_repeat_confirmation[conversation_key] = f"{drug} {quantity} {payment}"
                return f"Repeat {drug} x{quantity} {payment}? Reply YES."
            return "Which medicine and quantity should I repeat?"
        if normalized in {"nilikosea quantity", "wrong quantity", "ile ya mwisho ilikuwa wrong quantity"}:
            if self.operational_memory.resolve_reference(conversation_key, "last"):
                return "Ni quantity gani sahihi?"
            return "Which medicine quantity should I correct?"
        return ""

    def _medicine_selector_reply(self, text: str, conversation_key: str) -> str:
        clean = normalize_natural_text(replace_number_words(text.strip()))
        if not clean or len(clean.split()) > 3:
            return ""
        key = normalize_key(clean)
        blocked = {
            "help",
            "hello",
            "hi",
            "stock",
            "report",
            "trace",
            "expiry",
            "expiring",
            "cash",
            "mpesa",
            "credit",
            "receipt",
            "undo",
            "yes",
            "no",
        }
        if key in blocked or any(character.isdigit() for character in clean) or "+" in clean:
            return ""
        command_words = [
            "stock",
            "report",
            "restock",
            "sell",
            "sold",
            "cash",
            "mpesa",
            "credit",
            "receipt",
            "undo",
            "void",
            "cancel",
            "same",
            "last",
            "today",
            "yesterday",
            "summary",
            "sales",
            "best",
            "top",
            "trace",
            "expiry",
            "expiring",
            "supplier",
            "invoice",
            "batch",
        ]
        if any(word in key for word in command_words):
            return ""
        resolution = self._resolve_drug_name(clean)
        if resolution.question:
            return resolution.question
        if not resolution.drug_name:
            return ""
        if self._resolve_stock(resolution.drug_name) is None:
            return f"⚠ {resolution.drug_name} is not yet in your inventory. Add it during restock first."
        selector = OperatingCommand(
            kind="sale",
            drug_name=resolution.drug_name,
            quantity=1,
            payment_method="Cash",
            raw_text=resolution.drug_name,
        )
        self.pending_selector_confirmations[conversation_key] = selector
        return self._selector_approval_reply(selector)

    def _selector_approval_reply(self, selector: OperatingCommand, *, ready_to_confirm: bool = False) -> str:
        lines = [
            "Sale approval",
            f"{selector.drug_name} x{selector.quantity} - {selector.payment_method or 'Cash'}",
            "Qty: 1 | 2 | 3 | 5 | 10 | + | -",
            "Pay: Cash | M-Pesa | Credit | Mixed",
        ]
        if ready_to_confirm:
            lines.append("Confirm | Cancel")
        else:
            lines.append("Choose quantity and payment.")
            lines.append("Confirm | Cancel")
        return "\n".join(lines)

    def prepare_sale_selector(
        self,
        drug_name: str,
        quantity: int = 1,
        payment_method: str = "Cash",
        *,
        conversation_id: str | None = None,
    ) -> str:
        conversation_key = conversation_id or "__default__"
        selector = OperatingCommand(
            kind="sale",
            drug_name=drug_name,
            quantity=max(int(quantity or 1), 1),
            payment_method=parse_payment_method(payment_method or "Cash"),
            raw_text=f"{drug_name} {max(int(quantity or 1), 1)} {payment_method or 'Cash'}",
        )
        self.pending_selector_confirmations[conversation_key] = selector
        return self._selector_approval_reply(selector, ready_to_confirm=True)

    def _update_selector_choice(self, text: str, selector: OperatingCommand) -> OperatingCommand | None:
        clean = normalize_natural_text(replace_number_words(text.strip()))
        response_key = normalize_key(clean)
        if clean == "+":
            return replace(selector, quantity=max(selector.quantity + 1, 1))
        if clean == "-":
            return replace(selector, quantity=max(selector.quantity - 1, 1))
        quantity_payment = re.fullmatch(rf"(\d+)(?:\s+({payment_pattern()}))?", clean, flags=re.IGNORECASE)
        if quantity_payment:
            return replace(
                selector,
                quantity=positive_quantity(quantity_payment.group(1)),
                payment_method=parse_payment_method(quantity_payment.group(2) or selector.payment_method or "Cash"),
            )
        if re.fullmatch(payment_pattern(), clean, flags=re.IGNORECASE):
            return replace(selector, payment_method=parse_payment_method(clean))
        return None

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
        lines = [f"📦 {stock.drug_name} stock left: {stock_text}"]
        if stock.selling_price is not None:
            lines.append(f"Price: {format_kes(stock.selling_price)}")
        if stock.reorder_level is not None:
            lines.append(f"Restock when left with {stock.reorder_level}")
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
        out_of_stock: list[str] = []
        running_low: list[str] = []
        for item in items[:20]:
            current_stock = parse_int(item.current_stock, default=0) or 0
            if current_stock <= 0:
                out_of_stock.append(f"- {item.drug_name} out of stock")
                continue
            reorder_text = f"; restock when left with {item.reorder_level}" if item.reorder_level is not None else ""
            running_low.append(f"- {item.drug_name} — {current_stock} left{reorder_text}")
        lines = ["⚠ Stock needs attention"]
        if out_of_stock:
            lines.append("")
            lines.append("Out of stock:")
            lines.extend(out_of_stock)
        if running_low:
            lines.append("")
            lines.append("Running low:")
            lines.extend(running_low)
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
            lines.append(f"Stock left: {stock_text}")
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
            split_used = False
            for key, label in PAYMENT_SPLIT_NOTE_KEYS.items():
                amount = parse_money(note_meta.get(key))
                if amount:
                    payment_totals[label] = payment_totals.get(label, 0) + amount
                    split_used = True
            discounts += parse_money(note_meta.get("discount")) or 0
            if split_used:
                continue
            payment = note_meta.get("payment", "Cash")
            payment = "M-Pesa" if normalize_key(payment) in {"mpesa", "m pesa", "m-pesa"} else payment.title()
            payment_totals.setdefault(payment, 0.0)
            payment_totals[payment] += parse_money(row.get("Total Sales")) or 0
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
        return f"{self.app_base_url}/reports/download/{quote(pdf_path.name)}"

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
        section_candidates = [
            ("Sales", "sales"),
            ("Late Sales", "late_sales"),
            ("Restocks", "restocks"),
            ("No-stock requests", "no_stock"),
        ]
        section_titles = [(title, key) for title, key in section_candidates if groups[key]]
        if groups["stock_checks"]:
            section_titles.append(("Stock Checks", "stock_checks"))
        if groups["errors"]:
            section_titles.append(("Errors", "errors"))
        if not section_titles:
            return "No records were processed."

        for title, key in section_titles:
            lines.append(f"{title}:")
            lines.extend(f"- {item}" for item in groups[key])
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
        if command.drug_name and command.kind in {"sale", "late_sale", "restock", "stock_check", "no_stock"}:
            resolution = self._resolve_drug_name(command.drug_name)
            if resolution.question and command.kind != "no_stock":
                self.operational_memory.remember_clarification(conversation_key, resolution.question)
                return EntryResult(
                    logged=False,
                    reply=resolution.question,
                    summary_line=resolution.question,
                    category="errors",
                )
            if resolution.drug_name:
                command = replace(command, drug_name=resolution.drug_name)
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
        if command.target_day:
            note = merge_notes(note, f"Target day: {command.target_day}.")
        payment_breakdown = parse_payment_breakdown(command.raw_text)
        if payment_breakdown:
            note = merge_notes(
                note,
                build_note(
                    "",
                    payment_cash=payment_breakdown.get("Cash", ""),
                    payment_mpesa=payment_breakdown.get("M-Pesa", ""),
                    payment_card=payment_breakdown.get("Card", ""),
                    payment_credit=payment_breakdown.get("Credit", ""),
                ),
            )
        staff_name = command.staff_name or self.staff_by_conversation.get(conversation_key, "")
        return self._record_sale(
            command.drug_name,
            command.quantity,
            is_late=is_late,
            note=note,
            unit=command.unit,
            base_quantity=command.base_quantity,
            payment_method="Mixed" if payment_breakdown else command.payment_method,
            discount=command.discount,
            discount_percent=command.discount_percent,
            staff_name=staff_name,
            trace_id_value=command.trace_id,
            batch_number=command.batch_number,
            invoice_number=command.invoice_number,
            supplier=command.supplier,
            barcode=command.barcode,
            target_day=command.target_day,
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
        discount_percent: float = 0,
        staff_name: str = "",
        trace_id_value: str = "",
        batch_number: str = "",
        invoice_number: str = "",
        supplier: str = "",
        barcode: str = "",
        target_day: str = "",
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
        stock = self._stock_with_safety_quantity(stock)
        current_stock_value = parse_int(stock.current_stock, default=None)
        if current_stock_value is not None and current_stock_value < base_quantity:
            return self._record_missed_sale_attempt(
                stock=stock,
                display_quantity=display_quantity,
                base_quantity=base_quantity,
                unit=unit,
                payment_method=payment_method,
                note=note,
            )
        gross_sales = stock.selling_price * base_quantity if stock.selling_price is not None else None
        if gross_sales is not None and discount_percent:
            discount = round(gross_sales * (float(discount_percent) / 100), 2)
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
            discount_percent=discount_percent if discount_percent else "",
            staff=staff_name,
            batch=batch_number,
            invoice=invoice_number,
            supplier=supplier,
            barcode=barcode,
        )
        event = ParsedEvent(stock.drug_name, action, quantity=base_quantity, notes=notes)
        total_sales = max(gross_sales - discount, 0) if gross_sales is not None else None
        total_cost = stock.cost_price * base_quantity if stock.cost_price is not None else None
        profit = (
            total_sales - total_cost
            if total_sales is not None and total_cost is not None
            else None
        )
        missing_profit_data = stock.selling_price is None or stock.cost_price is None
        created_at = self._created_at_for_target_day(target_day)

        try:
            self._append_daily_log(event, stock.selling_price, total_sales, created_at=created_at)
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
                created_at=created_at,
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

        payment_label = payment_method or "Cash"
        if is_late:
            reply_parts = [
                f"✅ Late sale saved{f' for {target_day}' if target_day else ''}:",
                f"{event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)} recorded • {payment_label}",
            ]
        elif missing_profit_data:
            reply_parts = [
                f"✅ {event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)} recorded • {payment_label}",
            ]
        else:
            reply_parts = [
                f"✅ {event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)} recorded • {payment_label}",
            ]
        if unit and base_quantity != display_quantity:
            reply_parts.append(f"Equivalent: {base_quantity} tablets")
        if discount and gross_sales is not None:
            reply_parts.append(f"Original: {format_kes(gross_sales)}")
            if discount_percent:
                reply_parts.append(f"Discount: {format_kes(discount)} ({format_plain_number(discount_percent)}%)")
            else:
                reply_parts.append(f"Discount: {format_kes(discount)}")
            reply_parts.append(f"Paid: {format_kes(total_sales)}")
        if stock_plan.new_current_stock is not None:
            reply_parts.append(f"Stock left: {self._format_stock_level(stock.drug_name, stock_plan.new_current_stock, unit)}")
        else:
            reply_parts.append("Stock left: not set")
        if stock_plan.reply_warnings:
            reply_parts.extend(stock_plan.reply_warnings)
        if self.receipt_printing_enabled:
            if receipt_printer_available():
                reply_parts.append("🧾 Receipt printed")
            else:
                reply_parts.append("🧾 Digital receipt ready — printer not detected.")
        reply = "\n".join(reply_parts)
        sale_memory = {
            "drug_name": stock.drug_name,
            "quantity": base_quantity,
            "unit": unit,
            "display_quantity": display_quantity,
            "trace_id": sale_trace_id,
            "payment_method": payment_method,
            "discount": discount,
            "discount_percent": discount_percent,
            "profit": profit,
            "total_sales": total_sales,
            "total_cost": total_cost,
            "fefo": fefo_reply,
            "missing_profit_data": missing_profit_data,
        }
        self.last_sale_by_conversation[conversation_key] = sale_memory
        self.operational_memory.remember_transaction(conversation_key, sale_memory)

        return EntryResult(
            logged=True,
            reply=reply,
            summary_line=f"{event.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)} {payment_label}",
            category="late_sales" if is_late else "sales",
        )

    def _record_missed_sale_attempt(
        self,
        stock: StockItem,
        display_quantity: int,
        base_quantity: int,
        unit: str = "",
        payment_method: str = "Cash",
        note: str = "",
    ) -> EntryResult:
        parsed_available = parse_int(stock.current_stock, default=0)
        available = max(parsed_available if parsed_available is not None else 0, 0)
        notes = build_note(
            merge_notes(note, "Attempted sale blocked because stock was insufficient."),
            payment=payment_method,
            unit=unit or "unit",
            display_quantity=display_quantity,
            base_quantity=base_quantity,
        )
        event = ParsedEvent(stock.drug_name, Action.OUT_OF_STOCK, quantity=base_quantity, notes=notes)
        try:
            self.store.append_daily_log(event, None, None)
            self._append_transaction(
                "no_stock",
                stock.drug_name,
                base_quantity,
                note=notes or "Missed sale / insufficient stock",
            )
        except SheetsUnavailableError:
            return EntryResult(logged=False, reply=SHEETS_UNAVAILABLE_MESSAGE, summary_line="", category="errors")
        except Exception:
            return EntryResult(logged=False, reply=SAVE_ERROR, summary_line="", category="errors")

        quantity_label = f"{stock.drug_name} x{display_quantity}{unit_suffix(unit, display_quantity)}"
        if available <= 0:
            reason = f"{stock.drug_name} out of stock."
        else:
            reason = f"Only {self._format_stock_level(stock.drug_name, available, unit)} available."
        reply = (
            f"⚠️ {reason} Sale not recorded. "
            f"Missed sale saved: {quantity_label}.\n"
            f"Stock left: {self._format_stock_level(stock.drug_name, available, unit)}"
        )
        return EntryResult(
            logged=True,
            reply=reply,
            summary_line=f"{quantity_label} missed sale",
            category="no_stock",
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

        current_stock = parse_int(stock.current_stock, default=0) or 0
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
            reply_parts = [f"✅ {event.drug_name} restocked: {ordered_quantity} + {bonus_quantity} bonus = {display_quantity} added"]
            reply_parts.append(f"{event.drug_name} +{display_text} added")
        else:
            reply_parts = [f"✅ {event.drug_name} +{display_text} added"]
        if unit and quantity_to_add != display_quantity:
            reply_parts.append(f"Equivalent: +{quantity_to_add} tablets")
        if has_bonus and ordered_quantity:
            reply_parts.append(f"Bought {ordered_quantity} + bonus {bonus_quantity}")
        elif has_bonus:
            reply_parts.append(f"Bonus: {bonus_quantity}")
        if total_added_cost is not None and total_added_cost != 0:
            reply_parts.append(f"Paid: {format_kes(total_added_cost)}")
        if has_discount and discount_amount:
            reply_parts.append(f"Discount: {format_kes(discount_amount)}")
        if saved_amount is not None and expected_total_cost is not None:
            reply_parts.append(f"Saved: {format_kes(saved_amount)}")
        if command.supplier:
            reply_parts.append(f"Supplier: {command.supplier}")
        if command.expiry_date:
            reply_parts.append(f"Expiry: {command.expiry_date}")
        reply_parts.append(f"Stock left: {self._format_stock_level(stock.drug_name, new_current_stock, unit)}")
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

        totals = payment_totals_from_transactions(transactions)
        payment_totals = totals["payment_totals"]
        return "\n".join(
            [
                "💰 Daily Cash Summary",
                "",
                f"Cash: {format_kes(payment_totals.get('Cash', 0))}",
                f"M-Pesa: {format_kes(payment_totals.get('M-Pesa', 0))}",
                f"Card: {format_kes(payment_totals.get('Card', 0))}",
                f"Credit: {format_kes(payment_totals.get('Credit', 0))}",
                f"Discounts: {format_kes(totals['discounts'])}",
                f"Total Sales: {format_kes(totals['total_sales'])}",
                f"Profit: {format_kes(totals['profit'])}",
            ]
        )

    def _analytics_reply(self, intent: dict[str, str]) -> str:
        now = now_in_timezone(self.timezone)
        day = intent.get("day") or "today"
        report_date = (now.date() - timedelta(days=1)).isoformat() if day == "yesterday" else now.date().isoformat()
        day_label = "yesterday" if day == "yesterday" else "today"
        try:
            transactions = self.store.read_transactions(report_date)
            metrics = build_transaction_metrics(report_date, transactions, [])
            if intent.get("type") in {"best_seller", "missed_demand"} and not (metrics.most_sold or metrics.missed_sales):
                logs = self.store.read_daily_logs(report_date)
                metrics = build_report_metrics(report_date, logs, [])
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not check that right now. Please check the Google Sheets connection."

        if intent.get("type") == "best_seller":
            if not metrics.most_sold:
                return f"No records found for {day_label} yet."
            drug_name, quantity = metrics.most_sold[0]
            return f"Best seller {day_label}: {drug_name} — {quantity} sold"
        if intent.get("type") == "peak_hours":
            if not metrics.sale_transactions:
                return f"No records found for {day_label} yet."
            totals = payment_totals_from_transactions(transactions)
            payment_totals = totals["payment_totals"]
            lines = [f"⏰ Peak time {day_label}: {metrics.peak_activity_time}"]
            if metrics.most_sold:
                lines.append("Top medicines:")
                lines.extend(f"• {name} — {quantity} sold" for name, quantity in metrics.most_sold[:3])
            if any(payment_totals.values()):
                lines.append("Payments:")
                lines.append(f"• Cash — {format_kes(payment_totals.get('Cash', 0))}")
                lines.append(f"• M-Pesa — {format_kes(payment_totals.get('M-Pesa', 0))}")
                if payment_totals.get("Card", 0):
                    lines.append(f"• Card — {format_kes(payment_totals.get('Card', 0))}")
                if payment_totals.get("Credit", 0):
                    lines.append(f"• Credit — {format_kes(payment_totals.get('Credit', 0))}")
            return "\n".join(lines)
        if intent.get("type") == "missed_demand":
            if not metrics.missed_sales:
                return f"No no-stock requests found for {day_label} yet."
            lines = [f"No-stock requests {day_label}:"]
            lines.extend(f"- {name}: {count}" for name, count in metrics.missed_sales[:5])
            return "\n".join(lines)

        totals = payment_totals_from_transactions(transactions)
        payment_totals = totals["payment_totals"]
        if intent.get("type") == "payment_amount":
            payment = intent.get("payment") or "Cash"
            icon = {"Cash": "💵", "M-Pesa": "📱", "Card": "💳", "Credit": "🧾"}.get(payment, "💳")
            return f"{icon} {payment} received {day_label}: {format_kes(payment_totals.get(payment, 0))}"
        if intent.get("type") == "top_payment":
            payment_counts = totals.get("payment_counts", {})
            ranked = [
                (method, payment_totals.get(method, 0), payment_counts.get(method, 0))
                for method in ["Cash", "M-Pesa", "Card", "Credit"]
                if payment_totals.get(method, 0) or payment_counts.get(method, 0)
            ]
            if not ranked:
                return f"No payment records found for {day_label} yet."
            ranked.sort(key=lambda item: (-item[2], -item[1], item[0]))
            top_method, top_amount, top_count = ranked[0]
            lines = [f"Most used payment {day_label}: {top_method} - {format_kes(top_amount)} / {top_count} sales"]
            for method, amount, count in ranked[1:4]:
                lines.append(f"{method} - {format_kes(amount)} / {count} sales")
            return "\n".join(lines)
        if intent.get("type") == "payment_breakdown":
            if not any(payment_totals.values()):
                return f"No payment records found for {day_label} yet."
            return "\n".join([
                f"Payment breakdown {day_label}:",
                f"Cash: {format_kes(payment_totals.get('Cash', 0))}",
                f"M-Pesa: {format_kes(payment_totals.get('M-Pesa', 0))}",
                f"Card: {format_kes(payment_totals.get('Card', 0))}",
                f"Credit: {format_kes(payment_totals.get('Credit', 0))}",
            ])
        return UNDERSTAND_ERROR

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

    def _format_stock_level(self, drug_name: str, quantity: int | None, unit_context: str = "") -> str:
        if quantity is None:
            return "not set"
        total = parse_int(quantity, default=0) or 0
        canonical = canonical_unit(unit_context)
        conversion = self.conversions_by_drug.get(normalize_key(drug_name), {})
        strip_size = max(int(conversion.get("strip") or 10), 1)
        box_size = max(int(conversion.get("box") or strip_size * 10), strip_size)
        if not canonical and normalize_key(drug_name) not in self.conversions_by_drug:
            return str(total)
        if total < strip_size:
            return f"{total} tablets"
        boxes, after_boxes = divmod(total, box_size)
        strips, tablets = divmod(after_boxes, strip_size)
        parts: list[str] = []
        if boxes:
            parts.append(f"{boxes} {plural_unit('box', boxes)}")
        if strips:
            parts.append(f"{strips} {plural_unit('strip', strips)}")
        if tablets:
            parts.append(f"{tablets} {plural_unit('tablet', tablets)}")
        friendly = " + ".join(parts) if parts else "0 tablets"
        return f"{total} tablets ({friendly})"

    def _process_void_command(self, command: OperatingCommand, conversation_key: str) -> EntryResult:
        sale = self.last_sale_by_conversation.get(conversation_key)
        if sale is None:
            return EntryResult(
                logged=False,
                reply="No recent sale found to void.",
                summary_line="No recent sale found to void",
                category="errors",
            )
        requested_trace = normalize_key(command.trace_id).replace("-", "")
        sale_trace = normalize_key(str(sale.get("trace_id") or "")).replace("-", "")
        if requested_trace and sale_trace and requested_trace != sale_trace:
            return EntryResult(
                logged=False,
                reply=f"I could not find {command.trace_id}. Send details last or undo last sale.",
                summary_line="Void trace not found",
                category="errors",
            )
        reason = command.notes.strip()
        if reason == "__confirm_void__":
            self.pending_void_confirmation[conversation_key] = sale
            drug_name = str(sale.get("drug_name") or "sale")
            display_quantity = parse_int(sale.get("display_quantity"), default=parse_int(sale.get("quantity"), default=0)) or 0
            payment = str(sale.get("payment_method") or "Cash")
            return EntryResult(
                logged=False,
                reply=f"Undo last sale: {drug_name} x{display_quantity} {payment}?\nReply YES to confirm.",
                summary_line="Undo confirmation needed",
                category="errors",
            )
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
        display_quantity = parse_int(sale.get("display_quantity"), default=quantity) or quantity
        payment = str(sale.get("payment_method") or "Cash")
        original_trace_id = str(sale.get("trace_id") or "")
        void_trace_id = trace_id("VOID")
        stock_left: int | None = None
        try:
            stock = self._resolve_stock(drug_name)
            if stock and stock.current_stock is not None:
                stock_left = stock.current_stock + quantity
                self.store.update_current_stock(stock, stock_left)
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
        stock_line = f"Stock left: {stock_left}" if stock_left is not None else "Stock restored safely"
        return "\n".join(
            [
                "✅ Last sale removed safely",
                f"{drug_name} x{display_quantity} {payment} restored to stock",
                stock_line,
                f"{payment} total adjusted.",
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

    def _stock_with_safety_quantity(self, stock: StockItem) -> StockItem:
        """Apply the read-only lowest trusted stock before any sale is saved."""
        safety_lookup = getattr(self.store, "find_stock_for_safety", None)
        if not callable(safety_lookup):
            return stock
        try:
            safety_stock = safety_lookup(stock.drug_name)
        except TypeError:
            try:
                safety_stock = safety_lookup(stock.drug_name, pharmacy_id=None)
            except Exception:
                safety_stock = None
        except Exception:
            safety_stock = None
        if safety_stock is None:
            return stock
        return StockItem(
            drug_name=stock.drug_name or safety_stock.drug_name,
            selling_price=stock.selling_price if stock.selling_price is not None else safety_stock.selling_price,
            cost_price=stock.cost_price if stock.cost_price is not None else safety_stock.cost_price,
            current_stock=safety_stock.current_stock,
            reorder_level=stock.reorder_level if stock.reorder_level is not None else safety_stock.reorder_level,
            row_number=stock.row_number,
        )

    def _resolve_stock(self, drug_name: str) -> StockItem | None:
        stock = self.store.find_stock(drug_name)
        if stock is not None:
            return stock

        match = match_local_medicine(
            drug_name,
            inventory_names=self.store.list_master_drug_names(),
            pharmacy_aliases=self.aliases_by_key,
        )
        if not match.matched or not match.in_inventory:
            return None
        return self.store.find_stock(match.canonical_name)

    def _load_pharmacy_aliases(self) -> dict[str, str]:
        aliases = {normalize_key(key): value for key, value in SHORTCUT_DRUGS.items()}
        aliases.update(self.pharmacy_alias_store.accepted_aliases(self.pharmacy_learning_key))
        raw_aliases = os.getenv("PHARMAREEN_DRUG_ALIASES", "")
        for pair in raw_aliases.split(","):
            if "=" not in pair:
                continue
            alias, drug_name = pair.split("=", 1)
            alias_key = normalize_key(alias)
            drug_name = title_drug_name(drug_name)
            if alias_key and drug_name:
                aliases[alias_key] = drug_name
        return aliases

    def learn_pharmacy_alias(
        self,
        alias: str,
        drug_name: str,
        *,
        confirmed: bool,
        owner_approved: bool = False,
    ) -> dict[str, Any]:
        try:
            inventory_names = self.store.list_master_drug_names()
        except Exception:
            inventory_names = []
        result = self.pharmacy_alias_store.observe(
            self.pharmacy_learning_key,
            alias,
            drug_name,
            confirmed=confirmed,
            owner_approved=owner_approved,
            inventory_names=inventory_names,
        )
        if result.get("accepted"):
            self.aliases_by_key[normalize_key(alias)] = title_drug_name(drug_name)
        return result

    def _resolve_drug_name(self, drug_name: str) -> DrugResolution:
        text_key = normalize_key(drug_name)
        if not text_key:
            return DrugResolution()
        try:
            names = [name for name in self.store.list_master_drug_names() if str(name).strip()]
        except Exception:
            names = []
        match = match_local_medicine(
            drug_name,
            inventory_names=names,
            pharmacy_aliases=self.aliases_by_key,
        )
        if match.ambiguous:
            return DrugResolution(question=medicine_choice_question(drug_name, list(match.choices)))
        if match.matched:
            return DrugResolution(match.canonical_name)
        if len(text_key) <= 3:
            return DrugResolution(
                question=(
                    f'I’m not sure what "{drug_name}" means.\n'
                    "Please type the full medicine name, or ask Samuel to add it as a shortcut."
                )
            )
        return DrugResolution()

    def _payment_correction_reply(self, drug_name: str, new_payment: str, conversation_key: str) -> str:
        sale = self.last_sale_by_conversation.get(conversation_key)
        if not sale:
            return "No recent sale found to update."
        sale_drug = str(sale.get("drug_name") or "")
        if drug_name and normalize_key(drug_name) not in {normalize_key(sale_drug), ""}:
            return f"Which {title_drug_name(drug_name)} sale should I update?"
        old_payment = str(sale.get("payment_method") or "Cash")
        sale["payment_method"] = new_payment
        try:
            self._append_transaction(
                "correction",
                sale_drug,
                0,
                note=build_note(
                    f"Payment correction {old_payment} to {new_payment}",
                    trace_id=trace_id("CORR"),
                    original_trace_id=str(sale.get("trace_id") or ""),
                    payment=new_payment,
                ),
            )
        except Exception:
            pass
        return f"✅ Updated last {sale_drug} sale: {old_payment} → {new_payment}"

    def _quantity_correction_reply(self, instruction: dict[str, Any], conversation_key: str) -> str:
        sale = self.last_sale_by_conversation.get(conversation_key)
        if not sale:
            return "Which medicine should I update?"
        old_display = parse_int(sale.get("display_quantity"), default=0) or 0
        unit = str(sale.get("unit") or "")
        if instruction["mode"] == "set":
            new_display = max(parse_int(instruction.get("quantity"), default=old_display) or old_display, 0)
        elif instruction["mode"] == "increase":
            amount = max(parse_int(instruction.get("quantity"), default=1) or 1, 1)
            new_display = old_display + amount
        else:
            amount = max(parse_int(instruction.get("quantity"), default=1) or 1, 1)
            new_display = max(old_display - amount, 0)
        if new_display == old_display:
            return "No change needed."
        drug_name = str(sale.get("drug_name") or "")
        old_base = parse_int(sale.get("quantity"), default=old_display) or old_display
        new_base = self._to_base_quantity(drug_name, new_display, unit) if unit else new_display
        stock_change = old_base - new_base
        try:
            stock = self._resolve_stock(drug_name)
            if stock and stock.current_stock is not None:
                self.store.update_current_stock(stock, stock.current_stock + stock_change)
            self._append_transaction(
                "correction",
                drug_name,
                stock_change,
                note=build_note(
                    f"Quantity correction {old_display} to {new_display}",
                    trace_id=trace_id("CORR"),
                    original_trace_id=str(sale.get("trace_id") or ""),
                    unit=unit or "unit",
                ),
            )
        except Exception:
            return "I could not update that sale right now. Please check the connection."
        sale["display_quantity"] = new_display
        sale["quantity"] = new_base
        return f"✅ Updated last {drug_name} sale quantity: {old_display} → {new_display}"

    def _replace_last_sale_reply(self, instruction: dict[str, Any], conversation_key: str) -> str:
        sale = self.last_sale_by_conversation.get(conversation_key)
        if not sale:
            return "No recent sale found to replace."
        drug_name = str(instruction.get("drug_name") or "")
        resolution = self._resolve_drug_name(drug_name)
        if resolution.question:
            return resolution.question
        if not resolution.drug_name:
            return f"⚠ {title_drug_name(drug_name)} is not yet in your inventory. Add it during restock first."
        old_drug = str(sale.get("drug_name") or "last sale")
        old_display = parse_int(sale.get("display_quantity"), default=parse_int(sale.get("quantity"), default=0)) or 0
        old_payment = str(sale.get("payment_method") or "Cash")
        payment = str(instruction.get("payment_method") or old_payment or "Cash")
        quantity = positive_quantity(instruction.get("quantity") or 1)
        self._commit_void(sale, "Replaced by user", conversation_key)
        result = self._record_sale(
            resolution.drug_name,
            quantity,
            payment_method=payment,
            conversation_key=conversation_key,
        )
        if not result.logged:
            return result.reply
        return "\n".join(
            [
                "✅ Replaced last sale safely",
                f"{old_drug} x{old_display} removed",
                result.reply,
            ]
        )


    def _best_seller_reply(self, text: str) -> str:
        now = now_in_timezone(self.timezone)
        report_date = (now.date() - timedelta(days=1)).isoformat() if "yesterday" in text.lower() or "jana" in text.lower() else now.date().isoformat()
        try:
            transactions = self.store.read_transactions(report_date)
            metrics = build_transaction_metrics(report_date, transactions, [])
            if not metrics.most_sold:
                logs = self.store.read_daily_logs(report_date)
                metrics = build_report_metrics(report_date, logs, [])
        except SheetsUnavailableError:
            return SHEETS_UNAVAILABLE_MESSAGE
        except Exception:
            return "I could not check that right now. Please check the Google Sheets connection."
        if not metrics.most_sold:
            return "No sales recorded today yet." if report_date == now.date().isoformat() else "No sales recorded for that day."
        drug_name, quantity = metrics.most_sold[0]
        day_label = "today" if report_date == now.date().isoformat() else "yesterday"
        return f"Best seller {day_label}: {drug_name} — {quantity} sold"

    def _details_last_reply(self, conversation_key: str) -> str:
        sale = self.last_sale_by_conversation.get(conversation_key)
        if not sale:
            return "No recent sale details yet."
        lines = [
            "Last Sale Details",
            f"{sale['drug_name']} x{sale['display_quantity']}{unit_suffix(sale.get('unit', ''), sale['display_quantity'])}",
            f"Trace: {sale.get('trace_id') or 'not set'}",
        ]
        if sale.get("payment_method"):
            lines.append(f"Payment: {sale['payment_method']}")
        if sale.get("discount"):
            lines.append(f"Discount: {format_kes(sale['discount'])}")
        if sale.get("profit") is not None:
            lines.append(f"Profit: {format_kes(sale['profit'])}")
        if sale.get("fefo"):
            lines.append(str(sale["fefo"]))
        if sale.get("missing_profit_data"):
            lines.append("Profit details need price data.")
        return "\n".join(lines)

    def _receipt_last_reply(self, conversation_key: str) -> str:
        sale = self.last_sale_by_conversation.get(conversation_key)
        if not sale:
            return "No recent sale to print yet."
        amount = sale.get("total_sales")
        return "\n".join(
            [
                "PHARMAREEN RECEIPT",
                f"Medicine: {sale['drug_name']}",
                f"Quantity: {sale['display_quantity']}{unit_suffix(sale.get('unit', ''), sale['display_quantity'])}",
                f"Payment: {sale.get('payment_method') or 'Cash'}",
                f"Amount: {format_kes(amount) if amount is not None else 'not set'}",
                f"Time: {now_in_timezone(self.timezone).strftime('%Y-%m-%d %H:%M')}",
                f"Trace: {sale.get('trace_id') or 'not set'}",
                "Thank you.",
            ]
        )

    def _created_at_for_target_day(self, target_day: str = "") -> datetime | None:
        if normalize_key(target_day) != "yesterday":
            return None
        created_at = now_in_timezone(self.timezone) - timedelta(days=1)
        return created_at.replace(hour=12, minute=0, second=0, microsecond=0)

    def _append_daily_log(
        self,
        event: ParsedEvent,
        price: float | None,
        total_value: float | None,
        created_at: datetime | None = None,
    ) -> bool:
        append_daily_log = getattr(self.store, "append_daily_log", None)
        if append_daily_log is None:
            return False
        try:
            append_daily_log(event, price, total_value, created_at=created_at)
        except TypeError:
            append_daily_log(event, price, total_value)
        except Exception:
            return False
        return True

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
        created_at: datetime | None = None,
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
                created_at=created_at,
            )
        except TypeError:
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

    current_stock = parse_int(stock.current_stock, default=None)
    if current_stock is None:
        warning = "Current stock is blank. Please review stock when you have a moment."
        warning_notes.append(warning)
        reply_warnings.append(warning)
        return StockUpdatePlan(None, warning_notes, reply_warnings)

    new_stock = max(current_stock - quantity, 0)
    if current_stock < quantity:
        warning = "Sold more than the recorded stock. Please review stock after rush hour."
        warning_notes.append(warning)
        reply_warnings.append("Stock reached 0. Please review after rush hour.")

    reorder_level = parse_int(stock.reorder_level, default=None)
    if reorder_level is not None and new_stock <= reorder_level:
        warning_notes.append(f"Running low: {stock.drug_name} needs restocking soon.")

    return StockUpdatePlan(new_stock, warning_notes, reply_warnings)


def low_stock_status_text(current_stock: Any) -> str:
    value = parse_int(current_stock, default=None)
    if value is None:
        return "stock not set"
    if value <= 0:
        return "finished"
    return f"{value} left"


def payment_totals_from_transactions(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    payment_totals = {"Cash": 0.0, "M-Pesa": 0.0, "Card": 0.0, "Credit": 0.0}
    payment_counts = {"Cash": 0, "M-Pesa": 0, "Card": 0, "Credit": 0}
    discount_total = 0.0
    total_sales = 0.0
    profit = 0.0
    sale_count = 0
    for row in transactions:
        if normalize_key(row.get("Type")) not in {"sale", "late sale", "late_sale"}:
            continue
        sale_count += 1
        note_meta = parse_note_metadata(str(row.get("Note") or ""))
        row_sales = parse_money(row.get("Total Sales")) or 0
        row_profit = parse_money(row.get("Profit")) or 0
        row_discount = parse_money(note_meta.get("discount")) or 0
        split_used = False
        for key, label in PAYMENT_SPLIT_NOTE_KEYS.items():
            amount = parse_money(note_meta.get(key))
            if amount:
                payment_totals[label] = payment_totals.get(label, 0) + amount
                payment_counts[label] = payment_counts.get(label, 0) + 1
                split_used = True
        if not split_used:
            payment = note_meta.get("payment", "Cash")
            payment = "M-Pesa" if normalize_key(payment) in {"mpesa", "m pesa", "m-pesa"} else payment.title()
            payment_totals.setdefault(payment, 0.0)
            payment_counts.setdefault(payment, 0)
            payment_totals[payment] += row_sales
            payment_counts[payment] += 1
        discount_total += row_discount
        total_sales += row_sales
        profit += row_profit
    return {
        "payment_totals": payment_totals,
        "payment_counts": payment_counts,
        "discounts": discount_total,
        "total_sales": total_sales,
        "profit": profit,
        "sale_count": sale_count,
    }


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


def is_details_last_command(text: str) -> bool:
    return re.fullmatch(r"(?:details\s+last|last\s+details|details\s+sale|sale\s+details)", text.strip(), flags=re.IGNORECASE) is not None


def parse_receipt_setting_command(text: str) -> bool | None:
    match = re.fullmatch(r"(?:receipt|receipts|receipt\s+printing)\s+(on|off)", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    return normalize_key(match.group(1)) == "on"


def receipt_printer_available() -> bool:
    return str(os.environ.get("PHARMAREEN_RECEIPT_PRINTER") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "available",
    }


def is_print_receipt_last_command(text: str) -> bool:
    normalized = normalize_key(text)
    return re.fullmatch(
        r"(?:print\s+(?:last\s+)?receipt|print\s+receipt(?:\s+last)?|receipt\s+(?:last|ya\s+mwisho)|send\s+receipt|hiyo\s+ya\s+mwisho\s+print\s+receipt|print\s+receipt\s+for\s+.+)",
        normalized,
        flags=re.IGNORECASE,
    ) is not None

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


def parse_analytics_command(text: str) -> dict[str, str] | None:
    key = normalize_key(text).replace("m pesa", "mpesa").replace("m-pesa", "mpesa")
    day = "yesterday" if any(word in key for word in ["yesterday", "jana"]) else "today"
    if is_cash_summary_command(text):
        return None
    if is_low_stock_command(text) or "low stock" in key:
        return {"type": "low_stock", "day": day}
    if any(phrase in key for phrase in ["missed demand", "most missed demand", "no stock today", "no stock leo", "out of stock today", "hakuna stock leo"]):
        return {"type": "missed_demand", "day": day}
    if any(phrase in key for phrase in ["best seller", "what sold most", "what did i sell most", "sold most", "sell most", "imeuza sana", "imeuzwa sana", "dawa gani imeuza sana", "fastest moving medicine", "fast moving medicine", "what is moving fast"]):
        return {"type": "best_seller", "day": day}
    if any(phrase in key for phrase in ["peak hour", "peak hours", "busiest time", "busiest hour", "rush hour"]):
        return {"type": "peak_hours", "day": day}
    if any(phrase in key for phrase in [
        "top payment",
        "top payment method",
        "top payment methods",
        "which payment method",
        "payment method was used most",
        "payment was used most",
        "most used payment",
        "most used payment method",
        "payment method used most",
    ]):
        return {"type": "top_payment", "day": day}
    if any(phrase in key for phrase in ["payment breakdown", "payments breakdown", "payment split", "payment methods today"]):
        return {"type": "payment_breakdown", "day": day}
    payment_phrases = {"cash": "Cash", "mpesa": "M-Pesa", "card": "Card", "credit": "Credit"}
    finance_words = ["today", "leo", "yesterday", "jana", "received", "came in", "imeingia", "ingia", "summary", "how much"]
    if any(word in key for word in finance_words):
        for phrase, label in payment_phrases.items():
            if phrase in key:
                return {"type": "payment_amount", "day": day, "payment": label}
    return None


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

    late_match = re.fullmatch(r"(?:late|later|missed)\s+(.+)", clean, flags=re.IGNORECASE)
    if late_match:
        drug_name = title_drug_name(late_match.group(1))
        return FollowUpPrompt(
            OperatingCommand(kind="late_sale", drug_name=drug_name, quantity=0, raw_text=text),
            f"How many {drug_name} were sold earlier?",
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


def parse_payment_correction_command(text: str) -> tuple[str, str] | None:
    clean = normalize_natural_text(replace_number_words(text.strip()))
    match = re.fullmatch(
        rf"(.+?)\s+(?:ilikuwa|was)\s+({payment_pattern()})\s+(?:si|not)\s+({payment_pattern()})",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return title_drug_name(match.group(1)), parse_payment_method(match.group(2))
    match = re.fullmatch(
        rf"(?:change|update|badilisha)\s+(?:last\s+)?payment\s+(?:to|iwe)\s+({payment_pattern()})",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return "", parse_payment_method(match.group(1))
    match = re.fullmatch(
        rf"(?:change|update|badilisha)\s+(?:last|ya\s+mwisho|hiyo\s+ya\s+mwisho)\s+(?:to|iwe)\s+({payment_pattern()})",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return "", parse_payment_method(match.group(1))
    return None

def parse_quantity_correction_command(text: str) -> dict[str, Any] | None:
    clean = normalize_natural_text(replace_number_words(text.strip()))
    match = re.fullmatch(
        r"(?:nilikosea|nimekosea|wrong\s+quantity|nilikosea\s+quantity|ile\s+ya\s+mwisho\s+ilikuwa\s+wrong\s+quantity)\s+(?:ilikuwa|iwe|to)?\s*(\d+)",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return {"mode": "set", "quantity": positive_quantity(match.group(1))}
    match = re.fullmatch(
        r"(?:ya\s+mwisho|hiyo\s+ya\s+mwisho|ile\s+ya\s+mwisho|last)\s+(?:ilikuwa|iwe|to)?\s*(\d+)",
        clean,
        flags=re.IGNORECASE,
    )
    if match:
        return {"mode": "set", "quantity": positive_quantity(match.group(1))}
    match = re.fullmatch(r"(?:badilisha|change|update)\s+(?:ile\s+ya\s+mwisho|ya\s+mwisho|last|last\s+sale)\s+(?:iwe|to)\s+(\d+)", clean, flags=re.IGNORECASE)
    if not match:
        match = re.fullmatch(r"(?:fanya|make|weka)\s+(?:iwe|it|last|ya\s+mwisho)?\s*(?:to|iwe)?\s*(\d+)", clean, flags=re.IGNORECASE)
    if match:
        return {"mode": "set", "quantity": positive_quantity(match.group(1))}
    match = re.fullmatch(r"(?:punguza|reduce)\s*(\d+)?", clean, flags=re.IGNORECASE)
    if match:
        return {"mode": "reduce", "quantity": positive_quantity(match.group(1) or 1)}
    match = re.fullmatch(r"(?:ongeza|add)\s*(?:moja|one|another|nyingine|\d+)?", clean, flags=re.IGNORECASE)
    if match:
        amount = re.search(r"\d+", clean)
        return {"mode": "increase", "quantity": positive_quantity(amount.group(0) if amount else 1)}
    return None

def parse_replace_last_sale_command(text: str) -> dict[str, Any] | None:
    clean = normalize_natural_text(replace_number_words(text.strip()))
    match = re.fullmatch(
        rf"(?:replace|badilisha)\s+(?:last\s+sale|last|ya\s+mwisho|ile\s+ya\s+mwisho|hiyo\s+ya\s+mwisho)\s+(?:with|to|iwe)\s+(.+?)\s+(\d+)(?:\s+({payment_pattern()}))?",
        clean,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return {
        "drug_name": title_drug_name(match.group(1)),
        "quantity": positive_quantity(match.group(2)),
        "payment_method": parse_payment_method(match.group(3) or "") if match.group(3) else "",
    }

def is_unsafe_undo_number_command(text: str) -> bool:
    return re.fullmatch(r"(?:undo|void|cancel)\s+\d+", normalize_natural_text(text.strip()), flags=re.IGNORECASE) is not None

def is_best_seller_command(text: str) -> bool:
    key = normalize_key(text)
    return any(
        phrase in key
        for phrase in [
            "best seller",
            "what did i sell most",
            "sell most",
            "fast moving",
            "imeuza sana",
            "imeuzwa sana",
        ]
    )


def complete_followup_command(text: str, pending: OperatingCommand) -> OperatingCommand | None:
    clean = normalize_natural_text(replace_number_words(text.strip()))
    clean = " ".join(clean.split())
    if not clean:
        return None
    if pending.kind in {"sale", "late_sale", "restock"}:
        response_key = normalize_key(clean)
        if response_key in {"yes", "y", "confirm", "ndio", "sawa"} and pending.drug_name:
            return replace(pending, quantity=1, raw_text=f"{pending.raw_text} 1".strip())
        quantity_payment = re.fullmatch(rf"(\d+)(?:\s+({payment_pattern()}))?", clean, flags=re.IGNORECASE)
        if quantity_payment and pending.drug_name:
            payment = parse_payment_method(quantity_payment.group(2) or pending.payment_method or "Cash")
            return replace(
                pending,
                quantity=positive_quantity(quantity_payment.group(1)),
                payment_method=payment,
                raw_text=f"{pending.raw_text} {quantity_payment.group(1)} {payment}".strip(),
            )
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
    clean_text = expand_compact_pharmacy_text(normalize_natural_text(replace_number_words(text.strip())))
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

    if ";" in clean_text:
        clean_text = clean_text.replace(";", ",")

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

    spaced_sales = parse_space_separated_sale_commands(clean_text)
    if spaced_sales is not None:
        return spaced_sales

    command = parse_single_operating_command(clean_text)
    return [command] if command is not None else None


def parse_target_day(text: str) -> str:
    key = normalize_key(text)
    if any(word in key.split() for word in ["yesterday", "jana"]):
        return "yesterday"
    return ""


def strip_temporal_words(text: str) -> str:
    clean = re.sub(r"\b(?:yesterday|jana)\b", " ", text, flags=re.IGNORECASE)
    return " ".join(clean.split())


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


def parse_space_separated_sale_commands(text: str) -> list[OperatingCommand] | None:
    if re.search(
        rf"\b(?:restock|restocked|received|bought|bonus|cost|paid|discount|supplier|expiry|invoice|batch|{payment_pattern()})\b",
        text,
        flags=re.IGNORECASE,
    ):
        return None
    matches = list(re.finditer(r"([A-Za-z][A-Za-z\s'-]*?)\s+x?(\d+)(?=\s+[A-Za-z]|$)", text.strip()))
    if len(matches) < 2:
        return None
    covered = " ".join(match.group(0).strip() for match in matches)
    if normalize_key(covered) != normalize_key(text):
        return None
    commands: list[OperatingCommand] = []
    for match in matches:
        drug_name = title_drug_name(match.group(1))
        if not drug_name:
            return None
        commands.append(
            OperatingCommand(
                kind="sale",
                drug_name=drug_name,
                quantity=positive_quantity(match.group(2)),
                raw_text=match.group(0).strip(),
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
    unit: str = "",
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
        unit=canonical_unit(unit),
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

    match = re.fullmatch(
        rf"\+(.+?)\s+(\d+)(?:\s+({unit_pattern()}))?\s+(?:plus\s+)?bonus\s+(\d+)(?:\s+(?:cost|paid)\s+(\d+(?:\.\d+)?))?(?:\s+discount\s+(\d+(?:\.\d+)?))?",
        detail_clean,
        flags=re.IGNORECASE,
    )
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            unit=match.group(3) or "",
            bonus_quantity=positive_quantity(match.group(4)),
            actual_paid_amount=parse_money(match.group(5)),
            discount_amount=parse_money(match.group(6)) or 0,
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

    match = re.fullmatch(r"(.+?)\s+stock\s+\+(\d+)(?:\s+(?:cost|paid)\s+(\d+(?:\.\d+)?))?", detail_clean, flags=re.IGNORECASE)
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            actual_paid_amount=parse_money(match.group(3)),
            supplier=supplier,
            expiry_date=expiry_date,
            raw_text=raw_text,
        )

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
        rf"(.+?)\s+(?:restock|restocked|received|bought)\s+(\d+)(?:\s+({unit_pattern()}))?\s+(?:plus\s+)?bonus\s+(\d+)(?:\s+(?:cost|paid)\s+(\d+(?:\.\d+)?))?(?:\s+discount\s+(\d+(?:\.\d+)?))?",
        detail_clean,
        flags=re.IGNORECASE,
    )
    if match:
        paid_value = parse_money(match.group(5))
        discount_value = parse_money(match.group(6)) or 0
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            unit=match.group(3) or "",
            bonus_quantity=positive_quantity(match.group(4)),
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

    match = re.fullmatch(
        r"(.+?)\s+(?:restock|restocked|received|bought)\s+(\d+)\s+discount\s+(\d+(?:\.\d+)?)",
        detail_clean,
        flags=re.IGNORECASE,
    )
    if match:
        return make_restock_command(
            drug_name=match.group(1),
            ordered_quantity=positive_quantity(match.group(2)),
            discount_amount=parse_money(match.group(3)) or 0,
            restock_type="discount",
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
        discount_percent=command.discount_percent or modifiers.discount_percent,
        supplier=command.supplier or modifiers.supplier,
        expiry_date=command.expiry_date or modifiers.expiry_date,
        invoice_number=command.invoice_number or modifiers.invoice_number,
        batch_number=command.batch_number or modifiers.batch_number,
        barcode=command.barcode or modifiers.barcode,
        target_day=command.target_day or parse_target_day(raw_text),
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
        discount_amount = extract_labeled_money(clean, ["discount", "saved"]) or 0
        bonus_match = re.search(r"\b(?:bonus|free|extra)\s+(\d+)\b|\bplus\s+(\d+)\s+(?:bonus|free|extra)\b", clean, flags=re.IGNORECASE)
        bonus_quantity = positive_quantity(bonus_match.group(1) or bonus_match.group(2)) if bonus_match else 0
        ordered_quantity = quantity
        total_received = quantity + bonus_quantity
        restock_type = (
            "bonus_discount"
            if bonus_quantity and discount_amount
            else "bonus"
            if bonus_quantity
            else "discount"
            if discount_amount
            else "normal"
        )
        command = OperatingCommand(
            kind="restock",
            drug_name=drug_name,
            quantity=total_received,
            base_quantity=to_base_quantity(total_received, unit),
            total_cost=total_cost,
            restock_type=restock_type,
            ordered_quantity=ordered_quantity,
            bonus_quantity=bonus_quantity,
            discount_amount=discount_amount,
            actual_paid_amount=total_cost,
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
            discount_percent=modifiers.discount_percent,
            supplier=modifiers.supplier,
            invoice_number=modifiers.invoice_number,
            batch_number=modifiers.batch_number,
            barcode=modifiers.barcode,
            target_day=parse_target_day(clean),
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


def parse_late_sale_command(clean: str, raw_text: str) -> OperatingCommand | None:
    target_day = parse_target_day(clean)
    starts_late = re.match(r"^(?:later|late|missed|i\s+missed)\b", clean, flags=re.IGNORECASE)
    if not starts_late and not target_day:
        return None

    late_body = re.sub(r"^(?:later|late|missed|i\s+missed)\s+", "", clean, flags=re.IGNORECASE)
    late_body = strip_temporal_words(late_body)
    late_body = re.sub(r"^sold\s+", "", late_body, flags=re.IGNORECASE)
    late_body = re.sub(r"^(?:sale|sell)\s+", "", late_body, flags=re.IGNORECASE)
    late_body = " ".join(late_body.split())
    if not late_body:
        return None

    sale = parse_engine_sale_command(late_body, raw_text)
    if sale is not None:
        return replace(
            sale,
            kind="late_sale",
            raw_text=raw_text,
            target_day=target_day,
        )

    modifiers = parse_trace_modifiers(clean)
    match = re.fullmatch(r"(.+?)\s+(\d+)", strip_modifier_phrases(late_body), flags=re.IGNORECASE)
    if match:
        return OperatingCommand(
            kind="late_sale",
            drug_name=title_drug_name(match.group(1)),
            quantity=positive_quantity(match.group(2)),
            payment_method=modifiers.payment_method,
            discount=modifiers.discount,
            discount_percent=modifiers.discount_percent,
            target_day=target_day,
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

    swahili_void_match = re.fullmatch(
        r"(?:undo|void|cancel)\s+(?:hiyo\s+ya\s+mwisho|ile\s+ya\s+mwisho|ya\s+mwisho|last\s+sale)",
        clean,
        flags=re.IGNORECASE,
    )
    if swahili_void_match:
        return OperatingCommand(kind="void", notes="__confirm_void__", raw_text=text)

    transaction_void_match = re.fullmatch(
        r"(?:undo|void|cancel)\s+([A-Za-z]{2,8}-?[A-Za-z0-9]{3,})",
        clean,
        flags=re.IGNORECASE,
    )
    if transaction_void_match:
        return OperatingCommand(
            kind="void",
            trace_id=transaction_void_match.group(1).upper(),
            notes="__confirm_void__",
            raw_text=text,
        )

    void_match = re.fullmatch(r"(?:void|undo|correct)\s+(?:last|sale(?:\s+([A-Za-z0-9_-]+))?)(?:\s+(.+))?", clean, flags=re.IGNORECASE)
    if void_match:
        return OperatingCommand(kind="void", trace_id=void_match.group(1) or "", notes=void_match.group(2) or "", raw_text=text)

    stock_name = parse_stock_check_command(clean)
    if stock_name:
        return OperatingCommand(kind="stock_check", drug_name=title_drug_name(stock_name), raw_text=text)

    late_candidate = parse_late_sale_command(clean, text)
    if late_candidate is not None:
        return late_candidate

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
        r"(.+?)\s+\+(\d+)(?:\s+(\d+(?:\.\d+)?))?(?:\s+(bonus|disc|discount|discounted))?",
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


def parse_payment_breakdown(text: str) -> dict[str, float]:
    payments: dict[str, float] = {}
    for method, amount in re.findall(
        rf"\b({payment_pattern()})\s+(\d+(?:\.\d+)?)\b",
        text,
        flags=re.IGNORECASE,
    ):
        label = "M-Pesa" if normalize_key(method) in {"mpesa", "m pesa", "m-pesa"} else title_drug_name(method)
        payments[label] = payments.get(label, 0) + (parse_money(amount) or 0)
    return payments if len(payments) >= 2 else {}


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
    clean = re.sub(r"^(?:nimeuza|niliuza)\s+(?:jana|yesterday)\s+(.+)$", r"late yesterday \1", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^(?:jana|yesterday)\s+(.+)$", r"late yesterday \1", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^(?:nimeuza|niliuza)\s+", "sold ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^ongeza\s+(.+?)\s+(\d+)(.*)$", r"add \1 \2\3", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^(?:customer\s+amesema\s+hakuna|amesema\s+hakuna|hakuna)\s+(.+)$", r"\1 no stock", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^nilisahau\s+kuuza\s+(.+?)\s*(?:earlier|mapema)?$", r"late \1", clean, flags=re.IGNORECASE)
    if "\n" not in clean and re.match(r"^(?:i\s+sold|sold|restocked|no\s+stock)\b", clean, flags=re.IGNORECASE):
        clean = re.sub(r"\s+and\s+", ", ", clean, flags=re.IGNORECASE)
    return clean


def expand_compact_pharmacy_text(text: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return clean
    expanded_lines: list[str] = []
    compact_aliases = {
        "reporttoday": "report today",
        "dailyreport": "daily report",
        "cashtoday": "cash today",
        "mpesatoday": "mpesa today",
        "bestsellertoday": "best seller today",
        "topsellertoday": "best seller today",
        "sameaslast": "same as last",
        "printreceipt": "print receipt",
        "printlastreceipt": "print last receipt",
        "stockvalue": "stock value",
        "lowstock": "low stock",
    }
    for line in clean.splitlines():
        stripped = line.strip()
        compact_key = normalize_key(stripped).replace(" ", "")
        if compact_key in compact_aliases:
            expanded_lines.append(compact_aliases[compact_key])
            continue
        if re.fullmatch(r"(?:undo|void|cancel)\s+[A-Za-z]{2,8}-?[A-Za-z0-9]{3,}", stripped, flags=re.IGNORECASE):
            expanded_lines.append(stripped)
            continue
        expanded = re.sub(r"(?<=\w)\+(?=\d)", " +", stripped)
        expanded = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", expanded)
        expanded = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", expanded)
        expanded = re.sub(r"\b(less|discount)(?=\d)", r"\1 ", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\bmixed\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", r"mixed cash \1 mpesa \2", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"\b(INV|B)\s+(\d+)\b", r"\1\2", expanded, flags=re.IGNORECASE)
        expanded = re.sub(r"^(late|later)([A-Za-z])", r"\1 \2", expanded, flags=re.IGNORECASE)
        if " " not in expanded and re.fullmatch(r"[A-Za-z]+stock", expanded, flags=re.IGNORECASE):
            expanded = re.sub(r"stock$", " stock", expanded, flags=re.IGNORECASE)
        expanded_lines.append(" ".join(expanded.split()))
    return "\n".join(line for line in expanded_lines if line)


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
            f"Running low: {low_stock}",
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

