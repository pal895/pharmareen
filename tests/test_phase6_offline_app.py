from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.domain import StockItem
from app.intake import IntakeService


class FakeIntake:
    def __init__(self, reply: str = "ok"):
        self.messages: list[str] = []
        self.reply = reply

    def process_text(self, text: str) -> str:
        self.messages.append(text)
        return self.reply if self.reply != "ok" else f"synced: {text}"


class OfflineSafetyStore:
    def __init__(self):
        self.stocks = {
            "panadol": StockItem("Panadol", 220, 140, 20, 5, 2),
            "ors": StockItem("ORS", 80, 50, 0, 10, 3),
        }
        self.logged = []
        self.transactions = []

    def list_master_drug_names(self):
        return [stock.drug_name for stock in self.stocks.values()]

    def find_stock(self, drug_name):
        return self.stocks.get(str(drug_name).lower())

    def append_daily_log(self, event, price, total_value):
        self.logged.append((event, price, total_value))

    def update_current_stock(self, stock, new_current_stock):
        self.stocks[stock.drug_name.lower()] = StockItem(
            stock.drug_name,
            stock.selling_price,
            stock.cost_price,
            new_current_stock,
            stock.reorder_level,
            stock.row_number,
        )

    def append_transaction(
        self,
        transaction_type,
        drug_name,
        quantity,
        unit_cost=None,
        unit_selling_price=None,
        total_cost=None,
        total_sales=None,
        profit=None,
        note="",
        created_at=None,
    ):
        self.transactions.append(
            {
                "Type": transaction_type,
                "Drug": drug_name,
                "Quantity": quantity,
                "Note": note,
            }
        )


class SplitStockTruthStore(OfflineSafetyStore):
    """Simulates live sheets where Master_Stock is stale but Inventory is zero."""

    def find_stock(self, drug_name):
        if str(drug_name).lower() == "ors":
            return StockItem("ORS", 80, 50, 2, 10, 3)
        return super().find_stock(drug_name)

    def find_stock_for_safety(self, drug_name, pharmacy_id=None):
        if str(drug_name).lower() == "ors":
            return StockItem("ORS", 80, 50, 0, 10, 3)
        return super().find_stock(drug_name)


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
    assert "Confirmation WhatsApp Number" in followed_response.text
    assert "Scan Barcode" in followed_response.text
    assert "Scan Invoice" in followed_response.text
    assert "Tap & Talk" in followed_response.text
    assert "Manual Entry" in followed_response.text
    assert "Take Photo" in followed_response.text
    assert "Save Photo" in followed_response.text
    assert "Save Voice" in followed_response.text
    assert "PHARMAREEN REAL PATH BUILD launch-usability-v2026-05-29-1" in followed_response.text
    assert "PHARMAREEN SMOOTH TEST v2026-05-15" in followed_response.text
    assert "Cash mode active" in followed_response.text
    assert 'class="bottom-nav"' in followed_response.text
    assert 'data-mobile-tab="home"' in followed_response.text
    assert 'data-tab-panel="queue"' in followed_response.text
    assert 'id="queueCountTop"' in followed_response.text
    assert "Local voice selector" in followed_response.text
    assert "Confirm Sale" in followed_response.text
    assert "Common medicines" in followed_response.text
    assert "medicineGrid" in followed_response.text
    assert "Edit these to match the medicines your pharmacy sells most." in followed_response.text
    assert "Manual Entry" in followed_response.text
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
    assert compat_response.headers.get("x-pharmareen-offline-version") == "launch-usability-v2026-05-29-1"
    assert parser_response.status_code == 200
    assert manifest_response.status_code == 200
    assert worker_response.status_code == 200


def test_debug_version_exposes_realpath_build_marker():
    with TestClient(main.app) as client:
        response = client.get("/debug/version")

    assert response.status_code == 200
    data = response.json()
    assert data["offline_build_version"] == "launch-usability-v2026-05-29-1"
    assert "PHARMAREEN REAL PATH BUILD" in data["offline_frontend_marker"]


def test_offline_medicine_names_route_is_local_and_zero_ai(monkeypatch):
    class NameStore:
        def list_master_drug_names(self):
            return ["Panadol", "Glucose", "ORS", "Panadol"]

    class NameService:
        store = NameStore()

    monkeypatch.setattr(main, "get_intake_service", lambda: NameService())

    with TestClient(main.app) as client:
        response = client.get("/offline/medicine-names")

    assert response.status_code == 200
    data = response.json()
    assert data["ai_used"] is False
    assert data["medicines"] == ["Panadol", "Glucose", "ORS"]


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
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data["status"] == "ok"
    assert [item["id"] for item in data["synced"]] == ["sale-1", "restock-1"]
    assert data["failed"] == []
    assert data["pending"] == []
    assert "Offline records synced" in data["message"]
    assert "Panadol sold 2 Cash" in data["message"]
    assert data["whatsapp_reply"] == data["message"]
    assert data["admin_message"] == data["message"]
    assert fake.messages == ["Panadol sold 2 Cash", "Panadol restock 20"]
    log_path = tmp_path / "data" / "offline_sync_log.jsonl"
    assert log_path.exists()




def test_offline_sync_uses_backend_replies_for_whatsapp_confirmation(monkeypatch, tmp_path):
    class ReplyingIntake:
        def __init__(self):
            self.messages = []

        def process_text(self, text: str) -> str:
            self.messages.append(text)
            if "stock" in text.lower():
                return "?? Panadol stock left: 18\nPrice: KES 220"
            if "report" in text.lower():
                return "?? Today report ready\nCash: KES 500\nM-Pesa: KES 300\nSales: KES 800"
            return "? Panadol x2 cash recorded\nStock left: 18"

    fake = ReplyingIntake()
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: fake)
    main.offline_synced_entry_ids.clear()

    payload = {
        "sender": "254700000000@s.whatsapp.net",
        "entries": [
            {"id": "offline-sale", "action": "sale", "drug_name": "Panadol", "quantity": 2, "payment_method": "cash"},
            {"id": "offline-stock", "action": "stock_check", "raw_text": "Panadol stock"},
            {"id": "offline-report", "action": "unknown", "raw_text": "report today"},
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "ok"
    assert "Offline records synced safely" in data["whatsapp_reply"]
    assert "Panadol x2 cash recorded" in data["whatsapp_reply"]
    assert "Stock left: 18" in data["whatsapp_reply"]
    assert "Panadol stock left: 18" in data["whatsapp_reply"]
    assert "Today report ready" in data["whatsapp_reply"]
    assert data["synced"][0]["result_summary"]
    assert data["synced"][0]["whatsapp_confirmation"] == "ready"

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
    assert data["frontend_marker"] == "PHARMAREEN REAL PATH BUILD launch-usability-v2026-05-29-1"
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
    assert "PHARMAREEN REAL PATH BUILD realpath-stock-safety-v2026-05-28-1" in legacy_html
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
    assert "PHARMAREEN REAL PATH BUILD realpath-stock-safety-v2026-05-28-1" in legacy_html
    assert "PHARMAREEN SMOOTH TEST v2026-05-15" in legacy_html
    assert "Choose From Files/Gallery" in legacy_html
    assert "Choose voice/audio files" in legacy_html
    assert "Tap & Talk" in legacy_html
    assert "Save Photo" in legacy_html
    assert " required" not in legacy_html
    assert "disableNativeRequiredValidation" in legacy_app
    assert "queueMediaFiles" in legacy_app
    assert "pharmareen-offline-v16-realpath-stock-safety" in legacy_worker
    assert legacy_parser.exists()


def test_offline_media_inputs_allow_multiple_files_without_required_command():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "offline_app" / "index.html").read_text(encoding="utf-8")

    assert ">Sell<" in html
    assert ">Camera<" in html
    assert 'class="bottom-nav"' in html
    assert 'data-tab-panel="home"' in html
    assert "Cash mode active" in html
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
    assert "Local voice selector" in html
    assert "Confirm Sale" in html
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
    assert "Synced safely" in html
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
    assert "needs-review-entry" in script
    assert "Queue audio" not in html
    assert "Queue photo" not in html
    assert "Pending queue" not in html
    assert "indexeddb" not in html.lower()
    assert "retries" not in html.lower()


def test_mobile_layout_and_local_voice_selector_hooks_are_present():
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "offline_app" / "index.html").read_text(encoding="utf-8")
    css = (root / "static" / "offline_app" / "styles.css").read_text(encoding="utf-8")
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert 'class="bottom-nav"' in html
    assert 'data-mobile-tab="home"' in html
    assert 'data-tab-panel="media"' in html
    assert 'id="queueCountTop"' in html
    assert 'data-local-voice-selector' in html
    assert "Confirm Sale" in html
    assert "@media (max-width: 679px)" in css
    assert "active-tab-panel" in css
    assert "detectLocalMedicineFromSpeech" in script
    assert "/offline/medicine-names" in script
    assert "crypto.subtle.digest" in script
    assert "job_id" in script


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
    assert "Synced safely" in script
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
    assert "readOfflineSyncJson" in script
    assert "content-type" in script
    assert "Could not process this item. Try again or remove before sync." in script
    assert "splitCommands" in parser
    assert "parseCommand" in parser
    assert "Save Offline" in html
    assert "PHASE 6 FINAL MEDIA SAVE WORKING" in html
    assert "PHARMAREEN REAL PATH BUILD launch-usability-v2026-05-29-1" in html
    assert "PHARMAREEN SMOOTH TEST v2026-05-15" in html
    assert "Save Photo" in html
    assert "Save Voice" in html
    assert "Tap & Talk" in html
    assert '"start_url": "/offline-app"' in manifest
    assert "/offline_app/parser.js" in worker
    assert "pharmareen-offline-v17-launch-usability" in worker
    assert "caches.open" in worker




def test_offline_frontend_history_uses_synced_safely_not_sent_successfully():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "offline_app" / "app.js").read_text(encoding="utf-8")

    assert "Synced safely" in script
    assert "Sent successfully" not in script
    assert "Nothing synced safely yet." in script
    assert "Remove before sync" in script
    assert "item.reply || item.result_summary || item.message" in script
    assert "CONFIRMATION_WHATSAPP_KEY" in script
    assert "confirmation_whatsapp" in script



def test_offline_sync_preserves_backend_result_for_duplicate_and_queues_whatsapp(monkeypatch, tmp_path):
    class ReplyingIntake:
        def process_text(self, text: str) -> str:
            return "Panadol x2 cash recorded\nStock left: 721"

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: ReplyingIntake())
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()

    payload = {
        "sender": "254700000000@s.whatsapp.net",
        "entries": [{"id": "offline-sale-trust", "action": "sale", "drug_name": "Panadol", "quantity": 2, "payment_method": "cash"}],
    }

    with TestClient(main.app) as client:
        first = client.post("/offline/sync", json=payload)
        second = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")
        ack = client.post("/offline/whatsapp-confirmations/ack", json={"ids": [outbox.json()["confirmations"][0]["id"]]})
        after_ack = client.get("/offline/whatsapp-confirmations")

    first_data = first.json()
    second_data = second.json()
    assert first.status_code == 200
    assert first_data["whatsapp_confirmation"]["status"] == "queued"
    assert "Panadol x2 cash recorded" in first_data["synced"][0]["reply"]
    assert "Stock left: 721" in first_data["synced"][0]["reply"]
    assert second_data["synced"][0]["status"] == "already_synced"
    assert "Already synced" not in second_data["synced"][0]["reply"]
    assert "Panadol x2 cash recorded" in second_data["synced"][0]["reply"]
    assert second_data["whatsapp_confirmation"]["status"] == "not_queued"
    assert len(outbox.json()["confirmations"]) == 1
    assert "Offline records synced safely" in outbox.json()["confirmations"][0]["message"]
    assert "Panadol x2 cash recorded" in outbox.json()["confirmations"][0]["message"]
    assert ack.json()["acked"] == 1
    assert after_ack.json()["confirmations"] == []


def test_offline_sync_routes_confirmation_to_linked_whatsapp_number(monkeypatch, tmp_path):
    class ReplyingIntake:
        def process_text(self, text: str) -> str:
            return "Panadol x2 cash recorded\nStock left: 721"

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: ReplyingIntake())
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()

    payload = {
        "sender": "offline_app",
        "confirmation_whatsapp": "+254711111111",
        "entries": [{"id": "offline-linked-confirmation", "command_text": "Panadol 2 cash", "sync_status": "pending"}],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    data = response.json()
    confirmations = outbox.json()["confirmations"]
    assert data["whatsapp_confirmation"]["status"] == "queued"
    assert outbox.json()["pending_count"] == 1
    assert outbox.json()["pending"][0]["id"] == outbox.json()["confirmations"][0]["id"]
    assert confirmations[0]["to"] == "254711111111@s.whatsapp.net"
    assert "Panadol x2 cash recorded" in confirmations[0]["message"]


def test_offline_sync_with_explicit_confirmation_dedupes_already_synced_confirmation(monkeypatch, tmp_path):
    class ReplyingIntake:
        def process_text(self, text: str) -> str:
            return "Panadol x2 cash recorded\nStock left: 721"

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: ReplyingIntake())
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    payload = {
        "confirmation_whatsapp": "+254711111111",
        "entries": [{"id": "offline-explicit-repeat", "command_text": "Panadol 2 cash", "sync_status": "pending"}],
    }

    with TestClient(main.app) as client:
        first = client.post("/offline/sync", json=payload)
        second = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    assert first.json()["whatsapp_confirmation"]["status"] == "queued"
    assert second.json()["whatsapp_confirmation"]["status"] == "not_queued"
    assert second.json()["whatsapp_confirmation"]["reason"] == "duplicate"
    confirmations = outbox.json()["confirmations"]
    assert len(confirmations) == 1
    assert all(item["to"] == "254711111111@s.whatsapp.net" for item in confirmations)
    assert "Panadol x2 cash recorded" in confirmations[-1]["message"]


def test_offline_sync_accepts_entry_level_confirmation_whatsapp(monkeypatch, tmp_path):
    class ReplyingIntake:
        def process_text(self, text: str) -> str:
            return "Panadol x1 M-Pesa recorded\nStock left: 720"

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: ReplyingIntake())
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()

    payload = {
        "entries": [
            {
                "id": "offline-entry-linked-confirmation",
                "command_text": "Panadol 1 mpesa",
                "confirmation_whatsapp": "+254722222222",
                "sync_status": "pending",
            }
        ],
    }

    with TestClient(main.app) as client:
        client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    confirmations = outbox.json()["confirmations"]
    assert confirmations[0]["to"] == "254722222222@s.whatsapp.net"
    assert "Panadol x1 M-Pesa recorded" in confirmations[0]["message"]


def test_offline_out_of_stock_sale_sync_returns_missed_sale_card_and_confirmation(monkeypatch, tmp_path):
    def fake_process(text: str, sender: str) -> str:
        assert text == "ORS 2 cash"
        return "⚠️ ORS out of stock. Sale not recorded. Missed sale saved: ORS x2."

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()

    payload = {
        "confirmation_whatsapp": "+254733333333",
        "entries": [{"id": "offline-ors-missed-sale", "command_text": "ORS 2 cash", "sync_status": "pending"}],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    data = response.json()
    reply = data["synced"][0]["reply"]
    confirmation = outbox.json()["confirmations"][0]
    assert "ORS out of stock" in reply
    assert "Sale not recorded" in reply
    assert "Missed sale saved: ORS x2" in reply
    assert "ORS out of stock" in data["whatsapp_reply"]
    assert confirmation["to"] == "254733333333@s.whatsapp.net"
    assert "Missed sale saved: ORS x2" in confirmation["message"]


def test_real_browser_payload_offline_sync_blocks_zero_stock_sale_and_queues_confirmation(monkeypatch, tmp_path):
    store = OfflineSafetyStore()
    service = IntakeService(None, store)
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: service)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    payload = {
        "confirmation_whatsapp": "+254757637709",
        "entries": [
            {
                "id": "real-offline-panadol-sale",
                "timestamp": "2026-05-19T10:00:00.000Z",
                "raw_text": "Panadol 2 cash",
                "command_text": "Panadol 2 cash",
                "action": "sale",
                "type": "sale",
                "drug_name": "Panadol",
                "quantity": 2,
                "payment_method": "Cash",
                "sync_status": "pending",
            },
            {
                "id": "real-offline-panadol-stock",
                "timestamp": "2026-05-19T10:00:01.000Z",
                "raw_text": "Panadol stock",
                "command_text": "Panadol stock",
                "action": "stock_check",
                "type": "stock_check",
                "drug_name": "Panadol",
                "quantity": 0,
                "sync_status": "pending",
            },
            {
                "id": "real-offline-ors-zero-sale",
                "timestamp": "2026-05-19T10:00:02.000Z",
                "raw_text": "ORS 2 cash",
                "command_text": "ORS 2 cash",
                "action": "sale",
                "type": "sale",
                "drug_name": "ORS",
                "quantity": 2,
                "payment_method": "Cash",
                "sync_status": "pending",
            },
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    data = response.json()
    replies_by_id = {item["id"]: item["reply"] for item in data["synced"]}
    assert "Panadol x2 recorded" in replies_by_id["real-offline-panadol-sale"]
    assert "Panadol stock left" in replies_by_id["real-offline-panadol-stock"]
    ors_reply = replies_by_id["real-offline-ors-zero-sale"]
    assert "ORS out of stock" in ors_reply
    assert "Sale not recorded" in ors_reply
    assert "Missed sale saved: ORS x2" in ors_reply
    assert store.stocks["ors"].current_stock == 0
    assert store.transactions[-1]["Type"] == "no_stock"
    assert not any(row["Type"] == "sale" and row["Drug"] == "ORS" for row in store.transactions)
    confirmation = outbox.json()["confirmations"][0]
    assert outbox.json()["pending_count"] == 1
    assert confirmation["to"] == "254757637709@s.whatsapp.net"
    assert "Panadol x2" in confirmation["message"]
    assert "Panadol stock left" in confirmation["message"]
    assert "ORS out of stock" in confirmation["message"]


def test_offline_structured_zero_stock_sale_is_blocked_before_text_router(monkeypatch, tmp_path):
    store = OfflineSafetyStore()
    service = IntakeService(None, store)

    def fail_if_called(text: str, sender: str) -> str:
        raise AssertionError(f"stock safety guard should block before text routing: {text}")

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: service)
    monkeypatch.setattr(main, "process_intake_text_for_sender", fail_if_called)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    payload = {
        "confirmation_whatsapp": "+254708061426",
        "entries": [
            {
                "id": "offline-ors-preflight-block",
                "raw_text": "ORS 2 cash",
                "command_text": "ORS 2 cash",
                "action": "sale",
                "type": "sale",
                "drug_name": "ORS",
                "quantity": 2,
                "payment_method": "Cash",
                "sync_status": "pending",
            }
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    data = response.json()
    reply = data["synced"][0]["reply"]
    assert "ORS out of stock" in reply
    assert "Sale not recorded" in reply
    assert "Missed sale saved: ORS x2" in reply
    assert store.stocks["ors"].current_stock == 0
    assert store.transactions[-1]["Type"] == "no_stock"
    assert not any(row["Type"] == "sale" and row["Drug"] == "ORS" for row in store.transactions)
    assert outbox.json()["pending_count"] == 1
    assert "ORS out of stock" in outbox.json()["confirmations"][0]["message"]


def test_offline_sync_uses_stock_truth_service_before_stale_master_stock(monkeypatch, tmp_path, capsys):
    store = SplitStockTruthStore()
    service = IntakeService(None, store)

    def fail_if_called(text: str, sender: str) -> str:
        raise AssertionError(f"stale Master_Stock must not reach text router: {text}")

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: service)
    monkeypatch.setattr(main, "process_intake_text_for_sender", fail_if_called)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    payload = {
        "confirmation_whatsapp": "+254728571649",
        "offline_app_build_version": "realpath-stock-safety-v2026-05-28-1",
        "entries": [
            {
                "id": "offline-ors-split-stock-truth",
                "raw_text": "ORS 2 cash",
                "command_text": "ORS 2 cash",
                "action": "sale",
                "type": "sale",
                "drug_name": "ORS",
                "quantity": 2,
                "payment_method": "Cash",
                "pharmacy_id": "real_pharmacy",
                "sync_status": "pending",
            }
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    data = response.json()
    reply = data["synced"][0]["reply"]
    assert "ORS out of stock" in reply
    assert "Sale not recorded" in reply
    assert "Missed sale saved: ORS x2" in reply
    assert not any(row["Type"] == "sale" and row["Drug"] == "ORS" for row in store.transactions)
    assert store.transactions[-1]["Type"] == "no_stock"
    assert outbox.json()["confirmations"][0]["to"] == "254728571649@s.whatsapp.net"
    assert "ORS out of stock" in outbox.json()["confirmations"][0]["message"]
    logs = capsys.readouterr().out
    assert "REAL_BROWSER_OFFLINE_PAYLOAD_RECEIVED" in logs
    assert "STOCK_SAFETY_BLOCKED_OFFLINE_SYNC" in logs
    assert "OFFLINE_CONFIRMATION_QUEUED_REAL_SYNC" in logs


def test_debug_offline_confirmations_exposes_masked_pending_queue(monkeypatch, tmp_path):
    class ReplyingIntake:
        def process_text(self, text: str) -> str:
            return "Panadol x2 cash recorded\nStock left: 721"

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "get_intake_service", lambda: ReplyingIntake())
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()

    with TestClient(main.app) as client:
        client.post(
            "/offline/sync",
            json={
                "confirmation_whatsapp": "+254744444444",
                "entries": [{"id": "offline-debug-confirmation", "command_text": "Panadol 2 cash"}],
            },
        )
        debug = client.get("/debug/offline-confirmations")

    data = debug.json()
    assert data["pending_count"] == 1
    assert "2547******44" in data["pending"][0]["to"]
    assert "Panadol x2 cash recorded" in data["pending"][0]["message_preview"]


def test_debug_offline_confirmation_test_queue_ack_and_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    with TestClient(main.app) as client:
        queued = client.post(
            "/debug/offline-confirmations/test",
            json={"to": "+254755555555", "message": "Offline confirmation test"},
        )
        outbox = client.get("/offline/whatsapp-confirmations")
        item_id = outbox.json()["confirmations"][0]["id"]
        failed = client.post("/offline/whatsapp-confirmations/fail", json={"id": item_id, "error": "unit test send failed"})
        after_fail = client.get("/debug/offline-confirmations")
        acked = client.post("/offline/whatsapp-confirmations/ack", json={"ids": [item_id]})
        after_ack = client.get("/debug/offline-confirmations")

    assert queued.json()["queued"]["status"] == "queued"
    assert outbox.json()["confirmations"][0]["to"] == "254755555555@s.whatsapp.net"
    assert failed.json()["updated"] == 1
    assert after_fail.json()["pending_count"] == 1
    assert after_fail.json()["pending"][0]["attempts"] == 1
    assert after_fail.json()["failed_count"] == 1
    assert acked.json()["acked"] == 1
    assert after_ack.json()["pending_count"] == 0
    assert after_ack.json()["sent_count"] == 1


def test_debug_offline_confirmation_send_test_defaults_to_live_verification_number(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    with TestClient(main.app) as client:
        queued = client.post("/debug/offline-confirmations/send-test", json={})
        outbox = client.get("/offline/whatsapp-confirmations")

    assert queued.json()["status"] == "queued_for_bridge"
    assert queued.json()["queued"]["status"] == "queued"
    assert outbox.json()["pending_count"] == 1
    assert outbox.json()["confirmations"][0]["to"] == "254728571649@s.whatsapp.net"
    assert "PharMareen bridge delivery test" in outbox.json()["confirmations"][0]["message"]


def test_offline_confirmation_queue_persists_pending_between_memory_resets(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    with TestClient(main.app) as client:
        client.post(
            "/debug/offline-confirmations/test",
            json={"to": "+254757637709", "message": "Persistent offline confirmation test"},
        )

    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    with TestClient(main.app) as client:
        outbox = client.get("/offline/whatsapp-confirmations")

    data = outbox.json()
    assert data["pending_count"] == 1
    assert data["confirmations"][0]["to"] == "254757637709@s.whatsapp.net"
    assert data["pending"][0]["message"] == "Persistent offline confirmation test"


def test_offline_sync_returns_per_item_results_for_sale_stock_and_report(monkeypatch, tmp_path):
    replies = {
        "Panadol 2 cash": "Panadol x2 cash recorded\nStock left: 691",
        "Panadol stock": "Panadol stock left: 721",
        "report today": "Today report:\nCash: KES 300\nM-Pesa: KES 200\nSales: 2",
    }

    def fake_process(text: str, sender: str) -> str:
        return replies[text]

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "process_intake_text_for_sender", fake_process)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()

    payload = {
        "sender": "254700000000@s.whatsapp.net",
        "entries": [
            {"id": "offline-manual-sale", "command_text": "Panadol 2 cash", "sync_status": "pending"},
            {"id": "offline-stock-check", "command_text": "Panadol stock", "sync_status": "pending"},
            {"id": "offline-report", "command_text": "report today", "sync_status": "pending"},
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    data = response.json()
    replies_by_id = {item["id"]: item["reply"] for item in data["synced"]}
    assert "Panadol x2 cash recorded" in replies_by_id["offline-manual-sale"]
    assert "Stock left: 691" in replies_by_id["offline-manual-sale"]
    assert "Panadol stock left: 721" in replies_by_id["offline-stock-check"]
    assert "Today report:" in replies_by_id["offline-report"]
    assert "Offline records synced safely" in data["whatsapp_reply"]
    assert "Panadol x2 cash recorded" in data["whatsapp_reply"]
    assert "Panadol stock left: 721" in data["whatsapp_reply"]
    assert "Cash: KES 300" in data["whatsapp_reply"]
    assert outbox.json()["confirmations"]


def test_offline_sync_media_results_are_preserved_and_grouped(monkeypatch, tmp_path):
    async def fake_process_whatsapp_web_payload(**kwargs):
        mime_type = kwargs.get("media_mime_type", "")
        if str(mime_type).startswith("audio"):
            return main.WhatsAppProcessResult(
                reply="🎙 Offline voice processed\nHeard: Piriton one mpesa\nPiriton x1 M-Pesa recorded\nStock left: 88",
                message_type="voice",
                success=True,
                command_handler="voice_note_processed",
            )
        return main.WhatsAppProcessResult(
            reply="📷 Invoice processed\nSupplier: MedCare\nItems found:\n- Paracetamol x20\nReview needed before stock update.",
            message_type="image",
            success=True,
            command_handler="photo_invoice_extracted",
        )

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "process_whatsapp_web_payload", fake_process_whatsapp_web_payload)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()

    payload = {
        "sender": "254700000000@s.whatsapp.net",
        "entries": [
            {
                "id": "offline-voice-result",
                "action": "voice",
                "file_type": "audio/ogg",
                "data_url": "data:audio/ogg;base64," + base64.b64encode(b"voice").decode("ascii"),
                "sync_status": "pending",
            },
            {
                "id": "offline-invoice-result",
                "action": "photo",
                "purpose": "invoice_photo",
                "file_type": "image/jpeg",
                "data_url": "data:image/jpeg;base64," + base64.b64encode(b"invoice").decode("ascii"),
                "sync_status": "pending",
            },
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    data = response.json()
    replies_by_id = {item["id"]: item["reply"] for item in data["synced"]}
    assert "Piriton x1 M-Pesa recorded" in replies_by_id["offline-voice-result"]
    assert "Invoice processed" in replies_by_id["offline-invoice-result"]
    assert "Paracetamol x20" in replies_by_id["offline-invoice-result"]
    assert "Piriton x1 M-Pesa recorded" in data["whatsapp_reply"]
    assert "Invoice processed" in data["whatsapp_reply"]


def test_offline_media_sync_reuses_job_result_and_dedupes_confirmation(monkeypatch, tmp_path):
    calls: list[str] = []

    async def fake_process_whatsapp_web_payload(**kwargs):
        calls.append(str(kwargs.get("message_id") or ""))
        return main.WhatsAppProcessResult(
            reply="🎙 Voice synced: Glucose x2 M-Pesa recorded\nStock left: 44",
            message_type="voice",
            success=True,
            command_handler="voice_note_processed",
        )

    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(main, "process_whatsapp_web_payload", fake_process_whatsapp_web_payload)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_media_job_results.clear()
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    payload = {
        "sender": "254700000000@s.whatsapp.net",
        "confirmation_whatsapp": "+254711111111",
        "entries": [
            {
                "id": "offline-voice-retry-a",
                "action": "voice",
                "file_type": "audio/ogg",
                "data_url": "data:audio/ogg;base64," + base64.b64encode(b"voice").decode("ascii"),
                "sync_status": "pending",
            }
        ],
    }

    with TestClient(main.app) as client:
        first = client.post("/offline/sync", json=payload)
        payload["entries"][0]["id"] = "offline-voice-retry-b"
        second = client.post("/offline/sync", json=payload)
        outbox = client.get("/offline/whatsapp-confirmations")

    assert first.json()["synced"][0]["reply"].startswith("🎙 Voice synced")
    assert second.json()["synced"][0]["reply"].startswith("🎙 Voice synced")
    assert second.json()["synced"][0]["status"] == "already_synced"
    assert calls == ["offline-voice-retry-a"]
    assert len(outbox.json()["confirmations"]) == 1
    assert "Glucose x2 M-Pesa" in outbox.json()["confirmations"][0]["message"]
