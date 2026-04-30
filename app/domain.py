from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Action(str, Enum):
    SOLD = "Sold"
    LATE_SALE = "Late Sale"
    OUT_OF_STOCK = "Out of Stock"
    NOT_SOLD = "Not Sold"
    RESTOCKED = "Restocked"

    @classmethod
    def from_value(cls, value: Any) -> "Action | None":
        if isinstance(value, cls):
            return value
        if value is None:
            return None

        normalized = str(value).strip().lower().replace("_", " ").replace("-", " ")
        normalized = " ".join(normalized.split())

        aliases = {
            "sold": cls.SOLD,
            "sale": cls.SOLD,
            "late sale": cls.LATE_SALE,
            "late_sale": cls.LATE_SALE,
            "later sale": cls.LATE_SALE,
            "missed sale": cls.LATE_SALE,
            "out of stock": cls.OUT_OF_STOCK,
            "no stock": cls.OUT_OF_STOCK,
            "not available": cls.OUT_OF_STOCK,
            "not sold": cls.NOT_SOLD,
            "lost opportunity": cls.NOT_SOLD,
            "customer left": cls.NOT_SOLD,
            "restock": cls.RESTOCKED,
            "restocked": cls.RESTOCKED,
            "re stock": cls.RESTOCKED,
            "stock added": cls.RESTOCKED,
        }
        return aliases.get(normalized)


@dataclass(frozen=True)
class ParsedEvent:
    drug_name: str
    action: Action | None
    quantity: int = 1
    notes: str = ""
    needs_clarification: bool = False
    clarification_question: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ParsedEvent":
        quantity = _positive_int(data.get("quantity"), default=1)
        needs_clarification = bool(data.get("needs_clarification", False))
        action = Action.from_value(data.get("action"))

        if action is None and not needs_clarification:
            needs_clarification = True

        return cls(
            drug_name=str(data.get("drug_name") or "").strip(),
            action=action,
            quantity=quantity,
            notes=str(data.get("notes") or "").strip(),
            needs_clarification=needs_clarification,
            clarification_question=_optional_text(data.get("clarification_question")),
        )


@dataclass(frozen=True)
class ParseResult:
    events: list[ParsedEvent]
    needs_clarification: bool = False
    clarification_question: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ParseResult":
        events = [
            ParsedEvent.from_mapping(item)
            for item in data.get("events", [])
            if isinstance(item, dict)
        ]
        needs_clarification = bool(data.get("needs_clarification", False))
        if not events and not needs_clarification:
            needs_clarification = True

        return cls(
            events=events,
            needs_clarification=needs_clarification,
            clarification_question=_optional_text(data.get("clarification_question")),
        )


@dataclass(frozen=True)
class StockItem:
    drug_name: str
    selling_price: float | None
    cost_price: float | None = None
    current_stock: int | None = None
    reorder_level: int | None = None
    row_number: int | None = None


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
