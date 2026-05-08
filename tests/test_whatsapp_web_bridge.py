from __future__ import annotations

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
    assert "Stock left" in data["reply"]


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
    source = (Path(__file__).resolve().parents[1] / "baileys-bridge.js").read_text()

    assert "async function safeSendReply" in source
    assert "safe_mode_no_allowlist" in source
    assert "@s.whatsapp.net" in source
    assert "domain === '@lid'" in source
    assert "ALLOW_ALL_DIRECT_CHATS_FOR_TEST" in source
    assert "allow_all_direct_chats_for_test" in source
    assert "jid_domain=" in source
    assert "TEST MODE ACCEPTED DIRECT CHAT" in source
    assert "BACKEND_REPLY_RECEIVED" in source
    assert "WHATSAPP_REPLY_SENT" in source
    assert "WHATSAPP_SEND_FAILED" in source
    assert "SAFE MODE: no allowed numbers configured" in source
    assert "GROUP REPLIES: DISABLED" in source
    assert "UNKNOWN NUMBER REPLIES: DISABLED" in source

    send_lines = [line.strip() for line in source.splitlines() if "sock.sendMessage" in line]
    assert send_lines == ["await sock.sendMessage(jid, { text: body });"]


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
