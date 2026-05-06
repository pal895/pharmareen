from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.providers.meta_whatsapp import MetaWhatsAppClient, NormalizedMessage
from app.services.message_router import MessageRouter, build_default_router


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/meta/whatsapp", tags=["meta-whatsapp"])
meta_callback_router = APIRouter(tags=["meta-whatsapp"])
META_CALLBACK_VERIFY_TOKEN = "pharmareen123"


@lru_cache
def get_meta_client() -> MetaWhatsAppClient:
    return MetaWhatsAppClient(get_settings())


@lru_cache
def get_message_router() -> MessageRouter:
    return build_default_router()



@meta_callback_router.get("/meta/webhook")
def verify_meta_callback_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    if hub_mode == "subscribe" and hub_verify_token == META_CALLBACK_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@meta_callback_router.post("/meta/webhook")
async def receive_meta_callback_webhook(request: Request) -> dict[str, str]:
    return await receive_meta_webhook(request)

@router.get("")
def verify_meta_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    challenge = get_meta_client().verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return PlainTextResponse(challenge)


@router.post("")
async def receive_meta_webhook(request: Request) -> dict[str, str]:
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        logger.warning("META_WEBHOOK_INVALID_JSON")
        payload = {}

    entry_count = len(payload.get("entry", [])) if isinstance(payload.get("entry"), list) else 0
    logger.info("META_WEBHOOK_RECEIVED entries=%s", entry_count)

    client = get_meta_client()
    try:
        messages = client.normalize_webhook(payload)
    except Exception:
        logger.exception("META_WEBHOOK_NORMALIZE_FAILED")
        return {"status": "ok"}

    logger.info("META_WEBHOOK_MESSAGES count=%s types=%s", len(messages), [message.type for message in messages])
    for message in messages:
        await handle_normalized_message(message, client)
    return {"status": "ok"}


async def handle_normalized_message(message: NormalizedMessage, client: MetaWhatsAppClient) -> None:
    media_bytes: bytes | None = None
    content_type = None
    if message.type in {"image", "audio", "document"} and message.media_id:
        try:
            media_bytes = await client.download_media(message.media_id)
            content_type = str(((message.raw or {}).get(message.type) or {}).get("mime_type") or "")
        except Exception as exc:
            logger.warning("Meta media download failed for message %s: %s", message.message_id, exc)
    try:
        result = await get_message_router().handle(message, media_bytes=media_bytes, content_type=content_type)
        if result.reply:
            await client.send_text(message.from_phone, result.reply)
        logger.info("META_MESSAGE_HANDLED type=%s action=%s saved=%s", message.type, result.action_type, result.saved)
    except Exception:
        logger.exception("Meta message handling failed")
