from fastapi.testclient import TestClient

import app.main as main
from app.ai import AI_USAGE_LOG, ai_usage_snapshot
from app.intake import IntakeService
from app.services.operational_intelligence import decide_ai_route
from app.services.pharmacy_simulation import SimulationParser, SimulationStore


def test_layer1_commands_do_not_log_ai_calls():
    AI_USAGE_LOG.clear()
    service = IntakeService(SimulationParser(), SimulationStore())

    commands = [
        "Panadol 2 cash",
        "Panadol stock",
        "+Panadol 20",
        "report today",
        "best seller today",
        "cash total today",
        "show low stock",
        "change last to mpesa",
        "undo last sale",
    ]

    replies = [service.process_text(command, conversation_id="guardrail") for command in commands]

    assert all(reply for reply in replies)
    assert AI_USAGE_LOG == []
    assert ai_usage_snapshot()["total_logged"] == 0


def test_layer1_routing_policy_blocks_ai_for_normal_work():
    local_phrases = [
        "Panadol2cash",
        "Piriton 1 mpesa",
        "ORS stock",
        "best seller leo",
        "How much Mpesa imeingia leo",
        "low stock",
        "undo hiyo ya mwisho",
        "barcode 9789914441314",
        "offline sync Panadol 1 cash",
    ]

    for phrase in local_phrases:
        decision = decide_ai_route(text=phrase)
        assert decision.use_ai is False, phrase


def test_offline_typed_sync_stays_zero_token(monkeypatch, tmp_path):
    AI_USAGE_LOG.clear()
    service = IntakeService(SimulationParser(), SimulationStore())
    monkeypatch.setattr(main, "get_intake_service", lambda: service)
    monkeypatch.setattr(main, "PROJECT_ROOT", tmp_path)
    main.offline_synced_entry_ids.clear()
    main.offline_synced_entry_results.clear()
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()

    payload = {
        "confirmation_whatsapp": "+254728571649",
        "entries": [
            {"id": "zero-token-sale", "type": "sale", "command_text": "Panadol 1 cash", "sync_status": "pending"},
            {"id": "zero-token-stock", "type": "stock", "command_text": "Panadol stock", "sync_status": "pending"},
        ],
    }

    with TestClient(main.app) as client:
        response = client.post("/offline/sync", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert AI_USAGE_LOG == []


def test_media_routes_are_the_only_ai_allowed_shortcuts():
    assert decide_ai_route(message_type="voice", text="Panadol mbili cash").use_ai is True
    assert decide_ai_route(message_type="photo", text="scan invoice", explicit_ai_request=True).use_ai is True
    assert decide_ai_route(message_type="photo", text="invoice", explicit_ai_request=False).use_ai is False
