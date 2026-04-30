from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        return float(value)

    text = str(value).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def parse_int(value: Any, default: int | None = 0) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return default


def format_ksh(amount: float | int | None) -> str:
    amount = float(amount or 0)
    if abs(amount - round(amount)) < 0.005:
        return f"Ksh {int(round(amount)):,}"
    return f"Ksh {amount:,.2f}"


def now_in_timezone(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def normalize_key(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())
