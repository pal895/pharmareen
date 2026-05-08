from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main


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