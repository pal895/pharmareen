from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.reliability import APPLIED, DEAD_LETTER, QUEUED, ProductionReliabilityEngine, SyncEnvelope
from app.training_store import TrainingStore


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase10_reliability_cases.jsonl"
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
EVAL_WORKSPACE = ROOT_DIR / ".phase10_eval_workspace"


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = str(row["case"])
        errors = CASES[case]()
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_offline_queue_persists() -> list[str]:
    engine = make_engine("persist")
    result = engine.enqueue(
        SyncEnvelope(source="offline_pwa", source_message_id="offline-1", payload={"text": "panadol2cash"})
    )
    restarted = ProductionReliabilityEngine(
        ledger_path=engine.ledger_path,
        store=engine.store,
        pharmacy_id="pharmacy_eval",
    )
    errors: list[str] = []
    if not result.accepted:
        errors.append("offline queue item was not accepted")
    if len(restarted.due_items()) != 1:
        errors.append("queued item was not recovered after restart")
    return errors


def case_duplicate_prevention() -> list[str]:
    engine = make_engine("duplicate")
    envelope = SyncEnvelope(source="offline_pwa", source_message_id="dupe", payload={"text": "panadol2cash"})
    first = engine.enqueue(envelope)
    second = engine.enqueue(envelope)
    errors: list[str] = []
    if not first.accepted:
        errors.append("first enqueue failed")
    if not second.duplicate:
        errors.append("duplicate was not detected")
    if len(engine.all_items()) != 1:
        errors.append("duplicate created extra queue record")
    return errors


def case_whatsapp_offline_sync_safety() -> list[str]:
    engine = make_engine("sync_safety")
    payload = {"text": "panadol2cash", "sale_number": 1}
    engine.enqueue(
        SyncEnvelope(source="offline_pwa", idempotency_key="sale-1", payload=payload)
    )
    engine.mark_applied("sale-1", confirmation="Sale #1 synced")
    duplicate = engine.enqueue(
        SyncEnvelope(source="whatsapp_bridge", idempotency_key="sale-1", payload=payload)
    )
    errors: list[str] = []
    if not duplicate.duplicate:
        errors.append("WhatsApp/offline duplicate was not blocked")
    if engine.all_items()[0]["status"] != APPLIED:
        errors.append("applied record changed after duplicate")
    return errors


def case_reconnect_recovery() -> list[str]:
    engine = make_engine("reconnect")
    old = datetime(2026, 6, 12, 8, tzinfo=timezone.utc)
    current = old + timedelta(minutes=10)
    result = engine.enqueue(
        SyncEnvelope(source="offline_pwa", source_message_id="stale", payload={"text": "panadol2cash"})
    )
    engine.mark_inflight(result.record["idempotency_key"], now=old)
    recovered = engine.recover_after_reconnect(now=current)
    errors: list[str] = []
    if len(recovered) != 1:
        errors.append("stale inflight item was not recovered")
    elif recovered[0]["status"] != QUEUED:
        errors.append(f"recovered item status was {recovered[0]['status']}")
    return errors


def case_failed_sync_retry_safety() -> list[str]:
    engine = make_engine("retry")
    result = engine.enqueue(
        SyncEnvelope(source="offline_pwa", source_message_id="retry", payload={"text": "panadol2cash"})
    )
    key = result.record["idempotency_key"]
    engine.mark_inflight(key)
    retry_record = engine.mark_failed(key, "temporary outage", retryable=True)
    engine.mark_inflight(key)
    engine.mark_failed(key, "temporary outage", retryable=True)
    engine.mark_inflight(key)
    dead = engine.mark_failed(key, "temporary outage", retryable=True)
    errors: list[str] = []
    if retry_record["status"] != "retry":
        errors.append("first failure did not enter retry state")
    if dead["status"] != DEAD_LETTER:
        errors.append("max retries did not dead-letter safely")
    if engine.no_data_loss_report()["dead_letter"] != 1:
        errors.append("dead-letter evidence missing from no-data-loss report")
    return errors


def case_grouped_confirmation_handling() -> list[str]:
    engine = make_engine("grouped")
    first = engine.enqueue(
        SyncEnvelope(source="offline_pwa", source_message_id="1", group_id="batch", payload={"text": "panadol2cash"})
    )
    engine.enqueue(
        SyncEnvelope(source="offline_pwa", source_message_id="2", group_id="batch", payload={"text": "glucose2cash"})
    )
    third = engine.enqueue(
        SyncEnvelope(source="offline_pwa", source_message_id="3", group_id="batch", payload={"text": "ors9"})
    )
    engine.mark_applied(first.record["idempotency_key"])
    engine.mark_inflight(third.record["idempotency_key"])
    engine.mark_failed(third.record["idempotency_key"], "bad payload", retryable=False)
    confirmation = engine.grouped_confirmation("batch")
    return [] if confirmation == "1 synced, 1 waiting, 1 need review." else [f"unexpected confirmation {confirmation!r}"]


def case_low_network_behavior() -> list[str]:
    engine = make_engine("low_network")
    for index in range(5):
        engine.enqueue(
            SyncEnvelope(
                source="offline_pwa",
                source_message_id=f"low-{index}",
                payload={"text": f"panadol{index + 1}cash"},
            )
        )
    ack = engine.low_network_ack()
    return [] if ack == "Saved offline. It will sync when connection improves." else [f"unexpected low-network ack {ack!r}"]


def case_no_data_loss_guarantee() -> list[str]:
    engine = make_engine("no_data_loss")
    result = engine.enqueue(
        SyncEnvelope(source="offline_pwa", idempotency_key="conflict", payload={"text": "panadol1cash"})
    )
    engine.enqueue(
        SyncEnvelope(source="offline_pwa", idempotency_key="conflict", payload={"text": "glucose1cash"})
    )
    engine.mark_inflight(result.record["idempotency_key"])
    engine.mark_failed(result.record["idempotency_key"], "permanent failure", retryable=False)
    report = engine.no_data_loss_report()
    errors: list[str] = []
    if report["total_records"] != 1:
        errors.append("original record missing")
    if report["dead_letter"] != 1:
        errors.append("dead-letter record missing")
    if report["conflict"] != 1:
        errors.append("conflict evidence missing")
    return errors


CASES = {
    "offline_queue_persists": case_offline_queue_persists,
    "duplicate_prevention": case_duplicate_prevention,
    "whatsapp_offline_sync_safety": case_whatsapp_offline_sync_safety,
    "reconnect_recovery": case_reconnect_recovery,
    "failed_sync_retry_safety": case_failed_sync_retry_safety,
    "grouped_confirmation_handling": case_grouped_confirmation_handling,
    "low_network_behavior": case_low_network_behavior,
    "no_data_loss_guarantee": case_no_data_loss_guarantee,
}


def make_engine(name: str) -> ProductionReliabilityEngine:
    training_dir = EVAL_WORKSPACE / name / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    ledger_path = training_dir / "reliability_ledger.json"
    ledger_path.write_text('{"version": 1, "pharmacies": {}}\n', encoding="utf-8")
    store = TrainingStore(training_dir=training_dir, pharmacy_id="pharmacy_eval")
    return ProductionReliabilityEngine(ledger_path=ledger_path, store=store, pharmacy_id="pharmacy_eval")


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
        print(f"PHASE 10 RELIABILITY EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 10 RELIABILITY EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
