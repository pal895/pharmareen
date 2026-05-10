from __future__ import annotations

import json
import subprocess
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


def run_parser_case(script: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "-e", script],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_offline_app_routes_return_html():
    with TestClient(main.app) as client:
        root_response = client.get("/offline-app", follow_redirects=False)
        followed_response = client.get("/offline-app")
        compat_response = client.get("/offline_app/index.html")
        parser_response = client.get("/offline_app/parser.js")
        manifest_response = client.get("/offline_app/manifest.json")
        worker_response = client.get("/offline_app/service-worker.js")

    assert root_response.status_code in {200, 307}
    if root_response.status_code == 307:
        assert root_response.headers["location"] == "/offline_app/index.html"
    assert followed_response.status_code == 200
    assert followed_response.headers["content-type"].startswith("text/html")
    assert "PharMareen Offline Mode" in followed_response.text
    assert "Type or paste pharmacy command" in followed_response.text
    assert "Save Offline" in followed_response.text
    assert "Photo queue" in followed_response.text
    assert "Voice/audio queue" in followed_response.text
    assert compat_response.status_code == 200
    assert compat_response.headers["content-type"].startswith("text/html")
    assert "PharMareen Offline Mode" in compat_response.text
    assert parser_response.status_code == 200
    assert manifest_response.status_code == 200
    assert worker_response.status_code == 200


def test_offline_sync_accepts_sale_and_restock_entries(monkeypatch, tmp_path):
    fake = FakeIntake()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: fake)
    main.offline_synced_entry_ids.clear()

    payload = {
        "entries": [
            {"id": "sale-1", "action": "sale", "drug_name": "Panadol", "quantity": 2, "sync_status": "pending"},
            {"id": "restock-1", "action": "restock", "drug_name": "Panadol", "quantity": 20, "sync_status": "pending"},
        ]
    }
    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert [item["id"] for item in data["synced"]] == ["sale-1", "restock-1"]
    assert data["failed"] == []
    assert data["pending"] == []
    assert fake.messages == ["Panadol sold 2", "Panadol restock 20"]
    log_path = tmp_path / "data" / "offline_sync_log.jsonl"
    assert log_path.exists()


def test_offline_sync_accepts_bonus_and_discount_restock(monkeypatch, tmp_path):
    fake = FakeIntake()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: fake)
    main.offline_synced_entry_ids.clear()

    payload = {
        "entries": [
            {
                "id": "bonus-1",
                "action": "restock",
                "drug_name": "Panadol",
                "quantity": 20,
                "bonus_quantity": 5,
                "actual_paid_amount": 2000,
                "sync_status": "pending",
            },
            {
                "id": "discount-1",
                "action": "restock",
                "drug_name": "Amoxicillin",
                "quantity": 30,
                "actual_paid_amount": 2500,
                "discount_amount": 300,
                "sync_status": "pending",
            },
        ]
    }
    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["synced"]) == 2
    assert fake.messages == [
        "Panadol restock 20 bonus 5 cost 2000",
        "Amoxicillin restock 30 cost 2500",
    ]


def test_offline_sync_accepts_multiple_structured_entries(monkeypatch, tmp_path):
    fake = FakeIntake()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: fake)
    main.offline_synced_entry_ids.clear()

    payload = {
        "entries": [
            {"id": "multi-1", "raw_text": "Panadol sold 2", "action": "sale"},
            {"id": "multi-2", "raw_text": "Panadol restock 20 bonus 5 cost 2000", "action": "restock"},
            {"id": "multi-3", "raw_text": "Amoxicillin received 30 paid 2500 discount 300", "action": "restock"},
        ]
    }
    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["synced"]) == 3
    assert fake.messages == [
        "Panadol sold 2",
        "Panadol restock 20 bonus 5 cost 2000",
        "Amoxicillin received 30 paid 2500 discount 300",
    ]


def test_offline_sync_logs_photo_and_voice_placeholders(monkeypatch, tmp_path):
    fake = FakeIntake()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: fake)
    main.offline_synced_entry_ids.clear()

    payload = {
        "entries": [
            {"id": "photo-1", "action": "photo", "file_name": "invoice.jpg", "sync_status": "pending"},
            {"id": "audio-1", "action": "audio", "file_name": "voice.ogg", "sync_status": "pending"},
        ]
    }
    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert [item["status"] for item in data["synced"]] == ["media_logged", "media_logged"]
    assert fake.messages == []
    assert (tmp_path / "data" / "offline_sync_log.jsonl").exists()


def test_offline_sync_does_not_crash_on_unknown_command(monkeypatch, tmp_path):
    fake = FakeIntake("I didn't understand that yet. Try: Panadol 2")
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
    assert data["failed"] == []
    assert data["pending"][0]["id"] == "bad-1"
    assert (tmp_path / "data" / "offline_sync_log.jsonl").exists()


def test_debug_offline_app_reports_all_phase6_features(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/debug/offline-app")

    assert response.status_code == 200
    data = response.json()
    assert data["offline_app_installed"] is True
    assert data["offline_routes_ready"] is True
    assert data["sync_endpoint_ready"] is True
    assert data["multi_command_parser_ready"] is True
    assert data["photo_queue_ready"] is True
    assert data["audio_queue_ready"] is True
    assert data["voice_queue_ready"] is True
    assert data["persistent_storage_ready"] is True
    assert data["auto_sync_ready"] is True
    assert "offline_log_exists" in data


def test_offline_parser_handles_sales_restocks_bonus_discount_and_splitting():
    script = r'''
const parser = require('./static/offline_app/parser.js');
const cases = {
  sold: parser.parseCommand('Panadol sold 2'),
  plainSale: parser.parseCommand('Panadol 2'),
  plusRestock: parser.parseCommand('Panadol +20'),
  bonus: parser.parseCommand('Panadol restock 20 bonus 5 cost 2000'),
  discount: parser.parseCommand('Amoxicillin received 30 paid 2500 discount 300'),
  comma: parser.splitCommands('Panadol sold 2, Amoxil sold 5, Zinc restock 10'),
  newline: parser.splitCommands('Panadol sold 2\nAmoxil sold 5\nZinc restock 10')
};
console.log(JSON.stringify(cases));
'''
    data = run_parser_case(script)
    assert data["sold"]["action"] == "sale"
    assert data["sold"]["drug_name"] == "Panadol"
    assert data["sold"]["quantity"] == 2
    assert data["plainSale"]["action"] == "sale"
    assert data["plusRestock"]["action"] == "restock"
    assert data["plusRestock"]["quantity"] == 20
    assert data["bonus"]["bonus_quantity"] == 5
    assert data["bonus"]["total_received_quantity"] == 25
    assert data["bonus"]["actual_paid_amount"] == 2000
    assert data["discount"]["discount_amount"] == 300
    assert data["discount"]["actual_paid_amount"] == 2500
    assert len(data["comma"]) == 3
    assert len(data["newline"]) == 3


def test_offline_pwa_assets_contain_auto_sync_media_and_retry_logic():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")
    parser = (root / "static" / "offline_app" / "parser.js").read_text(encoding="utf-8")
    html = (root / "static" / "offline_app" / "index.html").read_text(encoding="utf-8")
    manifest = (root / "static" / "offline_app" / "manifest.json").read_text(encoding="utf-8")
    worker = (root / "static" / "offline_app" / "service-worker.js").read_text(encoding="utf-8")

    assert "navigator.onLine" in script
    assert "setInterval(syncQueue, 30000)" in script
    assert 'fetch("/offline/sync"' in script
    assert "retry_count" in script
    assert "last_error" in script
    assert "MAX_RETRIES = 3" in script
    assert "indexedDB" in script
    assert "DB_NAME" in script
    assert "QUEUE_STORE" in script
    assert "persistentStorageReady" in script
    assert "blobToDataUrl" in script
    assert "queueMedia" in script
    assert "queuePhotoInputIfPresent" in script
    assert "queueAudioInputIfPresent" in script
    assert "splitCommands" in parser
    assert "parseCommand" in parser
    assert "Save Offline" in html
    assert "Photo queue" in html
    assert "Voice/audio queue" in html
    assert '"start_url": "/offline-app"' in manifest
    assert "/offline_app/parser.js" in worker
    assert "caches.open" in worker
