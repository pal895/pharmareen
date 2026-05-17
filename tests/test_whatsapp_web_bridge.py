from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings


def bridge_payload(message: str, sender: str = "254700000000@s.whatsapp.net") -> dict[str, str]:
    return {
        "message": message,
        "from": sender,
        "message_id": f"waweb-{uuid4()}",
    }


def test_whatsapp_web_bridge_requires_message():
    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json={"from": "254700000000@s.whatsapp.net"},
        )

    assert response.status_code == 400


def test_whatsapp_web_bridge_ignores_direct_sender_without_allowlist(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("help"))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "safe_mode_no_allowlist"


def test_whatsapp_web_bridge_ignores_group_messages(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json={
                "message": "Panadol 2",
                "from": "120363000000000000@g.us",
                "message_id": f"waweb-group-{uuid4()}",
                "is_group": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "not_direct_chat"


def test_whatsapp_web_bridge_ignores_status_broadcast(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json={
                "message": "Panadol 2",
                "from": "status@broadcast",
                "message_id": f"waweb-status-{uuid4()}",
                "is_broadcast": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "not_direct_chat"


def test_whatsapp_web_bridge_ignores_newsletter_or_channel(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json={
                "message": "Panadol 2",
                "from": "123456789@newsletter",
                "message_id": f"waweb-newsletter-{uuid4()}",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "not_direct_chat"


def test_whatsapp_web_bridge_ignores_sender_not_in_allowlist(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254711111111"),
    )

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("Panadol 2"))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "sender_not_allowed"


def test_whatsapp_web_bridge_processes_allowed_sender(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("help"))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Panadol" in data["reply"]
    assert data["command_handler"] == "help_start"


def test_whatsapp_web_bridge_greeting_and_how_to_use_are_human_friendly(monkeypatch):
    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        hello = client.post("/bridge/whatsapp-web", json=bridge_payload("hello"))
        guide = client.post("/bridge/whatsapp-web", json=bridge_payload("how do I use this"))

    assert hello.status_code == 200
    assert "Welcome to PharMareen" in hello.json()["reply"]
    assert "Panadol 2" in hello.json()["reply"]
    assert guide.status_code == 200
    assert "PHARMAREEN QUICK COMMANDS" in guide.json()["reply"]
    assert "Offline mode" in guide.json()["reply"]


def test_whatsapp_web_bridge_followup_sale_uses_sender_context(monkeypatch):
    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        first = client.post("/bridge/whatsapp-web", json=bridge_payload("sell panadol"))
        second = client.post("/bridge/whatsapp-web", json=bridge_payload("2"))

    assert first.status_code == 200
    assert first.json()["reply"] == "How many Panadol were sold?"
    assert second.status_code == 200
    assert "Panadol x2 recorded" in second.json()["reply"]
    assert "Stock left:" in second.json()["reply"]


def test_whatsapp_web_bridge_ignores_lid_sender_without_test_mode(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json=bridge_payload("help", sender="894365771@lid"),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "sender_direct_but_no_phone_digits"


def test_whatsapp_web_bridge_allows_lid_sender_in_test_mode(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOW_ALL_DIRECT_CHATS_FOR_TEST=True),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json=bridge_payload("help", sender="894365771@lid"),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Panadol" in data["reply"]
    assert data["command_handler"] == "help_start"


def test_whatsapp_web_bridge_allows_lid_sender_when_payload_sets_test_mode(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))

    with TestClient(main.app) as client:
        payload = bridge_payload("help", sender="894365771@lid")
        payload["allow_all_direct_chats_for_test"] = True
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Panadol" in data["reply"]
    assert data["command_handler"] == "help_start"


def test_whatsapp_web_bridge_allows_lid_sender_when_payload_test_mode_is_string(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))

    with TestClient(main.app) as client:
        payload = bridge_payload("help", sender="894365771@lid")
        payload["allow_all_direct_chats_for_test"] = "true"
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["reply"]
    assert data["command_handler"] == "help_start"


def test_whatsapp_web_bridge_transcribes_audio_payload(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            assert audio_bytes == b"fake voice bytes"
            assert content_type == "audio/ogg"
            return "Panadol sold two"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"
    payload["voice_transcribe_only"] = True

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["reply"] == "🎧 Voice received: Panadol sold two"
    assert data["message_type"] == "voice"
    assert data["command_handler"] == "voice_note_transcribed"


def test_whatsapp_web_bridge_voice_quota_fallback(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            raise Exception("Error code: 429 - insufficient_quota")

    main.last_openai_error.update({"feature": "", "message": "", "quota_missing": False, "timestamp": ""})
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"
    payload["voice_transcribe_only"] = True

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)
        status = client.get("/debug/voice-ai")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["reply"] == "🎧 Voice received safely. AI transcription is ready but OpenAI credits are not active yet."
    assert data["command_handler"] == "voice_note_quota_missing"
    assert status.json()["voice_pipeline_installed"] is True
    assert status.json()["openai_key_present"] is True
    assert status.json()["quota_missing"] is True


def test_whatsapp_web_bridge_photo_quota_fallback(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            assert image_bytes == b"fake image bytes"
            assert content_type == "image/jpeg"
            raise Exception("Error code: 429 - insufficient_quota")

    main.last_openai_error.update({"feature": "", "message": "", "quota_missing": False, "timestamp": ""})
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)
        status = client.get("/debug/photo-ai")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["reply"] == "📷 Photo received safely. I saved it for review."
    assert data["message_type"] == "image"
    assert data["command_handler"] == "photo_received_saved_safely"
    saved_images = list((tmp_path / "data" / "photo_uploads").glob("*.jpg"))
    assert len(saved_images) == 1
    assert saved_images[0].read_bytes() == b"fake image bytes"
    log_path = tmp_path / "data" / "photo_intake_log.jsonl"
    assert log_path.exists()
    log_entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert log_entry["media_type"] == "image/jpeg"
    assert log_entry["file_path"].startswith("data/photo_uploads/")
    assert log_entry["processing_status"] == "needs_review"
    assert log_entry["classification"]["media_kind"] == "unknown_photo"
    assert log_entry["media_job"]["requires_confirmation"] is False
    assert log_entry["extraction"]["extraction_status"] == "saved_needs_review"
    status_data = status.json()
    assert status_data["photo_pipeline_installed"] is True
    assert status_data["upload_folder_exists"] is True
    assert status_data["images_received_count"] == 1
    assert status_data["last_uploaded_image"]["file_path"].startswith("data/photo_uploads/")


def test_whatsapp_web_bridge_classifies_invoice_photo_without_calling_ai(monkeypatch, tmp_path):
    class FailingAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            raise AssertionError("photo intake should not call AI unless extraction is explicitly requested")

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FailingAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"invoice image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "supplier invoice MedCare INV123"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "📷 Photo received safely. This looks like a supplier invoice.\nWaiting for your confirmation before stock update."
    log_entry = json.loads((tmp_path / "data" / "photo_intake_log.jsonl").read_text(encoding="utf-8").strip())
    assert log_entry["classification"]["media_kind"] == "supplier_invoice"
    assert log_entry["media_job"]["requires_confirmation"] is True


def test_whatsapp_web_bridge_payload_test_mode_still_blocks_group(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))

    with TestClient(main.app) as client:
        payload = bridge_payload("help", sender="120363000000000000@g.us")
        payload["allow_all_direct_chats_for_test"] = True
        payload["is_group"] = True
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "not_direct_chat"


def test_demo_mode_still_requires_allowlist(monkeypatch):
    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, DEMO_MODE=True))

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("Panadol 2"))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reply"] == ""
    assert data["error_reason"] == "safe_mode_no_allowlist"


def test_demo_mode_allows_sale_for_allowed_sender(monkeypatch):
    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            DEMO_MODE=True,
            ALLOWED_WHATSAPP_NUMBERS="254700000000",
        ),
    )

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("Panadol 2"))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Panadol" in data["reply"]
    assert "Stock left:" in data["reply"]


def test_blocked_sender_logs_masked_phone_without_message_body(monkeypatch, caplog):
    secret_body = "SECRET SPAM BODY Panadol stock"
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    caplog.set_level(logging.INFO)
    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json=bridge_payload(secret_body, sender="254799999921@s.whatsapp.net"),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert "2547******21" in caplog.text
    assert secret_body not in caplog.text


def test_baileys_bridge_source_uses_safe_reply_and_strict_allowlist():
    source = (Path(__file__).resolve().parents[1] / "baileys-bridge.js").read_text(encoding="utf-8-sig")
    backend_source = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")

    assert "async function safeSendReply" in source
    assert "safe_mode_no_allowlist" in source
    assert "@s.whatsapp.net" in source
    assert "domain === '@lid'" in source
    assert "ALLOW_ALL_DIRECT_CHATS_FOR_TEST" in source
    assert "allow_all_direct_chats_for_test" in source
    assert "jid_domain=" in source
    assert "TEST MODE ACCEPTED DIRECT CHAT" in source
    assert "BACKEND_REPLY_RECEIVED" in source
    assert "BACKEND_REQUEST_URL" in source
    assert "BACKEND_HTTP_STATUS" in source
    assert "BACKEND_JSON_RESPONSE" in source
    assert "INCOMING_SENDER_JID" in source
    assert "INCOMING_MESSAGE_TEXT" in source
    assert "EXTRACTED_REPLY_TEXT" in source
    assert "WHATSAPP_SEND_TARGET" in source
    assert "WHATSAPP_REPLY_SENT" in source
    assert "WHATSAPP_SEND_FAILED" in source
    assert "downloadMediaMessage" in source
    assert "VOICE_MESSAGE_RECEIVED" in source
    assert "VOICE_MESSAGE_DOWNLOADED" in source
    assert "PHOTO_MESSAGE_RECEIVED" in source
    assert "PHOTO_MESSAGE_DOWNLOADED" in source
    assert "voice_transcribe_only" in source
    assert "media_base64" in source
    assert "message_id=" in source
    assert "extractBackendReply" in source
    assert "whatsapp_reply" in source
    assert "✅ PharMareen received your message." in source
    assert "BACKEND_TEST_MODE_ACCEPTED_LID" in backend_source
    assert "BACKEND_REPLY_TEXT" in backend_source
    assert "boolish" in backend_source
    assert "SAFE MODE: no allowed numbers configured" in source
    assert "GROUP REPLIES: DISABLED" in source
    assert "UNKNOWN NUMBER REPLIES: DISABLED" in source

    send_lines = [line.strip() for line in source.splitlines() if "sock.sendMessage" in line]
    assert send_lines == ["const result = await sock.sendMessage(jid, { text: body });"]


def test_windows_local_bridge_helper_requires_backend_and_allowlist():
    root = Path(__file__).resolve().parents[1]
    script = (root / "start_local_whatsapp_bridge.bat").read_text()
    guide = (root / "WINDOWS_WHATSAPP_BRIDGE.md").read_text()
    wrapper = (root / "local_whatsapp_bridge.js").read_text()

    assert "PHARMAREEN_BACKEND_URL is missing" in script
    assert "ALLOWED_WHATSAPP_NUMBERS is missing" in script
    assert "TEST MODE ACTIVE" in script
    assert "GROUP REPLIES: DISABLED" in script
    assert "UNKNOWN NUMBER REPLIES: DISABLED" in script
    assert "node baileys-bridge.js" in script
    assert "https://nodejs.org/en/download" in guide
    assert "set PHARMAREEN_BACKEND_URL=https://pharmareen-1--pal895.replit.app" in guide
    assert "set ALLOWED_WHATSAPP_NUMBERS=254757637709" in guide
    assert "set ALLOW_ALL_DIRECT_CHATS_FOR_TEST=true" in guide
    assert "require('./baileys-bridge')" in wrapper
