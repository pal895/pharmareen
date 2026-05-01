from __future__ import annotations

from html import escape
from typing import Any

import httpx
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.config import Settings


class WhatsAppClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.validator = RequestValidator(settings.twilio_auth_token)

    async def download_media(self, media_url: str) -> bytes:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
            response = await http_client.get(
                media_url,
                auth=(self.settings.twilio_account_sid, self.settings.twilio_auth_token),
            )
            response.raise_for_status()
            return response.content

    def send_message(self, body: str, to: str | None = None, media_url: str | None = None) -> None:
        payload: dict[str, Any] = {
            "from_": self.settings.twilio_whatsapp_from,
            "to": to or self.settings.owner_whatsapp_to,
            "body": body,
        }
        if media_url:
            payload["media_url"] = [media_url]
        self.client.messages.create(**payload)

    def validate_request(
        self,
        url: str,
        form_values: dict[str, Any],
        signature: str | None,
    ) -> bool:
        if not signature:
            return False
        clean_values = {key: str(value) for key, value in form_values.items()}
        return self.validator.validate(url, clean_values, signature)


def twiml_response(message: str, media_url: str | None = None) -> str:
    safe_message = escape(str(message or ""), quote=False)
    if not media_url:
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe_message}</Message></Response>'

    safe_media_url = escape(str(media_url), quote=True)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Message>"
        f"<Body>{safe_message}</Body>"
        f"<Media>{safe_media_url}</Media>"
        "</Message>"
        "</Response>"
    )
