from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.correction_learning import CorrectionLearningEngine
from app.reliability import ProductionReliabilityEngine, QueueResult, SyncEnvelope
from app.training_store import DEFAULT_TRAINING_DIR, TrainingStore


DEFAULT_LIVE_PILOT_LEDGER_PATH = DEFAULT_TRAINING_DIR / "live_pilot_ledger.json"
LIVE_PILOT_POLICY_FILE = "live_pilot_policy.json"
LIVE_RETRAINING_EXAMPLES_FILE = "live_retraining_examples.jsonl"

ACTIVE = "active"
READY_FOR_PRODUCTION = "ready_for_production"
ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class PilotActionResult:
    accepted: bool
    message: str
    pilot: dict[str, Any] | None = None
    record: dict[str, Any] | None = None
    blockers: tuple[str, ...] = ()


class LivePharmacyPilotEngine:
    def __init__(
        self,
        *,
        ledger_path: str | Path | None = None,
        store: TrainingStore | None = None,
        reliability_engine: ProductionReliabilityEngine | None = None,
        pharmacy_id: str = "default",
    ) -> None:
        self.ledger_path = Path(ledger_path or DEFAULT_LIVE_PILOT_LEDGER_PATH)
        self.store = store or TrainingStore(pharmacy_id=pharmacy_id)
        self.pharmacy_id = pharmacy_id or self.store.pharmacy_id or "default"
        self.reliability = reliability_engine or ProductionReliabilityEngine(
            ledger_path=self.store.training_dir / "reliability_ledger.json",
            store=self.store,
            pharmacy_id=self.pharmacy_id,
        )

    def start_pilot(
        self,
        *,
        pharmacy_id: str | None = None,
        owner_id: str | None = None,
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        pilot_pharmacy_id = pharmacy_id or self.pharmacy_id
        data = self._load()
        active_pharmacy_id = data.get("active_pharmacy_id")
        if (
            self.policy()["one_active_pharmacy"]
            and active_pharmacy_id
            and active_pharmacy_id != pilot_pharmacy_id
            and self._pharmacy(data, str(active_pharmacy_id)).get("status") == ACTIVE
        ):
            return PilotActionResult(
                accepted=False,
                message=f"Pilot blocked: {active_pharmacy_id} is already active.",
                blockers=("one_pharmacy_at_a_time",),
            )

        pilot = self._pharmacy(data, pilot_pharmacy_id)
        if pilot.get("status") == ACTIVE:
            pilot.setdefault("audit", []).append({"type": "pilot_resumed", "at": current, "owner_id": owner_id})
            self._save(data)
            return PilotActionResult(True, "Pilot already active.", pilot)

        pilot.update(
            {
                "pharmacy_id": pilot_pharmacy_id,
                "owner_id": owner_id,
                "status": ACTIVE,
                "started_at": current,
                "ended_at": None,
                "protections": locked_phase11_protections(),
                "telemetry": [],
                "issues": [],
                "feedback": [],
                "friction": [],
                "corrections": [],
                "rollback_points": [],
                "token_usage": empty_token_usage(),
                "audit": [{"type": "pilot_started", "at": current, "owner_id": owner_id}],
            }
        )
        data["active_pharmacy_id"] = pilot_pharmacy_id
        self._save(data)
        return PilotActionResult(True, f"Pilot started for {pilot_pharmacy_id}.", pilot)

    def record_live_event(
        self,
        *,
        event_type: str,
        source: str,
        workflow_id: str,
        payload: dict[str, Any],
        evidence: dict[str, Any] | None = None,
        known_flow: bool = True,
        tokens_used: int = 0,
        status: str = "observed",
        error: str | None = None,
        idempotency_key: str | None = None,
        source_message_id: str | None = None,
        group_id: str | None = None,
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        data = self._load()
        pilot = self._active_pilot(data, self.pharmacy_id)
        if pilot is None:
            return PilotActionResult(False, "No active pilot for this pharmacy.", blockers=("pilot_not_active",))

        required_evidence = set(self.policy()["required_evidence_fields"])
        evidence = evidence or {}
        missing_evidence = sorted(required_evidence - set(evidence))
        reliability_result: QueueResult | None = None
        if idempotency_key or source_message_id:
            reliability_result = self.reliability.enqueue(
                SyncEnvelope(
                    source=source,
                    payload=payload,
                    pharmacy_id=self.pharmacy_id,
                    idempotency_key=idempotency_key,
                    source_message_id=source_message_id,
                    group_id=group_id,
                    created_at=current,
                ),
                now=now,
            )

        token_violation = known_flow and int(tokens_used) > int(self.policy()["max_known_flow_tokens"])
        token_usage = pilot.setdefault("token_usage", empty_token_usage())
        token_usage["total_tokens"] = int(token_usage.get("total_tokens") or 0) + int(tokens_used)
        if known_flow:
            token_usage["known_flow_tokens"] = int(token_usage.get("known_flow_tokens") or 0) + int(tokens_used)
        if token_violation:
            token_usage["known_flow_violations"] = int(token_usage.get("known_flow_violations") or 0) + 1
        token_usage.setdefault("events", []).append(
            {
                "workflow_id": workflow_id,
                "event_type": event_type,
                "known_flow": known_flow,
                "tokens_used": int(tokens_used),
                "token_violation": token_violation,
                "at": current,
            }
        )

        record = {
            "id": f"telemetry-{len(pilot.setdefault('telemetry', [])) + 1}",
            "event_type": event_type,
            "source": source,
            "workflow_id": workflow_id,
            "payload": payload,
            "evidence": evidence,
            "missing_evidence": missing_evidence,
            "known_flow": known_flow,
            "tokens_used": int(tokens_used),
            "token_violation": token_violation,
            "status": status,
            "error": error,
            "reliability": reliability_summary(reliability_result),
            "created_at": current,
        }
        pilot["telemetry"].append(record)
        pilot.setdefault("audit", []).append({"type": "telemetry_logged", "at": current, "telemetry_id": record["id"]})

        retraining_rows: list[dict[str, Any]] = []
        if token_violation:
            retraining_rows.append(
                self._append_issue(
                    pilot,
                    issue_type="known_flow_token_violation",
                    severity="critical",
                    source=source,
                    description=f"Known flow used {tokens_used} AI/OpenAI tokens.",
                    evidence={"telemetry_id": record["id"], **evidence},
                    created_at=current,
                )
            )
        if error or status in {"error", "failed"}:
            retraining_rows.append(
                self._append_issue(
                    pilot,
                    issue_type="live_error",
                    severity="high",
                    source=source,
                    description=error or f"Live workflow {workflow_id} failed.",
                    evidence={"telemetry_id": record["id"], **evidence},
                    created_at=current,
                )
            )

        self._save(data)
        for row in retraining_rows:
            self._append_retraining_example(row)
        return PilotActionResult(True, "Live telemetry logged.", pilot, record)

    def capture_issue(
        self,
        *,
        issue_type: str,
        severity: str,
        source: str,
        description: str,
        evidence: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        data = self._load()
        pilot = self._active_pilot(data, self.pharmacy_id)
        if pilot is None:
            return PilotActionResult(False, "No active pilot for this pharmacy.", blockers=("pilot_not_active",))
        issue = self._append_issue(
            pilot,
            issue_type=issue_type,
            severity=severity,
            source=source,
            description=description,
            evidence=evidence or {},
            created_at=current,
        )
        self._save(data)
        self._append_retraining_example(issue)
        return PilotActionResult(True, "Live issue captured.", pilot, issue)

    def apply_owner_correction(
        self,
        text: str,
        *,
        owner_id: str | None = None,
        source: str = "live_pilot",
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        data = self._load()
        pilot = self._active_pilot(data, self.pharmacy_id)
        if pilot is None:
            return PilotActionResult(False, "No active pilot for this pharmacy.", blockers=("pilot_not_active",))

        owner_id = owner_id or str(pilot.get("owner_id") or "")
        result = CorrectionLearningEngine(self.store).apply(
            text,
            actor_id=owner_id,
            actor_role="owner",
            owner_id=owner_id,
            source=source,
            approved=True,
        )
        record = {
            "id": f"correction-{len(pilot.setdefault('corrections', [])) + 1}",
            "text": text,
            "learned": result.learned,
            "correction_type": result.correction_type,
            "alias": result.alias,
            "target": result.target,
            "owner_id": owner_id,
            "source": source,
            "ai_calls_used": result.ai_calls_used,
            "created_at": current,
        }
        pilot["corrections"].append(record)
        pilot.setdefault("audit", []).append({"type": "live_correction_recorded", "at": current, "correction_id": record["id"]})
        self._save(data)
        return PilotActionResult(result.learned, result.message or "Correction could not be learned.", pilot, record)

    def capture_owner_feedback(
        self,
        *,
        owner_id: str,
        rating: int,
        comment: str,
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        data = self._load()
        pilot = self._active_pilot(data, self.pharmacy_id)
        if pilot is None:
            return PilotActionResult(False, "No active pilot for this pharmacy.", blockers=("pilot_not_active",))
        record = {
            "id": f"feedback-{len(pilot.setdefault('feedback', [])) + 1}",
            "owner_id": owner_id,
            "rating": max(1, min(int(rating), 5)),
            "comment": comment,
            "created_at": current,
        }
        pilot["feedback"].append(record)
        pilot.setdefault("audit", []).append({"type": "owner_feedback_captured", "at": current, "feedback_id": record["id"]})
        self._save(data)
        return PilotActionResult(True, "Owner feedback captured.", pilot, record)

    def track_workflow_friction(
        self,
        *,
        workflow_id: str,
        step: str,
        severity: str,
        detail: str,
        evidence: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        data = self._load()
        pilot = self._active_pilot(data, self.pharmacy_id)
        if pilot is None:
            return PilotActionResult(False, "No active pilot for this pharmacy.", blockers=("pilot_not_active",))
        record = {
            "id": f"friction-{len(pilot.setdefault('friction', [])) + 1}",
            "workflow_id": workflow_id,
            "step": step,
            "severity": normalize_severity(severity),
            "detail": detail,
            "evidence": evidence or {},
            "created_at": current,
        }
        pilot["friction"].append(record)
        pilot.setdefault("audit", []).append({"type": "workflow_friction_tracked", "at": current, "friction_id": record["id"]})
        self._save(data)
        return PilotActionResult(True, "Workflow friction tracked.", pilot, record)

    def prepare_rollback(
        self,
        *,
        reason: str,
        requested_by: str | None = None,
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        data = self._load()
        pilot = self._active_pilot(data, self.pharmacy_id)
        if pilot is None:
            return PilotActionResult(False, "No active pilot for this pharmacy.", blockers=("pilot_not_active",))
        snapshot = {
            "id": f"rollback-{len(pilot.setdefault('rollback_points', [])) + 1}",
            "reason": reason,
            "requested_by": requested_by,
            "created_at": current,
            "reliability_report": self.reliability.no_data_loss_report(),
            "grouped_confirmations_supported": True,
            "duplicate_prevention_supported": True,
            "offline_recovery_supported": True,
            "manual_restore_required": True,
        }
        pilot["rollback_points"].append(snapshot)
        pilot.setdefault("audit", []).append({"type": "rollback_prepared", "at": current, "rollback_id": snapshot["id"]})
        self._save(data)
        return PilotActionResult(True, "Rollback point prepared.", pilot, snapshot)

    def execute_rollback(
        self,
        *,
        rollback_id: str,
        requested_by: str | None = None,
        now: datetime | None = None,
    ) -> PilotActionResult:
        current = utc_now(now)
        data = self._load()
        pilot = self._active_pilot(data, self.pharmacy_id)
        if pilot is None:
            return PilotActionResult(False, "No active pilot for this pharmacy.", blockers=("pilot_not_active",))
        rollback = next(
            (item for item in pilot.setdefault("rollback_points", []) if item.get("id") == rollback_id),
            None,
        )
        if rollback is None:
            return PilotActionResult(False, f"Rollback point {rollback_id} was not found.", pilot)
        pilot["status"] = ROLLED_BACK
        pilot["ended_at"] = current
        pilot.setdefault("audit", []).append(
            {
                "type": "pilot_rolled_back",
                "at": current,
                "rollback_id": rollback_id,
                "requested_by": requested_by,
            }
        )
        if data.get("active_pharmacy_id") == self.pharmacy_id:
            data["active_pharmacy_id"] = None
        self._save(data)
        return PilotActionResult(True, "Pilot rolled back safely.", pilot, rollback)

    def stability_score(self) -> dict[str, Any]:
        pilot = self.current_pilot()
        if pilot is None:
            return {"score": 0, "penalties": ["pilot_not_found"]}
        score = 100
        penalties: list[str] = []
        severity_penalties = self.policy()["stability_penalties"]
        for issue in pilot.get("issues", []):
            if not isinstance(issue, dict) or issue.get("status") != "open":
                continue
            severity = normalize_severity(str(issue.get("severity") or "low"))
            penalty = int(severity_penalties.get(severity, 3))
            score -= penalty
            penalties.append(f"open_{severity}_issue:-{penalty}")
        token_violations = int(pilot.get("token_usage", {}).get("known_flow_violations") or 0)
        if token_violations:
            penalty = token_violations * int(severity_penalties.get("known_flow_token_violation", 25))
            score -= penalty
            penalties.append(f"known_flow_token_violation:-{penalty}")
        for friction in pilot.get("friction", []):
            if not isinstance(friction, dict):
                continue
            severity = normalize_severity(str(friction.get("severity") or "low"))
            if severity in {"critical", "high"}:
                score -= 5
                penalties.append(f"{severity}_workflow_friction:-5")
        reliability = self.reliability.no_data_loss_report()
        if reliability.get("dead_letter", 0):
            score -= 20
            penalties.append("dead_letter_sync:-20")
        if reliability.get("conflict", 0):
            score -= 15
            penalties.append("sync_conflict:-15")
        return {"score": max(0, score), "penalties": penalties}

    def validate_production_readiness(
        self,
        *,
        mark_ready: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = utc_now(now)
        data = self._load()
        pilot = self._pharmacy(data, self.pharmacy_id)
        blockers: list[str] = []
        score = self.stability_score()
        reliability = self.reliability.no_data_loss_report()
        token_usage = pilot.get("token_usage", empty_token_usage())
        if pilot.get("status") not in {ACTIVE, READY_FOR_PRODUCTION}:
            blockers.append("pilot_not_active")
        if not pilot.get("telemetry"):
            blockers.append("telemetry_missing")
        if not pilot.get("feedback"):
            blockers.append("owner_feedback_missing")
        if not pilot.get("rollback_points"):
            blockers.append("rollback_path_missing")
        if int(token_usage.get("known_flow_violations") or 0) > 0:
            blockers.append("known_flow_token_violation")
        if reliability.get("dead_letter", 0) or reliability.get("conflict", 0):
            blockers.append("reliability_review_required")
        open_critical = [
            issue
            for issue in pilot.get("issues", [])
            if isinstance(issue, dict) and issue.get("status") == "open" and issue.get("severity") == "critical"
        ]
        if open_critical:
            blockers.append("open_critical_issue")
        if int(score["score"]) < int(self.policy()["minimum_stability_score"]):
            blockers.append("stability_score_below_threshold")

        ready = not blockers
        validation = {
            "ready": ready,
            "blockers": blockers,
            "stability_score": score["score"],
            "stability_penalties": score["penalties"],
            "reliability_report": reliability,
            "token_usage": token_usage,
            "validated_at": current,
        }
        pilot["readiness"] = validation
        pilot.setdefault("audit", []).append({"type": "production_readiness_validated", "at": current, "ready": ready})
        if ready and mark_ready:
            pilot["status"] = READY_FOR_PRODUCTION
            pilot["ended_at"] = current
            if data.get("active_pharmacy_id") == self.pharmacy_id:
                data["active_pharmacy_id"] = None
        self._save(data)
        return validation

    def current_pilot(self) -> dict[str, Any] | None:
        data = self._load()
        pilot = self._pharmacy(data, self.pharmacy_id)
        return pilot if pilot else None

    def active_pharmacy_id(self) -> str | None:
        value = self._load().get("active_pharmacy_id")
        return str(value) if value else None

    def policy(self) -> dict[str, Any]:
        data = self.store.load_json(LIVE_PILOT_POLICY_FILE, default={})
        if not isinstance(data, dict):
            data = {}
        return {
            "one_active_pharmacy": True,
            "max_known_flow_tokens": 0,
            "minimum_stability_score": 90,
            "required_evidence_fields": [
                "input_sent",
                "actual_reply",
                "pass_fail",
                "token_observation",
            ],
            "stability_penalties": {
                "critical": 35,
                "high": 20,
                "medium": 10,
                "low": 3,
                "known_flow_token_violation": 25,
            },
            **data,
        }

    def _append_issue(
        self,
        pilot: dict[str, Any],
        *,
        issue_type: str,
        severity: str,
        source: str,
        description: str,
        evidence: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        issue = {
            "id": f"issue-{len(pilot.setdefault('issues', [])) + 1}",
            "type": issue_type,
            "severity": normalize_severity(severity),
            "source": source,
            "description": description,
            "evidence": evidence,
            "status": "open",
            "retraining_example_created": True,
            "created_at": created_at,
        }
        pilot["issues"].append(issue)
        pilot.setdefault("audit", []).append({"type": "live_issue_captured", "at": created_at, "issue_id": issue["id"]})
        return issue

    def _append_retraining_example(self, issue: dict[str, Any]) -> None:
        evidence = issue.get("evidence") if isinstance(issue.get("evidence"), dict) else {}
        row = {
            "type": "live_pilot_retraining_example",
            "phase": 11,
            "pharmacy_id": self.pharmacy_id,
            "issue_id": issue.get("id"),
            "issue_type": issue.get("type"),
            "severity": issue.get("severity"),
            "source": issue.get("source"),
            "description": issue.get("description"),
            "input_sent": evidence.get("input_sent"),
            "actual_reply": evidence.get("actual_reply"),
            "expected_reply": evidence.get("expected_reply"),
            "token_observation": evidence.get("token_observation"),
            "created_at": issue.get("created_at"),
            "needs_review": True,
        }
        self.store.append_jsonl(LIVE_RETRAINING_EXAMPLES_FILE, row)

    def _active_pilot(self, data: dict[str, Any], pharmacy_id: str) -> dict[str, Any] | None:
        pilot = self._pharmacy(data, pharmacy_id)
        return pilot if pilot.get("status") == ACTIVE else None

    def _pharmacy(self, data: dict[str, Any], pharmacy_id: str) -> dict[str, Any]:
        pharmacy = data.setdefault("pharmacies", {}).setdefault(pharmacy_id or self.pharmacy_id, {})
        pharmacy.setdefault("pharmacy_id", pharmacy_id or self.pharmacy_id)
        pharmacy.setdefault("telemetry", [])
        pharmacy.setdefault("issues", [])
        pharmacy.setdefault("feedback", [])
        pharmacy.setdefault("friction", [])
        pharmacy.setdefault("corrections", [])
        pharmacy.setdefault("rollback_points", [])
        pharmacy.setdefault("audit", [])
        pharmacy.setdefault("token_usage", empty_token_usage())
        return pharmacy

    def _load(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return {"version": 1, "active_pharmacy_id": None, "pharmacies": {}}
        text = self.ledger_path.read_text(encoding="utf-8").strip()
        if not text:
            return {"version": 1, "active_pharmacy_id": None, "pharmacies": {}}
        data = json.loads(text)
        if not isinstance(data, dict):
            return {"version": 1, "active_pharmacy_id": None, "pharmacies": {}}
        data.setdefault("version", 1)
        data.setdefault("active_pharmacy_id", None)
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


def locked_phase11_protections() -> dict[str, bool]:
    return {
        "phase2_10_regression_required": True,
        "zero_token_known_medicine_flows": True,
        "audit_reversal_reliability_protections": True,
        "offline_recovery_guarantees": True,
        "duplicate_prevention_guarantees": True,
        "grouped_confirmation_protections": True,
        "pilot_pharmacy_isolation": True,
        "safe_rollback_paths": True,
        "live_errors_generate_retraining_examples": True,
        "pilot_evidence_logged": True,
    }


def empty_token_usage() -> dict[str, Any]:
    return {
        "total_tokens": 0,
        "known_flow_tokens": 0,
        "known_flow_violations": 0,
        "events": [],
    }


def reliability_summary(result: QueueResult | None) -> dict[str, Any]:
    if result is None:
        return {
            "tracked": False,
            "accepted": None,
            "duplicate": False,
            "conflict": False,
            "idempotency_key": None,
        }
    return {
        "tracked": True,
        "accepted": result.accepted,
        "duplicate": result.duplicate,
        "conflict": result.conflict,
        "idempotency_key": result.record.get("idempotency_key"),
        "message": result.message,
    }


def normalize_severity(value: str) -> str:
    clean = str(value or "low").strip().lower()
    return clean if clean in {"critical", "high", "medium", "low"} else "low"


def utc_now(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()
