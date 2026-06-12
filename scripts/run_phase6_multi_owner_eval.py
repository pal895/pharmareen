from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.actor_context import ActorContext
from app.correction_learning import CorrectionLearningEngine
from app.domain import Action, ParsedEvent, ParseResult, StockItem
from app.intake import IntakeService, current_sale_date
from app.local_first_parser import LocalFirstParser
from app.medicine_brain import MATCHED, MedicineBrain
from app.reports import ReportService
from app.sale_numbering import DailySaleLedger
from app.training_store import TrainingStore


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase6_multi_owner_staff_cases.jsonl"
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
EVAL_WORKSPACE = ROOT_DIR / ".phase6_eval_workspace"


class EvalFallbackParser:
    def __init__(self) -> None:
        self.calls = 0

    def parse_events(self, text: str, master_drug_names: list[str]) -> ParseResult:
        self.calls += 1
        return ParseResult(events=[ParsedEvent("Fallback Medicine", Action.NOT_SOLD)])


class StaticParser:
    def __init__(self, event: ParsedEvent) -> None:
        self.event = event

    def parse_events(self, text: str, master_drug_names: list[str], **_context) -> ParseResult:
        return ParseResult(events=[self.event])


class EvalStore:
    def __init__(self) -> None:
        self.stocks = {
            "panadol": StockItem("Panadol", selling_price=200, current_stock=20, reorder_level=5),
            "glucose": StockItem("Glucose", selling_price=80, current_stock=10, reorder_level=3),
        }
        self.logged: list[tuple[ParsedEvent, float | None, float | None]] = []

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
        return None


class EvalReportStore:
    def __init__(self) -> None:
        self.report_rows: list[dict[str, Any]] = []

    def read_daily_logs(self, report_date: str) -> list[dict[str, Any]]:
        return []

    def append_daily_report(self, report_row: dict[str, Any]) -> None:
        self.report_rows.append(report_row)

    def list_low_stock_items(self) -> list[StockItem]:
        return []


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = row["case"]
        errors = CASES[case]()
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_pharmacy_namespace_isolation() -> list[str]:
    store_a = make_training_store("namespace", pharmacy_id="pharmacy_a")
    store_b = TrainingStore(training_dir=store_a.training_dir, pharmacy_id="pharmacy_b")
    CorrectionLearningEngine(store_a).apply("zpn means panadol", owner_id="owner-a")
    match_a = MedicineBrain(store_a).analyze("zpn2cash")
    match_b = MedicineBrain(store_b).analyze("zpn2cash")
    errors: list[str] = []
    if match_a.status != MATCHED or match_a.medicine_name != "Panadol":
        errors.append("pharmacy A did not learn alias")
    if match_b.status == MATCHED:
        errors.append("pharmacy B inherited pharmacy A alias")
    return errors


def case_staff_correction_pending() -> list[str]:
    store = make_training_store("pending", pharmacy_id="pharmacy_a")
    engine = CorrectionLearningEngine(store)
    result = engine.apply(
        "zzb means brufen",
        actor_context=ActorContext(pharmacy_id="pharmacy_a", actor_id="cashier-1", role="cashier"),
    )
    memory = store.pharmacy_memory()
    errors: list[str] = []
    if result.learned or not result.pending_approval:
        errors.append("staff correction was not held for owner approval")
    if result.correction_id != "pending-1":
        errors.append(f"unexpected correction id {result.correction_id}")
    if "zzb" in memory["medicine_aliases"]:
        errors.append("pending staff correction leaked into approved memory")
    if memory["pending_corrections"][0]["staff_id"] != "cashier-1":
        errors.append("pending correction missing staff id")
    return errors


def case_owner_approval_pharmacy_wide() -> list[str]:
    store = make_training_store("approval", pharmacy_id="pharmacy_a")
    engine = CorrectionLearningEngine(store)
    pending = engine.apply(
        "zzb means brufen",
        actor_context=ActorContext(pharmacy_id="pharmacy_a", actor_id="cashier-1", role="staff"),
    )
    approved = engine.approve_pending(str(pending.correction_id), owner_id="owner-1")
    followup = MedicineBrain(store).analyze("zzb2cash")
    memory = store.pharmacy_memory()
    errors: list[str] = []
    if not approved.learned:
        errors.append("owner approval did not commit learning")
    if followup.status != MATCHED or followup.medicine_name != "Brufen":
        errors.append("approved alias did not become pharmacy-wide")
    if memory["pending_corrections"][0]["status"] != "approved":
        errors.append("pending correction not marked approved")
    if memory["entries"][-2].get("approved_by_owner_id") != "owner-1":
        errors.append("approved learning missing owner trace")
    return errors


def case_staff_actions_traceable() -> list[str]:
    store = EvalStore()
    ledger = make_ledger("staff_actions")
    sale_service = IntakeService(
        StaticParser(ParsedEvent("Panadol", Action.SOLD, quantity=2, notes="Payment: Cash")),
        store,
        sale_ledger=ledger,
    )
    correction_service = IntakeService(
        StaticParser(ParsedEvent("Workflow", Action.CORRECTION_REQUEST, notes="Target sale: 1; Payment: M-Pesa")),
        store,
        sale_ledger=ledger,
    )
    sale_service.process_text(
        "panadol2cash",
        actor_context=ActorContext(actor_id="cashier-1", role="cashier", source="whatsapp"),
    )
    correction_service.process_text(
        "correct sale 1 to mpesa",
        actor_context=ActorContext(actor_id="owner-1", role="owner", source="whatsapp"),
    )
    sale = ledger.get_sale(current_sale_date(sale_service.timezone), 1).record
    errors: list[str] = []
    if sale.get("actor_id") != "cashier-1" or sale.get("actor_role") != "cashier":
        errors.append("sale missing staff actor trace")
    if sale["audit"][1].get("actor_id") != "owner-1" or sale["audit"][1].get("actor_role") != "owner":
        errors.append("correction missing owner actor trace")
    return errors


def case_reports_remain_accurate() -> list[str]:
    ledger = make_ledger("reports")
    ledger.record_sale(
        "2026-06-11",
        drug_name="Panadol",
        quantity=2,
        price=200,
        total_value=400,
        payment="cash",
        actor_id="cashier-1",
        actor_role="cashier",
    )
    ledger.record_sale(
        "2026-06-11",
        drug_name="Glucose",
        quantity=1,
        price=80,
        total_value=80,
        payment="credit",
        actor_id="staff-2",
        actor_role="staff",
    )
    ledger.correct_sale("2026-06-11", 1, {"payment": "mpesa"}, actor_id="owner-1", actor_role="owner")
    ledger.undo_sale("2026-06-11", 2, actor_id="owner-1", actor_role="owner")
    report_store = EvalReportStore()
    report = ReportService(store=report_store, sale_ledger=ledger).generate_daily_report(
        "2026-06-11",
        send_whatsapp=False,
    )
    errors: list[str] = []
    if "Total sales: Ksh 400" not in report:
        errors.append("report total did not use active ledger state")
    if "Payment totals: Cash Ksh 0, M-Pesa Ksh 400, Credit Ksh 0, Unknown Ksh 0" not in report:
        errors.append("report payment totals did not reconcile")
    if report_store.report_rows[0]["Total Sales"] != 400:
        errors.append("stored report row total incorrect")
    return errors


def case_zero_ai_staff_learning() -> list[str]:
    store = make_training_store("zero_ai", pharmacy_id="pharmacy_a")
    fallback = EvalFallbackParser()
    parser = LocalFirstParser(
        fallback,
        brain=MedicineBrain(store),
        learning_engine=CorrectionLearningEngine(store),
    )
    result = parser.parse_events(
        "zzb means brufen",
        master_drug_names=[],
        actor_context=ActorContext(pharmacy_id="pharmacy_a", actor_id="cashier-1", role="cashier"),
    )
    errors: list[str] = []
    if fallback.calls != 0:
        errors.append(f"fallback called {fallback.calls} times")
    if not result.needs_clarification or "owner approval" not in str(result.clarification_question):
        errors.append("staff learning did not return local pending approval reply")
    if not store.pending_corrections():
        errors.append("pending correction not saved")
    return errors


CASES = {
    "pharmacy_namespace_isolation": case_pharmacy_namespace_isolation,
    "staff_correction_pending": case_staff_correction_pending,
    "owner_approval_pharmacy_wide": case_owner_approval_pharmacy_wide,
    "staff_actions_traceable": case_staff_actions_traceable,
    "reports_remain_accurate": case_reports_remain_accurate,
    "zero_ai_staff_learning": case_zero_ai_staff_learning,
}


def make_training_store(name: str, pharmacy_id: str) -> TrainingStore:
    training_dir = EVAL_WORKSPACE / name / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    (training_dir / "corrections.json").write_text('{"version": 1, "pharmacies": {}}\n')
    (training_dir / "feedback_log.jsonl").write_text("")
    return TrainingStore(training_dir=training_dir, pharmacy_id=pharmacy_id)


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
        print(f"PHASE 6 MULTI-OWNER STAFF EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 6 MULTI-OWNER STAFF EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
