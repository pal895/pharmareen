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
    assert "PharMareen Pharmacy Assistant" in followed_response.text
    assert "Scan Barcode" in followed_response.text
    assert "Scan Invoice" in followed_response.text
    assert "Tap & Talk" in followed_response.text
    assert "Manual Entry" in followed_response.text
    assert "Take Photo" in followed_response.text
    assert "Save Photo" in followed_response.text
    assert "Save Voice" in followed_response.text
    assert "PHARMAREEN SMOOTH TEST v2026-05-15" in followed_response.text
    assert "🟢 Cash mode active" in followed_response.text
    assert "Common medicines" in followed_response.text
    assert "medicineGrid" in followed_response.text
    assert "Edit these to match the medicines your pharmacy sells most." in followed_response.text
    assert "Type or paste pharmacy command" in followed_response.text
    assert "Save Offline" in followed_response.text
    assert "PHASE 6 FINAL MEDIA SAVE WORKING" in followed_response.text
    assert "Saved Offline" in followed_response.text
    assert "Queue audio" not in followed_response.text
    assert "Queue photo" not in followed_response.text
    assert compat_response.status_code == 200
    assert compat_response.headers["content-type"].startswith("text/html")
    assert "PharMareen Offline Mode" in compat_response.text
    assert "PHASE 6 FINAL MEDIA SAVE WORKING" in compat_response.text
    assert "no-store" in compat_response.headers.get("cache-control", "")
    assert compat_response.headers.get("x-pharmareen-offline-version") == "phase6-smooth-test-v15"
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
            {"id": "sale-1", "action": "sale", "drug_name": "Panadol", "quantity": 2, "payment_method": "Cash", "sync_status": "pending"},
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
    assert "Offline records synced" in data["message"]
    assert "Panadol x2 Cash" in data["message"]
    assert data["whatsapp_reply"] == data["message"]
    assert data["admin_message"] == data["message"]
    assert fake.messages == ["Panadol sold 2 Cash", "Panadol restock 20"]
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
        "Amoxicillin restock 30 cost 2500 discount 300",
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
    assert "Offline records synced" in data["message"]
    assert "Invoice photo saved" in data["message"]
    assert "Voice note saved" in data["message"]
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
    assert data["frontend_marker"] == "PHASE 6 FINAL WORKING - SMOOTH TEST v2026-05-15"
    assert data["served_index_path"].endswith("static/offline_app/index.html") or data["served_index_path"].endswith("static\\offline_app\\index.html")
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
  unitSale: parser.parseCommand('Panadol 1 strip mpesa'),
  unitRestock: parser.parseCommand('Panadol +1 box'),
  shortcutSale: parser.parseCommand('p2'),
  shortcutRestock: parser.parseCommand('p +20'),
  shortcutStock: parser.parseCommand('stock p'),
  comma: parser.splitCommands('Panadol sold 2, Amoxil sold 5, Zinc restock 10'),
  newline: parser.splitCommands('Panadol sold 2\nAmoxil sold 5\nZinc restock 10'),
  semicolon: parser.splitCommands('Panadol sold 2; Amoxil sold 5'),
  fast: parser.splitCommands('Panadol 1 cash Amox 2 mpesa'),
  compact: parser.splitCommands('Panadol2Amox1ORS3'),
  compactStock: parser.parseCommand('Panadolstock'),
  compactRestock: parser.parseCommand('Panadol+20'),
  fastParsed: parser.splitCommands('Panadol 1 cash Amox 2 mpesa').map(value => parser.parseCommand(value))
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
    assert data["unitSale"]["unit"] == "strip"
    assert data["unitSale"]["payment_method"] == "M-Pesa"
    assert data["unitSale"]["base_quantity"] == 10
    assert data["unitRestock"]["unit"] == "box"
    assert data["unitRestock"]["base_quantity"] == 100
    assert data["shortcutSale"]["action"] == "sale"
    assert data["shortcutSale"]["drug_name"] == "Panadol"
    assert data["shortcutSale"]["quantity"] == 2
    assert data["shortcutRestock"]["action"] == "restock"
    assert data["shortcutRestock"]["quantity"] == 20
    assert data["shortcutStock"]["action"] == "stock_check"
    assert len(data["comma"]) == 3
    assert len(data["newline"]) == 3
    assert len(data["semicolon"]) == 2
    assert data["fast"] == ["Panadol 1 cash", "Amox 2 mpesa"]
    assert data["compact"] == ["Panadol 2", "Amox 1", "ORS 3"]
    assert data["compactStock"]["action"] == "stock_check"
    assert data["compactRestock"]["action"] == "restock"
    assert data["fastParsed"][0]["payment_method"] == "Cash"
    assert data["fastParsed"][1]["payment_method"] == "M-Pesa"




def test_legacy_local_offline_app_matches_phase6_frontend():
    root = Path(__file__).resolve().parents[1]
    legacy_html = (root / "local" / "index.html").read_text(encoding="utf-8")
    legacy_app = (root / "local" / "app.js").read_text(encoding="utf-8")
    legacy_parser = root / "local" / "parser.js"

    assert "PHASE 6 FINAL MEDIA SAVE WORKING" in legacy_html
    assert "PHARMAREEN SMOOTH TEST v2026-05-15" in legacy_html
    assert "Choose From Files/Gallery" in legacy_html
    assert "Choose voice/audio files" in legacy_html
    assert "Tap & Talk" in legacy_html
    assert "Save Voice" in legacy_html
    assert "queueMediaFiles" in legacy_app
    assert legacy_parser.exists()


def test_legacy_offline_app_folder_matches_final_frontend():
    root = Path(__file__).resolve().parents[1]
    legacy_html = (root / "offline_app" / "index.html").read_text(encoding="utf-8")
    legacy_app = (root / "offline_app" / "app.js").read_text(encoding="utf-8")
    legacy_worker = (root / "offline_app" / "service-worker.js").read_text(encoding="utf-8")
    legacy_parser = root / "offline_app" / "parser.js"

    assert "PHASE 6 FINAL MEDIA SAVE WORKING" in legacy_html
    assert "PHARMAREEN SMOOTH TEST v2026-05-15" in legacy_html
    assert "Choose From Files/Gallery" in legacy_html
    assert "Choose voice/audio files" in legacy_html
    assert "Tap & Talk" in legacy_html
    assert "Save Photo" in legacy_html
    assert " required" not in legacy_html
    assert "disableNativeRequiredValidation" in legacy_app
    assert "queueMediaFiles" in legacy_app
    assert "pharmareen-offline-v15" in legacy_worker
    assert legacy_parser.exists()


def test_offline_media_inputs_allow_multiple_files_without_required_command():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "offline_app" / "index.html").read_text(encoding="utf-8")

    assert "Cash Sale" in html
    assert "M-Pesa Sale" in html
    assert "Credit Sale" in html
    assert "🟢 Cash mode active" in html
    assert ">Cash<" in html
    assert ">M-Pesa<" in html
    assert ">Credit<" in html
    assert ">Mixed<" in html
    assert "Common medicines" in html
    assert 'id="medicineGrid"' in html
    assert "Edit these to match the medicines your pharmacy sells most." in html
    assert "Choose From Files/Gallery" in html
    assert "Choose voice/audio files" in html
    assert 'id="photoInput"' in html
    assert 'id="voiceInput"' in html
    assert 'accept="image/*"' in html
    assert 'id="cameraPhotoInput" type="file" accept="image/*" capture="environment" multiple hidden' in html
    assert 'id="photoInput" type="file" accept="image/*" multiple' in html
    assert 'accept="audio/*" multiple' in html
    assert 'id="commandText"' in html
    assert " required" not in html
    assert "Scan Barcode" in html
    assert "Scan Invoice" in html
    assert "Tap & Talk" in html
    assert "Take Photo" in html
    assert "Save Photo" in html
    assert "Save Voice" in html
    assert "Manual Entry" in html
    assert 'id="barcodeInput"' in html
    assert 'id="saveBarcodeMapping"' in html
    assert 'id="commandText" required' not in html
    assert 'id="photoInput" type="file" accept="image/*" multiple required' not in html
    assert 'id="voiceInput" type="file" accept="audio/*" multiple required' not in html


def test_offline_app_uses_pharmacy_owner_language_not_technical_queue_terms():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "offline_app" / "index.html").read_text(encoding="utf-8")
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "Saved Offline" in html
    assert "Sent successfully" in html
    assert "Tap & Talk" in html
    assert "Save Voice" in html
    assert "Save Photo" in html
    assert "Install PharMareen on phone" in html
    assert "Saved successfully" not in html
    assert "Waiting" in script
    assert "📡 Offline mode active — saving safely" in script
    assert "✅ Everything synced safely" in script
    assert "🔄 Syncing ${index + 1} of ${toSync.length}" in script
    assert "records synced safely" in script
    assert "Queue audio" not in html
    assert "Queue photo" not in html
    assert "Pending queue" not in html
    assert "indexeddb" not in html.lower()
    assert "retries" not in html.lower()


def test_offline_save_offline_queues_photo_and_audio_without_command_text():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "async function saveOfflineEntries" in script
    assert "createCommandEntries(commandText.value)" in script
    assert "const photoEntries = await queuePhotoInputIfPresent" in script
    assert "const audioEntries = await queueAudioInputIfPresent" in script
    assert "savedCount += photoEntries.length" in script
    assert "savedCount += audioEntries.length" in script
    assert "if (!savedCount) return" in script
    assert "if (!commandText.value" not in script


def test_offline_media_queue_supports_multiple_photos_and_audio_files():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "async function queueMediaFiles" in script
    assert "Array.from(fileList || [])" in script
    assert "for (const file of files)" in script
    assert "mediaSignature(file, kind)" in script
    assert "seen.has(signature)" in script
    assert 'queueMediaFiles(photoInput.files, "photo"' in script
    assert 'queueMediaFiles(voiceInput.files, "audio"' in script
    assert "photoInput.value = \"\"" in script
    assert "voiceInput.value = \"\"" in script


def test_offline_media_items_render_pending_and_synced_labels():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "mediaStatusLabel" in script
    assert "friendlySyncError" in script
    assert "Photo" in script
    assert "display_label" in script
    assert "Invoice photo" in script
    assert "Shelf photo" in script
    assert "Voice note saved safely" in script
    assert "Voice synced" in script
    assert "Waiting" in script
    assert "Synced" in script
    assert 'sync_status: "synced"' in script
    assert "addHistoryEntry" in script


def test_offline_payment_mode_defaults_are_applied_without_typing_payment():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "PAYMENT_MODE_KEY" in script
    assert "SHORTCUTS_KEY" in script
    assert "DEFAULT_MEDICINE_SHORTCUTS" in script
    assert "renderMedicineShortcuts" in script
    assert "editMedicineShortcut" in script
    assert "recordMedicineUse" in script
    assert "currentPaymentMode" in script
    assert "function applyPaymentMode" in script
    assert "🟢 ${currentPaymentMode} mode active" in script
    assert 'entry.action !== "sale"' in script
    assert '["Cash", "M-Pesa", "Credit"].includes(currentPaymentMode)' in script
    assert "data-payment-mode" in (root / "static" / "offline_app" / "index.html").read_text(encoding="utf-8")


def test_offline_media_queue_persists_after_refresh_with_indexeddb():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "indexedDB.open" in script
    assert "QUEUE_STORE" in script
    assert "HISTORY_STORE" in script
    assert "entry.blob = storedFile" in script
    assert "await idbPut(QUEUE_STORE, entry)" in script
    assert "async function loadQueue" in script
    assert "persistentStorageReady" in script


def test_offline_photo_storage_compression_and_low_space_guard_exist():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "async function compressPhoto" in script
    assert "canvas.toBlob" in script
    assert "image/jpeg" in script
    assert "async function storageHasRoom" in script
    assert "Phone storage is low" in script
    assert "data_url" in script


def test_offline_barcode_flow_has_safe_actions_and_success_feedback():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "offline_app" / "index.html").read_text(encoding="utf-8")
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert 'id="barcodeSell"' in html
    assert 'id="barcodeRestock"' in html
    assert 'id="barcodeCheck"' in html
    assert "Last scanned:" in html
    assert "✅ ${medicine} detected" in script
    assert "lastBarcodeScan" in script
    assert "pendingBarcodeScan" in script
    assert "Confirming barcode" in script
    assert "focusMode" in script
    assert "gentleFeedback" in script
    assert "await stopBarcodeScanner()" in script
    assert "How many" in script

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
    assert "PHASE 6 FINAL MEDIA SAVE WORKING" in html
    assert "PHARMAREEN SMOOTH TEST v2026-05-15" in html
    assert "Save Photo" in html
    assert "Save Voice" in html
    assert "Tap & Talk" in html
    assert '"start_url": "/offline-app"' in manifest
    assert "/offline_app/parser.js" in worker
    assert "pharmareen-offline-v15" in worker
    assert "caches.open" in worker

