from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any


UNIT_FACTORS = {
    "tablet": 1,
    "piece": 1,
    "unit": 1,
    "bottle": 1,
    "strip": 10,
    "box": 100,
}

UNIT_ALIASES = {
    "tab": "tablet",
    "tabs": "tablet",
    "tablet": "tablet",
    "tablets": "tablet",
    "piece": "piece",
    "pieces": "piece",
    "pc": "piece",
    "pcs": "piece",
    "unit": "unit",
    "units": "unit",
    "bottle": "bottle",
    "bottles": "bottle",
    "strip": "strip",
    "strips": "strip",
    "box": "box",
    "boxes": "box",
}

PAYMENT_ALIASES = {
    "cash": "Cash",
    "mpesa": "M-Pesa",
    "m-pesa": "M-Pesa",
    "m pesa": "M-Pesa",
    "card": "Card",
    "credit": "Credit",
    "mixed": "Mixed",
    "pay later": "Credit",
    "unpaid": "Credit",
}


@dataclass(frozen=True)
class QuantityUnit:
    quantity: int
    unit: str = ""

    @property
    def canonical_unit(self) -> str:
        return canonical_unit(self.unit)

    @property
    def base_quantity(self) -> int:
        return to_base_quantity(self.quantity, self.unit)


@dataclass(frozen=True)
class ParsedModifiers:
    payment_method: str = ""
    discount: float = 0
    discount_percent: float = 0
    staff_name: str = ""
    supplier: str = ""
    invoice_number: str = ""
    batch_number: str = ""
    barcode: str = ""
    expiry_date: str = ""


def canonical_unit(value: str | None) -> str:
    text = str(value or "").strip().lower()
    return UNIT_ALIASES.get(text, text if text in UNIT_FACTORS else "")


def unit_factor(unit: str | None) -> int:
    return UNIT_FACTORS.get(canonical_unit(unit), 1)


def to_base_quantity(quantity: int | float | str, unit: str | None = "") -> int:
    try:
        parsed = int(float(str(quantity).strip()))
    except (TypeError, ValueError):
        parsed = 1
    parsed = max(parsed, 1)
    return parsed * unit_factor(unit)


def plural_unit(unit: str | None, quantity: int | None = None) -> str:
    canonical = canonical_unit(unit)
    if not canonical:
        return "units"
    if quantity == 1:
        return canonical
    if canonical == "box":
        return "boxes"
    return f"{canonical}s"


def unit_pattern() -> str:
    words = sorted(UNIT_ALIASES, key=len, reverse=True)
    return r"(?:" + "|".join(re.escape(word) for word in words) + r")"


def payment_pattern() -> str:
    words = sorted(PAYMENT_ALIASES, key=len, reverse=True)
    return r"(?:" + "|".join(re.escape(word) for word in words) + r")"


def parse_payment_method(text: str) -> str:
    match = re.search(rf"\b({payment_pattern()})\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return PAYMENT_ALIASES.get(match.group(1).lower(), match.group(1).title())


def parse_discount(text: str) -> float:
    match = re.search(r"\b(?:discount|less)\s*(\d+(?:\.\d+)?)(?:\s*%)?\b", text, flags=re.IGNORECASE)
    if not match:
        return 0
    try:
        return float(match.group(1))
    except ValueError:
        return 0


def parse_discount_percent(text: str) -> float:
    match = re.search(r"\b(?:discount|less)\s*(\d+(?:\.\d+)?)\s*%", text, flags=re.IGNORECASE)
    if not match:
        return 0
    try:
        return float(match.group(1))
    except ValueError:
        return 0


def parse_staff_name(text: str) -> str:
    match = re.fullmatch(r"(?:set\s+staff|staff|login|switch\s+staff)\s+(.+)", text.strip(), flags=re.IGNORECASE)
    return " ".join(match.group(1).strip().split()).title() if match else ""


def parse_trace_modifiers(text: str) -> ParsedModifiers:
    supplier = _extract_after_label(text, ["supplier"], stop_labels=["invoice", "batch", "expiry", "expires", "exp", "barcode", "payment", "discount", "less"])
    invoice = _extract_after_label(text, ["invoice", "inv"], stop_labels=["batch", "expiry", "expires", "exp", "supplier", "barcode", "payment", "discount", "less"])
    batch = _extract_after_label(text, ["batch"], stop_labels=["invoice", "expiry", "expires", "exp", "supplier", "barcode", "payment", "discount", "less"])
    barcode = _extract_after_label(text, ["barcode", "code"], stop_labels=["invoice", "batch", "expiry", "expires", "exp", "supplier", "payment", "discount", "less"])
    expiry = _extract_after_label(text, ["expiry", "expires", "exp"], stop_labels=["invoice", "batch", "supplier", "barcode", "payment", "discount", "less"])
    return ParsedModifiers(
        payment_method=parse_payment_method(text),
        discount=parse_discount(text),
        discount_percent=parse_discount_percent(text),
        supplier=supplier,
        invoice_number=invoice,
        batch_number=batch,
        barcode=barcode,
        expiry_date=expiry,
    )


def strip_modifier_phrases(text: str) -> str:
    clean = f" {text.strip()} "
    clean = re.sub(rf"\s+\b{payment_pattern()}\b(?:\s+\d+(?:\.\d+)?)?", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+\b(?:discount|less)\s*\d+(?:\.\d+)?\s*%?\b", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+%", " ", clean)
    clean = re.sub(r"\s+\b(?:supplier|invoice|inv|batch|barcode|code|expiry|expires|exp)\s+.+?(?=\s+\b(?:supplier|invoice|inv|batch|barcode|code|expiry|expires|exp|payment|discount)\b|$)", " ", clean, flags=re.IGNORECASE)
    return " ".join(clean.split())


def trace_id(prefix: str = "TRX") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def build_note(existing: str = "", **metadata: Any) -> str:
    parts = [existing.strip()] if str(existing or "").strip() else []
    for key, value in metadata.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return "; ".join(parts)


def parse_note_metadata(note: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for part in str(note or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key:
            metadata[key] = value
    return metadata


def _extract_after_label(text: str, labels: list[str], stop_labels: list[str]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)
    match = re.search(rf"\b(?:{label_pattern})\s+(.+?)(?=\s+\b(?:{stop_pattern})\b|$)", text, flags=re.IGNORECASE)
    return " ".join(match.group(1).strip(" ,").split()) if match else ""
