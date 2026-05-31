from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from app.utils import normalize_key


DEFAULT_ALIAS_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "pharmacy_aliases.json"


class PharmacyAliasStore:
    """Small persistent store for pharmacy-approved shorthand.

    Short aliases are intentionally conservative: they need an explicit owner
    approval or repeated confirmed use before becoming automatic.
    """

    def __init__(self, path: Path | None = None, *, short_alias_threshold: int = 2):
        configured = str(os.getenv("PHARMAREEN_ALIAS_STORE_PATH") or "").strip()
        self.path = path or (Path(configured) if configured else DEFAULT_ALIAS_STORE_PATH)
        self.short_alias_threshold = max(int(short_alias_threshold), 1)

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return {"pharmacies": {}}
        if not isinstance(data, dict):
            return {"pharmacies": {}}
        data.setdefault("pharmacies", {})
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.path)

    def accepted_aliases(self, pharmacy_id: str) -> dict[str, str]:
        data = self._read()
        pharmacy = data.get("pharmacies", {}).get(normalize_key(pharmacy_id), {})
        aliases = pharmacy.get("aliases", {}) if isinstance(pharmacy, dict) else {}
        if not isinstance(aliases, dict):
            return {}
        return {
            alias: str(record.get("medicine") or "").strip()
            for alias, record in aliases.items()
            if isinstance(record, dict) and record.get("accepted") and str(record.get("medicine") or "").strip()
        }

    def observe(
        self,
        pharmacy_id: str,
        alias: str,
        medicine: str,
        *,
        confirmed: bool,
        owner_approved: bool = False,
        inventory_names: Iterable[str] = (),
    ) -> dict[str, Any]:
        alias_key = normalize_key(alias)
        medicine_name = " ".join(str(medicine or "").strip().split())
        if not alias_key or not medicine_name:
            return {"accepted": False, "needs_review": True, "reason": "missing alias or medicine"}
        inventory_choices = [
            str(name).strip()
            for name in inventory_names
            if normalize_key(name).startswith(alias_key)
        ]
        if len(set(inventory_choices)) > 1 and not owner_approved:
            return {
                "accepted": False,
                "needs_review": True,
                "reason": "inventory ambiguity",
                "choices": inventory_choices[:5],
            }
        data = self._read()
        pharmacies = data.setdefault("pharmacies", {})
        pharmacy = pharmacies.setdefault(normalize_key(pharmacy_id) or "default", {"aliases": {}, "review_log": []})
        aliases = pharmacy.setdefault("aliases", {})
        record = aliases.setdefault(alias_key, {"medicine": medicine_name, "confirmations": 0, "accepted": False})
        if normalize_key(record.get("medicine")) != normalize_key(medicine_name):
            pharmacy.setdefault("review_log", []).append(
                {
                    "alias": alias_key,
                    "medicine": medicine_name,
                    "status": "conflict",
                    "existing": record.get("medicine"),
                }
            )
            self._write(data)
            return {"accepted": False, "needs_review": True, "reason": "conflicting medicine"}
        if confirmed:
            record["confirmations"] = int(record.get("confirmations") or 0) + 1
        required = self.short_alias_threshold if len(alias_key) <= 3 else 1
        record["accepted"] = bool(owner_approved or (confirmed and int(record["confirmations"]) >= required))
        record["medicine"] = medicine_name
        pharmacy.setdefault("review_log", []).append(
            {
                "alias": alias_key,
                "medicine": medicine_name,
                "status": "accepted" if record["accepted"] else "needs_review",
                "confirmations": record["confirmations"],
            }
        )
        pharmacy["review_log"] = pharmacy["review_log"][-100:]
        self._write(data)
        return {
            "alias": alias_key,
            "medicine": medicine_name,
            "accepted": bool(record["accepted"]),
            "needs_review": not bool(record["accepted"]),
            "confirmations": int(record["confirmations"]),
            "reason": "owner approved" if owner_approved else ("confirmed pattern" if record["accepted"] else "needs another confirmation"),
        }

    def snapshot(self, pharmacy_id: str) -> dict[str, Any]:
        data = self._read()
        pharmacy = data.get("pharmacies", {}).get(normalize_key(pharmacy_id), {})
        return pharmacy if isinstance(pharmacy, dict) else {}
