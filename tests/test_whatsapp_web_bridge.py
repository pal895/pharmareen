from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings


@pytest.fixture(autouse=True)
def clear_bridge_media_cache():
    main.offline_media_job_results.clear()
    yield
    main.offline_media_job_results.clear()


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


def test_whatsapp_web_bridge_processes_voice_transcript_through_local_intake(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            assert audio_bytes == b"fake voice bytes"
            return "Panadol mbili cash na Amox moja mpesa"

    seen: dict[str, str] = {}

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        seen["text"] = text
        seen["sender"] = sender
        return "✅ Recorded:\n• Panadol x2 cash\n• Amox x1 M-Pesa\nStock updated."

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["command_handler"] == "voice_note_processed"
    assert "Heard:" in data["reply"]
    assert "Heard: Panadol mbili cash, Amox moja mpesa" in data["reply"]
    assert "Panadol x2 cash" in data["reply"]
    assert seen["sender"] == "254700000000@s.whatsapp.net"


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
    assert data["reply"] == "🎧 Voice received safely. Voice reading is unavailable right now. Please choose the medicine or type it."
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
    assert "Photo review is unavailable right now" in data["reply"]
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
    assert log_entry["processing_status"] == "waiting_for_openai_credits"
    assert log_entry["classification"]["media_kind"] == "unknown_photo"
    assert log_entry["media_job"]["requires_confirmation"] is False
    assert log_entry["extraction"]["extraction_status"] == "waiting_for_openai_credits"
    status_data = status.json()
    assert status_data["photo_pipeline_installed"] is True
    assert status_data["upload_folder_exists"] is True
    assert status_data["images_received_count"] == 1
    assert status_data["last_uploaded_image"]["file_path"].startswith("data/photo_uploads/")



def test_whatsapp_web_bridge_processes_invoice_photo_with_ai_when_key_active(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            assert image_bytes == b"invoice image bytes"
            assert content_type == "image/jpeg"
            return {
                "supplier": "MedCare",
                "confidence": 0.9,
                "items": [{"drug_name": "Panadol", "quantity": 20}],
            }

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"invoice image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "supplier invoice MedCare INV123"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "Invoice processed" in data["reply"]
    assert "Supplier: MedCare" in data["reply"]
    assert "Panadol x20" in data["reply"]
    log_entry = json.loads((tmp_path / "data" / "photo_intake_log.jsonl").read_text(encoding="utf-8").strip())
    assert log_entry["classification"]["media_kind"] == "supplier_invoice"
    assert log_entry["media_job"]["requires_confirmation"] is True

def test_whatsapp_web_bridge_runs_invoice_ai_when_scan_is_requested(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            assert image_bytes == b"invoice image bytes"
            assert content_type == "image/jpeg"
            return {
                "confidence": 0.87,
                "items": [
                    {"drug_name": "Panadol", "quantity": 20, "unit_type": "boxes", "supplier": "MedCare"},
                    {"drug_name": "ORS", "quantity": 10, "unit_type": "packs", "supplier": "MedCare"},
                ],
                "message": "2 invoice rows found",
            }

    monkeypatch.setenv("ENABLE_INVOICE_AI", "true")
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"invoice image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "scan invoice MedCare INV123"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "📷 Invoice processed" in data["reply"]
    assert "Supplier: MedCare" in data["reply"]
    assert "Panadol x20 boxes" in data["reply"]
    assert "Review needed before stock update." in data["reply"]
    log_entry = json.loads((tmp_path / "data" / "photo_intake_log.jsonl").read_text(encoding="utf-8").strip())
    assert log_entry["extraction"]["extraction_status"] == "needs_review"
    assert log_entry["extraction"]["items"][0]["drug_name"] == "Panadol"


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
    assert "async function safeSendSelectorReply" in source
    assert "SELECTOR_INTERACTIVE_ATTEMPT" in source
    assert "SELECTOR_INTERACTIVE_SENT" in source
    assert "SELECTOR_INTERACTIVE_FAILED" in source
    assert "buttonText: 'Choose'" in source
    assert "sections: [{ title: 'Quick sale', rows: selectorRows(card) }]" in source
    assert "buttonsResponseMessage" in source
    assert "listResponseMessage" in source
    assert "templateButtonReplyMessage" in source
    assert "nativeFlowResponseMessage" in source
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
    assert "reportRuntimeStatus" in source
    assert "/bridge/runtime-status" in source
    assert "setInterval(() => reportRuntimeStatus({}), 10000)" in source
    assert "scheduleReconnect" in source
    assert "bridge picked offline confirmation" in source
    assert "BRIDGE_PICKED_OFFLINE_CONFIRMATION" in source
    assert "normalized jid=" in source
    assert "payload.pending" in source
    assert "OFFLINE_CONFIRMATION_FORMAT_EMPTY" in source
    assert "WHATSAPP_CONFIRMATION_SEND_TARGET" in source
    assert "WHATSAPP_CONFIRMATION_SEND_RESULT" in source
    assert "OFFLINE_CONFIRMATION_ACKED" in source
    assert "offline confirmation onWhatsApp result" in source
    assert "sending offline confirmation" in source
    assert "offline confirmation sent successfully" in source
    assert "offline confirmation send failed" in source
    assert "confirmation delivery result" in source
    assert "number_not_registered_on_whatsapp" in source
    assert "/offline/whatsapp-confirmations/fail" in source
    assert "offline confirmation queued for" in backend_source
    assert "REAL_OFFLINE_SYNC_RECEIVED" in backend_source
    assert "REAL_OFFLINE_RESULT_SUMMARY" in backend_source
    assert "OFFLINE_CONFIRMATION_QUEUED_REAL_SYNC" in backend_source
    assert "confirmation_whatsapp_present" in backend_source
    assert "OFFLINE_CONFIRMATION_ACKED" in backend_source
    assert "OFFLINE_CONFIRMATION_FAILED" in backend_source
    assert "/debug/offline-confirmations" in backend_source
    assert "/debug/offline-confirmations/test" in backend_source
    assert "/debug/offline-confirmations/send-test" in backend_source
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
    assert "const result = await sock.sendMessage(jid, { text: body });" in send_lines
    assert "const result = await sock.sendMessage(target, { text: body });" in send_lines


def test_bridge_runtime_status_reports_connected_receive_reply_and_error_fields():
    previous = dict(main.whatsapp_bridge_runtime_status)
    try:
        with TestClient(main.app) as client:
            update = client.post(
                "/bridge/runtime-status",
                json={
                    "state": "open",
                    "connected": True,
                    "qr_required": False,
                    "last_message_received": "2026-05-31T12:00:00+03:00",
                    "last_reply_sent": "2026-05-31T12:00:01+03:00",
                    "last_error": "",
                },
            )
            status = client.get("/debug/system-status")

        assert update.status_code == 200
        assert status.status_code == 200
        runtime = status.json()["details"]["bridge"]["runtime"]
        assert runtime["state"] == "open"
        assert runtime["connected"] is True
        assert runtime["qr_required"] is False
        assert runtime["last_message_received"] == "2026-05-31T12:00:00+03:00"
        assert runtime["last_reply_sent"] == "2026-05-31T12:00:01+03:00"
        assert runtime["last_error"] == ""
        assert runtime["updated_at"]
    finally:
        main.whatsapp_bridge_runtime_status.clear()
        main.whatsapp_bridge_runtime_status.update(previous)


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



def test_whatsapp_voice_cleans_swahili_misheard_number_and_records(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            assert audio_bytes == b"fake voice bytes"
            return "Panadol, billi, cash"

    seen: dict[str, str] = {}

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        seen["text"] = text
        return "? Panadol x2 cash recorded\nStock left: 18"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "ok"
    assert seen == {}
    assert "Heard: Panadol mbili cash" in data["reply"]
    assert "Panadol x2 - Cash" in data["reply"]


def test_whatsapp_voice_does_not_claim_records_updated_when_parse_fails(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return "Panadol, billi, cash"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", lambda text, sender: "I am not fully sure what you meant.")

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert "Panadol x2 - Cash" in data["reply"]
    assert "Records updated safely" not in data["reply"]


def test_whatsapp_voice_random_transcript_is_saved_for_review_without_intake(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return "Share this video with your friends"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(
        main,
        "process_intake_text_for_sender",
        lambda text, sender: (_ for _ in ()).throw(AssertionError("random transcript must not enter intake")),
    )

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"random voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["command_handler"] == "voice_note_needs_review"
    assert "Voice note saved for review" in data["reply"]
    assert "Share this video" not in data["reply"]


def test_whatsapp_voice_known_medicine_only_opens_local_selector_without_ai_interpretation(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    class FakeTranscriptionService:
        is_available = True

        def __init__(self, transcripts: list[str]):
            self.transcripts = transcripts

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return self.transcripts.pop(0)

    transcription = FakeTranscriptionService(["Panadol", "Glucose", "ORS", "Belladonna"])
    selected: list[str] = []

    def fake_prepare_local_sale_selector_reply(text: str, quantity: int, payment: str, sender: str) -> str:
        selected.append(text)
        return "\n".join(
            [
                "Sale approval",
                f"{text} x{quantity} - {payment}",
                "Qty: 1 | 2 | 3 | 5 | 10 | + | -",
                "Pay: Cash | M-Pesa | Credit | Mixed",
                "Confirm | Cancel",
            ]
        )

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: transcription)
    monkeypatch.setattr(main, "prepare_local_sale_selector_reply", fake_prepare_local_sale_selector_reply)
    AI_ROUTE_DECISION_LOG.clear()

    with TestClient(main.app) as client:
        for medicine in ["Panadol", "Glucose", "ORS", "Belladonna"]:
            payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
            payload["media_base64"] = base64.b64encode(f"{medicine} voice".encode()).decode("ascii")
            payload["media_mime_type"] = "audio/ogg"
            response = client.post("/bridge/whatsapp-web", json=payload)
            data = response.json()
            assert response.status_code == 200
            assert data["command_handler"] == "voice_medicine_selector"
            assert f"{medicine} x1 - Cash" in data["reply"]
            assert "Qty: 1 | 2 | 3 | 5 | 10 | + | -" in data["reply"]

    assert selected == ["Panadol", "Glucose", "ORS", "Belladonna"]
    assert len(AI_ROUTE_DECISION_LOG) == 4
    assert all(item["reason"] == "voice_transcription" for item in AI_ROUTE_DECISION_LOG)


def test_whatsapp_text_glucose_opens_short_local_selector_card_without_ai(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )
    AI_ROUTE_DECISION_LOG.clear()

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("Glucose"))

    data = response.json()
    assert response.status_code == 200
    assert data["command_handler"] == "text_medicine_selector"
    assert data["selector_card"]["medicine"] == "Glucose"
    assert data["selector_card"]["quantity"] == 1
    assert "Glucose x1 - Cash" in data["reply"]
    assert "Qty: 1 | 2 | 3 | 5 | 10 | + | -" in data["reply"]
    assert "Then reply YES" not in data["reply"]
    assert AI_ROUTE_DECISION_LOG == []


def test_whatsapp_text_spoken_quantity_payment_prefills_local_selector_card_without_ai(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )
    AI_ROUTE_DECISION_LOG.clear()

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("Panadol mbili mpesa"))

    data = response.json()
    assert response.status_code == 200
    assert data["command_handler"] == "text_medicine_selector"
    assert data["selector_card"]["medicine"] == "Panadol"
    assert data["selector_card"]["quantity"] == 2
    assert data["selector_card"]["payment"] == "M-Pesa"
    assert "Panadol x2 - M-Pesa" in data["reply"]
    assert AI_ROUTE_DECISION_LOG == []


def test_whatsapp_text_unknown_medicine_uses_local_setup_prompt_without_ai(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )
    AI_ROUTE_DECISION_LOG.clear()

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("xyzmedicine 2"))

    assert response.status_code == 200
    assert "not found in inventory" in response.json()["reply"]
    assert all(not item["used_ai"] for item in AI_ROUTE_DECISION_LOG)


def test_whatsapp_text_amox_asks_local_clarification_without_ai(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )
    AI_ROUTE_DECISION_LOG.clear()

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("amox"))

    reply = response.json()["reply"]
    assert response.status_code == 200
    assert "Which medicine?" in reply
    assert "Amoxicillin" in reply
    assert "Amoxil" in reply
    assert AI_ROUTE_DECISION_LOG == []


def test_whatsapp_voice_spoken_quantity_payment_returns_one_prefilled_selector_card(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    class FakeTranscriptionService:
        is_available = True
        calls = 0

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            self.calls += 1
            return "Panadol mbili mpesa"

    transcription = FakeTranscriptionService()
    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    main.processed_whatsapp_web_message_ids.clear()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: transcription)
    AI_ROUTE_DECISION_LOG.clear()
    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["message_id"] = "voice-selector-once"
    payload["media_base64"] = base64.b64encode(b"voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        first = client.post("/bridge/whatsapp-web", json=payload)
        duplicate = client.post("/bridge/whatsapp-web", json=payload)

    data = first.json()
    assert first.status_code == 200
    assert data["command_handler"] == "voice_medicine_selector"
    assert data["selector_card"]["medicine"] == "Panadol"
    assert data["selector_card"]["quantity"] == 2
    assert data["selector_card"]["payment"] == "M-Pesa"
    assert "Panadol x2 - M-Pesa" in data["reply"]
    assert "saved for review" not in data["reply"]
    assert duplicate.json()["status"] == "duplicate"
    assert duplicate.json()["reply"] == ""
    assert transcription.calls == 1
    assert len(AI_ROUTE_DECISION_LOG) == 1
    assert AI_ROUTE_DECISION_LOG[0]["reason"] == "voice_transcription"


def test_whatsapp_voice_same_audio_reuses_selector_result_without_second_transcription(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    class FakeTranscriptionService:
        is_available = True
        calls = 0

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            self.calls += 1
            return "Glucose mbili mpesa"

    transcription = FakeTranscriptionService()
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_MODE=True, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: transcription)
    AI_ROUTE_DECISION_LOG.clear()
    first_payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    first_payload["media_base64"] = base64.b64encode(b"same glucose voice bytes").decode("ascii")
    first_payload["media_mime_type"] = "audio/ogg"
    second_payload = {**first_payload, "message_id": "same-audio-new-whatsapp-id"}

    with TestClient(main.app) as client:
        first = client.post("/bridge/whatsapp-web", json=first_payload)
        second = client.post("/bridge/whatsapp-web", json=second_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["selector_card"]["medicine"] == "Glucose"
    assert second.json()["selector_card"]["medicine"] == "Glucose"
    assert second.json()["selector_card"]["quantity"] == 2
    assert second.json()["selector_card"]["payment"] == "M-Pesa"
    assert transcription.calls == 1
    assert [item["reason"] for item in AI_ROUTE_DECISION_LOG] == ["voice_transcription", "media_result_cache"]
    assert AI_ROUTE_DECISION_LOG[-1]["from_cache"] is True


def test_whatsapp_voice_amox_asks_local_clarification_before_intake(monkeypatch):
    class FakeStore:
        @staticmethod
        def list_master_drug_names():
            return ["Amoxyl", "Amoxicillin"]

    class FakeIntakeService:
        store = FakeStore()
        aliases_by_key = {}

    monkeypatch.setattr(main, "get_intake_service", lambda: FakeIntakeService())
    monkeypatch.setattr(
        main,
        "process_intake_text_for_sender",
        lambda text, sender: (_ for _ in ()).throw(AssertionError("ambiguous medicine must not enter intake")),
    )

    reply = main.local_voice_selector_reply("amox", "254700000000@s.whatsapp.net")

    assert "Which medicine?" in reply
    assert "Amoxyl" in reply
    assert "Amoxicillin" in reply


def test_whatsapp_voice_random_words_do_not_open_local_selector(monkeypatch):
    monkeypatch.setattr(
        main,
        "process_intake_text_for_sender",
        lambda text, sender: (_ for _ in ()).throw(AssertionError("random words must not enter intake")),
    )

    assert main.local_voice_selector_reply("share this video with friends", "254700000000@s.whatsapp.net") == ""


def test_offline_voice_sync_transcribes_and_returns_parsed_confirmation(monkeypatch, tmp_path):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            assert audio_bytes == b"offline voice"
            assert content_type == "audio/ogg"
            return "Panadol mbili cash"

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", lambda text, sender: "? Panadol x2 cash recorded\nStock left: 18")
    main.offline_synced_entry_ids.clear()

    payload = {
        "sender": "254700000000@s.whatsapp.net",
        "entries": [
            {
                "id": "voice-ai-1",
                "action": "audio",
                "file_type": "audio/ogg",
                "data_url": "data:audio/ogg;base64," + base64.b64encode(b"offline voice").decode("ascii"),
                "sync_status": "pending",
            }
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["synced"][0]["message_type"] == "voice"
    assert "Panadol x2 cash recorded" in data["synced"][0]["reply"]
    assert "Offline records synced safely" in data["whatsapp_reply"]


def test_offline_invoice_photo_sync_runs_ai_when_enabled(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            assert image_bytes == b"invoice bytes"
            assert content_type == "image/jpeg"
            return {
                "supplier": "MedCare",
                "confidence": 0.88,
                "items": [
                    {"drug_name": "Panadol", "quantity": 20},
                    {"drug_name": "ORS", "quantity": 10},
                ],
            }

    monkeypatch.setenv("ENABLE_INVOICE_AI", "true")
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())
    main.offline_synced_entry_ids.clear()

    payload = {
        "sender": "254700000000@s.whatsapp.net",
        "entries": [
            {
                "id": "photo-ai-1",
                "action": "photo",
                "file_name": "supplier-invoice.jpg",
                "file_type": "image/jpeg",
                "purpose": "invoice_photo",
                "data_url": "data:image/jpeg;base64," + base64.b64encode(b"invoice bytes").decode("ascii"),
                "sync_status": "pending",
            }
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert data["synced"][0]["message_type"] == "image"
    assert "Invoice processed" in data["synced"][0]["reply"]
    assert "Supplier: MedCare" in data["synced"][0]["reply"]
    assert "Panadol x20" in data["synced"][0]["reply"]



def test_whatsapp_voice_splits_joined_swahili_quantity_payment(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return "Panadol Mbilkash"

    seen: dict[str, str] = {}

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        seen["text"] = text
        return "? Panadol x2 cash recorded\nStock left: 18"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert seen == {}
    assert "Heard: Panadol mbili cash" in data["reply"]
    assert "Panadol x2 - Cash" in data["reply"]


def test_whatsapp_unknown_photo_uses_ai_to_extract_invoice_when_key_active(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            assert image_bytes == b"captionless invoice bytes"
            return {
                "supplier": "Beta Suppliers",
                "confidence": 0.81,
                "items": [
                    {"drug_name": "Panadol", "quantity": 20},
                    {"drug_name": "ORS", "quantity": 10},
                ],
            }

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"captionless invoice bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["filename"] = "photo.jpg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert "Invoice processed" in data["reply"]
    assert "Supplier: Beta Suppliers" in data["reply"]
    assert "Panadol x20" in data["reply"]



def test_whatsapp_voice_repairs_close_medicine_and_joined_payment(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return "Anadol Mbelekash"

    seen: dict[str, str] = {}

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        seen["text"] = text
        return "Panadol x2 cash recorded\nStock left: 18"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert seen == {}
    assert "Heard: Panadol mbili cash" in data["reply"]
    assert "Panadol x2 - Cash" in data["reply"]


def test_whatsapp_voice_repairs_tukas_as_two_cash(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return "Panadol Tukas"

    seen: dict[str, str] = {}

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        seen["text"] = text
        return "Panadol x2 cash recorded\nStock left: 18"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert seen == {}
    assert "Heard: Panadol two cash" in data["reply"]
    assert "Panadol x2 - Cash" in data["reply"]


def test_whatsapp_voice_repairs_melikas_as_mbili_cash(monkeypatch):
    class FakeTranscriptionService:
        is_available = True

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return "Panadol melikas"

    seen: dict[str, str] = {}

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        seen["text"] = text
        return "Panadol x2 cash recorded\nStock left: 18"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: FakeTranscriptionService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"fake voice bytes").decode("ascii")
    payload["media_mime_type"] = "audio/ogg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert seen == {}
    assert "Heard: Panadol mbili cash" in data["reply"]
    assert "Panadol x2 - Cash" in data["reply"]


def test_whatsapp_voice_reconstructs_inventory_medicines_without_ai_interpretation(monkeypatch):
    from app.ai import AI_ROUTE_DECISION_LOG

    class FakeTranscriptionService:
        is_available = True

        def __init__(self, transcripts: list[str]):
            self.transcripts = transcripts

        def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
            return self.transcripts.pop(0)

    transcripts = ["Glucose mbili mpesa", "ORS mbili cash"]
    transcription = FakeTranscriptionService(transcripts)
    seen: list[str] = []

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        seen.append(text)
        if text.startswith("Glucose"):
            return "Glucose x2 M-Pesa recorded\nStock left: 44"
        return "⚠️ ORS out of stock. Sale not recorded. Missed sale saved: ORS x2. Stock left: 0"

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_transcription_service", lambda: transcription)
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)
    AI_ROUTE_DECISION_LOG.clear()

    with TestClient(main.app) as client:
        for index in range(2):
            payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
            payload["media_base64"] = base64.b64encode(f"fake voice bytes {index}".encode()).decode("ascii")
            payload["media_mime_type"] = "audio/ogg"
            response = client.post("/bridge/whatsapp-web", json=payload)
            assert response.status_code == 200

    assert seen == []
    assert all(item["route"] == "audio/transcriptions" for item in AI_ROUTE_DECISION_LOG)
    assert all(item["reason"] == "voice_transcription" for item in AI_ROUTE_DECISION_LOG)


def test_invoice_review_approve_updates_stock_after_ai_extraction(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            return {
                "supplier": "MedCare",
                "invoice_number": "INV123",
                "confidence": 0.9,
                "items": [
                    {"drug_name": "Paracetamol", "quantity": 10, "unit": "boxes"},
                    {"drug_name": "Cough Syrup", "quantity": 20},
                ],
            }

    commands: list[str] = []

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        commands.append(text)
        return f"restocked: {text}"

    main.pending_invoice_reviews.clear()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"invoice image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "supplier invoice"

    with TestClient(main.app) as client:
        first = client.post("/bridge/whatsapp-web", json=payload)
        approve = client.post("/bridge/whatsapp-web", json=bridge_payload("approve invoice", sender="254700000000@s.whatsapp.net"))

    assert first.status_code == 200
    assert "Review needed before stock update" in first.json()["reply"]
    assert "approve" in first.json()["reply"]
    assert approve.status_code == 200
    assert "Invoice approved and stock updated" in approve.json()["reply"]
    assert "Paracetamol restock 10 boxes" in commands[0]
    assert "supplier MedCare" in commands[0]
    assert "invoice INV123" in commands[0]
    assert "Cough Syrup restock 20" in commands[1]


def test_invoice_review_edit_item_quantity_before_approval(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            return {"supplier": "MedCare", "items": [{"drug_name": "Paracetamol"}]}

    commands: list[str] = []

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        commands.append(text)
        return f"restocked: {text}"

    main.pending_invoice_reviews.clear()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"invoice image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "supplier invoice"

    with TestClient(main.app) as client:
        first = client.post("/bridge/whatsapp-web", json=payload)
        edit = client.post("/bridge/whatsapp-web", json=bridge_payload("edit Paracetamol quantity 20", sender="254700000000@s.whatsapp.net"))
        approve = client.post("/bridge/whatsapp-web", json=bridge_payload("add to stock", sender="254700000000@s.whatsapp.net"))

    assert first.status_code == 200
    assert "Some quantities are missing" in first.json()["reply"]
    assert "Updated Paracetamol quantity to 20" in edit.json()["reply"]
    assert "Invoice approved and stock updated" in approve.json()["reply"]
    assert commands == ["Paracetamol restock 20 supplier MedCare"]


def test_shelf_photo_is_not_treated_as_invoice(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            raise AssertionError("shelf photo should not run invoice extraction")

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"shelf image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "stock shelf photo"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert "Stock photo received" in data["reply"]
    assert "scan barcode" in data["reply"]
    assert "Invoice processed" not in data["reply"]



def test_invoice_review_short_edit_rename_and_remove_stay_in_context(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            return {
                "supplier": "MedCare",
                "items": [
                    {"drug_name": "PEP Lime Cordial", "quantity": 3},
                    {"drug_name": "WaterGuard", "quantity": 5},
                    {"drug_name": "Antibiotic Cream", "quantity": 2},
                ],
            }

    commands: list[str] = []

    def fake_process_intake_text_for_sender(text: str, sender: str) -> str:
        commands.append(text)
        return text

    main.pending_invoice_reviews.clear()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process_intake_text_for_sender)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"invoice image bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "supplier invoice"

    with TestClient(main.app) as client:
        client.post("/bridge/whatsapp-web", json=payload)
        edit = client.post("/bridge/whatsapp-web", json=bridge_payload("Edit PEP Lime Cordial 20", sender="254700000000@s.whatsapp.net"))
        rename = client.post("/bridge/whatsapp-web", json=bridge_payload("Rename WaterGuard to Water Guard", sender="254700000000@s.whatsapp.net"))
        remove = client.post("/bridge/whatsapp-web", json=bridge_payload("Remove Antibiotic Cream", sender="254700000000@s.whatsapp.net"))
        approve = client.post("/bridge/whatsapp-web", json=bridge_payload("approve", sender="254700000000@s.whatsapp.net"))

    assert "Updated PEP Lime Cordial quantity to 20" in edit.json()["reply"]
    assert "Renamed WaterGuard to Water Guard" in rename.json()["reply"]
    assert "Removed Antibiotic Cream" in remove.json()["reply"]
    assert "Invoice approved and stock updated" in approve.json()["reply"]
    assert commands == [
        "PEP Lime Cordial restock 20 supplier MedCare",
        "Water Guard restock 5 supplier MedCare",
    ]


def test_unknown_product_photo_with_no_invoice_metadata_returns_shelf_review(monkeypatch, tmp_path):
    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            return {
                "photo_type": "stock shelf photo",
                "confidence": 0.7,
                "items": [
                    {"drug_name": "PEP Lime Cordial"},
                    {"drug_name": "WaterGuard"},
                    {"drug_name": "Luron Aloe Lotion"},
                ],
            }

    main.pending_invoice_reviews.clear()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"unknown shelf bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["filename"] = "photo.jpg"

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=payload)

    reply = response.json()["reply"]
    assert "Shelf photo analyzed" in reply
    assert "PEP Lime Cordial" in reply
    assert "WaterGuard" in reply
    assert "Luron Aloe Lotion" in reply
    assert "Missing:" in reply
    assert "Invoice processed" not in reply
    assert main.pending_invoice_reviews == {}


def test_voice_cleanup_supports_many_medicines_and_messy_phrases():
    cases = [
        ("Panadol mbili cash", "Panadol 2 cash"),
        ("Panadol melikas", "Panadol 2 cash"),
        ("Panadolmelikash", "Panadol 2 cash"),
        ("Anadol Mbelekash", "Panadol 2 cash"),
        ("Panadol Tukas", "Panadol 2 cash"),
        ("Panadol billi cash", "Panadol 2 cash"),
        ("Piriton moja mpesa", "Piriton 1 mpesa"),
        ("Piritononempesa", "Piriton 1 mpesa"),
        ("Paracet mbili cash", "Paracetamol 2 cash"),
        ("PCM mbili mpesa", "Paracetamol 2 mpesa"),
        ("Amox moja mpesa", "Amoxyl 1 mpesa"),
        ("Amoxil mbili cash", "Amoxyl 2 cash"),
        ("Amoxicilin tatu cash", "Amoxicillin 3 cash"),
        ("Cetirizine tukas", "Cetirizine 2 cash"),
        ("Cetrizine moja mpesa", "Cetirizine 1 mpesa"),
        ("ORS mbili cash", "ORS 2 cash"),
        ("Glucose moja mpesa", "Glucose 1 mpesa"),
        ("Insulin two cash", "Insulin 2 cash"),
        ("Antacid mbilicash", "Antacid 2 cash"),
        ("Coughsirup two cash", "Cough Syrup 2 cash"),
        ("Cough Syrup moja mpesa", "Cough Syrup 1 mpesa"),
        ("Antibioticcream one mpesa", "Antibiotic Cream 1 mpesa"),
        ("Antibiotic Cream mbili cash", "Antibiotic Cream 2 cash"),
        ("Watergard moja cash", "WaterGuard 1 cash"),
        ("Water guard mbili mpesa", "WaterGuard 2 mpesa"),
        ("PEP lime cordial mbili mpesa", "PEP Lime Cordial 2 mpesa"),
        ("PEP lime mbili mpesa", "PEP Lime Cordial 2 mpesa"),
        ("nimeuza Panadol mbili cash", "sold Panadol 2 cash"),
        ("niliuza Piriton moja mpesa", "sold Piriton 1 mpesa"),
        ("nimetoa Amox mbili cash", "sold Amoxyl 2 cash"),
        ("ongeza Cetirizine mbili", "+Cetirizine 2"),
        ("ongeza Watergard moja", "+WaterGuard 1"),
    ]

    for raw, expected in cases:
        cleaned = main.clean_voice_transcript_for_intake(raw)
        interpreted = main.normalize_spoken_command_text(cleaned)
        assert interpreted == expected, raw


def test_invoice_review_edit_x_quantity_and_cancel_win_before_inventory_parser(monkeypatch):
    calls: list[str] = []
    sender = "254700000000@s.whatsapp.net"
    main.pending_invoice_reviews.clear()
    main.pending_invoice_reviews[main.invoice_review_key(sender)] = {
        "supplier": "MedCare",
        "invoice_number": "INV777",
        "items": [{"drug_name": "Paracetamol"}, {"drug_name": "Cough Syrup", "quantity": 2}],
    }

    def fake_process(text: str, sender_value: str) -> str:
        calls.append(text)
        return text

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process)

    with TestClient(main.app) as client:
        edit = client.post("/bridge/whatsapp-web", json=bridge_payload("Edit paracetamol x20", sender=sender))
        cancel = client.post("/bridge/whatsapp-web", json=bridge_payload("cancel", sender=sender))

    assert "Updated Paracetamol quantity to 20" in edit.json()["reply"]
    assert "Invoice review cancelled" in cancel.json()["reply"]
    assert calls == []
    assert main.pending_invoice_reviews == {}


def test_invoice_review_item_number_edits_are_bound_to_pending_invoice(monkeypatch):
    calls: list[str] = []
    sender = "254700000000@s.whatsapp.net"
    main.pending_invoice_reviews.clear()
    main.pending_invoice_reviews[main.invoice_review_key(sender)] = {
        "supplier": "MedCare",
        "invoice_number": "INV779",
        "items": [
            {"drug_name": "Thermometer", "quantity": 1, "cost": 150},
            {"drug_name": "Syringe/Needle", "quantity": 1, "cost": 150},
        ],
    }

    def fake_process(text: str, sender_value: str) -> str:
        calls.append(text)
        return text

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process)

    with TestClient(main.app) as client:
        qty = client.post("/bridge/whatsapp-web", json=bridge_payload("edit 1 qty 20", sender=sender))
        cost = client.post("/bridge/whatsapp-web", json=bridge_payload("edit 1 cost 250", sender=sender))
        remove = client.post("/bridge/whatsapp-web", json=bridge_payload("remove 2", sender=sender))
        approve = client.post("/bridge/whatsapp-web", json=bridge_payload("add all", sender=sender))

    assert "Updated Thermometer quantity to 20" in qty.json()["reply"]
    assert "Updated Thermometer cost to 250" in cost.json()["reply"]
    assert "Removed Syringe/Needle" in remove.json()["reply"]
    assert "Invoice approved and stock updated" in approve.json()["reply"]
    assert calls == ["Thermometer restock 20 cost 250 supplier MedCare invoice INV779"]


def test_invoice_approval_guides_add_new_item_when_stock_update_reports_missing(monkeypatch):
    sender = "254700000000@s.whatsapp.net"
    main.pending_invoice_reviews.clear()
    main.pending_invoice_reviews[main.invoice_review_key(sender)] = {
        "supplier": "MedCare",
        "invoice_number": "INV778",
        "items": [{"drug_name": "PEP Lime Cordial", "quantity": 10}],
    }

    def fake_process(text: str, sender_value: str) -> str:
        return "PEP Lime Cordial not found in inventory. Add new item first."

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process)

    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json=bridge_payload("approve", sender=sender))

    reply = response.json()["reply"]
    assert "Some invoice items need item setup before stock update" in reply
    assert "PEP Lime Cordial x10" in reply
    assert "add new item PEP Lime Cordial price 250 stock 10" in reply
    assert main.invoice_review_key(sender) in main.pending_invoice_reviews


def test_same_whatsapp_invoice_image_uses_media_hash_cache_once(monkeypatch, tmp_path):
    calls = {"count": 0}

    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            calls["count"] += 1
            return {
                "supplier": "MedCare",
                "invoice_number": "INV-CACHE",
                "confidence": 0.9,
                "items": [{"drug_name": "Panadol", "quantity": 20}],
            }

    main.offline_media_job_results.clear()
    main.pending_invoice_reviews.clear()
    monkeypatch.setenv("ENABLE_INVOICE_AI", "true")
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"same invoice bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "supplier invoice"

    with TestClient(main.app) as client:
        first = client.post("/bridge/whatsapp-web", json={**payload, "message_id": "waweb-cache-a"})
        second = client.post("/bridge/whatsapp-web", json={**payload, "message_id": "waweb-cache-b"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert "Invoice processed" in first.json()["reply"]
    assert second.json()["reply"] == first.json()["reply"]
    assert calls["count"] == 1


def test_same_shelf_photo_uses_cache_and_never_updates_stock(monkeypatch, tmp_path):
    calls = {"count": 0}

    class FakeAIService:
        client = object()

        def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None):
            calls["count"] += 1
            return {
                "photo_type": "stock shelf photo",
                "items": [{"drug_name": "Glucose"}, {"drug_name": "ORS"}],
            }

    commands: list[str] = []

    main.offline_media_job_results.clear()
    main.pending_invoice_reviews.clear()
    monkeypatch.setenv("ENABLE_VISION_AI", "true")
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000", openai_api_key="test-key"),
    )
    monkeypatch.setattr(main, "get_ai_service", lambda: FakeAIService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", lambda text, sender: commands.append(text) or text)

    payload = bridge_payload("", sender="254700000000@s.whatsapp.net")
    payload["media_base64"] = base64.b64encode(b"same shelf bytes").decode("ascii")
    payload["media_mime_type"] = "image/jpeg"
    payload["caption"] = "analyze shelf photo"

    with TestClient(main.app) as client:
        first = client.post("/bridge/whatsapp-web", json={**payload, "message_id": "waweb-shelf-a"})
        second = client.post("/bridge/whatsapp-web", json={**payload, "message_id": "waweb-shelf-b"})

    assert "Shelf photo analyzed" in first.json()["reply"]
    assert second.json()["reply"] == first.json()["reply"]
    assert calls["count"] == 1
    assert commands == []
    assert main.pending_invoice_reviews == {}


def test_invoice_add_new_item_setup_then_approve_updates_stock_locally(monkeypatch):
    sender = "254700000000@s.whatsapp.net"
    created: list[dict[str, object]] = []
    commands: list[str] = []

    class FakeStore:
        def add_stock_item(self, drug_name, selling_price=None, cost_price=None, current_stock=0, reorder_level=5):
            created.append(
                {
                    "drug_name": drug_name,
                    "selling_price": selling_price,
                    "cost_price": cost_price,
                    "current_stock": current_stock,
                    "reorder_level": reorder_level,
                }
            )

    class FakeService:
        store = FakeStore()

    main.pending_invoice_reviews.clear()
    main.pending_invoice_reviews[main.invoice_review_key(sender)] = {
        "supplier": "MedCare",
        "invoice_number": "INV-NEW",
        "items": [{"drug_name": "PEP Lime Cordial", "quantity": 10}],
    }

    monkeypatch.setattr(main, "get_intake_service", lambda: FakeService())
    monkeypatch.setattr(main, "process_intake_text_for_sender", lambda text, sender_value: commands.append(text) or f"restocked: {text}")
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254700000000"),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json=bridge_payload("add new item PEP Lime Cordial price 250 stock 10", sender=sender),
        )

    reply = response.json()["reply"]
    assert "Item setup saved." in reply
    assert "Invoice approved and stock updated" in reply
    assert created == [
        {
            "drug_name": "PEP Lime Cordial",
            "selling_price": 250.0,
            "cost_price": None,
            "current_stock": 0,
            "reorder_level": 5,
        }
    ]
    assert commands == ["PEP Lime Cordial restock 10 supplier MedCare invoice INV-NEW"]
    assert main.pending_invoice_reviews == {}
