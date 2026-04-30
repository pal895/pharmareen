from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings
from app.sheets import (
    GoogleSheetsStore,
    SHEETS_UNAVAILABLE_MESSAGE,
    SheetsUnavailableError,
    prepare_google_credentials_file,
)


class UnavailableStore:
    is_available = False

    def ensure_schema(self) -> None:
        return None


class FailingReportService:
    def generate_daily_report(self, report_date, send_whatsapp=True):
        raise SheetsUnavailableError(SHEETS_UNAVAILABLE_MESSAGE)


class FakeSettings:
    timezone = "Africa/Nairobi"
    report_trigger_token = None


LOCAL_TMP = Path(__file__).parent / "_tmp_service_accounts"


def make_settings(service_account_path: str) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test-openai-key",
        openai_parse_model="gpt-5",
        google_sheets_spreadsheet_id="test-sheet",
        google_service_account_json=service_account_path,
        twilio_account_sid="ACtest",
        twilio_auth_token="test-token",
        twilio_whatsapp_from="whatsapp:+10000000000",
        owner_whatsapp_to="whatsapp:+20000000000",
    )


@pytest.mark.parametrize("file_contents", ["", "{not-json"])
def test_store_starts_unavailable_for_empty_or_invalid_service_account(file_contents):
    LOCAL_TMP.mkdir(exist_ok=True)
    service_account = LOCAL_TMP / f"service-account-{uuid4().hex}.json"
    service_account.write_text(file_contents, encoding="utf-8")

    store = GoogleSheetsStore(make_settings(str(service_account)))

    assert store.is_available is False
    with pytest.raises(SheetsUnavailableError, match="Google Sheets is not configured"):
        store.list_master_drug_names()
    service_account.unlink(missing_ok=True)


def test_store_starts_unavailable_for_missing_service_account():
    LOCAL_TMP.mkdir(exist_ok=True)
    missing_service_account = LOCAL_TMP / f"missing-service-account-{uuid4().hex}.json"

    store = GoogleSheetsStore(make_settings(str(missing_service_account)))

    assert store.is_available is False
    with pytest.raises(SheetsUnavailableError, match="Google Sheets is not configured"):
        store.read_daily_logs("2026-04-27")


def test_google_sheets_credentials_env_is_written_to_service_account_file(tmp_path, monkeypatch):
    credentials_json = """
    {
      "type": "service_account",
      "project_id": "test-project",
      "private_key_id": "test-key-id",
      "private_key": "-----BEGIN PRIVATE KEY-----\\nTEST\\n-----END PRIVATE KEY-----\\n",
      "client_email": "test@example.iam.gserviceaccount.com",
      "client_id": "123456789",
      "token_uri": "https://oauth2.googleapis.com/token"
    }
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS", credentials_json)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")

    path = prepare_google_credentials_file(make_settings("./service-account.json"))

    assert path == tmp_path / "service-account.json"
    assert path.exists()
    written = path.read_text(encoding="utf-8")
    assert "test@example.iam.gserviceaccount.com" in written
    assert "private_key" in written


def test_google_sheets_credentials_env_invalid_json_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS", "{not-json")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")

    with pytest.raises(ValueError, match="not valid JSON"):
        prepare_google_credentials_file(make_settings("./service-account.json"))


def test_health_and_test_endpoint_work_when_sheets_are_unavailable(monkeypatch):
    monkeypatch.setattr(main, "get_sheet_store", lambda: UnavailableStore())

    with TestClient(main.app) as client:
        health_response = client.get("/health")
        test_response = client.get("/test")

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "service": "PharMareen",
        "version": "day-2",
    }
    assert test_response.status_code == 200
    assert test_response.json()["message"] == SHEETS_UNAVAILABLE_MESSAGE


def test_daily_report_endpoint_returns_clear_message_when_sheets_are_unavailable(monkeypatch):
    monkeypatch.setattr(main, "get_sheet_store", lambda: UnavailableStore())
    monkeypatch.setattr(main, "get_report_service", lambda: FailingReportService())
    monkeypatch.setattr(main, "get_settings", lambda: FakeSettings())

    with TestClient(main.app) as client:
        response = client.post("/reports/daily?send_whatsapp=false")

    assert response.status_code == 503
    assert response.json() == {"detail": SHEETS_UNAVAILABLE_MESSAGE}
