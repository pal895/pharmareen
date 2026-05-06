from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OfflineSyncService:
    intake_service: Any
    synced_action_ids: set[str]

    def sync_actions(self, actions: list[dict[str, Any]]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for action in actions:
            action_id = str(action.get("action_id") or "").strip()
            if not action_id:
                results.append({"action_id": "", "status": "failed", "error": "Missing action_id"})
                continue
            if action_id in self.synced_action_ids:
                results.append({"action_id": action_id, "status": "already_synced"})
                continue
            try:
                message = offline_action_to_message(action)
                if not message:
                    raise ValueError("Unsupported offline action")
                reply = self.intake_service.process_text(message)
            except Exception as exc:
                results.append({"action_id": action_id, "status": "failed", "error": str(exc)})
                continue
            self.synced_action_ids.add(action_id)
            results.append({"action_id": action_id, "status": "synced", "reply": reply})
        return {"status": "ok", "results": results}


def offline_action_to_message(action: dict[str, Any]) -> str:
    action_type = str(action.get("action_type") or "").strip().lower()
    drug_name = str(action.get("drug_name") or "").strip()
    quantity = int(float(str(action.get("quantity") or 1)))
    if not drug_name:
        return ""
    if action_type == "sale":
        return f"{drug_name} {quantity}"
    if action_type == "restock":
        return f"+{drug_name} {quantity}"
    if action_type == "stock_adjustment":
        return f"{drug_name} stock"
    if action_type == "issue":
        return f"{drug_name} bad"
    if action_type == "return":
        return f"return {drug_name} {quantity}"
    return ""
