from __future__ import annotations

from app.config import Settings


def test_pharmacy_name_fallback_when_env_missing(monkeypatch):
    monkeypatch.delenv("PHARMACY_NAME", raising=False)

    settings = Settings(
        _env_file=None,
        openai_api_key="test-openai-key",
        openai_parse_model="gpt-5",
        google_sheets_spreadsheet_id="test-sheet",
        google_service_account_json="{}",
        twilio_account_sid="ACtest",
        twilio_auth_token="test-token",
        twilio_whatsapp_from="whatsapp:+10000000000",
        owner_whatsapp_to="whatsapp:+20000000000",
    )

    assert settings.pharmacy_name == "PharMareen"


def test_production_env_aliases_are_supported():
    settings = Settings(
        _env_file=None,
        APP_BASE_URL="https://pharmareen.example.com",
        GOOGLE_SHEET_ID="sheet-id",
        GOOGLE_SHEETS_CREDENTIALS='{"client_email":"test@example.com"}',
        TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886",
        owner_whatsapp_to="whatsapp:+254700000000",
    )

    assert settings.public_base_url == "https://pharmareen.example.com"
    assert settings.google_sheets_spreadsheet_id == "sheet-id"
    assert settings.google_service_account_json == '{"client_email":"test@example.com"}'
    assert settings.twilio_whatsapp_from == "whatsapp:+14155238886"
    assert settings.app_version == "day-2"


def test_missing_env_values_do_not_crash_local_mode():
    settings = Settings(_env_file=None)

    assert settings.owner_whatsapp_to == ""
    assert settings.twilio_account_sid == ""
    assert settings.twilio_auth_token == ""
    assert settings.google_sheets_spreadsheet_id == ""
