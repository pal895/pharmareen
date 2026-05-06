from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Request

from app.services.message_router import build_default_router
from app.services.offline_sync import OfflineSyncService


router = APIRouter(prefix="/sync", tags=["offline-sync"])
synced_action_ids: set[str] = set()


@lru_cache
def get_offline_sync_service() -> OfflineSyncService:
    return OfflineSyncService(build_default_router().intake_service, synced_action_ids)


@router.post("/offline-actions")
async def sync_offline_actions(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    actions = payload.get("actions") if isinstance(payload, dict) else None
    if not isinstance(actions, list):
        return {"status": "error", "message": "Send actions as a list.", "results": []}
    return get_offline_sync_service().sync_actions(actions)
