from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain import Action, ParsedEvent, ParseResult, StockItem
from app.intake import IntakeService
from app.local_first_parser import LocalFirstParser


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase4_workflow_cases.jsonl"


class EvalFallbackParser:
    def __init__(self) -> None:
        self.calls = 0

    def parse_events(self, text: str, master_drug_names: list[str], **_context) -> ParseResult:
        self.calls += 1
        return ParseResult(events=[ParsedEvent("Fallback Medicine", Action.NOT_SOLD)])


class StaticParser:
    def __init__(self, event: ParsedEvent) -> None:
        self.event = event
        self.called = False

    def parse_events(self, text: str, master_drug_names: list[str], **_context) -> ParseResult:
        self.called = True
        return ParseResult(events=[self.event])


class FailingParser:
    called = False

    def parse_events(self, text: str, master_drug_names: list[str]) -> ParseResult:
        self.called = True
        raise AssertionError("report command should not call parser")


class EvalStore:
    def __init__(self) -> None:
        self.stocks = {
            "panadol": StockItem("Panadol", selling_price=200, current_stock=20, reorder_level=5),
            "ors": StockItem("ORS", selling_price=50, current_stock=0, reorder_level=5),
        }
        self.logged: list[tuple[ParsedEvent, float | None, float | None]] = []
        self.reports = {"2026-04-27": "Daily Intelligence Report - 2026-04-27"}

    def list_master_drug_names(self) -> list[str]:
        return [stock.drug_name for stock in self.stocks.values()]

    def find_stock(self, drug_name: str) -> StockItem | None:
        return self.stocks.get(drug_name.lower())

    def append_daily_log(
        self,
        event: ParsedEvent,
        price: float | None,
        total_value: float | None,
    ) -> None:
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


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, case in enumerate(load_jsonl(eval_path), start=1):
        errors = run_case(case)
        if errors:
            failures.append(f"case {index} {case['input']!r}: " + "; ".join(errors))
    return not failures, failures


def run_case(case: dict[str, Any]) -> list[str]:
    mode = case["mode"]
    if mode == "parser":
        return run_parser_case(case)
    if mode == "intake":
        return run_intake_case(case)
    if mode == "report":
        return run_report_case(case)
    return [f"unknown mode {mode!r}"]


def run_parser_case(case: dict[str, Any]) -> list[str]:
    fallback = EvalFallbackParser()
    parser = LocalFirstParser(fallback)
    result = parser.parse_events(str(case["input"]), master_drug_names=[])
    expected = case["expected"]
    errors: list[str] = []

    if fallback.calls != expected.get("fallback_calls", 0):
        errors.append(f"fallback_calls expected {expected.get('fallback_calls')}, got {fallback.calls}")
    if not result.events:
        return [*errors, "no events returned"]

    event = result.events[0]
    actual_action = event.action.value if event.action else None
    for field, actual in {
        "action": actual_action,
        "medicine_name": event.drug_name,
        "quantity": event.quantity,
    }.items():
        if field in expected and actual != expected[field]:
            errors.append(f"{field} expected {expected[field]!r}, got {actual!r}")
    if expected.get("notes_contains") and expected["notes_contains"] not in event.notes:
        errors.append(f"notes missing {expected['notes_contains']!r}")
    return errors


def run_intake_case(case: dict[str, Any]) -> list[str]:
    event_data = case["event"]
    event = ParsedEvent(
        str(event_data["drug_name"]),
        Action.from_value(event_data["action"]),
        quantity=int(event_data.get("quantity", 1)),
    )
    store = EvalStore()
    service = IntakeService(StaticParser(event), store)
    reply = service.process_text(str(case["input"]))
    expected = case["expected"]
    errors: list[str] = []

    if expected.get("reply_contains") and expected["reply_contains"] not in reply:
        errors.append(f"reply missing {expected['reply_contains']!r}: {reply!r}")
    if "logs" in expected and len(store.logged) != expected["logs"]:
        errors.append(f"logs expected {expected['logs']}, got {len(store.logged)}")
    if expected.get("logged_action"):
        if not store.logged:
            errors.append("expected a log entry")
        else:
            actual = store.logged[0][0].action.value if store.logged[0][0].action else None
            if actual != expected["logged_action"]:
                errors.append(f"logged_action expected {expected['logged_action']!r}, got {actual!r}")
    return errors


def run_report_case(case: dict[str, Any]) -> list[str]:
    parser = FailingParser()
    service = IntakeService(parser, EvalStore())
    reply = service.process_text(str(case["input"]))
    expected = case["expected"]
    errors: list[str] = []
    if expected.get("reply_contains") and expected["reply_contains"] not in reply:
        errors.append(f"reply missing {expected['reply_contains']!r}")
    if parser.called != expected.get("parser_called", False):
        errors.append(f"parser_called expected {expected.get('parser_called')}, got {parser.called}")
    return errors


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
        print(f"PHASE 4 WORKFLOW EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 4 WORKFLOW EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
