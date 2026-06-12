from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.provisioning import (
    INFRASTRUCTURE_NAMESPACES,
    STEP3_VALIDATIONS,
    AutonomousProvisioningEngine,
)
from app.training_store import TrainingStore


EVAL_PATH = ROOT_DIR / "training" / "evals" / "phase13_provisioning_cases.jsonl"
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
EVAL_WORKSPACE = ROOT_DIR / ".phase13_eval_workspace"


def run_eval(eval_path: Path = EVAL_PATH) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for index, row in enumerate(load_jsonl(eval_path), start=1):
        case = str(row["case"])
        errors = CASES[case]()
        if errors:
            failures.append(f"case {index} {case}: " + "; ".join(errors))
    return not failures, failures


def case_central_provisioning_creates_full_infrastructure() -> list[str]:
    engine = make_engine("central")
    result = engine.provision_pharmacy(onboarding=sample_onboarding(), medicines=sample_medicines())
    duplicate = engine.provision_pharmacy(onboarding=sample_onboarding(), medicines=sample_medicines())
    record = result.record or {}
    errors: list[str] = []
    if not result.accepted:
        errors.append("central provisioning was not accepted")
    for key in required_infrastructure_keys():
        if key not in record:
            errors.append(f"{key} missing from provisioned record")
    if sorted(record.get("namespaces", {})) != sorted(INFRASTRUCTURE_NAMESPACES):
        errors.append("namespace map does not include all required infrastructure namespaces")
    if duplicate.pharmacy_id != result.pharmacy_id:
        errors.append("repeat provisioning for the same phone created a duplicate pharmacy")
    gate = engine.activation_gate(str(result.pharmacy_id))
    if gate.get("decision") != "ALLOW":
        errors.append(f"activation gate blocked ready pharmacy: {gate.get('blockers')}")
    return errors


def case_three_step_owner_onboarding_provisions_ready_pharmacy() -> list[str]:
    engine = make_engine("owner_three_step")
    session = engine.start_owner_onboarding(phone_number="+254711000002")
    session_id = str((session.record or {})["session_id"])
    premature = engine.submit_owner_step2(session_id, source_type="csv", medicines=sample_medicines())
    step1 = engine.submit_owner_step1(session_id, sample_onboarding(phone="+254711000002", name="Owner Flow Chemist"))
    step2 = engine.submit_owner_step2(session_id, source_type="csv", medicines=sample_medicines())
    step3 = engine.submit_owner_step3(session_id, validations={key: True for key in STEP3_VALIDATIONS})
    data = engine._load()
    stored = data["owner_sessions"][session_id]
    errors: list[str] = []
    if premature.accepted or "step1_required" not in premature.blockers:
        errors.append("step 2 was allowed before step 1")
    if not step1.accepted or not step2.accepted or not step3.accepted:
        errors.append("three-step owner onboarding did not complete")
    if stored.get("max_steps") != 3:
        errors.append("owner onboarding is not capped to three steps")
    if stored.get("status") != "provisioned":
        errors.append("owner session did not auto-provision after step 3")
    if engine.activation_gate(str(stored.get("pharmacy_id"))).get("decision") != "ALLOW":
        errors.append("auto-provisioned owner pharmacy failed activation gate")
    return errors


def case_medicine_bootstrap_normalizes_aliases_and_duplicates() -> list[str]:
    engine = make_engine("medicine_bootstrap")
    result = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000003", name="Alias Chemist"),
        medicines=[
            {"name": "Panadol", "aliases": "panado/pain tab", "opening_stock": 12, "selling_price": 200},
            {"name": "Panadol", "aliases": ["duplicate"], "opening_stock": 4},
            {"name": "ORS", "aliases": ["oral rehydration salts"], "opening_stock": 15},
        ],
    )
    record = result.record or {}
    errors: list[str] = []
    if len(record.get("medicine_database", [])) != 2:
        errors.append("duplicate medicine was not removed during bootstrap")
    if record.get("duplicate_medicines") != ["Panadol"]:
        errors.append("duplicate medicine evidence was not retained")
    aliases = record.get("alias_namespace", {})
    if aliases.get("panado") != "Panadol" or aliases.get("pain tab") != "Panadol":
        errors.append("pharmacy-specific medicine aliases were not normalized")
    if "panadol" not in record.get("medicine_search_index", {}):
        errors.append("medicine search index was not generated")
    return errors


def case_unknown_number_admin_approval_provisions_pharmacy() -> list[str]:
    engine = make_engine("unknown_approval")
    opened = engine.handle_unknown_number_message(phone_number="+254711000004", message="Need setup")
    repeated = engine.handle_unknown_number_message(phone_number="+254711000004", message="Another setup message")
    session_id = str((opened.record or {})["session_id"])
    info = engine.submit_unknown_onboarding_info(
        session_id,
        sample_onboarding(phone="+254711000004", name="Unknown Approval Chemist"),
    )
    approved = engine.admin_review_unknown_session(session_id, action="approve", admin_id="admin-a")
    known = engine.handle_unknown_number_message(phone_number="+254711000004", message="panadol2cash")
    errors: list[str] = []
    if (repeated.record or {}).get("session_id") != session_id:
        errors.append("unknown number duplicate onboarding session was created")
    if not info.accepted or not approved.accepted:
        errors.append("unknown-number admin approval did not provision")
    if not known.pharmacy_id or known.pharmacy_id != approved.pharmacy_id:
        errors.append("approved unknown number was not promoted into phone index")
    return errors


def case_unknown_number_admin_review_controls() -> list[str]:
    engine = make_engine("unknown_controls")
    errors: list[str] = []
    for index, (action, expected_status) in enumerate(
        (
            ("reject", "rejected"),
            ("pause", "paused"),
            ("request_corrections", "corrections_requested"),
        ),
        start=1,
    ):
        opened = engine.handle_unknown_number_message(
            phone_number=f"+25472200000{index}",
            message="setup please",
        )
        session_id = str((opened.record or {})["session_id"])
        result = engine.admin_review_unknown_session(
            session_id,
            action=action,
            admin_id="admin-a",
            corrections_requested="Send owner name." if action == "request_corrections" else None,
        )
        stored = (result.record or {}).get("status")
        if not result.accepted or stored != expected_status:
            errors.append(f"{action} produced status {stored!r}, expected {expected_status!r}")
    return errors


def case_activation_gate_allows_ready_and_blocks_unready() -> list[str]:
    engine = make_engine("activation_gate")
    ready = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000005", name="Ready Chemist"),
        medicines=sample_medicines(),
    )
    gate_ready = engine.activation_gate(str(ready.pharmacy_id))
    data = engine._load()
    data["pharmacies"][str(ready.pharmacy_id)]["configs"]["offline_sync"]["healthy"] = False
    engine._save(data)
    gate_blocked = engine.activation_gate(str(ready.pharmacy_id))
    errors: list[str] = []
    if gate_ready.get("decision") != "ALLOW":
        errors.append(f"ready pharmacy was blocked: {gate_ready.get('blockers')}")
    if gate_blocked.get("decision") != "BLOCK" or "offline_sync_not_healthy" not in gate_blocked.get("blockers", []):
        errors.append("activation gate did not block unhealthy offline sync")
    return errors


def case_namespace_isolation_between_pharmacies() -> list[str]:
    engine = make_engine("namespace_isolation")
    first = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000006", name="Alpha Chemist"),
        medicines=[{"name": "Panadol", "aliases": ["alpha-pan"], "opening_stock": 20}],
    )
    second = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000007", name="Beta Chemist"),
        medicines=[{"name": "ORS", "aliases": ["beta-ors"], "opening_stock": 20}],
    )
    a = first.record or {}
    b = second.record or {}
    errors: list[str] = []
    if set(a.get("namespaces", {}).values()) & set(b.get("namespaces", {}).values()):
        errors.append("provisioned namespaces collided between pharmacies")
    if "alpha-pan" in b.get("alias_namespace", {}) or "beta-ors" in a.get("alias_namespace", {}):
        errors.append("medicine aliases leaked across pharmacy namespaces")
    if a.get("offline_sync_queues", {}).get("queue_id") == b.get("offline_sync_queues", {}).get("queue_id"):
        errors.append("offline queue ids are not isolated")
    return errors


def case_templates_cover_required_deployments() -> list[str]:
    engine = make_engine("templates")
    templates = engine.templates()
    errors: list[str] = []
    for template_id in ("starter_pharmacy", "small_pharmacy", "medium_pharmacy", "multi_branch_pharmacy"):
        template = templates.get(template_id)
        if not template:
            errors.append(f"{template_id} template missing")
            continue
        if not template.get("branches"):
            errors.append(f"{template_id} branches missing")
        if not template.get("starter_medicines"):
            errors.append(f"{template_id} starter medicines missing")
    return errors


def case_stress_test_generates_required_sizes() -> list[str]:
    engine = make_engine("stress")
    report = engine.run_stress_test()
    errors: list[str] = []
    if report.get("sizes") != [10, 50, 100, 500, 1000]:
        errors.append("stress sizes did not match required scale set")
    if report.get("safe_deployment_estimate") != 1000:
        errors.append(f"safe deployment estimate was {report.get('safe_deployment_estimate')}, expected 1000")
    if report.get("scaling_health") != "PASS":
        errors.append(f"scaling health was {report.get('scaling_health')}")
    for result in report.get("results", []):
        if result.get("namespace_isolation") is not True:
            errors.append(f"namespace isolation failed at {result.get('size')}")
        if result.get("queue_safety") is not True:
            errors.append(f"queue safety failed at {result.get('size')}")
        if result.get("rollback_systems") is not True or result.get("recovery_systems") is not True:
            errors.append(f"rollback/recovery systems missing at {result.get('size')}")
    if not (engine.store.training_dir / "provisioning_stress_report.json").exists():
        errors.append("stress report artifact was not written")
    return errors


def case_rollback_recovery_configs_created() -> list[str]:
    engine = make_engine("rollback_recovery")
    result = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000008", name="Rollback Chemist"),
        medicines=sample_medicines(),
    )
    record = result.record or {}
    errors: list[str] = []
    if not record.get("rollback_configs", {}).get("checkpoints"):
        errors.append("provisioning rollback checkpoint missing")
    if record.get("recovery_configs", {}).get("status") != "ready":
        errors.append("recovery config was not ready")
    deployment_pharmacy = engine._deployment_engine(str(result.pharmacy_id)).current_pharmacy() or {}
    if not deployment_pharmacy.get("rollback_points"):
        errors.append("Phase 12 deployment rollback point missing")
    return errors


def case_zero_token_and_phase_protections_preserved() -> list[str]:
    engine = make_engine("protections")
    result = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000009", name="Protection Chemist"),
        medicines=sample_medicines(),
    )
    record = result.record or {}
    deployment_pharmacy = engine._deployment_engine(str(result.pharmacy_id)).current_pharmacy() or {}
    protections = deployment_pharmacy.get("protections", {})
    errors: list[str] = []
    if record.get("token_safety_profile", {}).get("known_flow_max_tokens") != 0:
        errors.append("Phase 13 known-flow token profile is not zero-token")
    token_monitoring = deployment_pharmacy.get("token_monitoring", {})
    if token_monitoring.get("known_flow_tokens") != 0 or token_monitoring.get("known_flow_violations") != 0:
        errors.append("Phase 12 token monitoring recorded known-flow token usage")
    for key in (
        "zero_token_known_medicine_flows",
        "offline_reliability_protections",
        "rollback_recovery_protections",
        "pilot_safety_protections",
        "duplicate_prevention_guarantees",
        "grouped_confirmation_protections",
        "pharmacy_isolation_guarantees",
        "token_monitoring_protections",
    ):
        if protections.get(key) is not True:
            errors.append(f"{key} protection missing")
    return errors


CASES = {
    "central_provisioning_creates_full_infrastructure": case_central_provisioning_creates_full_infrastructure,
    "three_step_owner_onboarding_provisions_ready_pharmacy": case_three_step_owner_onboarding_provisions_ready_pharmacy,
    "medicine_bootstrap_normalizes_aliases_and_duplicates": case_medicine_bootstrap_normalizes_aliases_and_duplicates,
    "unknown_number_admin_approval_provisions_pharmacy": case_unknown_number_admin_approval_provisions_pharmacy,
    "unknown_number_admin_review_controls": case_unknown_number_admin_review_controls,
    "activation_gate_allows_ready_and_blocks_unready": case_activation_gate_allows_ready_and_blocks_unready,
    "namespace_isolation_between_pharmacies": case_namespace_isolation_between_pharmacies,
    "templates_cover_required_deployments": case_templates_cover_required_deployments,
    "stress_test_generates_required_sizes": case_stress_test_generates_required_sizes,
    "rollback_recovery_configs_created": case_rollback_recovery_configs_created,
    "zero_token_and_phase_protections_preserved": case_zero_token_and_phase_protections_preserved,
}


def make_engine(name: str) -> AutonomousProvisioningEngine:
    training_dir = EVAL_WORKSPACE / name / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    reset_ledgers(training_dir)
    store = TrainingStore(training_dir=training_dir)
    return AutonomousProvisioningEngine(ledger_path=training_dir / "provisioning_ledger.json", store=store)


def reset_ledgers(training_dir: Path) -> None:
    (training_dir / "provisioning_ledger.json").write_text(
        '{"version": 1, "pharmacies": {}, "phone_index": {}, "owner_sessions": {}, "unknown_sessions": {}, "counters": {}}\n',
        encoding="utf-8",
    )
    (training_dir / "deployment_ledger.json").write_text('{"version": 1, "pharmacies": {}}\n', encoding="utf-8")
    (training_dir / "reliability_ledger.json").write_text('{"version": 1, "pharmacies": {}}\n', encoding="utf-8")
    (training_dir / "live_pilot_ledger.json").write_text(
        '{"version": 1, "active_pharmacy_id": null, "pharmacies": {}}\n',
        encoding="utf-8",
    )


def sample_onboarding(*, phone: str = "+254711000001", name: str = "Zuri Chemist") -> dict[str, Any]:
    return {
        "pharmacy_name": name,
        "owner_name": "Owner A",
        "branch_name": "Main Branch",
        "phone_number": phone,
        "location": "Nairobi",
        "payment_modes": ["cash", "mpesa", "credit"],
    }


def sample_medicines() -> list[dict[str, Any]]:
    return [
        {"name": "Panadol", "aliases": ["panado"], "form": "tablet", "unit": "tablet", "opening_stock": 20, "selling_price": 200},
        {"name": "Cetirizine", "aliases": ["cet"], "form": "tablet", "unit": "tablet", "opening_stock": 10, "selling_price": 50},
    ]


def required_infrastructure_keys() -> tuple[str, ...]:
    return (
        "profile",
        "owner_profile",
        "branch_structure",
        "google_sheets_setup",
        "medicine_database",
        "alias_namespace",
        "onboarding_state",
        "offline_sync_queues",
        "whatsapp_routing",
        "deployment_configs",
        "rollback_configs",
        "monitoring_configs",
        "recovery_configs",
        "audit_logs",
        "dashboard_configs",
        "deployment_readiness_profile",
        "namespaces",
        "configs",
        "validation_results",
        "token_safety_profile",
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
        stress_report_path = EVAL_WORKSPACE / "stress" / "training" / "provisioning_stress_report.json"
        stress_report = json.loads(stress_report_path.read_text(encoding="utf-8")) if stress_report_path.exists() else None
        print(f"PHASE 13 PROVISIONING EVAL: PASS ({EVAL_PATH})")
        if stress_report:
            print(
                "PHASE 13 STRESS RESULT: "
                f"{stress_report.get('safe_deployment_estimate')} pharmacies safe estimate, "
                f"{stress_report.get('scaling_health')}"
            )
        return 0

    print(f"PHASE 13 PROVISIONING EVAL: FAIL ({EVAL_PATH})")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
