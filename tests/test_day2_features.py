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


class UnavailableTranscription:
    is_available = False


class FailingTranscription:
    is_available = True

    def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
        raise RuntimeError("transcription failed")


class FakeIntake:
    def __init__(self, reply: str | None = None):
        self.received = ""
        self.reply = reply or "✅ Batch processed\n\nSales:\n- Panadol x2\n\nLate Sales:\n- Cetirizine x3\n\nRestocks:\n- None\n\nNo-stock requests:\n- None\n\nErrors:\n- None"

    def process_text(self, text: str) -> str:
        self.received = text
        return self.reply


class FakeStatusStore:
    is_available = False


def xml_payload(xml_text: str) -> str:
    return xml_text.removeprefix('<?xml version="1.0" encoding="UTF-8"?>')


def test_health_endpoint_is_simple_ok():
    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_landing_page_and_manifest_work():
    with TestClient(main.app) as client:
        root = client.get("/")
        page = client.get("/landing")
        manifest = client.get("/manifest.json")

    assert root.status_code == 200
    assert root.json() == {"status": "running"}
    assert page.status_code == 200
    assert "Start MS2.0" in page.text
    assert "verification code" in page.text
    assert "WhatsApp" not in page.text
    assert manifest.status_code == 200
    assert manifest.json()["short_name"] == "MS2.0"
    assert manifest.json()["start_url"] == "/start"


def test_status_page_shows_startup_readiness_and_localhost_warning(monkeypatch):
    settings = Settings(_env_file=None, public_base_url="http://localhost:8000")
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_sheet_store", lambda: FakeStatusStore())

    with TestClient(main.app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert "App running" in response.text
    assert "Google Sheets connected" in response.text
    assert "WhatsApp provider" in response.text
    assert "http://localhost:8000/bridge/whatsapp-web" in response.text
    assert "Baileys WhatsApp bridge can still run locally" in response.text


def test_status_page_shows_production_ready_for_https_domain(monkeypatch):
    settings = Settings(
        _env_file=None,
        APP_BASE_URL="https://pharmareen.example.co.ke",
        WHATSAPP_NUMBER="25414155238886",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_sheet_store", lambda: FakeStatusStore())

    with TestClient(main.app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    assert "Public URL looks ready" in response.text
    assert "https://pharmareen.example.co.ke/bridge/whatsapp-web" in response.text


def test_debug_config_does_not_expose_secrets(monkeypatch):
    settings = Settings(
        _env_file=None,
        APP_BASE_URL="https://pharmareen.replit.app",
        WHATSAPP_NUMBER="25414155238886",
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
    assert data["whatsapp_provider"] == "whatsapp_web"
    assert data["whatsapp_number_present"] is True
    assert data["google_credentials_present"] is True
    assert "super-secret-token" not in response.text
    assert "sk-secret" not in response.text


def test_debug_whatsapp_test_returns_xml(monkeypatch):
    fake_intake = FakeIntake("👋 MS2.0 Help")
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, WHATSAPP_NUMBER="25414155238886"))

    with TestClient(main.app) as client:
        response = client.post("/debug/whatsapp-test")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["response_type"] == "whatsapp_xml"
    assert "<Response><Message>" in data["response_body_preview"]
    assert data["command_handler"] == "help_start"
    assert fake_intake.received == "start"


def test_legacy_form_webhook_logs_reply_length_and_returns_xml(monkeypatch, capsys):
    fake_intake = FakeIntake("MS2.0 Help\n\nSell:\nPanadol 2")
    monkeypatch.setattr(main, "get_intake_service", lambda: fake_intake)
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)
    main.processed_message_sids.clear()

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/whatsapp",
            data={
                "Body": "Start",
                "From": "whatsapp:+254700000000",
                "To": "whatsapp:+14155238886",
                "MessageSid": "SMHELPLOG1",
            },
        )

    captured = capsys.readouterr().out
    assert response.status_code == 200
    assert "xml" in response.headers["content-type"]
    assert response.text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert xml_payload(response.text).startswith("<Response>")
    assert "<Message>" in response.text
    assert "WHATSAPP_REPLY_LENGTH=" in captured
    assert "WHATSAPP_REPLY_PREVIEW=MS2.0 Help" in captured
    assert "WHATSAPP_REPLY_XML_PREVIEW=" in captured
    assert "WHATSAPP_REPLY_CONTENT_TYPE=application/xml" in captured
    assert fake_intake.received == "Start"


def test_debug_xml_test_returns_valid_xml():
    with TestClient(main.app) as client:
        response = client.get("/debug/xml-test")

    assert response.status_code == 200
    assert "xml" in response.headers["content-type"]
    assert response.text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert xml_payload(response.text).startswith("<Response>")
    assert "<Message>MS2.0 XML test</Message>" in response.text


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


def test_pdf_download_route_searches_configured_report_folder(tmp_path, monkeypatch):
    generated_dir = tmp_path / "generated"
    fallback_dir = tmp_path / "fallback"
    generated_dir.mkdir()
    fallback_dir.mkdir()
    report = generated_dir / "live-report.pdf"
    report.write_bytes(b"%PDF-1.4 live")
    monkeypatch.setenv("PHARMAREEN_REPORTS_DIR", str(generated_dir))
    monkeypatch.setattr(main, "reports_pdf_dir", lambda: fallback_dir)

    with TestClient(main.app) as client:
        response = client.get("/reports/download/live-report.pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-1.4")


def test_pdf_download_route_regenerates_missing_daily_report(tmp_path, monkeypatch):
    class EmptyReportStore:
        def read_transactions(self, report_date):
            return []

        def read_daily_logs(self, report_date):
            return []

        def list_low_stock_items(self):
            return []

    monkeypatch.setattr(main, "reports_pdf_dir", lambda: tmp_path)
    monkeypatch.setattr(main, "get_sheet_store", lambda: EmptyReportStore())
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, pharmacy_name="PharMareen"))

    with TestClient(main.app) as client:
        response = client.get("/reports/download/PharMareen_Daily_Report_2026-05-16.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


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
    assert "Heard:" in response.text
    assert "Heard: Panadol two, later Cetirizine three" in response.text
    assert "Command: Panadol 2, later Cetirizine 3" in response.text
    assert fake_intake.received == "Panadol 2, later Cetirizine 3"


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
    assert "I heard the voice but could not read it clearly" in response.text
    assert 'Try saying: "Panadol two" or type: Panadol 2.' in response.text


def test_voice_note_without_openai_key_fails_gracefully(monkeypatch):
    monkeypatch.setattr(main, "get_whatsapp_client", lambda: FakeWhatsApp())
    monkeypatch.setattr(main, "get_transcription_service", lambda: UnavailableTranscription())
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/whatsapp",
            data={
                "NumMedia": "1",
                "MediaContentType0": "audio/ogg",
                "MediaUrl0": "https://example.com/audio.ogg",
                "From": "whatsapp:+254700000003",
                "MessageSid": "SMVOICENOKEY1",
            },
        )

    assert response.status_code == 200
    assert "Voice received, but voice is not enabled yet" in response.text
    assert "Send text like: Panadol 2" in response.text


def test_voice_webhook_with_fake_media_transcription_error_does_not_crash(monkeypatch):
    monkeypatch.setattr(main, "get_whatsapp_client", lambda: FakeWhatsApp())
    monkeypatch.setattr(main, "get_transcription_service", lambda: FailingTranscription())
    monkeypatch.setattr(main, "log_webhook_request", lambda *args, **kwargs: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/webhook/whatsapp",
            data={
                "NumMedia": "1",
                "MediaContentType0": "audio/ogg",
                "MediaUrl0": "https://example.com/audio.ogg",
                "From": "whatsapp:+254700000004",
                "MessageSid": "SMVOICEFAIL1",
            },
        )

    assert response.status_code == 200
    assert "<Response><Message>" in response.text
    assert "I heard the voice but could not read it clearly" in response.text


def test_xml_pdf_media_payload_created_for_public_report(monkeypatch):
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


def test_xml_pdf_fallback_link_stays_when_not_attachable(monkeypatch):
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


def test_unclear_voice_note_asks_for_small_correction(monkeypatch):
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

    assert "I could not safely record that." in first.text
    assert "Try: Panadol 2 cash" in first.text
    assert fake_intake.received == ""


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
