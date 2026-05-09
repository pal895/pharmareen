from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main


class FakeIntake:
    def __init__(self, reply: str = "ok"):
        self.messages: list[str] = []
        self.reply = reply

    def process_text(self, text: str) -> str:
        self.messages.append(text)
        return self.reply if self.reply != "ok" else f"synced: {text}"


def test_offline_app_routes_return_html():
    with TestClient(main.app) as client:
        root_response = client.get("/offline-app")
        compat_response = client.get("/offline_app/index.html")
        manifest_response = client.get("/offline_app/manifest.json")
        worker_response = client.get("/offline_app/service-worker.js")

    assert root_response.status_code == 200
    assert root_response.headers["content-type"].startswith("text/html")
    assert "PharMareen Offline Mode" in root_response.text
    assert "Save offline entry" in root_response.text
    assert compat_response.status_code == 200
    assert compat_response.headers["content-type"].startswith("text/html")
    assert "PharMareen Offline Mode" in compat_response.text
    assert manifest_response.status_code == 200
    assert worker_response.status_code == 200


def test_offline_sync_accepts_valid_entry(monkeypatch, tmp_path):
    fake = FakeIntake()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: fake)
    main.offline_synced_entry_ids.clear()

    payload = {
        "entries": [
            {
                "id": "test-1",
                "timestamp": "2026-05-09T00:00:00Z",
                "pharmacy_id": "demo",
                "command_text": "Panadol restock 20 bonus 5 cost 2000",
                "type": "restock",
                "sync_status": "pending",
            }
        ]
    }
    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["synced"][0]["id"] == "test-1"
    assert fake.messages == ["Panadol restock 20 bonus 5 cost 2000"]
    log_path = tmp_path / "data" / "offline_sync_log.jsonl"
    assert log_path.exists()
    assert json.loads(log_path.read_text(encoding="utf-8").strip())["sync_status"] == "synced"


def test_offline_sync_does_not_crash_on_unknown_command(monkeypatch, tmp_path):
    fake = FakeIntake("I didn’t understand that yet.\n\nTry:\nPanadol 2")
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: fake)
    main.offline_synced_entry_ids.clear()

    with TestClient(main.app) as client:
        response = client.post(
            "/offline/sync",
            json={"entries": [{"id": "bad-1", "command_text": "strange unknown command", "sync_status": "pending"}]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["synced"] == []
    assert data["failed"][0]["id"] == "bad-1"
    assert (tmp_path / "data" / "offline_sync_log.jsonl").exists()


def test_debug_offline_app_reports_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/debug/offline-app")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "offline_app_installed": True,
        "offline_routes_ready": True,
        "sync_endpoint_ready": True,
        "offline_log_exists": True,
    }


def test_offline_pwa_assets_contain_auto_sync_and_retry_logic():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")
    manifest = (root / "static" / "offline_app" / "manifest.json").read_text(encoding="utf-8")
    worker = (root / "static" / "offline_app" / "service-worker.js").read_text(encoding="utf-8")

    assert "navigator.onLine" in script
    assert "setInterval(syncQueue, 30000)" in script
    assert 'fetch("/offline/sync"' in script
    assert "retry_count" in script
    assert "last_error" in script
    assert "MAX_RETRIES = 10" in script
    assert '"start_url": "/offline-app"' in manifest
    assert "caches.open" in worker
