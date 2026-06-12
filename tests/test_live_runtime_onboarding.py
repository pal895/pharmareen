from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.live_runtime import LIVE_TEST_NUMBER, LiveRuntimeResult, LiveRuntimeRouter, parse_onboarding_details
from app.provisioning import AutonomousProvisioningEngine
from app.training_store import TrainingStore


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_TRAINING_DIR = ROOT_DIR / "training"
TEST_WORKSPACE = ROOT_DIR / ".live_runtime_test_workspace"


class FakeIntake:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def process_text(self, text, **kwargs):
        self.calls.append({"text": text, **kwargs})
        return f"processed: {text}"


class AvailableStore:
    is_available = True

    def ensure_schema(self) -> None:
        return None


class FakeRouter:
    def handle_whatsapp_message(self, **kwargs):
        return LiveRuntimeResult(
            reply=f"handled {kwargs['text']}",
            status="processed_existing_pharmacy",
            phone_number=kwargs["phone_number"],
            source=kwargs["source"],
            pharmacy_id="fake_pharmacy",
        )


def make_engine(name: str) -> AutonomousProvisioningEngine:
    training_dir = TEST_WORKSPACE / name / "training"
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


def test_unknown_live_test_number_onboards_waits_for_admin_then_routes_to_intake():
    intake = FakeIntake()
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: intake,
        provisioning_engine=make_engine("unknown_live"),
        admin_numbers=["+254700000000"],
        existing_pharmacy_numbers=["+254700000000"],
    )

    first = router.handle_whatsapp_message(
        phone_number=LIVE_TEST_NUMBER,
        text="hello",
        source="baileys",
        message_id="m1",
    )
    details = router.handle_whatsapp_message(
        phone_number=LIVE_TEST_NUMBER,
        text="Pharmacy: Zuri Chemist; Owner: Amina; Branch: Main; Location: Nairobi; Payments: cash, mpesa, credit",
        source="baileys",
        message_id="m2",
    )
    approved = router.admin_review_unknown_session(
        session_id=str(details.session_id),
        action="approve",
        admin_id="+254700000000",
        source="admin",
    )
    sale = router.handle_whatsapp_message(
        phone_number=LIVE_TEST_NUMBER,
        text="panadol2cash",
        source="baileys",
        message_id="m3",
    )

    assert first.status == "unknown_onboarding_started"
    assert details.status == "awaiting_admin_approval"
    assert details.admin_required is True
    assert approved.status == "approved_provisioned"
    assert approved.provisioned is True
    assert sale.status == "processed_existing_pharmacy"
    assert sale.reply == "processed: panadol2cash"
    assert intake.calls[0]["actor_id"] == LIVE_TEST_NUMBER
    assert intake.calls[0]["source"] == "baileys"


def test_existing_owner_number_bypasses_onboarding():
    intake = FakeIntake()
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: intake,
        provisioning_engine=make_engine("existing_owner"),
        existing_pharmacy_numbers=["whatsapp:+254700000001"],
    )

    result = router.handle_whatsapp_message(
        phone_number="+254700000001",
        text="panadol2cash",
        source="baileys",
    )

    assert result.status == "processed_existing_pharmacy"
    assert result.reply == "processed: panadol2cash"
    assert intake.calls[0]["text"] == "panadol2cash"


def test_onboarding_detail_parser_accepts_keyed_owner_message():
    details = parse_onboarding_details(
        "Pharmacy: Zuri Chemist; Owner: Amina; Branch: Main; Location: Nairobi; Payments: cash, mpesa",
        LIVE_TEST_NUMBER,
    )

    assert details["pharmacy_name"] == "Zuri Chemist"
    assert details["owner_name"] == "Amina"
    assert details["branch_name"] == "Main"
    assert details["location"] == "Nairobi"
    assert details["payment_modes"] == ["cash", "mpesa"]
    assert details["phone_number"] == LIVE_TEST_NUMBER


def test_baileys_endpoint_returns_json_reply(monkeypatch):
    monkeypatch.setattr(main, "get_sheet_store", lambda: AvailableStore())
    monkeypatch.setattr(main, "get_live_runtime_router", lambda: FakeRouter())

    with TestClient(main.app) as client:
        response = client.post(
            "/webhooks/baileys/whatsapp",
            json={"from": LIVE_TEST_NUMBER, "text": "panadol2cash", "message_id": "m1"},
        )

    assert response.status_code == 200
    assert response.json()["reply"] == "handled panadol2cash"
    assert response.json()["source"] == "baileys"


def test_live_readiness_reports_blockers_without_replit_or_offline_sources(monkeypatch):
    monkeypatch.setattr(main, "get_sheet_store", lambda: AvailableStore())
    monkeypatch.setattr(main, "try_get_settings", lambda: (None, "settings missing in test"))

    with TestClient(main.app) as client:
        response = client.get("/live/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["onboarding_ready"] is True
    assert body["provisioning_ready"] is True
    assert "no_git_remote_available_for_replit_push" in body["blocked"]
    assert "offline_app_source_not_present_locally" in body["blocked"]
