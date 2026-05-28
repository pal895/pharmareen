from pathlib import Path

import json

from app.ai import AI_USAGE_LOG
from app.domain import ParseResult
from app.services.operational_intelligence import (
    AdaptiveAliasLearner,
    OperationalMemory,
    classify_media_input,
    classify_photo_kind,
    decide_ai_route,
    voice_pattern_hint,
)
from app.intake import IntakeService
from app.services.pharmacy_simulation import SimulationParser, SimulationStore, load_training_cases, run_simulation


def test_training_datasets_cover_real_pharmacy_behaviors():
    cases = load_training_cases(Path("datasets/pharmacy_training"))
    categories = {case.category for case in cases}

    assert len(cases) >= 250
    assert {
        "conversation",
        "shorthand",
        "rush_hour",
        "memory",
        "payments",
        "supplier",
        "analytics",
        "offline",
        "media",
        "voice",
        "clarification",
        "swahili",
        "trust",
    }.issubset(categories)


def test_token_policy_keeps_core_pharmacy_work_local():
    local_commands = [
        "Panadol2cash",
        "Panadol+20",
        "Best seller today",
        "How much Mpesa imeingia leo",
        "receipt ya mwisho",
        "badilisha payment iwe mpesa",
        "show low stock",
        "undo last sale",
        "cancel TX-1046",
        "cash total today",
        "barcode 9789914441314",
    ]

    for command in local_commands:
        decision = decide_ai_route(text=command)
        assert decision.use_ai is False, command
        assert decision.route in {"local", "clarify"}

    assert decide_ai_route(message_type="voice", text="Panadol mbili cash").use_ai is True
    assert decide_ai_route(message_type="photo", text="invoice", explicit_ai_request=False).use_ai is False
    assert decide_ai_route(message_type="photo", text="scan invoice", explicit_ai_request=True).use_ai is True


def test_ai_usage_snapshot_exposes_cost_guardrails():
    from app.ai import ai_usage_snapshot, log_ai_call

    AI_USAGE_LOG.clear()
    snapshot = ai_usage_snapshot()
    assert snapshot["total_logged"] == 0
    assert "sale" in snapshot["zero_token_layer1_routes"]
    assert "offline_typed_sync" in snapshot["zero_token_layer1_routes"]

    log_ai_call("voice_transcription", "audio/transcriptions", "voice note transcription")
    snapshot = ai_usage_snapshot()
    assert snapshot["total_logged"] == 1
    assert snapshot["by_route"]["audio/transcriptions"] == 1
    assert snapshot["last_reason"] == "voice_transcription"
    AI_USAGE_LOG.clear()


def test_safe_alias_learning_requires_repeated_confirmations_and_respects_ambiguity():
    learner = AdaptiveAliasLearner(threshold=3)

    first = learner.observe("pd", "Panadol", confirmed=False, context="pd 2")
    assert first.needs_review is True
    assert first.accepted is False

    learner.observe("pd", "Panadol", confirmed=True)
    learner.observe("pd", "Panadol", confirmed=True)
    not_enough = learner.suggest("pd", ["Panadol", "Piriton", "Paracetamol"])
    assert not_enough.accepted is False

    learner.observe("pd", "Panadol", confirmed=True)
    learner.observe("pd", "Panadol", confirmed=True)
    accepted = learner.suggest("pd", ["Panadol", "Piriton", "Paracetamol"])
    assert accepted.accepted is True
    assert accepted.drug_name == "Panadol"


def test_operational_memory_resolves_recent_last_transaction_safely():
    memory = OperationalMemory(ttl_minutes=30)
    memory.remember_transaction(
        "owner",
        {
            "drug_name": "Panadol",
            "quantity": 2,
            "display_quantity": 2,
            "payment_method": "Cash",
            "trace_id": "SALE-1",
        },
    )

    resolved = memory.resolve_reference("owner", "ile ya mwisho")
    assert resolved is not None
    assert resolved["drug_name"] == "Panadol"


def test_photo_and_voice_classification_are_local_until_extraction_needed():
    assert classify_photo_kind(filename="invoice_123.jpg", caption="invoice ya jana") == "invoice_photo"
    assert classify_photo_kind(filename="shelf.jpg", caption="stock shelf photo") == "stock_shelf_photo"
    assert classify_photo_kind(filename="pack.jpg", caption="barcode medicine pack") == "barcode_or_pack_photo"
    assert classify_photo_kind(filename="random.jpg", caption="family photo") == "unknown_photo"
    assert classify_media_input(caption="supplier invoice MedCare INV123").media_kind == "supplier_invoice"
    assert classify_media_input(caption="handwritten supplier note").media_kind == "handwritten_invoice"
    assert classify_media_input(caption="blurry invoice poor lighting").media_kind == "blurry_unclear_photo"
    assert voice_pattern_hint("Niliuza Panadol mbili cash") == "parse_locally_after_transcription"


def test_pharmacy_facing_stock_wording_says_stock_left():
    service = IntakeService(SimulationParser(), SimulationStore())

    sale_reply = service.process_text("Panadol2cash", conversation_id="wording")
    stock_reply = service.process_text("Panadolstock", conversation_id="wording")
    restock_reply = service.process_text("+Panadol 20 bonus 5 cost 2000", conversation_id="wording")

    for reply in [sale_reply, stock_reply, restock_reply]:
        assert "Stock left:" in reply or "stock left:" in reply
        assert "Stock:" not in reply
        assert "stock:" not in reply
    assert "Saved safely" not in sale_reply  # sale confirmations stay short, not verbose


def test_unclear_pharmacy_phrase_logs_edge_case_for_future_training(tmp_path, monkeypatch):
    class ClarifyingParser:
        def parse_events(self, text, master_drug_names):
            return ParseResult(events=[], needs_clarification=True, clarification_question="Which medicine and quantity?")

    log_path = tmp_path / "edge_cases.jsonl"
    monkeypatch.setenv("PHARMAREEN_EDGE_CASE_LOG", str(log_path))
    service = IntakeService(ClarifyingParser(), SimulationStore())

    reply = service.process_text("hiyo ingine ya jana", conversation_id="owner-254")

    assert reply == "Which medicine and quantity?"
    record = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert record["text"] == "hiyo ingine ya jana"
    assert record["sender"] == "owner-254"
    assert record["guessed_intent"] in {"unknown", "memory"}
    assert record["ai_fallback_used"] is False
    assert record["final_outcome"] == "clarification"


def test_expanded_training_examples_teach_current_friction():
    cases = load_training_cases(Path("datasets/pharmacy_training"))
    texts = {case.text.lower() for case in cases}

    for required in [
        "p2cash",
        "pan2mpesa",
        "piriton1mpesa",
        "amox2cash",
        "nimeuza panadol mbili cash",
        "nilikosea ilikuwa 5",
        "badilisha payment iwe mpesa",
        "undo last sale",
        "cancel tx-1046",
        "ors 2 cash when stock is zero",
        "supplier invoice",
        "edit item paracetamol qty 20 cost 1500",
        "random non pharmacy image",
        "blurry invoice poor lighting",
        "shelf photo vs invoice photo",
        "nimeuza panadol mbili cash noisy",
        "voice transcript: anadol mbili kash",
        "supplier receipt partial payment",
        "best seller leo",
        "how much mpesa imeingia leo",
        "offline save panadol 1 cash",
        "offline sync grouped whatsapp confirmation",
    ]:
        assert required in texts


def test_pharmacy_simulation_runs_rush_hour_cases_without_unexpected_ai():
    AI_USAGE_LOG.clear()
    cases = [case for case in load_training_cases(Path("datasets/pharmacy_training")) if case.simulate]
    summary = run_simulation(cases)

    assert summary.total >= 60
    assert summary.failed == 0, [result for result in summary.results if not result.ok][:5]
    assert summary.ai_calls_blocked == 0
    assert AI_USAGE_LOG == []
    assert summary.average_ms < 50
