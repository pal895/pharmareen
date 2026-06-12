from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.actor_context import ActorContext
from app.correction_learning import CorrectionLearningEngine
from app.domain import Action, ParsedEvent, ParseResult
from app.medicine_brain import AMBIGUOUS, MATCHED, MedicineBrain, MedicineBrainResult


class FallbackParser(Protocol):
    def parse_events(
        self,
        text: str,
        master_drug_names: list[str],
        *,
        actor_context: ActorContext | None = None,
    ) -> ParseResult:
        ...


@dataclass(frozen=True)
class LocalCommand:
    intent: str
    brain_result: MedicineBrainResult | None
    used_fallback: bool = False


class LocalFirstParser:
    def __init__(
        self,
        fallback: FallbackParser,
        brain: MedicineBrain | None = None,
        learning_engine: CorrectionLearningEngine | None = None,
        min_sale_confidence: float = 0.8,
    ) -> None:
        self.fallback = fallback
        self.brain = brain or MedicineBrain()
        self.learning_engine = learning_engine or CorrectionLearningEngine(self.brain.store)
        self.min_sale_confidence = min_sale_confidence
        self.last_command: LocalCommand | None = None
        self.last_used_fallback = False

    def parse_events(
        self,
        text: str,
        master_drug_names: list[str],
        *,
        actor_context: ActorContext | None = None,
    ) -> ParseResult:
        correction_result = self.learning_engine.apply(text, actor_context=actor_context)
        if correction_result.learned or correction_result.message:
            if correction_result.learned:
                self.brain = MedicineBrain(self.brain.store)
            self.last_used_fallback = False
            self.last_command = None
            return ParseResult(
                events=[],
                needs_clarification=True,
                clarification_question=correction_result.message,
            )

        local_result = self.try_parse_local(text)
        if local_result is not None:
            self.last_used_fallback = False
            return local_result

        self.last_used_fallback = True
        self.last_command = None
        return self.fallback.parse_events(text, master_drug_names)

    def try_parse_local(self, text: str) -> ParseResult | None:
        intent = detect_intent(text)
        workflow_result = parse_workflow_only_command(text, intent)
        if workflow_result is not None:
            self.last_command = LocalCommand(intent=intent, brain_result=None)
            return workflow_result

        brain_text = strip_intent_words(text, intent)
        result = self.brain.analyze(brain_text)
        self.last_command = LocalCommand(intent=intent, brain_result=result)

        if result.status == AMBIGUOUS:
            return ParseResult(
                events=[],
                needs_clarification=True,
                clarification_question=ambiguity_question(result.candidates),
            )

        if result.status != MATCHED or not result.medicine_name:
            return None

        if intent == "stock_check":
            return ParseResult(
                events=[
                    ParsedEvent(
                        drug_name=result.medicine_name,
                        action=Action.STOCK_CHECK,
                        quantity=1,
                        notes=event_notes(result),
                    )
                ]
            )

        if intent == "restock":
            quantity = result.quantity or 1
            return ParseResult(
                events=[
                    ParsedEvent(
                        drug_name=result.medicine_name,
                        action=Action.RESTOCK,
                        quantity=quantity,
                        notes=event_notes(result),
                    )
                ]
            )

        if intent == "missed_demand":
            return ParseResult(
                events=[
                    ParsedEvent(
                        drug_name=result.medicine_name,
                        action=Action.OUT_OF_STOCK,
                        quantity=result.quantity or 1,
                        notes=event_notes(result),
                    )
                ]
            )

        if result.confidence < self.min_sale_confidence:
            return None
        if not is_clear_sale_shape(result):
            return None

        return ParseResult(
            events=[
                ParsedEvent(
                    drug_name=result.medicine_name,
                    action=Action.SOLD,
                    quantity=result.quantity or 1,
                    notes=event_notes(result),
                )
            ]
        )


def detect_intent(text: str) -> str:
    clean = normalize_for_intent(text)
    compact = compact_for_intent(clean)

    if re.search(r"\b(undo|reverse|cancel)\b", clean):
        return "undo"
    if re.search(r"\b(correct|correction|change|fix)\b", clean):
        return "operational_correction"
    if re.search(r"\b(show|view)\s+sale\b", clean):
        return "show_sale"
    if re.search(r"\b(?:today\s+)?sale\s+count\b", clean):
        return "sale_count"
    if re.search(r"\b(expiry|expires|expire|exp)\b", clean):
        return "expiry_note"
    if re.search(r"\b(supplier|supplied\s+by|from\s+supplier)\b", clean):
        return "supplier_note"
    if re.search(r"\b(batch|batch\s+no|lot|lot\s+no)\b", clean):
        return "batch_note"

    if any(token in clean for token in ("no stock", "out of stock", "not available")):
        return "missed_demand"
    if any(token in compact for token in ("nostock", "outofstock", "notavailable", "finished")):
        return "missed_demand"
    if re.search(r"\b(oos|hakuna)\b", clean):
        return "missed_demand"

    if any(token in clean for token in ("stock check", "check stock")):
        return "stock_check"
    if re.search(r"\bstock\b", clean):
        return "stock_check"

    if re.search(r"\b(restock|restocked|received|receive)\b", clean):
        return "restock"
    if re.search(r"\b(add|ongeza)\b", clean) and re.search(r"\bstock\b", clean):
        return "restock"

    return "sale"


def parse_workflow_only_command(text: str, intent: str) -> ParseResult | None:
    if intent not in {
        "undo",
        "operational_correction",
        "show_sale",
        "sale_count",
        "expiry_note",
        "supplier_note",
        "batch_note",
    }:
        return None

    action = {
        "undo": Action.UNDO,
        "operational_correction": Action.CORRECTION_REQUEST,
        "show_sale": Action.SHOW_SALE,
        "sale_count": Action.SALE_COUNT,
        "expiry_note": Action.EXPIRY_NOTE,
        "supplier_note": Action.SUPPLIER_NOTE,
        "batch_note": Action.BATCH_NOTE,
    }[intent]
    return ParseResult(
        events=[
            ParsedEvent(
                drug_name="Workflow",
                action=action,
                quantity=1,
                notes=workflow_notes(text, intent),
            )
        ]
    )


def strip_intent_words(text: str, intent: str) -> str:
    clean = str(text or "")
    replacements = {
        "missed_demand": [
            r"\bno\s+stock\b",
            r"\bout\s+of\s+stock\b",
            r"\bnot\s+available\b",
            r"\boos\b",
            r"\bhakuna\b",
            r"\bfinished\b",
        ],
        "stock_check": [
            r"\bstock\s+check\b",
            r"\bcheck\s+stock\b",
            r"\bstock\b",
        ],
        "restock": [
            r"\brestocked\b",
            r"\brestock\b",
            r"\breceived\b",
            r"\breceive\b",
            r"\badd(?:ed)?\b",
            r"\bongeza\b",
            r"\bstock\b",
        ],
    }
    for pattern in replacements.get(intent, []):
        clean = re.sub(pattern, " ", clean, flags=re.IGNORECASE)
    return " ".join(clean.split())


def workflow_notes(text: str, intent: str) -> str:
    clean = " ".join(str(text or "").strip().split())
    sale_match = re.search(r"\b(?:sale\s*#?|#)\s*(\d+)\b", clean, flags=re.IGNORECASE)
    plain_number = re.search(r"\b(\d+)\b", clean)
    target = sale_match.group(1) if sale_match else plain_number.group(1) if plain_number else ""

    notes: list[str] = [f"Workflow input: {clean}"]
    if intent == "undo" and re.search(r"\blast\s+sale\b", clean, flags=re.IGNORECASE):
        notes.append("Target sale: last")
    if target and intent in {"undo", "operational_correction", "show_sale"}:
        notes.append(f"Target sale: {target}")
    if intent == "operational_correction":
        payment_match = re.search(r"\b(?:to|payment)\s+(cash|m-?pesa|mpesa|credit)\b", clean, flags=re.IGNORECASE)
        if payment_match:
            payment = payment_match.group(1).lower().replace("-", "")
            notes.append(f"Payment: {payment_label(payment)}")
        quantity_match = re.search(r"\b(?:quantity|qty|x)\s*(\d+)\b", clean, flags=re.IGNORECASE)
        if quantity_match:
            notes.append(f"Quantity: {quantity_match.group(1)}")
        medicine_match = re.search(r"\b(?:medicine|drug)\s+([a-z][a-z0-9 ]*)", clean, flags=re.IGNORECASE)
        if medicine_match:
            medicine = re.split(
                r"\b(?:quantity|qty|payment|to|cash|m-?pesa|mpesa|credit)\b",
                medicine_match.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            if medicine:
                notes.append(f"Medicine: {title_text(medicine)}")
    if intent in {"expiry_note", "supplier_note", "batch_note"}:
        notes.append("Placeholder: staged for structured tracking")
    return "; ".join(notes)


def event_notes(result: MedicineBrainResult) -> str:
    notes: list[str] = []
    if result.payment:
        notes.append(f"Payment: {payment_label(result.payment)}")
    if result.form:
        notes.append(f"Form: {result.form}")
    if result.packaging:
        notes.append(f"Packaging: {result.packaging}")
    if result.dose:
        notes.append(f"Dose: {result.dose}")
    return "; ".join(notes)


def ambiguity_question(candidates: list[str]) -> str:
    if not candidates:
        return "Which medicine did you mean?"
    if len(candidates) == 1:
        return f"Did you mean {candidates[0]}?"
    options = ", ".join(candidates[:-1]) + f", or {candidates[-1]}"
    return f"Which medicine did you mean: {options}?"


def normalize_for_intent(text: str) -> str:
    clean = str(text or "").lower().replace("m-pesa", "mpesa").replace("m pesa", "mpesa")
    clean = re.sub(r"[^a-z0-9]+", " ", clean)
    clean = re.sub(r"([a-z])(\d)", r"\1 \2", clean)
    clean = re.sub(r"(\d)([a-z])", r"\1 \2", clean)
    return " ".join(clean.split())


def compact_for_intent(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def payment_label(payment: str) -> str:
    return "M-Pesa" if payment == "mpesa" else payment.title()


def title_text(value: str) -> str:
    return " ".join(word.capitalize() for word in str(value or "").split())


def is_clear_sale_shape(result: MedicineBrainResult) -> bool:
    if result.quantity is not None:
        return True
    if result.payment or result.form or result.packaging or result.dose:
        return True
    return len(result.normalized_text.split()) <= 2
