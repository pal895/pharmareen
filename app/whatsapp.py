from __future__ import annotations

import logging
from html import escape

import httpx

from app.config import Settings


logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Provider-neutral WhatsApp helper for the Web MVP.

    The Node bridge sends live replies; this adapter keeps report/service code
    provider-neutral and safe when no official API credentials exist.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    async def download_media(self, media_url: str) -> bytes:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
            response = await http_client.get(media_url)
            response.raise_for_status()
            return response.content

    def send_message(self, body: str, to: str | None = None, media_url: str | None = None) -> None:
        logger.info("WhatsApp provider send skipped in Web MVP mode; bridge replies happen in Node.")

    def validate_request(self, url: str, form_values: dict[str, object], signature: str | None) -> bool:
        return False


def xml_message_response(message: str, media_url: str | None = None) -> str:
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
