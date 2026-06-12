from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.live_pilot import (
    LIVE_RETRAINING_EXAMPLES_FILE,
    READY_FOR_PRODUCTION,
    LivePharmacyPilotEngine,
)
from app.reliability import ProductionReliabilityEngine
from app.training_store import TrainingStore


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase11_live_pilot_cases.jsonl"
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
EVAL_WORKSPACE = ROOT_DIR / ".phase11_eval_workspace"


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = str(row["case"])
        errors = CASES[case]()
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_one_pharmacy_at_a_time_rollout() -> list[str]:
    engine_a = make_engine("one_at_a_time", "pilot_a")
    start_a = engine_a.start_pilot(owner_id="owner-a")
    engine_b = make_engine_from_existing(engine_a, "pilot_b")
    start_b = engine_b.start_pilot(owner_id="owner-b")
    errors: list[str] = []
    if not start_a.accepted:
        errors.append("first pilot did not start")
    if start_b.accepted or "one_pharmacy_at_a_time" not in start_b.blockers:
        errors.append("second active pharmacy was not blocked")
    if engine_a.active_pharmacy_id() != "pilot_a":
        errors.append("active pilot pharmacy changed unexpectedly")
    return errors


def case_telemetry_evidence_and_reliability_logging() -> list[str]:
    engine = make_engine("telemetry")
    engine.start_pilot(owner_id="owner-a")
    first = engine.record_live_event(
        event_type="sale",
        source="offline_pwa",
        workflow_id="whatsapp_deterministic_sale",
        payload={"text": "panadol2cash", "sale_number": 1},
        evidence=evidence(),
        idempotency_key="sale-1",
        source_message_id="offline-1",
        group_id="pilot-group",
    )
    second = engine.record_live_event(
        event_type="sale",
        source="whatsapp_bridge",
        workflow_id="whatsapp_deterministic_sale",
        payload={"text": "panadol2cash", "sale_number": 1},
        evidence=evidence(),
        idempotency_key="sale-1",
        source_message_id="wa-1",
        group_id="pilot-group",
    )
    pilot = engine.current_pilot() or {}
    errors: list[str] = []
    if not first.accepted:
        errors.append("telemetry was not accepted")
    if not second.record or second.record.get("reliability", {}).get("duplicate") is not True:
        errors.append("duplicate prevention evidence missing from telemetry")
    if len(pilot.get("telemetry", [])) != 2:
        errors.append("telemetry log count incorrect")
    if pilot.get("telemetry", [{}])[0].get("missing_evidence"):
        errors.append("complete evidence was marked missing")
    return errors


def case_live_issue_creates_retraining_example() -> list[str]:
    engine = make_engine("issue")
    engine.start_pilot(owner_id="owner-a")
    issue = engine.capture_issue(
        issue_type="wrong_quantity",
        severity="high",
        source="offline_pwa",
        description="Owner corrected quantity during live pilot.",
        evidence={
            **evidence("fail"),
            "expected_reply": "Correct sale #1 quantity to 1.",
        },
    )
    rows = retraining_rows(engine)
    errors: list[str] = []
    if not issue.accepted:
        errors.append("issue was not captured")
    if not rows:
        errors.append("retraining example was not written")
    elif rows[0].get("issue_type") != "wrong_quantity":
        errors.append("wrong retraining issue type")
    return errors


def case_owner_correction_learns_in_pharmacy_namespace() -> list[str]:
    engine = make_engine("correction", "pilot_a")
    engine.start_pilot(owner_id="owner-a")
    result = engine.apply_owner_correction("zedtab means cetirizine", owner_id="owner-a")
    other_store = TrainingStore(training_dir=engine.store.training_dir, pharmacy_id="pilot_b")
    errors: list[str] = []
    if not result.accepted:
        errors.append("owner correction was not learned")
    if engine.store.pharmacy_memory().get("medicine_aliases", {}).get("zedtab") != "Cetirizine":
        errors.append("pilot pharmacy alias missing")
    if "zedtab" in other_store.pharmacy_memory().get("medicine_aliases", {}):
        errors.append("alias leaked into another pharmacy namespace")
    return errors


def case_known_flow_token_monitoring() -> list[str]:
    engine = make_engine("tokens")
    engine.start_pilot(owner_id="owner-a")
    event = engine.record_live_event(
        event_type="sale",
        source="whatsapp_bridge",
        workflow_id="whatsapp_deterministic_sale",
        payload={"text": "panadol2cash"},
        evidence={**evidence(), "token_observation": "unexpected_ai"},
        known_flow=True,
        tokens_used=2,
        idempotency_key="token-sale",
    )
    validation = engine.validate_production_readiness()
    errors: list[str] = []
    if not event.record or event.record.get("token_violation") is not True:
        errors.append("known-flow token violation was not flagged")
    if validation.get("ready") is True:
        errors.append("readiness passed despite token violation")
    if "known_flow_token_violation" not in validation.get("blockers", []):
        errors.append("token violation blocker missing")
    if not retraining_rows(engine):
        errors.append("token violation did not create retraining evidence")
    return errors


def case_rollback_recovery_safety() -> list[str]:
    engine = make_engine("rollback")
    engine.start_pilot(owner_id="owner-a")
    engine.record_live_event(
        event_type="sale",
        source="offline_pwa",
        workflow_id="offline_tap_talk_offline",
        payload={"text": "panadol2cash"},
        evidence=evidence(),
        idempotency_key="rollback-sale",
    )
    rollback = engine.prepare_rollback(reason="owner requested rollback", requested_by="owner-a")
    errors: list[str] = []
    if not rollback.accepted or not rollback.record:
        errors.append("rollback point was not prepared")
        return errors
    if rollback.record.get("reliability_report", {}).get("total_records") != 1:
        errors.append("rollback reliability snapshot missing")
    if rollback.record.get("duplicate_prevention_supported") is not True:
        errors.append("duplicate prevention was not declared on rollback")
    if rollback.record.get("offline_recovery_supported") is not True:
        errors.append("offline recovery was not declared on rollback")
    return errors


def case_owner_feedback_and_friction_tracking() -> list[str]:
    engine = make_engine("feedback")
    engine.start_pilot(owner_id="owner-a")
    feedback = engine.capture_owner_feedback(owner_id="owner-a", rating=4, comment="Works, network slow.")
    friction = engine.track_workflow_friction(
        workflow_id="offline_media_queue_online_offline",
        step="reconnect",
        severity="medium",
        detail="Sync took longer than expected.",
        evidence={"connection": "low"},
    )
    pilot = engine.current_pilot() or {}
    errors: list[str] = []
    if not feedback.accepted:
        errors.append("owner feedback was not accepted")
    if not friction.accepted:
        errors.append("workflow friction was not accepted")
    if len(pilot.get("feedback", [])) != 1:
        errors.append("owner feedback missing from pilot ledger")
    if len(pilot.get("friction", [])) != 1:
        errors.append("workflow friction missing from pilot ledger")
    return errors


def case_pilot_stability_and_readiness_validation() -> list[str]:
    engine = make_engine("readiness")
    engine.start_pilot(owner_id="owner-a")
    engine.record_live_event(
        event_type="sale",
        source="offline_pwa",
        workflow_id="whatsapp_deterministic_sale",
        payload={"text": "panadol2cash"},
        evidence=evidence(),
        known_flow=True,
        tokens_used=0,
        idempotency_key="ready-sale",
    )
    engine.capture_owner_feedback(owner_id="owner-a", rating=5, comment="Ready.")
    engine.prepare_rollback(reason="standard safety point", requested_by="owner-a")
    score = engine.stability_score()
    validation = engine.validate_production_readiness(mark_ready=True)
    errors: list[str] = []
    if score.get("score") != 100:
        errors.append(f"unexpected stability score {score.get('score')}")
    if validation.get("ready") is not True:
        errors.append(f"readiness failed with blockers {validation.get('blockers')}")
    if (engine.current_pilot() or {}).get("status") != READY_FOR_PRODUCTION:
        errors.append("pilot was not marked ready for production")
    return errors


CASES = {
    "one_pharmacy_at_a_time_rollout": case_one_pharmacy_at_a_time_rollout,
    "telemetry_evidence_and_reliability_logging": case_telemetry_evidence_and_reliability_logging,
    "live_issue_creates_retraining_example": case_live_issue_creates_retraining_example,
    "owner_correction_learns_in_pharmacy_namespace": case_owner_correction_learns_in_pharmacy_namespace,
    "known_flow_token_monitoring": case_known_flow_token_monitoring,
    "rollback_recovery_safety": case_rollback_recovery_safety,
    "owner_feedback_and_friction_tracking": case_owner_feedback_and_friction_tracking,
    "pilot_stability_and_readiness_validation": case_pilot_stability_and_readiness_validation,
}


def make_engine(name: str, pharmacy_id: str = "pilot_a") -> LivePharmacyPilotEngine:
    training_dir = EVAL_WORKSPACE / name / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    (training_dir / "live_pilot_ledger.json").write_text(
        '{"version": 1, "active_pharmacy_id": null, "pharmacies": {}}\n',
        encoding="utf-8",
    )
    (training_dir / "reliability_ledger.json").write_text(
        '{"version": 1, "pharmacies": {}}\n',
        encoding="utf-8",
    )
    retraining_path = training_dir / LIVE_RETRAINING_EXAMPLES_FILE
    if retraining_path.exists():
        retraining_path.unlink()
    store = TrainingStore(training_dir=training_dir, pharmacy_id=pharmacy_id)
    reliability = ProductionReliabilityEngine(
        ledger_path=training_dir / "reliability_ledger.json",
        store=store,
        pharmacy_id=pharmacy_id,
    )
    return LivePharmacyPilotEngine(
        ledger_path=training_dir / "live_pilot_ledger.json",
        store=store,
        reliability_engine=reliability,
        pharmacy_id=pharmacy_id,
    )


def make_engine_from_existing(engine: LivePharmacyPilotEngine, pharmacy_id: str) -> LivePharmacyPilotEngine:
    store = TrainingStore(training_dir=engine.store.training_dir, pharmacy_id=pharmacy_id)
    reliability = ProductionReliabilityEngine(
        ledger_path=engine.store.training_dir / "reliability_ledger.json",
        store=store,
        pharmacy_id=pharmacy_id,
    )
    return LivePharmacyPilotEngine(
        ledger_path=engine.ledger_path,
        store=store,
        reliability_engine=reliability,
        pharmacy_id=pharmacy_id,
    )


def evidence(pass_fail: str = "pass") -> dict[str, str]:
    return {
        "input_sent": "panadol2cash",
        "actual_reply": "Sale #1 saved",
        "pass_fail": pass_fail,
        "token_observation": "zero_ai",
    }


def retraining_rows(engine: LivePharmacyPilotEngine) -> list[dict[str, Any]]:
    path = engine.store.training_dir / LIVE_RETRAINING_EXAMPLES_FILE
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
        print(f"PHASE 11 LIVE PILOT EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 11 LIVE PILOT EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
