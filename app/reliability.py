from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.training_store import DEFAULT_TRAINING_DIR, TrainingStore


DEFAULT_RELIABILITY_LEDGER_PATH = DEFAULT_TRAINING_DIR / "reliability_ledger.json"
RELIABILITY_POLICY_FILE = "reliability_policy.json"

QUEUED = "queued"
INFLIGHT = "inflight"
APPLIED = "applied"
RETRY = "retry"
DEAD_LETTER = "dead_letter"
CONFLICT = "conflict"
DUPLICATE = "duplicate"

SYNC_SOURCES = {"offline", "offline_pwa", "whatsapp", "whatsapp_bridge", "baileys", "backend"}


@dataclass(frozen=True)
class SyncEnvelope:
    source: str
    payload: dict[str, Any]
    pharmacy_id: str = "default"
    idempotency_key: str | None = None
    source_message_id: str | None = None
    group_id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class QueueResult:
    accepted: bool
    duplicate: bool
    conflict: bool
    record: dict[str, Any]
    message: str


class ProductionReliabilityEngine:
    def __init__(
        self,
        *,
        ledger_path: str | Path | None = None,
        store: TrainingStore | None = None,
        pharmacy_id: str = "default",
    ) -> None:
        self.ledger_path = Path(ledger_path or DEFAULT_RELIABILITY_LEDGER_PATH)
        self.store = store or TrainingStore(pharmacy_id=pharmacy_id)
        self.pharmacy_id = pharmacy_id or self.store.pharmacy_id or "default"

    def enqueue(self, envelope: SyncEnvelope, *, now: datetime | None = None) -> QueueResult:
        current = utc_now(now)
        data = self._load()
        pharmacy_id = self._effective_pharmacy_id(envelope.pharmacy_id)
        pharmacy = self._pharmacy(data, pharmacy_id)
        key = envelope.idempotency_key or stable_sync_key(
            pharmacy_id=pharmacy_id,
            source=envelope.source,
            source_message_id=envelope.source_message_id,
            payload=envelope.payload,
        )
        payload_hash = stable_payload_hash(envelope.payload)
        existing = pharmacy.setdefault("items", {}).get(key)

        if existing is not None:
            if existing.get("payload_hash") == payload_hash:
                existing.setdefault("duplicates", []).append(
                    {
                        "source": normalize_source(envelope.source),
                        "source_message_id": envelope.source_message_id,
                        "seen_at": current,
                    }
                )
                existing.setdefault("audit", []).append({"type": DUPLICATE, "at": current})
                self._save(data)
                return QueueResult(
                    accepted=False,
                    duplicate=True,
                    conflict=False,
                    record=existing,
                    message=str(self.policy().get("duplicate_ack") or "Already synced. No duplicate was created."),
                )

            conflict = {
                "idempotency_key": key,
                "source": normalize_source(envelope.source),
                "source_message_id": envelope.source_message_id,
                "payload": envelope.payload,
                "payload_hash": payload_hash,
                "status": CONFLICT,
                "created_at": current,
            }
            pharmacy.setdefault("conflicts", []).append(conflict)
            existing.setdefault("audit", []).append({"type": CONFLICT, "at": current})
            self._save(data)
            return QueueResult(
                accepted=False,
                duplicate=False,
                conflict=True,
                record=existing,
                message=f"Sync conflict held for review: {key}.",
            )

        source = normalize_source(envelope.source)
        record = {
            "idempotency_key": key,
            "source": source,
            "source_message_id": envelope.source_message_id,
            "group_id": envelope.group_id,
            "payload": envelope.payload,
            "payload_hash": payload_hash,
            "status": QUEUED,
            "attempts": 0,
            "max_attempts": int(self.policy().get("max_attempts") or 3),
            "created_at": envelope.created_at or current,
            "updated_at": current,
            "last_attempt_at": None,
            "next_retry_at": current,
            "error": None,
            "confirmations": [],
            "duplicates": [],
            "audit": [{"type": QUEUED, "at": current, "source": source}],
        }
        pharmacy.setdefault("items", {})[key] = record
        self._save(data)
        return QueueResult(
            accepted=True,
            duplicate=False,
            conflict=False,
            record=record,
            message=str(self.policy().get("offline_ack") or "Saved offline. It will sync when connection improves."),
        )

    def mark_inflight(self, idempotency_key: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        data = self._load()
        record = self._record(data, idempotency_key)
        if record is None or record.get("status") == APPLIED:
            return record
        current = utc_now(now)
        record["status"] = INFLIGHT
        record["attempts"] = int(record.get("attempts") or 0) + 1
        record["last_attempt_at"] = current
        record["updated_at"] = current
        record.setdefault("audit", []).append({"type": INFLIGHT, "at": current, "attempt": record["attempts"]})
        self._save(data)
        return record

    def mark_applied(
        self,
        idempotency_key: str,
        *,
        confirmation: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        data = self._load()
        record = self._record(data, idempotency_key)
        if record is None:
            return None
        current = utc_now(now)
        if record.get("status") != APPLIED:
            record["status"] = APPLIED
            record["updated_at"] = current
            record.setdefault("audit", []).append({"type": APPLIED, "at": current})
        if confirmation:
            record.setdefault("confirmations", []).append({"text": confirmation, "at": current})
        self._save(data)
        return record

    def mark_failed(
        self,
        idempotency_key: str,
        error: str,
        *,
        retryable: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        data = self._load()
        record = self._record(data, idempotency_key)
        if record is None:
            return None
        current_dt = now or datetime.now(timezone.utc)
        current = utc_now(current_dt)
        attempts = int(record.get("attempts") or 0)
        max_attempts = int(record.get("max_attempts") or self.policy().get("max_attempts") or 3)
        if not retryable or attempts >= max_attempts:
            status = DEAD_LETTER
            next_retry_at = None
        else:
            status = RETRY
            delay = retry_delay_seconds(attempts, self.policy())
            next_retry_at = utc_now(current_dt + timedelta(seconds=delay))

        record["status"] = status
        record["error"] = str(error)
        record["updated_at"] = current
        record["next_retry_at"] = next_retry_at
        record.setdefault("audit", []).append(
            {
                "type": status,
                "at": current,
                "error": str(error),
                "attempt": attempts,
                "retryable": retryable,
            }
        )
        self._save(data)
        return record

    def recover_after_reconnect(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current_dt = now or datetime.now(timezone.utc)
        current = utc_now(current_dt)
        timeout_seconds = int(self.policy().get("inflight_timeout_seconds") or 300)
        recovered: list[dict[str, Any]] = []
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        for record in pharmacy.setdefault("items", {}).values():
            if not isinstance(record, dict):
                continue
            status = record.get("status")
            if status == INFLIGHT and is_older_than(record.get("updated_at"), current_dt, timeout_seconds):
                record["status"] = QUEUED
                record["updated_at"] = current
                record.setdefault("audit", []).append({"type": "recovered_from_inflight", "at": current})
                recovered.append(record)
            elif status == RETRY and retry_due(record.get("next_retry_at"), current_dt):
                record["status"] = QUEUED
                record["updated_at"] = current
                record.setdefault("audit", []).append({"type": "retry_requeued", "at": current})
                recovered.append(record)
        self._save(data)
        return recovered

    def due_items(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        current_dt = now or datetime.now(timezone.utc)
        pharmacy = self._pharmacy(self._load(), self.pharmacy_id)
        due: list[dict[str, Any]] = []
        for record in pharmacy.setdefault("items", {}).values():
            if not isinstance(record, dict):
                continue
            status = record.get("status")
            if status == QUEUED:
                due.append(record)
            elif status == RETRY and retry_due(record.get("next_retry_at"), current_dt):
                due.append(record)
        return sorted(due, key=lambda item: str(item.get("created_at") or ""))

    def process_due(
        self,
        handler: Callable[[dict[str, Any]], str | None],
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        processed: list[dict[str, Any]] = []
        for record in self.due_items(now=now):
            key = str(record["idempotency_key"])
            inflight = self.mark_inflight(key, now=now)
            if inflight is None:
                continue
            try:
                confirmation = handler(inflight)
            except Exception as exc:
                failed = self.mark_failed(key, str(exc), retryable=True, now=now)
                if failed is not None:
                    processed.append(failed)
                continue
            applied = self.mark_applied(key, confirmation=confirmation, now=now)
            if applied is not None:
                processed.append(applied)
        return processed

    def grouped_confirmation(self, group_id: str) -> str:
        items = self.items_by_group(group_id)
        applied = sum(1 for item in items if item.get("status") == APPLIED)
        queued = sum(1 for item in items if item.get("status") in {QUEUED, RETRY, INFLIGHT})
        failed = sum(1 for item in items if item.get("status") in {DEAD_LETTER, CONFLICT})
        template = str(
            self.policy().get("grouped_confirmation_template")
            or "{applied} synced, {queued} waiting, {failed} need review."
        )
        return template.format(applied=applied, queued=queued, failed=failed)

    def low_network_ack(self) -> str:
        pending = len([item for item in self.all_items() if item.get("status") in {QUEUED, RETRY, INFLIGHT}])
        threshold = int(self.policy().get("low_network_backlog_threshold") or 5)
        if pending >= threshold:
            return str(self.policy().get("offline_ack") or "Saved offline. It will sync when connection improves.")
        return "Saved. Sync is healthy."

    def no_data_loss_report(self) -> dict[str, int]:
        items = self.all_items()
        pharmacy = self._pharmacy(self._load(), self.pharmacy_id)
        return {
            "total_records": len(items),
            "queued": sum(1 for item in items if item.get("status") == QUEUED),
            "applied": sum(1 for item in items if item.get("status") == APPLIED),
            "retry": sum(1 for item in items if item.get("status") == RETRY),
            "dead_letter": sum(1 for item in items if item.get("status") == DEAD_LETTER),
            "conflict": len([item for item in pharmacy.get("conflicts", []) if isinstance(item, dict)]),
        }

    def all_items(self) -> list[dict[str, Any]]:
        pharmacy = self._pharmacy(self._load(), self.pharmacy_id)
        return [item for item in pharmacy.setdefault("items", {}).values() if isinstance(item, dict)]

    def items_by_group(self, group_id: str) -> list[dict[str, Any]]:
        return [item for item in self.all_items() if item.get("group_id") == group_id]

    def policy(self) -> dict[str, Any]:
        data = self.store.load_json(RELIABILITY_POLICY_FILE, default={})
        if not isinstance(data, dict):
            data = {}
        return {
            "max_attempts": 3,
            "retry_delays_seconds": [0, 30, 120],
            "inflight_timeout_seconds": 300,
            "low_network_backlog_threshold": 5,
            "offline_ack": "Saved offline. It will sync when connection improves.",
            "duplicate_ack": "Already synced. No duplicate was created.",
            "grouped_confirmation_template": "{applied} synced, {queued} waiting, {failed} need review.",
            **data,
        }

    def _record(self, data: dict[str, Any], idempotency_key: str) -> dict[str, Any] | None:
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        record = pharmacy.setdefault("items", {}).get(idempotency_key)
        return record if isinstance(record, dict) else None

    def _effective_pharmacy_id(self, pharmacy_id: str | None) -> str:
        if not pharmacy_id or pharmacy_id == "default":
            return self.pharmacy_id
        return pharmacy_id

    def _pharmacy(self, data: dict[str, Any], pharmacy_id: str) -> dict[str, Any]:
        pharmacy = data.setdefault("pharmacies", {}).setdefault(pharmacy_id or self.pharmacy_id, {})
        pharmacy.setdefault("items", {})
        pharmacy.setdefault("conflicts", [])
        return pharmacy

    def _load(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return {"version": 1, "pharmacies": {}}
        text = self.ledger_path.read_text(encoding="utf-8").strip()
        if not text:
            return {"version": 1, "pharmacies": {}}
        data = json.loads(text)
        if not isinstance(data, dict):
            return {"version": 1, "pharmacies": {}}
        data.setdefault("version", 1)
        data.setdefault("pharmacies", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(self.ledger_path)


def stable_sync_key(
    *,
    pharmacy_id: str,
    source: str,
    source_message_id: str | None,
    payload: dict[str, Any],
) -> str:
    if source_message_id:
        base = f"{pharmacy_id}:{normalize_source(source)}:{source_message_id}"
    else:
        base = f"{pharmacy_id}:{stable_payload_hash(payload)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def stable_payload_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def normalize_source(source: str) -> str:
    clean = str(source or "backend").strip().lower()
    return clean if clean in SYNC_SOURCES else "backend"


def retry_delay_seconds(attempts: int, policy: dict[str, Any]) -> int:
    delays = policy.get("retry_delays_seconds") or [0, 30, 120]
    if not isinstance(delays, list) or not delays:
        return 30
    index = min(max(attempts - 1, 0), len(delays) - 1)
    try:
        return int(delays[index])
    except (TypeError, ValueError):
        return 30


def retry_due(value: Any, current: datetime) -> bool:
    if not value:
        return True
    try:
        target = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return target <= current.astimezone(timezone.utc)


def is_older_than(value: Any, current: datetime, seconds: int) -> bool:
    if not value:
        return True
    try:
        target = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return target <= current.astimezone(timezone.utc) - timedelta(seconds=seconds)


def utc_now(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()
