from __future__ import annotations

import json
import time
from copy import deepcopy
from typing import Any

from app.config import Settings
from app.services.owner_auth_persistence import owner_auth_sheet_id
from app.services.pharmacy_onboarding import PharmacyOnboardingService, ensure_worksheet


FRONT_DOOR_SHEET = "Front_Door_State"
FRONT_DOOR_HEADERS = ["Pharmacy ID", "State JSON"]
PLATFORM_ROW = "__platform__"


class GoogleSheetsFrontDoorStore:
    """Protected durable store for non-secret front-door state.

    Raw phone numbers, invitation tokens, device keys, PINs and cookies are
    prohibited. The service writes only one-way digests, bounded authorization
    state and pharmacy-level identities.
    """

    def __init__(self, settings: Settings):
        self._onboarding = PharmacyOnboardingService(settings)
        self._sheet_id = owner_auth_sheet_id(settings)
        if not self._sheet_id:
            raise RuntimeError("Front-door durable workbook is not configured")

    def _worksheet(self):
        spreadsheet = self._onboarding._gspread_client().open_by_key(self._sheet_id)
        return ensure_worksheet(spreadsheet, FRONT_DOOR_SHEET, FRONT_DOOR_HEADERS)

    def load(self) -> dict[str, Any]:
        state: dict[str, Any] = {"version": 1, "community_counter": 0, "pharmacies": {}, "used_nonces": [], "pending_entries": {}}
        for row in self._worksheet().get_all_records():
            key = str(row.get("Pharmacy ID") or "").strip()
            raw = str(row.get("State JSON") or "").strip()
            if not key or not raw:
                continue
            try:
                value = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError("Front-door durable state is invalid") from exc
            if key == PLATFORM_ROW:
                state["community_counter"] = int(value.get("community_counter") or 0)
                state["used_nonces"] = list(value.get("used_nonces") or [])[-10000:]
                state["pending_entries"] = dict(value.get("pending_entries") or {})
            elif isinstance(value, dict) and value.get("pharmacy_id") == key:
                state["pharmacies"][key] = value
            else:
                raise RuntimeError("Front-door pharmacy binding is invalid")
        return state

    def save(self, value: dict[str, Any]) -> None:
        payload = deepcopy(value)
        pending_entries = {
            key: item for key, item in dict(payload.get("pending_entries") or {}).items()
            if item.get("status") in {"active", "provisioning"} and int(item.get("expires_at") or 0) > int(time.time())
        }
        rows = [[PLATFORM_ROW, _json({"community_counter": int(payload.get("community_counter") or 0), "used_nonces": list(payload.get("used_nonces") or [])[-10000:], "pending_entries": pending_entries})]]
        for pharmacy_id, pharmacy in sorted(payload.get("pharmacies", {}).items()):
            if not pharmacy_id or not isinstance(pharmacy, dict) or pharmacy.get("pharmacy_id") != pharmacy_id:
                raise ValueError("Front-door pharmacy binding is invalid")
            serialized = _json(pharmacy)
            for forbidden in ("pin", "cookie", "raw_phone", "raw_device", "raw_token"):
                if f'"{forbidden}"' in serialized.lower():
                    raise ValueError("Raw secret-like front-door field is prohibited")
            rows.append([pharmacy_id, serialized])
        worksheet = self._worksheet()
        worksheet.clear()
        worksheet.update("A1", [FRONT_DOOR_HEADERS, *rows])


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
