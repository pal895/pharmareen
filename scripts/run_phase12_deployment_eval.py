from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.deployment import ACTIVE, ROLLED_BACK, PharmacyDeploymentEngine
from app.live_pilot import LivePharmacyPilotEngine
from app.reliability import ProductionReliabilityEngine
from app.training_store import TrainingStore


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase12_deployment_cases.jsonl"
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
EVAL_WORKSPACE = ROOT_DIR / ".phase12_eval_workspace"


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = str(row["case"])
        errors = CASES[case]()
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_pharmacy_profile_bootstrap_and_checklist() -> list[str]:
    engine = make_engine("profile")
    result = engine.bootstrap_pharmacy_profile(
        pharmacy_name="Zuri Chemist",
        owner_id="owner-a",
        owner_phone="+254700000001",
    )
    pharmacy = engine.current_pharmacy() or {}
    errors: list[str] = []
    if not result.accepted:
        errors.append("profile bootstrap was not accepted")
    if pharmacy.get("checklist", {}).get("profile_bootstrapped", {}).get("status") != "passed":
        errors.append("profile checklist item was not passed")
    if pharmacy.get("protections", {}).get("phase2_11_regression_required") is not True:
        errors.append("locked Phase 2-11 protection missing")
    return errors


def case_medicine_import_bootstrap_tools() -> list[str]:
    engine = make_engine("medicine_import")
    engine.bootstrap_pharmacy_profile(pharmacy_name="Zuri Chemist", owner_id="owner-a")
    result = engine.import_medicines(
        [
            {"name": "Panadol", "aliases": ["panado"], "opening_stock": 20, "selling_price": 200},
            {"name": "Cetirizine", "aliases": ["cet"], "opening_stock": 10, "selling_price": 50},
            {"name": "Panadol", "opening_stock": 5},
        ],
        source="owner_csv",
    )
    pharmacy = engine.current_pharmacy() or {}
    errors: list[str] = []
    if not result.accepted:
        errors.append("medicine import failed")
    if result.record and result.record.get("imported_count") != 2:
        errors.append("imported count was not 2")
    if "panadol" not in pharmacy.get("medicine_bootstrap", {}):
        errors.append("Panadol missing from medicine bootstrap")
    if pharmacy.get("checklist", {}).get("medicines_imported", {}).get("status") != "passed":
        errors.append("medicine checklist item was not passed")
    return errors


def case_owner_setup_assistant_and_speed_optimization() -> list[str]:
    engine = make_engine("owner_setup")
    engine.bootstrap_pharmacy_profile(pharmacy_name="Zuri Chemist", owner_id="owner-a")
    assistant = engine.run_owner_setup_assistant(owner_id="owner-a", display_name="Owner A")
    speed = engine.optimize_onboarding_speed()
    errors: list[str] = []
    if not assistant.accepted:
        errors.append("owner setup assistant failed")
    if not speed.record or speed.record.get("next_step") != "branch_registered":
        errors.append("speed optimizer did not select branch registration next")
    if speed.record and int(speed.record.get("estimated_minutes_remaining") or 0) <= 0:
        errors.append("speed optimizer did not estimate remaining time")
    return errors


def case_deployment_readiness_verification() -> list[str]:
    engine = bootstrap_ready_engine("readiness")
    validation = engine.verify_deployment_readiness(mark_ready=True)
    activation = engine.activate_pharmacy(requested_by="owner-a")
    errors: list[str] = []
    if validation.get("ready") is not True:
        errors.append(f"readiness failed with blockers {validation.get('blockers')}")
    if validation.get("deployment_score") != 100:
        errors.append(f"deployment score was {validation.get('deployment_score')}")
    if not activation.accepted or (engine.current_pharmacy() or {}).get("status") != ACTIVE:
        errors.append("activation failed after readiness")
    return errors


def case_monitoring_dashboard_support_and_recovery() -> list[str]:
    engine = make_engine("support")
    engine.bootstrap_pharmacy_profile(pharmacy_name="Zuri Chemist", owner_id="owner-a")
    failure = engine.record_onboarding_failure(
        checklist_item="medicines_imported",
        description="Owner spreadsheet had no medicine names.",
        severity="high",
        evidence={"file": "owner-upload.csv"},
    )
    dashboard = engine.monitoring_dashboard()
    errors: list[str] = []
    if not failure.accepted:
        errors.append("onboarding failure was not captured")
    if not failure.record or not failure.record.get("rollback", {}).get("manual_restore_required"):
        errors.append("onboarding failure did not create recovery rollback")
    if dashboard.get("rollback_available") is not True:
        errors.append("dashboard did not expose rollback availability")
    if len(dashboard.get("open_support_tickets", [])) != 1:
        errors.append("dashboard did not expose open support ticket")
    return errors


def case_multi_pharmacy_isolation_and_branch_registration() -> list[str]:
    engine_a = make_engine("isolation", "deploy_a")
    engine_b = build_engine(engine_a.store.training_dir, "deploy_b")
    engine_a.bootstrap_pharmacy_profile(pharmacy_name="Alpha Chemist", owner_id="owner-a")
    engine_a.register_branch(branch_id="main", branch_name="Alpha Main")
    engine_a.import_medicines([{"name": "Panadol", "opening_stock": 20}])
    engine_b.bootstrap_pharmacy_profile(pharmacy_name="Beta Chemist", owner_id="owner-b")
    engine_b.register_branch(branch_id="main", branch_name="Beta Main")
    engine_b.import_medicines([{"name": "ORS", "opening_stock": 30}])
    pharmacy_a = engine_a.current_pharmacy() or {}
    pharmacy_b = engine_b.current_pharmacy() or {}
    errors: list[str] = []
    if pharmacy_a.get("branches", {}).get("main", {}).get("branch_name") != "Alpha Main":
        errors.append("pharmacy A branch missing")
    if pharmacy_b.get("branches", {}).get("main", {}).get("branch_name") != "Beta Main":
        errors.append("pharmacy B branch missing")
    if "panadol" not in pharmacy_a.get("medicine_bootstrap", {}):
        errors.append("pharmacy A medicine missing")
    if "panadol" in pharmacy_b.get("medicine_bootstrap", {}):
        errors.append("medicine leaked into pharmacy B")
    return errors


def case_activation_deactivation_and_rollback_safety() -> list[str]:
    engine = bootstrap_ready_engine("activation")
    activation = engine.activate_pharmacy(requested_by="owner-a")
    deactivation = engine.deactivate_pharmacy(reason="planned support pause", requested_by="owner-a")
    rollback_id = (engine.current_pharmacy() or {}).get("rollback_points", [{}])[0].get("id")
    rollback = engine.execute_deployment_rollback(rollback_id=rollback_id, requested_by="owner-a")
    pharmacy = engine.current_pharmacy() or {}
    actions = [entry.get("action") for entry in pharmacy.get("audit", [])]
    errors: list[str] = []
    if not activation.accepted:
        errors.append("activation failed")
    if not deactivation.accepted or deactivation.record.get("active") is not False:
        errors.append("deactivation failed")
    if not rollback.accepted or pharmacy.get("status") != ROLLED_BACK:
        errors.append("rollback failed")
    for action in ("pharmacy_activated", "pharmacy_deactivated", "deployment_rolled_back"):
        if action not in actions:
            errors.append(f"{action} audit missing")
    return errors


def case_deployment_audit_logging_and_scoring() -> list[str]:
    engine = bootstrap_ready_engine("scoring")
    validation = engine.verify_deployment_readiness(mark_ready=True)
    dashboard = engine.monitoring_dashboard()
    pharmacy = engine.current_pharmacy() or {}
    actions = [entry.get("action") for entry in pharmacy.get("audit", [])]
    errors: list[str] = []
    if validation.get("deployment_score") != 100:
        errors.append("deployment score was not 100")
    if dashboard.get("checklist_progress", {}).get("pending") != 0:
        errors.append("dashboard checklist still has pending items")
    if "medicine_bootstrap_imported" not in actions:
        errors.append("medicine import audit missing")
    if "deployment_readiness_verified" not in actions:
        errors.append("readiness audit missing")
    return errors


def case_token_monitoring_blocks_activation() -> list[str]:
    engine = bootstrap_ready_engine("token_block")
    engine.record_token_observation(source="known_sale", known_flow=True, tokens_used=1)
    validation = engine.verify_deployment_readiness()
    activation = engine.activate_pharmacy(requested_by="owner-a")
    errors: list[str] = []
    if validation.get("ready") is True:
        errors.append("readiness passed despite known-flow token violation")
    if "known_flow_token_violation" not in validation.get("blockers", []):
        errors.append("token violation blocker missing")
    if activation.accepted:
        errors.append("activation succeeded despite token violation")
    return errors


CASES = {
    "pharmacy_profile_bootstrap_and_checklist": case_pharmacy_profile_bootstrap_and_checklist,
    "medicine_import_bootstrap_tools": case_medicine_import_bootstrap_tools,
    "owner_setup_assistant_and_speed_optimization": case_owner_setup_assistant_and_speed_optimization,
    "deployment_readiness_verification": case_deployment_readiness_verification,
    "monitoring_dashboard_support_and_recovery": case_monitoring_dashboard_support_and_recovery,
    "multi_pharmacy_isolation_and_branch_registration": case_multi_pharmacy_isolation_and_branch_registration,
    "activation_deactivation_and_rollback_safety": case_activation_deactivation_and_rollback_safety,
    "deployment_audit_logging_and_scoring": case_deployment_audit_logging_and_scoring,
    "token_monitoring_blocks_activation": case_token_monitoring_blocks_activation,
}


def bootstrap_ready_engine(name: str = "ready") -> PharmacyDeploymentEngine:
    engine = make_engine(name)
    engine.bootstrap_pharmacy_profile(
        pharmacy_name="Zuri Chemist",
        owner_id="owner-a",
        owner_phone="+254700000001",
    )
    engine.run_owner_setup_assistant(owner_id="owner-a", display_name="Owner A")
    engine.register_branch(branch_id="main", branch_name="Main Branch", location="Nairobi")
    engine.import_medicines(
        [
            {"name": "Panadol", "aliases": ["panado"], "opening_stock": 20, "selling_price": 200},
            {"name": "Cetirizine", "aliases": ["cet"], "opening_stock": 10, "selling_price": 50},
        ]
    )
    engine.verify_reliability_protections()
    engine.record_pilot_safety_validation(ready=True, evidence={"phase11": "ready_for_production"})
    engine.prepare_deployment_rollback(reason="standard deployment safety point", requested_by="owner-a")
    engine.enable_live_monitoring(channels=["dashboard", "audit_log"])
    engine.record_token_observation(source="deployment_eval", known_flow=True, tokens_used=0)
    return engine


def make_engine(name: str, pharmacy_id: str = "deploy_a") -> PharmacyDeploymentEngine:
    training_dir = EVAL_WORKSPACE / name / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    reset_ledgers(training_dir)
    return build_engine(training_dir, pharmacy_id)


def build_engine(training_dir: Path, pharmacy_id: str) -> PharmacyDeploymentEngine:
    store = TrainingStore(training_dir=training_dir, pharmacy_id=pharmacy_id)
    reliability = ProductionReliabilityEngine(
        ledger_path=training_dir / "reliability_ledger.json",
        store=store,
        pharmacy_id=pharmacy_id,
    )
    pilot = LivePharmacyPilotEngine(
        ledger_path=training_dir / "live_pilot_ledger.json",
        store=store,
        reliability_engine=reliability,
        pharmacy_id=pharmacy_id,
    )
    return PharmacyDeploymentEngine(
        ledger_path=training_dir / "deployment_ledger.json",
        store=store,
        reliability_engine=reliability,
        pilot_engine=pilot,
        pharmacy_id=pharmacy_id,
    )


def reset_ledgers(training_dir: Path) -> None:
    (training_dir / "deployment_ledger.json").write_text('{"version": 1, "pharmacies": {}}\n', encoding="utf-8")
    (training_dir / "reliability_ledger.json").write_text('{"version": 1, "pharmacies": {}}\n', encoding="utf-8")
    (training_dir / "live_pilot_ledger.json").write_text(
        '{"version": 1, "active_pharmacy_id": null, "pharmacies": {}}\n',
        encoding="utf-8",
    )


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
        print(f"PHASE 12 DEPLOYMENT EVAL: PASS ({EVAL_PATH})")
        return 0

    print(f"PHASE 12 DEPLOYMENT EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
