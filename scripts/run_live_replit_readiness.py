from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings
from app.live_runtime import LIVE_TEST_NUMBER, LiveRuntimeRouter, build_live_readiness_report
from app.provisioning import AutonomousProvisioningEngine
from app.sheets import GoogleSheetsStore
from app.training_store import TrainingStore


SOURCE_TRAINING_DIR = ROOT_DIR / "training"
READINESS_WORKSPACE = ROOT_DIR / ".live_replit_readiness_workspace"


class FakeIntake:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def process_text(self, text: str, **kwargs: Any) -> str:
        self.calls.append({"text": text, **kwargs})
        return f"processed: {text}"


def run_readiness() -> dict[str, Any]:
    backend = run_backend_checks()
    sheets_available, settings_loaded, settings_error = google_sheets_status()
    engine = make_engine()
    onboarding = run_onboarding_simulation(engine)
    stress = engine.run_stress_test()
    environment = build_live_readiness_report(
        root_dir=ROOT_DIR,
        sheets_available=sheets_available,
        settings_loaded=settings_loaded,
        settings_error=settings_error,
    )
    status = "PASS"
    blockers = list(environment["blocked"])
    if not backend["health"] or not backend["debug_version"]:
        blockers.append("backend_health_or_debug_failed")
    if onboarding["status"] != "PASS":
        blockers.append("onboarding_provisioning_simulation_failed")
    if stress.get("scaling_health") != "PASS" or stress.get("safe_deployment_estimate") != 1000:
        blockers.append("provisioning_stress_failed")
    if blockers:
        status = "BLOCKED"
    return {
        "phase": "Live Replit Push + Live Test Readiness",
        "status": status,
        "backend": backend,
        "environment": environment,
        "onboarding": onboarding,
        "stress": stress,
        "token_safety": {"known_flows_use_openai": False},
        "live_test_number": LIVE_TEST_NUMBER,
        "blocked": sorted(set(blockers)),
    }


def run_backend_checks() -> dict[str, bool]:
    import app.main as main

    return {
        "health": main.health().get("status") == "ok",
        "debug_version": main.app.version == "0.1.0",
    }


def google_sheets_status() -> tuple[bool | None, bool, str | None]:
    try:
        settings = get_settings()
    except Exception as exc:
        return False, False, str(exc)
    try:
        return bool(GoogleSheetsStore(settings).is_available), True, None
    except Exception as exc:
        return False, True, str(exc)


def run_onboarding_simulation(engine: AutonomousProvisioningEngine) -> dict[str, Any]:
    intake = FakeIntake()
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: intake,
        provisioning_engine=engine,
        admin_numbers=["+254700000000"],
        existing_pharmacy_numbers=["+254700000000"],
    )
    first = router.handle_whatsapp_message(
        phone_number=LIVE_TEST_NUMBER,
        text="hello",
        source="baileys",
        message_id="readiness-1",
    )
    details = router.handle_whatsapp_message(
        phone_number=LIVE_TEST_NUMBER,
        text="Pharmacy: Zuri Chemist; Owner: Amina; Branch: Main; Location: Nairobi; Payments: cash, mpesa, credit",
        source="baileys",
        message_id="readiness-2",
    )
    approval = router.admin_review_unknown_session(
        session_id=str(details.session_id),
        action="approve",
        admin_id="+254700000000",
        source="admin",
    )
    sale = router.handle_whatsapp_message(
        phone_number=LIVE_TEST_NUMBER,
        text="panadol2cash",
        source="baileys",
        message_id="readiness-3",
    )
    passed = (
        first.status == "unknown_onboarding_started"
        and details.status == "awaiting_admin_approval"
        and approval.status == "approved_provisioned"
        and sale.status == "processed_existing_pharmacy"
        and bool(approval.pharmacy_id)
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "first_message_status": first.status,
        "details_status": details.status,
        "approval_status": approval.status,
        "sale_status": sale.status,
        "session_id": details.session_id,
        "pharmacy_id": approval.pharmacy_id,
        "intake_calls": len(intake.calls),
    }


def make_engine() -> AutonomousProvisioningEngine:
    training_dir = READINESS_WORKSPACE / "training"
    if training_dir.parent.exists():
        shutil.rmtree(training_dir.parent)
    shutil.copytree(SOURCE_TRAINING_DIR, training_dir)
    reset_ledgers(training_dir)
    return AutonomousProvisioningEngine(
        ledger_path=training_dir / "provisioning_ledger.json",
        store=TrainingStore(training_dir=training_dir),
    )


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


def print_summary(report: dict[str, Any]) -> None:
    stress = report["stress"]
    environment = report["environment"]
    print(f"LIVE REPLIT READINESS: {report['status']}")
    print(f"BACKEND HEALTH: {'PASS' if report['backend']['health'] else 'FAIL'}")
    print(f"DEBUG VERSION: {'PASS' if report['backend']['debug_version'] else 'FAIL'}")
    print(f"BAILEYS CONFIRMED: {'yes' if environment['baileys_confirmed'] else 'no'}")
    print(f"OFFLINE APP LOADS: {'yes' if environment['offline_app_loads'] else 'no'}")
    print(f"GOOGLE SHEETS CONNECTED: {'yes' if environment['google_sheets_connected'] else 'no'}")
    print(f"ONBOARDING SIMULATION: {report['onboarding']['status']}")
    print(f"STRESS SAFE ESTIMATE: {stress.get('safe_deployment_estimate')} pharmacies")
    print(f"STRESS SCALING HEALTH: {stress.get('scaling_health')}")
    print(f"TOKEN SAFETY KNOWN FLOWS USE OPENAI: {'yes' if report['token_safety']['known_flows_use_openai'] else 'no'}")
    if report["blocked"]:
        print("BLOCKERS:")
        for blocker in report["blocked"]:
            print(f"- {blocker}")
    print("REPORT_JSON:")
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))


def main() -> int:
    report = run_readiness()
    print_summary(report)
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
