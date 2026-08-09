from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


@dataclass(frozen=True)
class NormalizedMessage:
    provider: str
    from_phone: str
    message_id: str
    type: str
    text: str = ""
    media_id: str = ""
    timestamp: str = ""
    raw: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "from": self.from_phone,
            "message_id": self.message_id,
            "type": self.type,
            "text": self.text,
            "media_id": self.media_id,
            "timestamp": self.timestamp,
            "raw": self.raw or {},
        }


class MetaWhatsAppClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = f"https://graph.facebook.com/{settings.meta_graph_api_version}"

    def verify_webhook(self, mode: str | None, token: str | None, challenge: str | None) -> str | None:
        expected_token = self.settings.meta_verify_token or "test_verify_token"
        if mode == "subscribe" and token and token == expected_token:
            return challenge or ""
        return None

    def normalize_webhook(self, payload: dict[str, Any]) -> list[NormalizedMessage]:
        messages: list[NormalizedMessage] = []
        for entry in payload.get("entry", []) or []:
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes", []) or []:
                if not isinstance(change, dict):
                    continue
                value = change.get("value") or {}
                if not isinstance(value, dict):
                    continue
                for message in value.get("messages", []) or []:
                    if isinstance(message, dict):
                        messages.append(normalize_meta_message(message))
        return messages

    async def send_text(self, to_phone: str, body: str) -> None:
        if not self.settings.meta_access_token or not self.settings.meta_phone_number_id:
            return
        url = f"{self.base_url}/{self.settings.meta_phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_whatsapp_phone(to_phone),
            "type": "text",
            "text": {"body": body[:4000]},
        }
        headers = {"Authorization": f"Bearer {self.settings.meta_access_token}"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()


    async def get_media_url(self, media_id: str) -> str:
        url = f"{self.base_url}/{media_id}"
        headers = {"Authorization": f"Bearer {self.settings.meta_access_token}"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        return str(data.get("url") or "")

    async def download_media(self, media_id: str) -> bytes:
        media_url = await self.get_media_url(media_id)
        if not media_url:
            return b""
        headers = {"Authorization": f"Bearer {self.settings.meta_access_token}"}
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(media_url, headers=headers)
            response.raise_for_status()
            return response.content


def normalize_meta_message(message: dict[str, Any]) -> NormalizedMessage:
    message_type = str(message.get("type") or "unknown")
    text = ""
    media_id = ""
    if message_type == "text":
        text = str((message.get("text") or {}).get("body") or "").strip()
    elif message_type in {"image", "audio", "document"}:
        media_id = str((message.get(message_type) or {}).get("id") or "").strip()
        text = str((message.get(message_type) or {}).get("caption") or "").strip()
    else:
        message_type = "unknown"
    return NormalizedMessage(
        provider="meta",
        from_phone=str(message.get("from") or "").strip(),
        message_id=str(message.get("id") or "").strip(),
        type=message_type,
        text=text,
        media_id=media_id,
        timestamp=str(message.get("timestamp") or "").strip(),
        raw=message,
    )


def clean_whatsapp_phone(value: str) -> str:
    text = str(value or "").replace("whatsapp:", "").strip()
    return "".join(character for character in text if character.isdigit() or character == "+")
