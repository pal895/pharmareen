from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.domain import StockItem
from app.intake import IntakeService
from app.utils import now_in_timezone
from app.services.operational_intelligence import decide_ai_route


@dataclass(frozen=True)
class SimulationCase:
    id: str
    category: str
    text: str
    expected: str = ""
    expect_contains: tuple[str, ...] = ()
    ai_allowed: bool = False
    simulate: bool = True

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "SimulationCase":
        return cls(
            id=str(row.get("id") or ""),
            category=str(row.get("category") or "general"),
            text=str(row.get("text") or row.get("input") or ""),
            expected=str(row.get("expected") or ""),
            expect_contains=tuple(str(item) for item in row.get("expect_contains") or ()),
            ai_allowed=bool(row.get("ai_allowed", False)),
            simulate=bool(row.get("simulate", True)),
        )


@dataclass
class SimulationResult:
    case_id: str
    category: str
    ok: bool
    route: str
    used_ai: bool
    elapsed_ms: float
    reply: str
    issues: list[str] = field(default_factory=list)


@dataclass
class SimulationSummary:
    total: int
    passed: int
    failed: int
    ai_calls_allowed: int
    ai_calls_blocked: int
    average_ms: float
    results: list[SimulationResult]

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "ai_calls_allowed": self.ai_calls_allowed,
            "ai_calls_blocked": self.ai_calls_blocked,
            "average_ms": round(self.average_ms, 2),
            "results": [result.__dict__ for result in self.results],
        }


class SimulationParser:
    called = False

    def parse_events(self, text, master_drug_names):
        self.called = True
        raise AssertionError("simulation should stay local unless a case explicitly allows AI")


class SimulationStore:
    def __init__(self):
        self.today = now_in_timezone("Africa/Nairobi").date().isoformat()
        self.stocks = {
            "panadol": StockItem("Panadol", 10, 5, 800, 50, 2),
            "amoxyl": StockItem("Amoxyl", 80, 50, 120, 20, 3),
            "amox": StockItem("Amox", 80, 50, 120, 20, 4),
            "ors": StockItem("ORS", 50, 30, 90, 15, 5),
            "piriton": StockItem("Piriton", 20, 12, 100, 20, 6),
            "insulin": StockItem("Insulin", 500, 300, 12, 4, 7),
            "antacid": StockItem("Antacid", 15, 8, 70, 10, 8),
            "glucose": StockItem("Glucose", 40, 20, 4, 5, 9),
            "paracetamol": StockItem("Paracetamol", 10, 5, 500, 50, 10),
            "cetirizine": StockItem("Cetirizine", 30, 16, 80, 10, 11),
        }
        self.transactions: list[dict[str, Any]] = [
            {
                "Date": self.today,
                "Timestamp": "2026-05-17 09:10:00",
                "Type": "sale",
                "Drug": "Panadol",
                "Quantity": 14,
                "Unit Cost": 5,
                "Unit Selling Price": 10,
                "Total Cost": 70,
                "Total Sales": 140,
                "Profit": 70,
                "Note": "payment=Cash",
            },
            {
                "Date": self.today,
                "Timestamp": "2026-05-17 10:30:00",
                "Type": "sale",
                "Drug": "Amoxyl",
                "Quantity": 2,
                "Unit Cost": 50,
                "Unit Selling Price": 80,
                "Total Cost": 100,
                "Total Sales": 160,
                "Profit": 60,
                "Note": "payment=M-Pesa",
            },
            {
                "Date": self.today,
                "Timestamp": "2026-05-17 11:00:00",
                "Type": "no_stock",
                "Drug": "Insulin",
                "Quantity": 1,
                "Unit Cost": "",
                "Unit Selling Price": "",
                "Total Cost": "",
                "Total Sales": "",
                "Profit": "",
                "Note": "missed demand",
            },
        ]
        self.daily_logs: list[dict[str, Any]] = [
            {"Date": self.today, "Time": "09:10:00", "Drug Name": "Panadol", "Action": "Sold", "Quantity": 14, "Price": 10, "Total Value": 140, "Notes": ""},
            {"Date": self.today, "Time": "10:30:00", "Drug Name": "Amoxyl", "Action": "Sold", "Quantity": 2, "Price": 80, "Total Value": 160, "Notes": ""},
            {"Date": self.today, "Time": "11:00:00", "Drug Name": "Insulin", "Action": "Out of Stock", "Quantity": 1, "Price": "", "Total Value": "", "Notes": ""},
        ]

    def list_master_drug_names(self):
        return [stock.drug_name for stock in self.stocks.values()]

    def find_stock(self, drug_name):
        return self.stocks.get(str(drug_name or "").strip().lower())

    def append_daily_log(self, event, price, total_value):
        self.daily_logs.append(
            {
                "Date": self.today,
                "Time": "10:00:00",
                "Drug Name": event.drug_name,
                "Action": event.action.value if event.action else "",
                "Quantity": event.quantity,
                "Price": price or "",
                "Total Value": total_value or "",
                "Notes": event.notes,
            }
        )

    def update_current_stock(self, stock, new_current_stock):
        self.stocks[stock.drug_name.lower()] = StockItem(
            stock.drug_name,
            stock.selling_price,
            stock.cost_price,
            new_current_stock,
            stock.reorder_level,
            stock.row_number,
        )

    def update_current_stock_and_cost(self, stock, new_current_stock, new_cost_price):
        self.stocks[stock.drug_name.lower()] = StockItem(
            stock.drug_name,
            stock.selling_price,
            new_cost_price,
            new_current_stock,
            stock.reorder_level,
            stock.row_number,
        )

    def append_transaction(
        self,
        transaction_type,
        drug_name,
        quantity,
        unit_cost=None,
        unit_selling_price=None,
        total_cost=None,
        total_sales=None,
        profit=None,
        note="",
    ):
        self.transactions.append(
            {
                "Date": self.today,
                "Timestamp": "2026-05-17 10:00:00",
                "Type": transaction_type,
                "Drug": drug_name,
                "Quantity": quantity,
                "Unit Cost": unit_cost if unit_cost is not None else "",
                "Unit Selling Price": unit_selling_price if unit_selling_price is not None else "",
                "Total Cost": total_cost if total_cost is not None else "",
                "Total Sales": total_sales if total_sales is not None else "",
                "Profit": profit if profit is not None else "",
                "Note": note,
            }
        )

    def read_transactions(self, start_date, end_date=None):
        return [row for row in self.transactions if str(row.get("Date")) == str(start_date)]

    def get_daily_report_text(self, report_date):
        return None

    def read_daily_logs(self, report_date):
        return [row for row in self.daily_logs if str(row.get("Date")) == str(report_date)]

    def list_low_stock_items(self):
        return [
            stock for stock in self.stocks.values()
            if stock.current_stock is not None and stock.reorder_level is not None and stock.current_stock <= stock.reorder_level
        ]

    def append_batch(self, batch):
        return None

    def list_batches(self, drug_name=None):
        return []

    def update_batch_remaining(self, batch_id, remaining_units):
        return None


def load_cases(paths: Iterable[Path]) -> list[SimulationCase]:
    cases: list[SimulationCase] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                cases.append(SimulationCase.from_mapping(json.loads(line)))
    return cases


def load_training_cases(root: Path | str = "datasets/pharmacy_training") -> list[SimulationCase]:
    folder = Path(root)
    return load_cases(sorted(folder.glob("*.jsonl")))


def run_simulation(cases: Iterable[SimulationCase]) -> SimulationSummary:
    store = SimulationStore()
    parser = SimulationParser()
    service = IntakeService(parser, store)
    results: list[SimulationResult] = []
    total_elapsed = 0.0
    ai_calls_allowed = 0
    ai_calls_blocked = 0

    for case in cases:
        if not case.simulate:
            continue
        decision = decide_ai_route(text=case.text, message_type="text")
        used_ai = decision.use_ai
        if used_ai and case.ai_allowed:
            ai_calls_allowed += 1
        if used_ai and not case.ai_allowed:
            ai_calls_blocked += 1
        started = time.perf_counter()
        issues: list[str] = []
        try:
            conversation_id = "simulation-memory" if case.category == "memory" else f"simulation-{case.id}"
            reply = service.process_text(case.text, conversation_id=conversation_id)
        except AssertionError as exc:
            reply = str(exc)
            issues.append("parser_fallback")
        elapsed_ms = (time.perf_counter() - started) * 1000
        total_elapsed += elapsed_ms
        for expected in case.expect_contains:
            if expected.lower() not in reply.lower():
                issues.append(f"missing:{expected}")
        if used_ai and not case.ai_allowed:
            issues.append("unexpected_ai_route")
        results.append(
            SimulationResult(
                case_id=case.id,
                category=case.category,
                ok=not issues,
                route=decision.route,
                used_ai=used_ai,
                elapsed_ms=elapsed_ms,
                reply=reply,
                issues=issues,
            )
        )

    total = len(results)
    passed = sum(1 for result in results if result.ok)
    failed = total - passed
    return SimulationSummary(
        total=total,
        passed=passed,
        failed=failed,
        ai_calls_allowed=ai_calls_allowed,
        ai_calls_blocked=ai_calls_blocked,
        average_ms=(total_elapsed / total) if total else 0,
        results=results,
    )
