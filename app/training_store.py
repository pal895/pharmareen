from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_TRAINING_DIR = Path(__file__).resolve().parent.parent / "training"


class TrainingStore:
    """Small file-backed store for pharmacy training memory."""

    def __init__(
        self,
        training_dir: str | Path | None = None,
        pharmacy_id: str = "default",
    ) -> None:
        self.training_dir = Path(training_dir or DEFAULT_TRAINING_DIR)
        self.pharmacy_id = pharmacy_id or "default"

    def load_json(self, filename: str, default: Any | None = None) -> Any:
        path = self.training_dir / filename
        if not path.exists():
            return {} if default is None else default
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return {} if default is None else default
        return json.loads(text)

    def save_json(self, filename: str, data: Any) -> None:
        path = self.training_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def load_jsonl(self, filename: str) -> list[dict[str, Any]]:
        path = self.training_dir / filename
        if not path.exists():
            return []

        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            clean = line.strip()
            if not clean:
                continue
            value = json.loads(clean)
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def append_jsonl(self, filename: str, row: dict[str, Any]) -> None:
        path = self.training_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")

    def forms_units(self) -> dict[str, Any]:
        return self.load_json("forms_units.json", default={})

    def medicine_profiles(self) -> dict[str, Any]:
        return self.load_json("medicine_profiles.json", default={"medicines": []})

    def aliases(self) -> dict[str, Any]:
        return self.load_json("aliases.json", default={})

    def corrections(self) -> dict[str, Any]:
        data = self.load_json("corrections.json", default={"version": 1, "pharmacies": {}})
        if not isinstance(data, dict):
            data = {"version": 1, "pharmacies": {}}
        data.setdefault("version", 1)
        data.setdefault("pharmacies", {})
        return data

    def pharmacy_memory(self) -> dict[str, Any]:
        data = self.corrections()
        pharmacies = data.setdefault("pharmacies", {})
        memory = pharmacies.setdefault(
            self.pharmacy_id,
            {
                "actors": {},
                "medicine_aliases": {},
                "payment_aliases": {},
                "form_aliases": {},
                "packaging_aliases": {},
                "unit_aliases": {},
                "pending_corrections": [],
                "entries": [],
            },
        )
        memory.setdefault("actors", {})
        memory.setdefault("medicine_aliases", {})
        memory.setdefault("payment_aliases", {})
        memory.setdefault("form_aliases", {})
        memory.setdefault("packaging_aliases", {})
        memory.setdefault("unit_aliases", {})
        memory.setdefault("pending_corrections", [])
        memory.setdefault("entries", [])
        return memory

    def save_pharmacy_memory(self, memory: dict[str, Any]) -> None:
        data = self.corrections()
        data.setdefault("pharmacies", {})[self.pharmacy_id] = memory
        self.save_json("corrections.json", data)

    def register_actor(
        self,
        actor_id: str | None,
        role: str,
        *,
        display_name: str | None = None,
        source: str | None = None,
    ) -> None:
        if not actor_id:
            return
        memory = self.pharmacy_memory()
        memory.setdefault("actors", {})[actor_id] = {
            "actor_id": actor_id,
            "role": role,
            "display_name": display_name,
            "source": source,
        }
        self.save_pharmacy_memory(memory)

    def add_pending_correction(
        self,
        *,
        correction_type: str,
        alias: str,
        target: str,
        actor_id: str | None,
        actor_role: str,
        owner_id: str | None = None,
        staff_id: str | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        memory = self.pharmacy_memory()
        pending = memory.setdefault("pending_corrections", [])
        correction_id = f"pending-{len(pending) + 1}"
        entry = {
            "id": correction_id,
            "status": "pending",
            "type": correction_type,
            "alias": " ".join(alias.strip().lower().split()),
            "target": " ".join(target.strip().split()),
            "actor_id": actor_id,
            "actor_role": actor_role,
            "owner_id": owner_id,
            "staff_id": staff_id,
            "source": source,
        }
        pending.append(entry)
        memory.setdefault("entries", []).append(
            {
                "type": "pending_correction",
                "correction_id": correction_id,
                "correction_type": correction_type,
                "alias": entry["alias"],
                "target": entry["target"],
                "actor_id": actor_id,
                "actor_role": actor_role,
                "owner_id": owner_id,
                "staff_id": staff_id,
                "approved": False,
                "status": "pending",
            }
        )
        self.save_pharmacy_memory(memory)
        return entry

    def pending_corrections(self, status: str | None = "pending") -> list[dict[str, Any]]:
        pending = self.pharmacy_memory().get("pending_corrections", [])
        if status is None:
            return [entry for entry in pending if isinstance(entry, dict)]
        return [
            entry
            for entry in pending
            if isinstance(entry, dict) and str(entry.get("status") or "") == status
        ]

    def pending_correction(self, correction_id: str) -> dict[str, Any] | None:
        for entry in self.pending_corrections(status=None):
            if str(entry.get("id") or "") == correction_id:
                return entry
        return None

    def mark_pending_correction(
        self,
        correction_id: str,
        status: str,
        *,
        owner_id: str | None = None,
    ) -> dict[str, Any] | None:
        memory = self.pharmacy_memory()
        found: dict[str, Any] | None = None
        for entry in memory.setdefault("pending_corrections", []):
            if isinstance(entry, dict) and str(entry.get("id") or "") == correction_id:
                entry["status"] = status
                entry["approved_by_owner_id"] = owner_id
                found = entry
                break
        if found is not None:
            memory.setdefault("entries", []).append(
                {
                    "type": "pending_correction_decision",
                    "correction_id": correction_id,
                    "status": status,
                    "owner_id": owner_id,
                }
            )
            self.save_pharmacy_memory(memory)
        return found

    def add_medicine_alias(
        self,
        alias: str,
        medicine_name: str,
        *,
        owner_id: str | None = None,
        staff_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        approved_by_owner_id: str | None = None,
        source: str | None = None,
        approved: bool = True,
    ) -> None:
        memory = self.pharmacy_memory()
        clean_alias = " ".join(alias.strip().lower().split())
        clean_name = " ".join(medicine_name.strip().split())
        if not clean_alias or not clean_name:
            return

        memory["medicine_aliases"][clean_alias] = clean_name
        memory["entries"].append(
            {
                "type": "medicine_alias",
                "alias": clean_alias,
                "medicine_name": clean_name,
                "owner_id": owner_id,
                "staff_id": staff_id,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "approved_by_owner_id": approved_by_owner_id,
                "source": source,
                "approved": approved,
            }
        )
        self.save_pharmacy_memory(memory)

    def add_payment_alias(
        self,
        alias: str,
        payment: str,
        *,
        owner_id: str | None = None,
        staff_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        approved_by_owner_id: str | None = None,
        source: str | None = None,
        approved: bool = True,
    ) -> None:
        self._add_simple_alias(
            "payment_alias",
            "payment_aliases",
            alias,
            payment,
            owner_id=owner_id,
            staff_id=staff_id,
            actor_id=actor_id,
            actor_role=actor_role,
            approved_by_owner_id=approved_by_owner_id,
            source=source,
            approved=approved,
        )

    def add_form_alias(
        self,
        alias: str,
        form: str,
        *,
        owner_id: str | None = None,
        staff_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        approved_by_owner_id: str | None = None,
        source: str | None = None,
        approved: bool = True,
    ) -> None:
        self._add_simple_alias(
            "form_alias",
            "form_aliases",
            alias,
            form,
            owner_id=owner_id,
            staff_id=staff_id,
            actor_id=actor_id,
            actor_role=actor_role,
            approved_by_owner_id=approved_by_owner_id,
            source=source,
            approved=approved,
        )

    def add_packaging_alias(
        self,
        alias: str,
        packaging: str,
        *,
        owner_id: str | None = None,
        staff_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        approved_by_owner_id: str | None = None,
        source: str | None = None,
        approved: bool = True,
    ) -> None:
        self._add_simple_alias(
            "packaging_alias",
            "packaging_aliases",
            alias,
            packaging,
            owner_id=owner_id,
            staff_id=staff_id,
            actor_id=actor_id,
            actor_role=actor_role,
            approved_by_owner_id=approved_by_owner_id,
            source=source,
            approved=approved,
        )

    def add_unit_alias(
        self,
        alias: str,
        unit: str,
        *,
        owner_id: str | None = None,
        staff_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        approved_by_owner_id: str | None = None,
        source: str | None = None,
        approved: bool = True,
    ) -> None:
        self._add_simple_alias(
            "unit_alias",
            "unit_aliases",
            alias,
            unit,
            owner_id=owner_id,
            staff_id=staff_id,
            actor_id=actor_id,
            actor_role=actor_role,
            approved_by_owner_id=approved_by_owner_id,
            source=source,
            approved=approved,
        )

    def _add_simple_alias(
        self,
        entry_type: str,
        memory_key: str,
        alias: str,
        target: str,
        *,
        owner_id: str | None,
        staff_id: str | None,
        actor_id: str | None,
        actor_role: str | None,
        approved_by_owner_id: str | None,
        source: str | None,
        approved: bool,
    ) -> None:
        memory = self.pharmacy_memory()
        clean_alias = " ".join(alias.strip().lower().split())
        clean_target = " ".join(target.strip().lower().split())
        if not clean_alias or not clean_target:
            return

        memory[memory_key][clean_alias] = clean_target
        memory["entries"].append(
            {
                "type": entry_type,
                "alias": clean_alias,
                "target": clean_target,
                "owner_id": owner_id,
                "staff_id": staff_id,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "approved_by_owner_id": approved_by_owner_id,
                "source": source,
                "approved": approved,
            }
        )
        self.save_pharmacy_memory(memory)
