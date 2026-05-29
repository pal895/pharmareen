from __future__ import annotations

import base64
import json
import mimetypes
import re
from typing import Any

from openai import OpenAI

from app.config import Settings
from app.domain import Action, ParsedEvent, ParseResult
from app.utils import normalize_key


EVENT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "drug_name": {"type": "string"},
        "action": {
            "type": "string",
            "enum": ["Sold", "Out of Stock", "Not Sold", "Restocked"],
        },
        "quantity": {"type": "integer", "minimum": 1},
        "notes": {"type": "string"},
    },
    "required": ["drug_name", "action", "quantity", "notes"],
    "additionalProperties": False,
}


PARSE_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": EVENT_ITEM_SCHEMA,
        },
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": "string"},
    },
    "required": ["events", "needs_clarification", "clarification_question"],
    "additionalProperties": False,
}


RECOMMENDATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["recommendations"],
    "additionalProperties": False,
}


AI_USAGE_LOG: list[dict[str, str]] = []
AI_ROUTE_DECISION_LOG: list[dict[str, Any]] = []
ZERO_TOKEN_LAYER1_ROUTES = [
    "sale",
    "stock_check",
    "restock",
    "report",
    "analytics",
    "correction",
    "undo",
    "barcode",
    "offline_typed_sync",
    "low_stock",
    "missed_demand",
    "receipt",
]


def log_ai_call(reason: str, route: str, purpose: str) -> None:
    record = {"reason": reason, "route": route, "purpose": purpose}
    AI_USAGE_LOG.append(record)
    del AI_USAGE_LOG[:-20]
    print(f"AI_CALL route={route} reason={reason} purpose={purpose}", flush=True)


def log_ai_route_decision(
    *,
    text: str,
    route: str,
    used_ai: bool,
    reason: str,
    job_id: str = "",
    from_cache: bool = False,
    user_number: str = "",
    media_hash: str = "",
) -> None:
    record = {
        "text": str(text or "")[:160],
        "route": str(route or "unknown"),
        "used_ai": bool(used_ai),
        "reason": str(reason or ""),
        "job_id": str(job_id or "")[:120],
        "from_cache": bool(from_cache),
        "user_number": str(user_number or "")[:80],
        "media_hash": str(media_hash or "")[:80],
    }
    AI_ROUTE_DECISION_LOG.append(record)
    del AI_ROUTE_DECISION_LOG[:-50]


def ai_usage_snapshot() -> dict[str, Any]:
    by_route: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for record in AI_USAGE_LOG:
        route = str(record.get("route") or "unknown")
        reason = str(record.get("reason") or "unknown")
        by_route[route] = by_route.get(route, 0) + 1
        by_reason[reason] = by_reason.get(reason, 0) + 1
    last = AI_USAGE_LOG[-1] if AI_USAGE_LOG else {}
    last_decision = AI_ROUTE_DECISION_LOG[-1] if AI_ROUTE_DECISION_LOG else {}
    unexpected_ai = [
        record
        for record in AI_USAGE_LOG
        if str(record.get("route") or "").lower() in {route.lower() for route in ZERO_TOKEN_LAYER1_ROUTES}
    ]
    return {
        "total_logged": len(AI_USAGE_LOG),
        "recent": list(AI_USAGE_LOG[-5:]),
        "by_route": by_route,
        "by_reason": by_reason,
        "last_reason": last.get("reason", ""),
        "unexpected_ai": len(unexpected_ai),
        "recent_route_decisions": list(AI_ROUTE_DECISION_LOG[-5:]),
        "last_command_ai_flag": bool(last_decision.get("used_ai")) if last_decision else False,
        "last_command_ai_reason": str(last_decision.get("reason") or "") if last_decision else "",
        "zero_token_layer1_routes": ZERO_TOKEN_LAYER1_ROUTES,
    }


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twenty": 20,
    "thirty": 30,
    "fifty": 50,
    "hundred": 100,
}


class AIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def transcribe_audio(self, audio_bytes: bytes, content_type: str | None) -> str:
        if self.client is None:
            return ""
        clean_content_type = (content_type or "audio/ogg").split(";")[0].strip()
        extension = mimetypes.guess_extension(clean_content_type) or ".ogg"
        filename = f"voice-note{extension}"

        log_ai_call("voice_transcription", "audio/transcriptions", "voice note transcription")
        result = self.client.audio.transcriptions.create(
            model=self.settings.openai_transcription_model,
            file=(filename, audio_bytes, clean_content_type),
            response_format="text",
        )
        if isinstance(result, str):
            return result.strip()
        return str(getattr(result, "text", "")).strip()

    def parse_events(self, text: str, master_drug_names: list[str]) -> ParseResult:
        simple_result = parse_simple_events(text, master_drug_names)
        if simple_result is not None:
            return simple_result
        if self.client is None:
            return ParseResult(
                events=[],
                needs_clarification=True,
                clarification_question="Please send it like: Panadol 2",
            )

        known_drugs = "\n".join(f"- {name}" for name in master_drug_names[:500])
        if not known_drugs:
            known_drugs = "- No Master_Stock drugs were loaded."

        log_ai_call("local_parser_failed", "chat/completions", "messy text normalization")
        completion = self.client.chat.completions.create(
            model=self.settings.openai_parse_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract pharmacy activity events from a WhatsApp text. "
                        "Return JSON only. Never infer prices. "
                        "Use Master_Stock names when the user's drug phrase is clearly the same drug. "
                        "If the drug or action is unclear, set needs_clarification=true and ask one short WhatsApp question. "
                        "Split multiple items into separate events, for example comma-separated updates. "
                        "Action rules: sold/bought/gave = Sold; restock/restocked/stock added = Restocked; "
                        "no stock/out of stock/not available = Out of Stock; "
                        "asked/customer left/left/too expensive/did not buy/didn't buy = Not Sold. "
                        "If a message only says people asked for a drug without saying no stock, use Not Sold. "
                        "If quantity is missing, use 1. Convert number words to numbers: "
                        "one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10. "
                        "Ignore package words like tabs, tablets, bottles, packets, strips, or boxes unless they are part of the drug name."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Master_Stock drug names:\n"
                        f"{known_drugs}\n\n"
                        f"Owner message: {text}"
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "pharmacy_activity_events",
                    "strict": True,
                    "schema": PARSE_RESULT_SCHEMA,
                },
            },
        )

        message = completion.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            return ParseResult(
                events=[],
                needs_clarification=True,
                clarification_question="Please send that again as a simple pharmacy update.",
            )

        raw_content = message.content or "{}"
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            return ParseResult(
                events=[],
                needs_clarification=True,
                clarification_question="Please send that again as a simple pharmacy update.",
            )
        return ParseResult.from_mapping(data)

    def parse_message(self, text: str, master_drug_names: list[str]) -> ParsedEvent:
        result = self.parse_events(text, master_drug_names)
        if result.events:
            return result.events[0]
        return ParsedEvent(
            drug_name="",
            action=None,
            needs_clarification=True,
            clarification_question=result.clarification_question,
        )

    def generate_recommendations(self, metrics: dict[str, Any]) -> list[str]:
        if self.client is None:
            return []
        log_ai_call("advanced_summary_requested", "chat/completions", "business recommendations")
        completion = self.client.chat.completions.create(
            model=self.settings.openai_parse_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise daily business recommendations for a small pharmacy owner. "
                        "Use only the supplied facts. Do not invent prices, stock levels, or medical advice. "
                        "Return short, practical WhatsApp-ready recommendations as JSON. "
                        "Focus on what to restock urgently, what to increase stock for, "
                        "which missed demand could be causing lost sales, and which drugs moved fastest."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(metrics, ensure_ascii=True),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "pharmacy_recommendations",
                    "strict": True,
                    "schema": RECOMMENDATION_SCHEMA,
                },
            },
        )
        raw_content = completion.choices[0].message.content or "{}"
        data = json.loads(raw_content)
        recommendations = data.get("recommendations") or []
        return [str(item).strip() for item in recommendations if str(item).strip()]

    def extract_restock_from_image(self, image_bytes: bytes, content_type: str | None = None) -> dict[str, Any]:
        if self.client is None or not image_bytes:
            return {"items": [], "confidence": 0, "message": "Image AI is not configured."}
        clean_content_type = (content_type or "image/jpeg").split(";")[0].strip()
        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{clean_content_type};base64,{encoded}"
        log_ai_call("photo_invoice_extraction", "chat/completions", "invoice/photo extraction")
        completion = self.client.chat.completions.create(
            model=self.settings.openai_parse_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract pharmacy restock details from an invoice or medicine photo. "
                        "Return JSON only with keys: items, confidence, message. "
                        "Each item may include drug_name, strength, quantity, unit_type, expiry_date, supplier, "
                        "invoice_number, batch_number, and cost. Do not guess missing values."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract visible restock details from this image."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
        )
        try:
            data = json.loads(completion.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            return {"items": [], "confidence": 0, "message": "Image could not be read clearly."}
        return {
            "items": list(data.get("items") or []),
            "confidence": float(data.get("confidence") or 0),
            "message": str(data.get("message") or ""),
        }


def parse_simple_events(text: str, master_drug_names: list[str]) -> ParseResult | None:
    segments = [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
    if not segments:
        return None

    events: list[ParsedEvent] = []
    for segment in segments:
        event = parse_simple_event(segment, master_drug_names)
        if event is None:
            return None
        events.append(event)

    return ParseResult(events=events)


def parse_simple_event(text: str, master_drug_names: list[str]) -> ParsedEvent | None:
    action = detect_action(text)
    if action is None:
        return None

    drug_name = detect_drug_name(text, master_drug_names)
    if not drug_name:
        return None

    return ParsedEvent(
        drug_name=drug_name,
        action=action,
        quantity=detect_quantity(text),
        notes="",
    )


def detect_action(text: str) -> Action | None:
    normalized = normalize_key(text)
    if re.search(r"\b(restock|restocked|re stock)\b", normalized) or "stock added" in normalized:
        return Action.RESTOCKED
    if any(phrase in normalized for phrase in ("no stock", "out of stock", "not available")):
        return Action.OUT_OF_STOCK
    if any(
        phrase in normalized
        for phrase in ("customer left", "left", "too expensive", "didnt buy", "didn't buy", "did not buy")
    ):
        return Action.NOT_SOLD
    if re.search(r"\b(sold|sale|bought|gave)\b", normalized):
        return Action.SOLD
    if "asked" in normalized:
        return Action.NOT_SOLD
    return None


def detect_quantity(text: str) -> int:
    digit_match = re.search(r"\b(\d+)\b", text)
    if digit_match:
        return max(int(digit_match.group(1)), 1)

    normalized = normalize_key(text)
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", normalized):
            return value
    return 1


def detect_drug_name(text: str, master_drug_names: list[str]) -> str:
    normalized_text = normalize_key(text)
    matching_names = [
        name.strip()
        for name in master_drug_names
        if name.strip() and normalize_key(name) in normalized_text
    ]
    if matching_names:
        return max(matching_names, key=len)

    cleaned = normalize_key(text)
    phrases_to_remove = [
        "no stock",
        "out of stock",
        "not available",
        "stock added",
        "customer asked",
        "customer left",
        "too expensive",
        "didn't buy",
        "didnt buy",
        "did not buy",
        "sold",
        "sale",
        "bought",
        "gave",
        "asked for",
        "asked",
        "restocked",
        "restock",
        "re stock",
        "people",
        "person",
        "customers",
        "customer",
        "left",
        "but",
        "for",
    ]
    for phrase in phrases_to_remove:
        cleaned = re.sub(rf"\b{re.escape(phrase)}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d+\b", " ", cleaned)
    for word in NUMBER_WORDS:
        cleaned = re.sub(rf"\b{re.escape(word)}\b", " ", cleaned)
    cleaned = re.sub(
        r"\b(tabs|tab|tablets|tablet|packets|packet|bottles|bottle|strips|strip|boxes|box)\b",
        " ",
        cleaned,
    )
    cleaned = " ".join(cleaned.split())
    return cleaned.title()
