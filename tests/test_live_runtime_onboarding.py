from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from gspread.exceptions import WorksheetNotFound

import app.main as main
from app.local_first_parser import LocalFirstParser
from app.live_runtime import LIVE_TEST_NUMBER, LiveRuntimeResult, LiveRuntimeRouter, parse_onboarding_details
from app.pharmacy_registry import GoogleSheetsPharmacyRegistry, PHARMACY_REGISTRY_HEADERS
from app.provisioning import AutonomousProvisioningEngine
from app.sale_numbering import DailySaleLedger
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


class FakeRegistryWorksheet:
    def __init__(self, title: str):
        self.title = title
        self.rows: list[list[object]] = []

    def row_values(self, row: int) -> list[object]:
        if row <= 0 or row > len(self.rows):
            return []
        return self.rows[row - 1]

    def update(self, _range_name: str, values: list[list[object]]) -> None:
        if self.rows:
            self.rows[0] = list(values[0])
        else:
            self.rows.append(list(values[0]))

    def append_row(self, row: list[object], value_input_option: str = "") -> None:
        self.rows.append(list(row))

    def get_all_values(self) -> list[list[object]]:
        return [list(row) for row in self.rows]

    def get_all_records(self) -> list[dict[str, object]]:
        if not self.rows:
            return []
        headers = [str(value) for value in self.rows[0]]
        records: list[dict[str, object]] = []
        for row in self.rows[1:]:
            records.append({header: row[index] if index < len(row) else "" for index, header in enumerate(headers)})
        return records


class FakeRegistrySpreadsheet:
    id = "model20-test-sheet"
    url = "https://docs.google.com/spreadsheets/d/model20-test-sheet"

    def __init__(self):
        self.worksheets: dict[str, FakeRegistryWorksheet] = {}

    def worksheet(self, title: str) -> FakeRegistryWorksheet:
        if title not in self.worksheets:
            raise WorksheetNotFound(title)
        return self.worksheets[title]

    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeRegistryWorksheet:
        worksheet = FakeRegistryWorksheet(title)
        self.worksheets[title] = worksheet
        return worksheet


class FakeRegistryStore:
    is_available = True

    def __init__(self):
        self.spreadsheet = FakeRegistrySpreadsheet()

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


def clear_runtime_caches() -> None:
    for name in (
        "get_ai_service",
        "get_correction_learning_engine",
        "get_deployment_engine",
        "get_intake_service",
        "get_live_pilot_engine",
        "get_local_first_parser",
        "get_medicine_brain",
        "get_report_service",
        "get_reliability_engine",
        "get_sale_ledger",
        "get_training_store",
        "get_whatsapp_client",
    ):
        cache_clear = getattr(getattr(main, name, None), "cache_clear", None)
        if callable(cache_clear):
            cache_clear()


@pytest.fixture(autouse=True)
def clear_runtime_caches_fixture():
    clear_runtime_caches()
    yield
    clear_runtime_caches()


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


def test_google_sheets_registry_onboards_phone_and_routes_sale():
    store = FakeRegistryStore()
    registry = GoogleSheetsPharmacyRegistry(store, timezone_name="Africa/Nairobi", currency="KES")
    intake = FakeIntake()
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: intake,
        provisioning_engine=make_engine("registry_onboard"),
        pharmacy_registry=registry,
    )
    phone = "+254700000777"

    start = router.handle_whatsapp_message(phone_number=phone, text="START", source="baileys")
    setup = router.handle_whatsapp_message(
        phone_number=phone,
        text="Pharmacy: Afya Chemist; Owner: Njeri; Location: Nakuru",
        source="baileys",
    )
    sale = router.handle_whatsapp_message(phone_number=phone, text="Panadol 2 cash", source="baileys")

    worksheet = store.spreadsheet.worksheets["Pharmacies"]
    assert worksheet.rows[0] == PHARMACY_REGISTRY_HEADERS
    assert len(worksheet.rows) == 2
    assert worksheet.rows[1][1] == "Afya Chemist"
    assert worksheet.rows[1][10] == phone
    assert start.status == "unknown_onboarding_started"
    assert setup.status == "registered_active_pharmacy"
    assert setup.provisioned is True
    assert sale.status == "processed_existing_pharmacy"
    assert sale.pharmacy_id == setup.pharmacy_id
    assert intake.calls[0]["text"] == "Panadol 2 cash"
    assert intake.calls[0]["actor_id"] == phone


def test_verified_channel_new_pharmacy_hands_off_to_secure_owner_activation():
    store = FakeRegistryStore()
    registry = GoogleSheetsPharmacyRegistry(store)
    issued = []
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: FakeIntake(),
        provisioning_engine=make_engine("registry_secure_handoff"),
        pharmacy_registry=registry,
        new_pharmacy_entry_factory=lambda phone: issued.append(phone) or "/main-app/new-pharmacy?entry=signed",
    )
    result = router.handle_whatsapp_message(
        phone_number="+254700000776",
        text="Pharmacy: Tumaini Chemist; Owner: Akinyi; Location: Eldoret",
        source="baileys",
    )
    assert result.status == "registered_active_pharmacy"
    assert issued == ["+254700000776"]
    assert "/main-app/new-pharmacy?entry=signed" in result.reply
    assert "send sales" not in result.reply


def test_registry_duplicate_onboarding_does_not_create_second_row():
    store = FakeRegistryStore()
    registry = GoogleSheetsPharmacyRegistry(store)
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: FakeIntake(),
        provisioning_engine=make_engine("registry_duplicate"),
        pharmacy_registry=registry,
    )
    phone = "+254700000888"

    first = router.handle_whatsapp_message(
        phone_number=phone,
        text="Pharmacy: Baraka Pharmacy; Owner: Otieno; Location: Kisumu",
        source="baileys",
    )
    second = router.handle_whatsapp_message(phone_number=phone, text="START", source="baileys")

    assert first.status == "registered_active_pharmacy"
    assert second.status == "registered_active_pharmacy"
    assert len(store.spreadsheet.worksheets["Pharmacies"].rows) == 2


def test_unregistered_non_onboarding_number_gets_registry_prompt_without_intake():
    store = FakeRegistryStore()
    registry = GoogleSheetsPharmacyRegistry(store)
    intake = FakeIntake()
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: intake,
        provisioning_engine=make_engine("registry_block"),
        pharmacy_registry=registry,
    )

    result = router.handle_whatsapp_message(
        phone_number="+254700000999",
        text="Panadol 2 cash",
        source="baileys",
    )

    assert result.status == "unregistered_onboarding_prompt"
    assert "Reply START" in result.reply
    assert intake.calls == []


def test_allowed_whatsapp_number_still_works_as_development_override():
    intake = FakeIntake()
    router = LiveRuntimeRouter(
        intake_service_factory=lambda: intake,
        provisioning_engine=make_engine("dev_override"),
        development_override_numbers=["254721149472"],
    )

    result = router.handle_whatsapp_message(
        phone_number="+254721149472",
        text="Panadol 2 cash",
        source="baileys",
    )

    assert result.status == "processed_existing_pharmacy"
    assert result.pharmacy_id == "development_override_pharmacy"
    assert intake.calls[0]["text"] == "Panadol 2 cash"


def test_baileys_endpoint_returns_json_reply(monkeypatch):
    clear_runtime_caches()
    run_id = uuid.uuid4().hex
    monkeypatch.setenv("PHARMAREEN_DEFAULT_PHARMACY_ID", f"test_baileys_{run_id}")
    monkeypatch.setattr(main, "get_sheet_store", lambda: AvailableStore())
    monkeypatch.setattr(main, "get_live_runtime_router", lambda: FakeRouter())

    with TestClient(main.app) as client:
        response = client.post(
            "/webhooks/baileys/whatsapp",
            json={"from": LIVE_TEST_NUMBER, "text": "panadol2cash", "message_id": f"m1-{run_id}"},
        )

    assert response.status_code == 200
    assert response.json()["reply"] == "handled panadol2cash"
    assert response.json()["source"] == "baileys"
    assert response.json()["token_safe"] is True
    assert response.json()["reliability"]["tracked"] is True


def test_live_factories_wire_local_parser_sale_ledger_and_reports(monkeypatch):
    clear_runtime_caches()
    monkeypatch.setenv("PHARMAREEN_DEFAULT_PHARMACY_ID", "test_live_factory")
    monkeypatch.setattr(main, "get_sheet_store", lambda: AvailableStore())
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: main.Settings(_env_file=None, pharmacy_name="Test Pharmacy", timezone="Africa/Nairobi"),
    )

    intake = main.get_intake_service()
    reports = main.get_report_service()

    assert isinstance(intake.parser, LocalFirstParser)
    assert isinstance(intake.sale_ledger, DailySaleLedger)
    assert isinstance(reports.sale_ledger, DailySaleLedger)
    assert main.get_reliability_engine().no_data_loss_report()["dead_letter"] == 0


def test_runtime_status_exposes_live_wiring(monkeypatch):
    clear_runtime_caches()
    monkeypatch.setenv("PHARMAREEN_DEFAULT_PHARMACY_ID", "test_runtime_status")
    monkeypatch.setattr(main, "get_sheet_store", lambda: AvailableStore())
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: main.Settings(_env_file=None, pharmacy_name="Test Pharmacy", timezone="Africa/Nairobi"),
    )

    with TestClient(main.app) as client:
        response = client.get("/live/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["intake_parser"] == "LocalFirstParser"
    assert body["reliability"]["dead_letter"] == 0
    assert body["deployment"]["pharmacy_id"] == "test_runtime_status"


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
