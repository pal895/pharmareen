from __future__ import annotations

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
