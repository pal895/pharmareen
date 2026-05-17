from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.utils import normalize_key


LOCAL_FIRST_PATTERNS: tuple[tuple[str, str], ...] = (
    ("conversation", r"^(hello|hi|hey|habari|morning|good morning|mambo|sasa|help|menu|commands|guide|tutorial|how do i use this|what can you do)$"),
    ("memory", r"\b(same kama jana|same again|same as yesterday|nilikosea quantity|wrong quantity|ile ya mwisho|hiyo ya mwisho|ya mwisho)\b"),
    ("clarification", r"\b(sell|sold|sale|restock|add|received|check stock|stock)\b"),
    ("analytics", r"\b(best seller|sold most|peak hours?|busiest|cash|mpesa|payment breakdown|top payment|low stock|missed demand|no stock|hakuna|out of stock)\b"),
    ("receipt", r"\b(receipt|risiti|print)\b"),
    ("correction", r"\b(undo|void|badilisha|change|update|punguza|ongeza|fanya|wrong quantity|payment iwe)\b"),
    ("report", r"\b(report|summary|profit today|sales today|daily report)\b"),
    ("stock", r"\b(stock|remaining|expiry|expiring|trace|history)\b|stock$"),
    ("restock", r"(^\s*\+|\b(restock|received|bought|bonus|supplier|invoice|batch|expiry)\b)"),
    ("sale", r"\b(sold|sell|late|later|missed|nimeuza|niliuza|cash|mpesa|credit|card|strip|tablet|box)\b|^[a-z]+\s*\d+|^late[a-z]+\d+"),
    ("barcode", r"\b(barcode|scan|sku)\b"),
)

AI_ONLY_MEDIA_TYPES = {"voice", "audio", "photo", "image", "invoice_photo", "supplier_receipt", "stock_photo"}
DANGEROUS_ALIAS_THRESHOLD = 3
MEMORY_TTL_MINUTES = 30


@dataclass(frozen=True)
class AIRoutingDecision:
    use_ai: bool
    route: str
    reason: str
    confidence: float


@dataclass
class OperationalMemorySnapshot:
    last_transaction: dict[str, Any] | None = None
    last_medicine: str = ""
    last_action: str = ""
    last_quantity: int | None = None
    last_payment: str = ""
    last_correction_target: str = ""
    last_receipt_target: str = ""
    last_offline_batch: list[dict[str, Any]] = field(default_factory=list)
    recent_clarification: str = ""
    recent_analytics_target: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OperationalMemory:
    """Small local memory for rush-hour follow-ups.

    This intentionally stores only operational facts needed for short references like
    "ile ya mwisho" or "ongeza moja". It is local-first and does not call AI.
    """

    def __init__(self, ttl_minutes: int = MEMORY_TTL_MINUTES):
        self.ttl = timedelta(minutes=ttl_minutes)
        self._sessions: dict[str, OperationalMemorySnapshot] = {}

    def remember_transaction(self, conversation_id: str, transaction: dict[str, Any], now: datetime | None = None) -> None:
        timestamp = now or datetime.now(timezone.utc)
        snapshot = self._sessions.get(conversation_id, OperationalMemorySnapshot())
        snapshot.last_transaction = dict(transaction)
        snapshot.last_medicine = str(transaction.get("drug_name") or transaction.get("drug") or "")
        snapshot.last_action = str(transaction.get("action") or transaction.get("type") or "sale")
        quantity = transaction.get("display_quantity") or transaction.get("quantity")
        snapshot.last_quantity = int(quantity) if str(quantity).isdigit() else snapshot.last_quantity
        snapshot.last_payment = str(transaction.get("payment_method") or transaction.get("payment") or snapshot.last_payment)
        snapshot.last_receipt_target = str(transaction.get("trace_id") or snapshot.last_receipt_target)
        snapshot.updated_at = timestamp
        self._sessions[conversation_id] = snapshot

    def remember_clarification(self, conversation_id: str, question: str, now: datetime | None = None) -> None:
        snapshot = self._sessions.get(conversation_id, OperationalMemorySnapshot())
        snapshot.recent_clarification = question
        snapshot.updated_at = now or datetime.now(timezone.utc)
        self._sessions[conversation_id] = snapshot

    def remember_offline_batch(self, conversation_id: str, entries: list[dict[str, Any]], now: datetime | None = None) -> None:
        snapshot = self._sessions.get(conversation_id, OperationalMemorySnapshot())
        snapshot.last_offline_batch = [dict(entry) for entry in entries[-20:]]
        snapshot.updated_at = now or datetime.now(timezone.utc)
        self._sessions[conversation_id] = snapshot

    def get(self, conversation_id: str, now: datetime | None = None) -> OperationalMemorySnapshot | None:
        snapshot = self._sessions.get(conversation_id)
        if snapshot is None:
            return None
        current = now or datetime.now(timezone.utc)
        if current - snapshot.updated_at > self.ttl:
            return None
        return snapshot

    def resolve_reference(self, conversation_id: str, text: str, now: datetime | None = None) -> dict[str, Any] | None:
        key = normalize_key(text)
        if not any(phrase in key for phrase in ["last", "ya mwisho", "ile ya mwisho", "hiyo", "same", "kama jana"]):
            return None
        snapshot = self.get(conversation_id, now=now)
        return snapshot.last_transaction if snapshot and snapshot.last_transaction else None


@dataclass
class AliasLearningDecision:
    alias: str
    drug_name: str = ""
    accepted: bool = False
    needs_review: bool = False
    reason: str = ""


class AdaptiveAliasLearner:
    """Learns pharmacy shorthand only after repeated safe confirmations."""

    def __init__(self, threshold: int = DANGEROUS_ALIAS_THRESHOLD):
        self.threshold = threshold
        self._counts: dict[str, Counter[str]] = defaultdict(Counter)
        self._review_log: list[dict[str, Any]] = []

    def observe(self, alias: str, drug_name: str, *, confirmed: bool, context: str = "") -> AliasLearningDecision:
        alias_key = normalize_key(alias)
        drug = " ".join(str(drug_name or "").strip().split())
        if not alias_key or not drug:
            return AliasLearningDecision(alias=alias_key, needs_review=True, reason="missing alias or medicine")
        if not confirmed:
            self._review_log.append({"alias": alias_key, "drug_name": drug, "context": context, "status": "unconfirmed"})
            return AliasLearningDecision(alias=alias_key, drug_name=drug, needs_review=True, reason="needs confirmation")
        self._counts[alias_key][drug] += 1
        return self.suggest(alias_key, [])

    def suggest(self, alias: str, inventory_names: Iterable[str]) -> AliasLearningDecision:
        alias_key = normalize_key(alias)
        counts = self._counts.get(alias_key, Counter())
        if not counts:
            return AliasLearningDecision(alias=alias_key, needs_review=True, reason="no observations")
        ranked = counts.most_common(2)
        top_drug, top_count = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        ambiguous_inventory = [name for name in inventory_names if normalize_key(name).startswith(alias_key)]
        if len(ambiguous_inventory) > 1 and top_count < self.threshold + 2:
            return AliasLearningDecision(alias=alias_key, drug_name=top_drug, needs_review=True, reason="inventory ambiguity")
        if top_count >= self.threshold and top_count - runner_up >= 2:
            return AliasLearningDecision(alias=alias_key, drug_name=top_drug, accepted=True, reason="confirmed pattern")
        return AliasLearningDecision(alias=alias_key, drug_name=top_drug, needs_review=True, reason="not enough confirmations")

    def review_log(self) -> list[dict[str, Any]]:
        return list(self._review_log)


def classify_local_intent(text: str) -> tuple[str, float]:
    key = normalize_key(text).replace("m pesa", "mpesa").replace("m-pesa", "mpesa")
    for intent, pattern in LOCAL_FIRST_PATTERNS:
        if re.search(pattern, key, flags=re.IGNORECASE):
            return intent, 0.9
    if re.fullmatch(r"[a-z]{1,8}\s*\+?\s*\d+", key):
        return "shorthand", 0.78
    return "unknown", 0.25


def decide_ai_route(
    *,
    text: str = "",
    message_type: str = "text",
    local_confidence: float | None = None,
    explicit_ai_request: bool = False,
) -> AIRoutingDecision:
    media_type = normalize_key(message_type)
    if media_type in {"voice", "audio"}:
        return AIRoutingDecision(True, "audio/transcriptions", "voice transcription", 1.0)
    if media_type in {"photo", "image", "invoice_photo", "supplier_receipt", "stock_photo"}:
        if explicit_ai_request:
            return AIRoutingDecision(True, "vision/extraction", "explicit photo extraction", 1.0)
        return AIRoutingDecision(False, "local_media_store", "save media safely before AI", 0.95)
    intent, inferred_confidence = classify_local_intent(text)
    confidence = inferred_confidence if local_confidence is None else local_confidence
    if intent != "unknown" or confidence >= 0.72:
        return AIRoutingDecision(False, "local", f"deterministic {intent}", confidence)
    if confidence >= 0.45:
        return AIRoutingDecision(False, "clarify", "medium confidence needs short clarification", confidence)
    return AIRoutingDecision(True, "chat/completions", "messy text after local parser fails", confidence)


def classify_photo_kind(*, filename: str = "", caption: str = "", purpose: str = "") -> str:
    key = normalize_key(" ".join([filename, caption, purpose]))
    if any(word in key for word in ["invoice", "inv", "delivery note", "stock imefika"]):
        return "invoice_photo"
    if any(word in key for word in ["supplier", "receipt", "payment"]):
        return "supplier_receipt"
    if any(word in key for word in ["shelf", "stock count", "stock photo", "display"]):
        return "stock_shelf_photo"
    if any(word in key for word in ["barcode", "pack", "medicine pack", "label"]):
        return "barcode_or_pack_photo"
    return "unknown_photo"


def voice_pattern_hint(transcript: str) -> str:
    intent, confidence = classify_local_intent(transcript)
    if intent != "unknown" and confidence >= 0.72:
        return "parse_locally_after_transcription"
    return "needs_review"
