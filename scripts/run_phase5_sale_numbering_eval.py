from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain import Action, ParsedEvent, ParseResult, StockItem
from app.intake import IntakeService, current_sale_date
from app.local_first_parser import LocalFirstParser
from app.reports import ReportService
from app.sale_numbering import DailySaleLedger


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase5_sale_numbering_cases.jsonl"
EVAL_WORKSPACE = ROOT_DIR / ".phase5_eval_workspace"


class EvalFallbackParser:
    def __init__(self) -> None:
        self.calls = 0

    def parse_events(self, text: str, master_drug_names: list[str]) -> ParseResult:
        self.calls += 1
        return ParseResult(events=[ParsedEvent("Fallback Medicine", Action.NOT_SOLD)])


class EvalStore:
    def __init__(self) -> None:
        self.stocks = {
            "panadol": StockItem("Panadol", selling_price=200, current_stock=20, reorder_level=5),
            "ors": StockItem("ORS", selling_price=50, current_stock=0, reorder_level=5),
            "glucose": StockItem("Glucose", selling_price=80, current_stock=10, reorder_level=3),
            "cough syrup": StockItem("Cough Syrup", selling_price=150, current_stock=8, reorder_level=2),
        }
        self.logged: list[tuple[ParsedEvent, float | None, float | None]] = []
        self.reports: dict[str, str] = {}
        self.report_rows: list[dict[str, Any]] = []

    def list_master_drug_names(self) -> list[str]:
        return [stock.drug_name for stock in self.stocks.values()]

    def find_stock(self, drug_name: str) -> StockItem | None:
        return self.stocks.get(drug_name.lower())

    def append_daily_log(self, event: ParsedEvent, price: float | None, total_value: float | None) -> None:
        self.logged.append((event, price, total_value))

    def update_current_stock(self, stock: StockItem, new_current_stock: int) -> None:
        self.stocks[stock.drug_name.lower()] = StockItem(
            stock.drug_name,
            selling_price=stock.selling_price,
            cost_price=stock.cost_price,
            current_stock=new_current_stock,
            reorder_level=stock.reorder_level,
            row_number=stock.row_number,
        )

    def get_daily_report_text(self, report_date: str) -> str | None:
        return self.reports.get(report_date)

    def read_daily_logs(self, report_date: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for event, price, total_value in self.logged:
            rows.append(
                {
                    "Date": report_date,
                    "Time": "09:00:00",
                    "Drug Name": event.drug_name,
                    "Action": event.action.value if event.action else "",
                    "Quantity": event.quantity,
                    "Price": "" if price is None else price,
                    "Total Value": "" if total_value is None else total_value,
                    "Notes": event.notes,
                }
            )
        return rows

    def append_daily_report(self, report_row: dict[str, Any]) -> None:
        self.report_rows.append(report_row)
        report_date = str(report_row.get("Date") or "")
        report_text = str(report_row.get("Full Report Text") or "")
        if report_date and report_text:
            self.reports[report_date] = report_text

    def list_low_stock_items(self) -> list[StockItem]:
        return [
            stock
            for stock in self.stocks.values()
            if stock.current_stock is not None
            and stock.reorder_level is not None
            and stock.current_stock <= stock.reorder_level
        ]


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = row["case"]
        errors = CASES[case]()
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_ledger_reset_by_date() -> list[str]:
    ledger = make_ledger("reset")
    ledger.record_sale("2026-06-11", drug_name="Panadol", quantity=1, price=200, total_value=200)
    errors: list[str] = []
    if ledger.preview_next_sale_number("2026-06-11") != 2:
        errors.append("same-day next sale was not #2")
    if ledger.preview_next_sale_number("2026-06-12") != 1:
        errors.append("next day did not reset to #1")
    return errors


def case_parser_sale_number_commands() -> list[str]:
    fallback = EvalFallbackParser()
    parser = LocalFirstParser(fallback)
    show = parser.parse_events("show sale 12", [])
    count = parser.parse_events("today sale count", [])
    errors: list[str] = []
    if fallback.calls != 0:
        errors.append(f"fallback called {fallback.calls} times")
    if show.events[0].action != Action.SHOW_SALE:
        errors.append("show sale did not map to SHOW_SALE")
    if count.events[0].action != Action.SALE_COUNT:
        errors.append("sale count did not map to SALE_COUNT")
    return errors


def case_sale_flow_assigns_numbers() -> list[str]:
    store, ledger, service = make_service("assign")
    first = service.process_text("panadol2cash")
    second = service.process_text("panadol2cash")
    errors: list[str] = []
    if "Sale #1:" not in first:
        errors.append(f"first reply missing Sale #1: {first}")
    if "Sale #2:" not in second:
        errors.append(f"second reply missing Sale #2: {second}")
    if "Sale #1" not in store.logged[0][0].notes or "Sale #2" not in store.logged[1][0].notes:
        errors.append("daily log notes missing sale numbers")
    if ledger.sale_count(current_sale_date(service.timezone)) != 2:
        errors.append("ledger sale count was not 2")
    return errors


def case_undo_by_sale_number() -> list[str]:
    store, ledger, service = make_service("undo")
    service.process_text("panadol2cash")
    reply = service.process_text("undo sale 1")
    sale = ledger.get_sale(current_sale_date(service.timezone), 1).record
    errors: list[str] = []
    if "Undone sale #1" not in reply:
        errors.append(f"undo reply unexpected: {reply}")
    if sale["status"] != "undone":
        errors.append("ledger status not undone")
    if store.stocks["panadol"].current_stock != 20:
        errors.append(f"stock not restored: {store.stocks['panadol'].current_stock}")
    return errors


def case_undo_last_sale_restores_stock() -> list[str]:
    store, ledger, service = make_service("undo_last")
    service.process_text("panadol2cash")
    service.process_text("panadol2cash")
    reply = service.process_text("undo last sale")
    sale_date = current_sale_date(service.timezone)
    first_sale = ledger.get_sale(sale_date, 1).record
    second_sale = ledger.get_sale(sale_date, 2).record
    errors: list[str] = []
    if "Undone sale #2" not in reply:
        errors.append(f"undo last reply unexpected: {reply}")
    if first_sale["status"] != "active" or second_sale["status"] != "undone":
        errors.append("undo last did not target latest active sale")
    if store.stocks["panadol"].current_stock != 18:
        errors.append(f"stock not restored to 18: {store.stocks['panadol'].current_stock}")
    return errors


def case_correction_by_sale_number() -> list[str]:
    _store, ledger, service = make_service("correct")
    service.process_text("panadol2cash")
    reply = service.process_text("correct sale 1 to mpesa")
    sale = ledger.get_sale(current_sale_date(service.timezone), 1).record
    errors: list[str] = []
    if "Corrected sale #1" not in reply:
        errors.append(f"correction reply unexpected: {reply}")
    if sale["payment"] != "mpesa":
        errors.append(f"payment not corrected: {sale['payment']}")
    if not sale["corrections"]:
        errors.append("correction audit missing")
    return errors


def case_wrong_medicine_correction() -> list[str]:
    store, ledger, service = make_service("wrong_medicine")
    service.process_text("panadol2cash")
    reply = service.process_text("correct sale 1 medicine glucose")
    sale = ledger.get_sale(current_sale_date(service.timezone), 1).record
    errors: list[str] = []
    if "Corrected sale #1" not in reply:
        errors.append(f"wrong medicine reply unexpected: {reply}")
    if sale["drug_name"] != "Glucose":
        errors.append(f"drug was not corrected: {sale['drug_name']}")
    if sale["price"] != 80 or sale["total_value"] != 160:
        errors.append(f"price/total not corrected: {sale['price']} / {sale['total_value']}")
    if store.stocks["panadol"].current_stock != 20:
        errors.append(f"old stock not restored: {store.stocks['panadol'].current_stock}")
    if store.stocks["glucose"].current_stock != 8:
        errors.append(f"new stock not deducted: {store.stocks['glucose'].current_stock}")
    return errors


def case_wrong_quantity_correction() -> list[str]:
    store, ledger, service = make_service("wrong_quantity")
    service.process_text("panadol2cash")
    reply = service.process_text("correct sale 1 quantity 1")
    sale = ledger.get_sale(current_sale_date(service.timezone), 1).record
    errors: list[str] = []
    if "Corrected sale #1" not in reply:
        errors.append(f"wrong quantity reply unexpected: {reply}")
    if sale["quantity"] != 1:
        errors.append(f"quantity was not corrected: {sale['quantity']}")
    if sale["total_value"] != 200:
        errors.append(f"total value was not corrected: {sale['total_value']}")
    if store.stocks["panadol"].current_stock != 19:
        errors.append(f"stock not reconciled: {store.stocks['panadol'].current_stock}")
    return errors


def case_wrong_payment_correction() -> list[str]:
    _store, ledger, service = make_service("wrong_payment")
    service.process_text("panadol2cash")
    reply = service.process_text("correct sale 1 to credit")
    sale = ledger.get_sale(current_sale_date(service.timezone), 1).record
    finance = ledger.finance_summary(current_sale_date(service.timezone))
    errors: list[str] = []
    if "Corrected sale #1" not in reply:
        errors.append(f"wrong payment reply unexpected: {reply}")
    if sale["payment"] != "credit":
        errors.append(f"payment was not corrected: {sale['payment']}")
    if finance["payment_totals"]["credit"] != 400 or finance["payment_totals"]["cash"] != 0:
        errors.append(f"credit/cash totals not reconciled: {finance['payment_totals']}")
    return errors


def case_finance_totals_reverse_safely() -> list[str]:
    ledger = make_ledger("finance_reverse")
    ledger.record_sale("2026-06-11", drug_name="Panadol", quantity=2, price=200, total_value=400, payment="cash")
    ledger.record_sale("2026-06-11", drug_name="Glucose", quantity=1, price=80, total_value=80, payment="mpesa")
    ledger.undo_sale("2026-06-11", 2)
    finance = ledger.finance_summary("2026-06-11")
    errors: list[str] = []
    if finance["total_sales"] != 400:
        errors.append(f"undone sale remained in total: {finance['total_sales']}")
    if finance["payment_totals"]["mpesa"] != 0:
        errors.append(f"undone mpesa remained in totals: {finance['payment_totals']}")
    if finance["active_sales"] != 1:
        errors.append(f"active sale count wrong after undo: {finance['active_sales']}")
    return errors


def case_payment_totals_reconcile_after_undo_edit() -> list[str]:
    ledger = make_ledger("payment_reconcile")
    ledger.record_sale("2026-06-11", drug_name="Panadol", quantity=2, price=200, total_value=400, payment="cash")
    ledger.record_sale("2026-06-11", drug_name="ORS", quantity=2, price=50, total_value=100, payment="mpesa")
    ledger.record_sale("2026-06-11", drug_name="Glucose", quantity=1, price=80, total_value=80, payment="credit")
    ledger.record_sale("2026-06-11", drug_name="Cough Syrup", quantity=1, price=150, total_value=150, payment="cash")
    ledger.undo_sale("2026-06-11", 2)
    ledger.correct_sale("2026-06-11", 1, {"payment": "mpesa"})
    finance = ledger.finance_summary("2026-06-11")
    expected = {"cash": 150.0, "mpesa": 400.0, "credit": 80.0, "unknown": 0.0}
    errors: list[str] = []
    if finance["payment_totals"] != expected:
        errors.append(f"payment totals mismatch: {finance['payment_totals']}")
    if finance["total_sales"] != 630:
        errors.append(f"finance total mismatch: {finance['total_sales']}")
    return errors


def case_reports_reflect_corrected_totals() -> list[str]:
    store = EvalStore()
    ledger = make_ledger("reports_corrected")
    ledger.record_sale("2026-06-11", drug_name="Panadol", quantity=2, price=200, total_value=400, payment="cash")
    ledger.record_sale("2026-06-11", drug_name="ORS", quantity=2, price=50, total_value=100, payment="mpesa")
    ledger.record_sale("2026-06-11", drug_name="Glucose", quantity=1, price=80, total_value=80, payment="credit")
    ledger.record_sale("2026-06-11", drug_name="Cough Syrup", quantity=1, price=150, total_value=150, payment="cash")
    ledger.undo_sale("2026-06-11", 2)
    ledger.correct_sale("2026-06-11", 1, {"payment": "mpesa"})
    ledger.correct_sale("2026-06-11", 3, {"quantity": 2})
    report = ReportService(store=store, sale_ledger=ledger).generate_daily_report("2026-06-11", send_whatsapp=False)
    errors: list[str] = []
    if "Total sales: Ksh 710" not in report:
        errors.append("report total did not reflect corrected ledger total")
    if "Payment totals: Cash Ksh 150, M-Pesa Ksh 400, Credit Ksh 160, Unknown Ksh 0" not in report:
        errors.append("report payment totals did not reflect corrected ledger totals")
    if "ORS - 2" in report:
        errors.append("undone sale appeared in sold/requested report totals")
    if not store.report_rows or store.report_rows[0]["Total Sales"] != 710:
        errors.append("stored daily report row did not use corrected total")
    return errors


def case_audit_history_trace() -> list[str]:
    ledger = make_ledger("audit_trace")
    ledger.record_sale(
        "2026-06-11",
        drug_name="Panadol",
        quantity=2,
        price=200,
        total_value=400,
        payment="cash",
        actor_id="owner-1",
    )
    ledger.correct_sale("2026-06-11", 1, {"payment": "credit"}, actor_id="owner-2")
    ledger.undo_sale("2026-06-11", 1, actor_id="owner-1", reason="owner reversed duplicate")
    record = ledger.get_sale("2026-06-11", 1).record
    errors: list[str] = []
    audit_types = [entry["type"] for entry in record["audit"]]
    if audit_types != ["created", "corrected", "undone"]:
        errors.append(f"audit types wrong: {audit_types}")
    if record["audit"][0]["record"]["payment"] != "cash":
        errors.append("original sale snapshot missing")
    if record["corrections"][0]["before"] != {"payment": "cash"}:
        errors.append("correction before trace missing")
    if record["audit"][2]["reversal"]["payment"] != "credit":
        errors.append("reversal trace missing corrected payment")
    return errors


def case_duplicate_reversal_blocked() -> list[str]:
    ledger = make_ledger("duplicate_reversal")
    ledger.record_sale("2026-06-11", drug_name="Panadol", quantity=1, price=200, total_value=200, payment="cash")
    first = ledger.undo_sale("2026-06-11", 1)
    second = ledger.undo_sale("2026-06-11", 1)
    record = ledger.get_sale("2026-06-11", 1).record
    errors: list[str] = []
    if not first.found:
        errors.append("first undo failed")
    if second.found or second.message != "Sale #1 is already undone.":
        errors.append(f"duplicate undo was not blocked: {second.message}")
    if [entry["type"] for entry in record["audit"]].count("undone") != 1:
        errors.append("duplicate undo created more than one reversal audit entry")
    return errors


def case_zero_ai_phase5_commands() -> list[str]:
    fallback = EvalFallbackParser()
    parser = LocalFirstParser(fallback)
    commands = [
        "undo last sale",
        "undo sale 1",
        "correct sale 1 medicine glucose",
        "correct sale 1 quantity 1",
        "correct sale 1 to credit",
        "show sale 1",
        "today sale count",
    ]
    errors: list[str] = []
    for command in commands:
        result = parser.parse_events(command, [])
        if not result.events:
            errors.append(f"no local event for command: {command}")
    if fallback.calls != 0:
        errors.append(f"fallback called {fallback.calls} times")
    return errors


def case_show_sale_and_today_count() -> list[str]:
    _store, _ledger, service = make_service("show_count")
    service.process_text("panadol2cash")
    show = service.process_text("show sale 1")
    count = service.process_text("today sale count")
    errors: list[str] = []
    if "Sale #1: Panadol x2" not in show:
        errors.append(f"show sale reply unexpected: {show}")
    if count != "Today sale count: 1.":
        errors.append(f"sale count reply unexpected: {count}")
    return errors


CASES = {
    "ledger_reset_by_date": case_ledger_reset_by_date,
    "parser_sale_number_commands": case_parser_sale_number_commands,
    "sale_flow_assigns_numbers": case_sale_flow_assigns_numbers,
    "undo_by_sale_number": case_undo_by_sale_number,
    "undo_last_sale_restores_stock": case_undo_last_sale_restores_stock,
    "correction_by_sale_number": case_correction_by_sale_number,
    "wrong_medicine_correction": case_wrong_medicine_correction,
    "wrong_quantity_correction": case_wrong_quantity_correction,
    "wrong_payment_correction": case_wrong_payment_correction,
    "finance_totals_reverse_safely": case_finance_totals_reverse_safely,
    "payment_totals_reconcile_after_undo_edit": case_payment_totals_reconcile_after_undo_edit,
    "reports_reflect_corrected_totals": case_reports_reflect_corrected_totals,
    "audit_history_trace": case_audit_history_trace,
    "duplicate_reversal_blocked": case_duplicate_reversal_blocked,
    "zero_ai_phase5_commands": case_zero_ai_phase5_commands,
    "show_sale_and_today_count": case_show_sale_and_today_count,
}


def make_service(name: str) -> tuple[EvalStore, DailySaleLedger, IntakeService]:
    store = EvalStore()
    ledger = make_ledger(name)
    service = IntakeService(
        LocalFirstParser(EvalFallbackParser()),
        store,
        sale_ledger=ledger,
    )
    return store, ledger, service


def make_ledger(name: str) -> DailySaleLedger:
    path = EVAL_WORKSPACE / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    return DailySaleLedger(path=path, pharmacy_id=name)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean:
            rows.append(json.loads(clean))
    return rows


def main() -> int:
    passed, failures = run_eval()
    if passed:
        print(f"PHASE 5 SALE NUMBERING EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 5 SALE NUMBERING EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
