from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings


class FakeWhatsApp:
    async def download_media(self, media_url: str) -> bytes:
        return b"fake audio"


class FakeTranscription:
    is_available = True

    def __init__(self, text: str):
        self.text = text

    def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
        return self.text


class FakeIntake:
    def __init__(self, reply: str | None = None):
        self.received = ""
        self.reply = reply or "✅ Batch processed\n\nSales:\n- Panadol x2\n\nLate Sales:\n- Cetrizine x3\n\nRestocks:\n- None\n\nNo Stock:\n- None\n\nErrors:\n- None"

    def process_text(self, text: str) -> str:
        self.received = text
        return self.reply


class FakeStatusStore:
    is_available = False


def test_health_endpoint_is_day_2():
    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "PharMareen",
        "version": "day-2",
    }


def test_landing_page_and_manifest_work():
    with TestClient(main.app) as client:
        page = client.get("/")
        manifest = client.get("/manifest.json")

    assert page.status_code == 200
    assert "Run your pharmacy from WhatsApp" in page.text
    assert "wa.me" in page.text
    assert "create-qr-code" in page.text
    assert "/status" in page.text
    assert manifest.status_code == 200
    assert manifest.json()["short_name"] == "PharMareen"


def test_status_page_shows_startup_readiness_and_localhost_warning(monkeypatch):
    settings = Settings(_env_file=None, public_base_url="http://localhost:8000")
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_sheet_store", lambda: FakeStatusStore())

    with TestClient(main.app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert "App running" in response.text
    assert "Google Sheets connected" in response.text
    assert "Twilio credentials found" in response.text
    assert "http://localhost:8000/webhook/whatsapp" in response.text
    assert "WhatsApp will NOT reply while APP_BASE_URL is localhost" in response.text


def test_status_page_shows_production_ready_for_https_domain(monkeypatch):
    settings = Settings(
        _env_file=None,
        APP_BASE_URL="https://pharmareen.example.co.ke",
        TWILIO_ACCOUNT_SID="ACtest",
        TWILIO_AUTH_TOKEN="token",
        TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_sheet_store", lambda: FakeStatusStore())

    with TestClient(main.app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert "Production URL looks ready" in response.text
    assert "https://pharmareen.example.co.ke/webhook/whatsapp" in response.text


def test_debug_config_does_not_expose_secrets(monkeypatch):
    settings = Settings(
        _env_file=None,
        APP_BASE_URL="https://pharmareen.replit.app",
        twilio_account_sid="ACsecret",
        twilio_auth_token="super-secret-token",
        TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886",
        OWNER_WHATSAPP_TO="whatsapp:+254700000000",
        GOOGLE_SHEET_ID="sheet-id",
        GOOGLE_SHEETS_CREDENTIALS='{"client_email":"test@example.com"}',
        openai_api_key="sk-secret",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)

    with TestClient(main.app) as client:
        response = client.get("/debug/config")

    assert response.status_code == 200
    data = response.json()
    assert data["app_running"] is True
    assert data["app_base_url"] == "https://pharmareen.replit.app"
    assert data["app_base_url_is_https"] is True
    assert data["app_base_url_has_placeholder"] is False
    assert data["twilio_account_sid_present"] is True
    assert data["twilio_auth_token_present"] is True
    assert data["google_credentials_present"] is True
    assert "super-secret-token" not in response.text
    assert "sk-secret" not in response.text


def test_debug_whatsapp_test_returns_twiml(monkeypatch):
    fake_intake = FakeIntake("👋 PharMareen Help")
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"))

    with TestClient(main.app) as client:
        response = client.post("/debug/whatsapp-test")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["response_type"] == "twiml_xml"
    assert "<Response><Message>" in data["response_body_preview"]
    assert data["command_handler"] == "help_start"
    assert fake_intake.received == "start"


def test_debug_report_test_generates_pdf(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "reports_pdf_dir", lambda: tmp_path)
    monkeypatch.setenv("PHARMAREEN_REPORTS_DIR", str(tmp_path))
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, APP_BASE_URL="https://pharmareen.replit.app"))

    with TestClient(main.app) as client:
        response = client.get("/debug/report-test")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["file_exists"] is True
    assert data["public_pdf_url"].startswith("https://pharmareen.replit.app/reports/download/")


def test_smoke_test_script_exists():
    root = Path(__file__).resolve().parents[1]

    assert (root / "scripts" / "smoke_test.py").exists()


def test_start_launcher_file_exists():
    root = Path(__file__).resolve().parents[1]

    assert (root / "START_PHARMAREEN.bat").exists()


def test_pdf_download_route_serves_pdf(tmp_path, monkeypatch):
    report = tmp_path / "test-report.pdf"
    report.write_bytes(b"%PDF-1.4 test")
    monkeypatch.setattr(main, "reports_pdf_dir", lambda: tmp_path)

    with TestClient(main.app) as client:
        response = client.get("/reports/download/test-report.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_voice_note_uses_mocked_transcription(monkeypatch):
    fake_intake = FakeIntake()
    monkeypatch.setattr(main, "get_whatsapp_client", lambda: FakeWhatsApp())
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscription("Panadol two, later Cetrizine three"))
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/whatsapp",
            data={
                "NumMedia": "1",
                "MediaContentType0": "audio/ogg",
                "MediaUrl0": "https://example.com/audio.ogg",
                "From": "whatsapp:+254700000000",
                "MessageSid": "SMVOICE1",
            },
        )

    assert response.status_code == 200
    assert "Voice note received" in response.text
    assert "Records updated" in response.text
    assert fake_intake.received == "Panadol two, later Cetrizine three"


def test_unclear_voice_note_returns_clear_message(monkeypatch):
    monkeypatch.setattr(main, "get_whatsapp_client", lambda: FakeWhatsApp())
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscription(""))
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/whatsapp",
            data={
                "NumMedia": "1",
                "MediaContentType0": "audio/ogg",
                "MediaUrl0": "https://example.com/audio.ogg",
                "From": "whatsapp:+254700000000",
                "MessageSid": "SMVOICE2",
            },
        )

    assert response.status_code == 200
    assert "I could not clearly understand the voice note" in response.text


def test_twilio_pdf_media_payload_created_for_public_report(monkeypatch):
    fake_intake = FakeIntake(
        "📊 Daily Report\n\nSales: KES 440\n\n📎 PDF report attached below.\nhttps://reports.pharmareen.app/reports/download/report.pdf"
    )
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/whatsapp",
            data={
                "Body": "report today",
                "From": "whatsapp:+254700000000",
                "MessageSid": "SMPDFMEDIA1",
            },
        )

    assert response.status_code == 200
    assert "<Media>https://reports.pharmareen.app/reports/download/report.pdf</Media>" in response.text
    assert "attached below" in response.text
    assert "https://reports.pharmareen.app/reports/download/report.pdf" not in response.text.replace(
        "<Media>https://reports.pharmareen.app/reports/download/report.pdf</Media>", ""
    )


def test_twilio_pdf_fallback_link_stays_when_not_attachable(monkeypatch):
    fake_intake = FakeIntake(
        "📊 Daily Report\n\nSales: KES 440\n\n📄 PDF report:\nTap here to download: http://localhost:8000/reports/download/report.pdf"
    )
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/whatsapp",
            data={
                "Body": "report today",
                "From": "whatsapp:+254700000000",
                "MessageSid": "SMPDFFALLBACK1",
            },
        )

    assert response.status_code == 200
    assert "<Media>" not in response.text
    assert "Tap here to download" in response.text


def test_unclear_voice_note_asks_confirmation_then_yes_processes(monkeypatch):
    fake_intake = FakeIntake("✅ Panadol x2 recorded\nStock left: 18\nProfit: KES 160")
    monkeypatch.setattr(main, "get_whatsapp_client", lambda: FakeWhatsApp())
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscription("maybe panadol"))
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)
    main.pending_voice_confirmations.clear()

    with TestClient(main.app) as client:
        first = client.post(
            "/webhook/whatsapp",
            data={
                "NumMedia": "1",
                "MediaContentType0": "audio/ogg",
                "MediaUrl0": "https://example.com/audio.ogg",
                "From": "whatsapp:+254700000001",
                "MessageSid": "SMVOICECONFIRM1",
            },
        )
        second = client.post(
            "/webhook/whatsapp",
            data={
                "Body": "yes",
                "From": "whatsapp:+254700000001",
                "MessageSid": "SMVOICECONFIRM2",
            },
        )

    assert "I’m not fully sure I understood" in first.text
    assert "Please confirm by typing" in first.text
    assert "Confirmed. Records updated" in second.text
    assert fake_intake.received == "maybe panadol"


def test_voice_correction_processes_corrected_text(monkeypatch):
    fake_intake = FakeIntake("✅ Panadol x2 recorded\nStock left: 18\nProfit: KES 160")
    monkeypatch.setattr(main, "get_whatsapp_client", lambda: FakeWhatsApp())
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscription("maybe panadol"))
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)
    main.pending_voice_confirmations.clear()

    with TestClient(main.app) as client:
        client.post(
            "/webhook/whatsapp",
            data={
                "NumMedia": "1",
                "MediaContentType0": "audio/ogg",
                "MediaUrl0": "https://example.com/audio.ogg",
                "From": "whatsapp:+254700000002",
                "MessageSid": "SMVOICECORRECT1",
            },
        )
        response = client.post(
            "/webhook/whatsapp",
            data={
                "Body": "Panadol 2",
                "From": "whatsapp:+254700000002",
                "MessageSid": "SMVOICECORRECT2",
            },
        )

    assert "Panadol x2 recorded" in response.text
    assert fake_intake.received == "Panadol 2"
