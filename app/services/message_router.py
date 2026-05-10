from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.ai import AIService
from app.config import Settings, get_settings
from app.intake import IntakeService, normalize_spoken_command_text
from app.providers.meta_whatsapp import NormalizedMessage
from app.services.batch_service import BatchService
from app.services.image_restock import ImageRestockService
from app.services.pending_actions import pending_actions
from app.sheets import GoogleSheetsStore, SheetsUnavailableError
from app.transcription import TranscriptionService, TranscriptionUnavailableError


@dataclass(frozen=True)
class RouterResult:
    reply: str
    saved: bool = False
    requires_confirmation: bool = False
    action_type: str = "message"


class MessageRouter:
    def __init__(
        self,
        intake_service: IntakeService,
        store: Any,
        ai_service: AIService | None = None,
        transcription_service: TranscriptionService | None = None,
        batch_service: BatchService | None = None,
        image_service: ImageRestockService | None = None,
    ):
        self.intake_service = intake_service
        self.store = store
        self.ai_service = ai_service
        self.transcription_service = transcription_service
        self.batch_service = batch_service or BatchService(store)
        self.image_service = image_service or ImageRestockService(ai_service, store)

    async def handle(
        self,
        message: NormalizedMessage,
        media_bytes: bytes | None = None,
        content_type: str | None = None,
    ) -> RouterResult:
        pending = pending_actions.get(message.from_phone)
        if pending and message.type == "text":
            return self._handle_pending_reply(message.text, message.from_phone, pending)

        if message.type == "audio":
            return self._handle_audio(message, media_bytes or b"", content_type)
        if message.type == "image":
            return self._handle_image(message, media_bytes or b"", content_type)
        if message.type == "document":
            return self._handle_image(message, media_bytes or b"", content_type)
        if message.type != "text":
            return RouterResult("Please send text, voice, or a clear medicine photo.")

        text = (message.text or "").strip()
        if not text:
            return RouterResult("Please send a short pharmacy update.")
        if is_drug_name_only(text):
            return RouterResult(self._drug_card(text), saved=False, action_type="drug_card")
        risky_type = detect_high_risk_action(text)
        if risky_type:
            pending_actions.set(message.from_phone, risky_type, {"text": text, "from": message.from_phone})
            return RouterResult(
                confirmation_reply(risky_type, text),
                saved=False,
                requires_confirmation=True,
                action_type=risky_type,
            )
        reply = process_intake_text(self.intake_service, text, message.from_phone)
        return RouterResult(reply, saved=True, action_type="intake")

    def _handle_audio(self, message: NormalizedMessage, audio_bytes: bytes, content_type: str | None) -> RouterResult:
        if not self.transcription_service or not self.transcription_service.is_available:
            return RouterResult("Voice is not enabled yet. Send text like: Panadol 2")
        try:
            transcript = self.transcription_service.transcribe_audio(audio_bytes, content_type)
        except (TranscriptionUnavailableError, Exception):
            return RouterResult('I heard the voice but could not read it clearly. Try saying: "Panadol two".')
        interpreted = normalize_spoken_command_text(transcript)
        risky_type = detect_high_risk_action(interpreted)
        if risky_type:
            pending_actions.set(message.from_phone, risky_type, {"text": interpreted, "transcript": transcript})
            return RouterResult(f"Please confirm: did you mean {interpreted}?", requires_confirmation=True, action_type=risky_type)
        reply = process_intake_text(self.intake_service, interpreted, message.from_phone)
        return RouterResult(f"I heard: {transcript}\nCommand: {interpreted}\n\n{reply}", saved=True, action_type="voice")

    def _handle_image(self, message: NormalizedMessage, media_bytes: bytes, content_type: str | None) -> RouterResult:
        extraction = self.image_service.extract(media_bytes, content_type)
        self.image_service.queue_for_review(message.from_phone, extraction, message.raw)
        if extraction.confidence < 0.65 or not extraction.items:
            pending_actions.set(message.from_phone, "image_restock", {"items": extraction.items, "confidence": extraction.confidence})
            return RouterResult(
                "I can see the image, but I am not fully sure. Please send a clearer photo or type the missing part.",
                requires_confirmation=True,
                action_type="image_restock",
            )
        pending_actions.set(message.from_phone, "image_restock", {"items": extraction.items, "confidence": extraction.confidence})
        lines = ["Confirm restock?"]
        for index, item in enumerate(extraction.items[:5], start=1):
            lines.append("")
            lines.append(f"{index}. {item.get('drug_name', 'Medicine')}")
            lines.append(f"Qty: {item.get('quantity', 'not sure')}")
            lines.append(f"Expiry: {item.get('expiry_date', 'not seen')}")
            if item.get("supplier"):
                lines.append(f"Supplier: {item['supplier']}")
            if item.get("invoice_number"):
                lines.append(f"Invoice: {item['invoice_number']}")
        lines.append("")
        lines.append("Reply YES to save, EDIT to correct, or CANCEL.")
        return RouterResult("\n".join(lines), requires_confirmation=True, action_type="image_restock")

    def _handle_pending_reply(self, text: str, phone: str, pending: Any) -> RouterResult:
        answer = text.strip().lower()
        if answer in {"cancel", "no"}:
            pending_actions.clear(phone)
            return RouterResult("Cancelled. Nothing was saved.", saved=False, action_type="cancel")
        if answer == "edit":
            return RouterResult("Please type the corrected details.", requires_confirmation=True, action_type="edit")
        if answer in {"yes", "y"}:
            pending_actions.clear(phone)
            if pending.action_type in {"bad_drug", "expired_drug", "damaged_drug"}:
                self.batch_service.record_issue(pending.payload)
                return RouterResult("Saved issue record.", saved=True, action_type=pending.action_type)
            if pending.action_type == "return":
                self.batch_service.record_return(pending.payload)
                return RouterResult("Saved return record.", saved=True, action_type="return")
            if pending.action_type in {"expiry_entry", "image_restock", "stock_correction", "batch_change"}:
                return RouterResult("Confirmed. Saved for pharmacy review.", saved=True, action_type=pending.action_type)
        pending_actions.clear(phone)
        reply = process_intake_text(self.intake_service, text, phone)
        return RouterResult(reply, saved=True, action_type="correction")

    def _drug_card(self, drug_name: str) -> str:
        try:
            stock = self.store.find_stock(drug_name)
        except (SheetsUnavailableError, Exception):
            stock = None
        return self.batch_service.drug_card(drug_name, stock=stock)


def detect_high_risk_action(text: str) -> str | None:
    normalized = " ".join(text.lower().split())
    if re.search(r"\b(bad|damaged)\b", normalized):
        return "bad_drug"
    if re.search(r"\bexpired\b", normalized):
        return "expired_drug"
    if re.search(r"\breturn\b", normalized):
        return "return"
    if re.search(r"\b(exp|expiry|expires)\b", normalized):
        return "expiry_entry"
    if re.search(r"\b(correct stock|adjust stock|stock correction|delete|edit record|batch change)\b", normalized):
        return "stock_correction"
    return None


def confirmation_reply(action_type: str, text: str) -> str:
    label = action_type.replace("_", " ")
    return f"This is a {label} action.\n\nI will not save it yet.\nReply YES to confirm, EDIT to correct, or CANCEL."


def process_intake_text(intake_service: Any, text: str, conversation_id: str) -> str:
    try:
        return intake_service.process_text(text, conversation_id=conversation_id)
    except TypeError as exc:
        if "conversation_id" not in str(exc):
            raise
        return intake_service.process_text(text)


def is_drug_name_only(text: str) -> bool:
    normalized = " ".join(text.strip().lower().split())
    if normalized in {
        "hello",
        "hi",
        "hey",
        "habari",
        "morning",
        "good morning",
        "mambo",
        "sasa",
        "help",
        "start",
        "menu",
        "commands",
        "guide",
        "tutorial",
        "how do i use this",
        "what can you do",
    }:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9\s+./-]{1,60}", text.strip())) and not any(
        word in normalized.split()
        for word in {
            "sold",
            "sell",
            "sale",
            "later",
            "late",
            "stock",
            "report",
            "profit",
            "bonus",
            "free",
            "return",
            "bad",
            "damaged",
            "expired",
            "expires",
            "restock",
            "received",
            "add",
            "summary",
            "today",
        }
    )


@lru_cache
def build_default_router() -> MessageRouter:
    settings = get_settings()
    store = GoogleSheetsStore(settings)
    ai_service = AIService(settings)
    transcription_service = TranscriptionService(settings)
    return MessageRouter(
        intake_service=IntakeService(
            ai_service,
            store,
            timezone=settings.timezone,
            pharmacy_name=settings.pharmacy_name,
            app_base_url=settings.public_base_url,
            whatsapp_number=settings.whatsapp_number,
        ),
        store=store,
        ai_service=ai_service,
        transcription_service=transcription_service,
    )
