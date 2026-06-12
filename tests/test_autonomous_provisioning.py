from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.provisioning import (
    INFRASTRUCTURE_NAMESPACES,
    OWNER_STEP1_FIELDS,
    STEP3_VALIDATIONS,
    AutonomousProvisioningEngine,
)
from app.training_store import TrainingStore


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
TEST_WORKSPACE = ROOT_DIR / ".phase13_test_workspace"


def make_engine(name: str) -> AutonomousProvisioningEngine:
    training_dir = TEST_WORKSPACE / name / "training"
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


def test_central_provisioning_creates_full_infrastructure_and_blocks_duplicates():
    engine = make_engine("central")

    result = engine.provision_pharmacy(onboarding=sample_onboarding(), medicines=sample_medicines())
    duplicate = engine.provision_pharmacy(onboarding=sample_onboarding(), medicines=sample_medicines())
    record = result.record

    assert result.accepted is True
    assert duplicate.pharmacy_id == result.pharmacy_id
    assert sorted(record["namespaces"]) == sorted(INFRASTRUCTURE_NAMESPACES)
    assert record["google_sheets_setup"]["status"] == "config_generated"
    assert record["offline_sync_queues"]["idempotency_required"] is True
    assert record["configs"]["duplicate_prevention"]["active"] is True
    assert record["configs"]["grouped_confirmations"]["active"] is True
    assert record["deployment_configs"]["phase12_status"] == "ready"
    assert record["deployment_readiness_profile"]["ready"] is True
    assert engine.activation_gate(result.pharmacy_id)["decision"] == "ALLOW"


def test_three_step_owner_onboarding_is_sequenced_and_auto_provisions():
    engine = make_engine("owner_three_step")
    session = engine.start_owner_onboarding(phone_number="+254711000002")
    session_id = session.record["session_id"]

    premature = engine.submit_owner_step2(session_id, source_type="csv", medicines=sample_medicines())
    extra_fields = engine.submit_owner_step1(session_id, {**sample_onboarding(phone="+254711000002"), "extra": "not allowed"})
    step1 = engine.submit_owner_step1(session_id, sample_onboarding(phone="+254711000002", name="Owner Flow Chemist"))
    step2 = engine.submit_owner_step2(session_id, source_type="csv", medicines=sample_medicines())
    step3 = engine.submit_owner_step3(session_id, validations={key: True for key in STEP3_VALIDATIONS})
    stored = engine._load()["owner_sessions"][session_id]

    assert premature.accepted is False
    assert "step1_required" in premature.blockers
    assert extra_fields.accepted is False
    assert any(blocker.startswith("unexpected_fields") for blocker in extra_fields.blockers)
    assert step1.accepted is True
    assert set(stored["steps"]["1"]) == OWNER_STEP1_FIELDS
    assert step2.accepted is True
    assert step3.accepted is True
    assert stored["max_steps"] == 3
    assert stored["status"] == "provisioned"
    assert engine.activation_gate(stored["pharmacy_id"])["decision"] == "ALLOW"


def test_medicine_bootstrap_normalizes_aliases_duplicates_and_search_index():
    engine = make_engine("medicine_bootstrap")

    result = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000003", name="Alias Chemist"),
        medicines=[
            {"name": "Panadol", "aliases": "panado/pain tab", "opening_stock": 12, "selling_price": 200},
            {"name": "Panadol", "aliases": ["duplicate"], "opening_stock": 4},
            {"name": "ORS", "aliases": ["oral rehydration salts"], "opening_stock": 15},
        ],
    )
    record = result.record

    assert [item["name"] for item in record["medicine_database"]] == ["Panadol", "ORS"]
    assert record["duplicate_medicines"] == ["Panadol"]
    assert record["alias_namespace"]["panado"] == "Panadol"
    assert record["alias_namespace"]["pain tab"] == "Panadol"
    assert "panadol" in record["medicine_search_index"]


def test_unknown_number_onboarding_requires_admin_review_and_promotes_known_phone():
    engine = make_engine("unknown_approval")

    opened = engine.handle_unknown_number_message(phone_number="+254711000004", message="Need setup")
    repeated = engine.handle_unknown_number_message(phone_number="+254711000004", message="Another setup message")
    session_id = opened.record["session_id"]
    info = engine.submit_unknown_onboarding_info(
        session_id,
        sample_onboarding(phone="+254711000004", name="Unknown Approval Chemist"),
    )
    approved = engine.admin_review_unknown_session(session_id, action="approve", admin_id="admin-a")
    known = engine.handle_unknown_number_message(phone_number="+254711000004", message="panadol2cash")

    assert repeated.record["session_id"] == session_id
    assert info.accepted is True
    assert approved.accepted is True
    assert known.pharmacy_id == approved.pharmacy_id
    assert engine._load()["unknown_sessions"][session_id]["status"] == "approved_provisioned"


def test_unknown_number_admin_reject_pause_and_corrections_are_audited():
    engine = make_engine("unknown_controls")

    for phone, action, expected_status in (
        ("+254722000001", "reject", "rejected"),
        ("+254722000002", "pause", "paused"),
        ("+254722000003", "request_corrections", "corrections_requested"),
    ):
        opened = engine.handle_unknown_number_message(phone_number=phone, message="setup please")
        session_id = opened.record["session_id"]
        result = engine.admin_review_unknown_session(
            session_id,
            action=action,
            admin_id="admin-a",
            corrections_requested="Send owner name." if action == "request_corrections" else None,
        )

        assert result.accepted is True
        assert result.record["status"] == expected_status
        assert result.record["admin_reviews"][0]["action"] == action


def test_activation_gate_allows_ready_pharmacy_and_blocks_unhealthy_offline_sync():
    engine = make_engine("activation_gate")
    result = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000005", name="Ready Chemist"),
        medicines=sample_medicines(),
    )

    assert engine.activation_gate(result.pharmacy_id)["decision"] == "ALLOW"

    data = engine._load()
    data["pharmacies"][result.pharmacy_id]["configs"]["offline_sync"]["healthy"] = False
    engine._save(data)
    blocked = engine.activation_gate(result.pharmacy_id)

    assert blocked["decision"] == "BLOCK"
    assert "offline_sync_not_healthy" in blocked["blockers"]


def test_namespace_alias_and_queue_isolation_between_pharmacies():
    engine = make_engine("namespace_isolation")

    first = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000006", name="Alpha Chemist"),
        medicines=[{"name": "Panadol", "aliases": ["alpha-pan"], "opening_stock": 20}],
    )
    second = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000007", name="Beta Chemist"),
        medicines=[{"name": "ORS", "aliases": ["beta-ors"], "opening_stock": 20}],
    )

    assert not (set(first.record["namespaces"].values()) & set(second.record["namespaces"].values()))
    assert "alpha-pan" not in second.record["alias_namespace"]
    assert "beta-ors" not in first.record["alias_namespace"]
    assert first.record["offline_sync_queues"]["queue_id"] != second.record["offline_sync_queues"]["queue_id"]


def test_templates_cover_required_deployment_shapes():
    templates = make_engine("templates").templates()

    for template_id in ("starter_pharmacy", "small_pharmacy", "medium_pharmacy", "multi_branch_pharmacy"):
        assert template_id in templates
        assert templates[template_id]["branches"]
        assert templates[template_id]["starter_medicines"]


def test_stress_test_generates_required_scales_and_artifact():
    engine = make_engine("stress")

    report = engine.run_stress_test()

    assert report["sizes"] == [10, 50, 100, 500, 1000]
    assert report["safe_deployment_estimate"] == 1000
    assert report["scaling_health"] == "PASS"
    assert all(result["namespace_isolation"] for result in report["results"])
    assert all(result["queue_safety"] for result in report["results"])
    assert all(result["rollback_systems"] and result["recovery_systems"] for result in report["results"])
    assert (engine.store.training_dir / "provisioning_stress_report.json").exists()


def test_rollback_recovery_and_zero_token_phase_protections_are_preserved():
    engine = make_engine("protections")

    result = engine.provision_pharmacy(
        onboarding=sample_onboarding(phone="+254711000009", name="Protection Chemist"),
        medicines=sample_medicines(),
    )
    record = result.record
    deployment_pharmacy = engine._deployment_engine(result.pharmacy_id).current_pharmacy()
    protections = deployment_pharmacy["protections"]

    assert record["rollback_configs"]["checkpoints"]
    assert record["recovery_configs"]["status"] == "ready"
    assert record["token_safety_profile"]["known_flow_max_tokens"] == 0
    assert deployment_pharmacy["rollback_points"]
    assert deployment_pharmacy["token_monitoring"]["known_flow_tokens"] == 0
    assert deployment_pharmacy["token_monitoring"]["known_flow_violations"] == 0
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
        assert protections[key] is True
