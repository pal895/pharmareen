from pathlib import Path

from app.ai import AI_USAGE_LOG
from app.services.operational_intelligence import (
    AdaptiveAliasLearner,
    OperationalMemory,
    classify_photo_kind,
    decide_ai_route,
    voice_pattern_hint,
)
from app.services.pharmacy_simulation import load_training_cases, run_simulation


def test_training_datasets_cover_real_pharmacy_behaviors():
    cases = load_training_cases(Path("datasets/pharmacy_training"))
    categories = {case.category for case in cases}

    assert len(cases) >= 80
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
        "barcode 9789914441314",
    ]

    for command in local_commands:
        decision = decide_ai_route(text=command)
        assert decision.use_ai is False, command
        assert decision.route in {"local", "clarify"}

    assert decide_ai_route(message_type="voice", text="Panadol mbili cash").use_ai is True
    assert decide_ai_route(message_type="photo", text="invoice", explicit_ai_request=False).use_ai is False
    assert decide_ai_route(message_type="photo", text="scan invoice", explicit_ai_request=True).use_ai is True


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
    assert voice_pattern_hint("Niliuza Panadol mbili cash") == "parse_locally_after_transcription"


def test_pharmacy_simulation_runs_rush_hour_cases_without_unexpected_ai():
    AI_USAGE_LOG.clear()
    cases = [case for case in load_training_cases(Path("datasets/pharmacy_training")) if case.simulate]
    summary = run_simulation(cases)

    assert summary.total >= 60
    assert summary.failed == 0, [result for result in summary.results if not result.ok][:5]
    assert summary.ai_calls_blocked == 0
    assert AI_USAGE_LOG == []
    assert summary.average_ms < 50
