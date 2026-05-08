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
    assert "endsWith('@s.whatsapp.net')" in source
    assert "SAFE MODE: no allowed numbers configured" in source
    assert "GROUP REPLIES: DISABLED" in source
    assert "UNKNOWN NUMBER REPLIES: DISABLED" in source

    send_lines = [line.strip() for line in source.splitlines() if "sock.sendMessage" in line]
    assert send_lines == ["await sock.sendMessage(jid, { text: body });"]
