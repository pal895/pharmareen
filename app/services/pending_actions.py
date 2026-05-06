from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingAction:
    action_id: str
    phone: str
    action_type: str
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    risky: bool = True


class PendingActionStore:
    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds
        self._actions: dict[str, PendingAction] = {}

    def set(self, phone: str, action_type: str, payload: dict[str, Any]) -> PendingAction:
        action = PendingAction(
            action_id=f"{safe_phone(phone)}-{int(time.time() * 1000)}",
            phone=safe_phone(phone),
            action_type=action_type,
            payload=payload,
        )
        self._actions[action.phone] = action
        return action

    def get(self, phone: str) -> PendingAction | None:
        key = safe_phone(phone)
        action = self._actions.get(key)
        if action and time.time() - action.created_at <= self.ttl_seconds:
            return action
        self._actions.pop(key, None)
        return None

    def clear(self, phone: str) -> None:
        self._actions.pop(safe_phone(phone), None)


def safe_phone(value: str) -> str:
    return "".join(character for character in str(value or "") if character.isdigit() or character == "+") or "unknown"


pending_actions = PendingActionStore()
