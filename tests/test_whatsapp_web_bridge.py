from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings


def test_whatsapp_web_bridge_processes_help_message():
    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json={
                "message": "help",
                "from": "254700000000@c.us",
                "message_id": f"waweb-{uuid4()}",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "reply" in data
    assert "Panadol" in data["reply"]
    assert data["command_handler"] == "help_start"


def test_whatsapp_web_bridge_requires_message():
    with TestClient(main.app) as client:
        response = client.post("/bridge/whatsapp-web", json={"from": "254700000000@c.us"})

    assert response.status_code == 400


def test_whatsapp_web_bridge_ignores_group_messages(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None))

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


def test_whatsapp_web_bridge_ignores_sender_not_in_allowlist(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, ALLOWED_WHATSAPP_NUMBERS="254711111111"),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json={
                "message": "Panadol 2",
                "from": "254700000000@s.whatsapp.net",
                "message_id": f"waweb-denied-{uuid4()}",
            },
        )

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
        response = client.post(
            "/bridge/whatsapp-web",
            json={
                "message": "help",
                "from": "254700000000@s.whatsapp.net",
                "message_id": f"waweb-allowed-{uuid4()}",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Panadol" in data["reply"]


def test_demo_mode_allows_sale_without_google_sheets(monkeypatch):
    main.get_sheet_store.cache_clear()
    main.get_intake_service.cache_clear()
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, DEMO_MODE=True))

    with TestClient(main.app) as client:
        response = client.post(
            "/bridge/whatsapp-web",
            json={
                "message": "Panadol 2",
                "from": "254700000000@s.whatsapp.net",
                "message_id": f"waweb-demo-{uuid4()}",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Panadol" in data["reply"]
    assert "Stock left" in data["reply"]
