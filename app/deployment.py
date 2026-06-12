from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.live_pilot import LivePharmacyPilotEngine
from app.reliability import ProductionReliabilityEngine
from app.training_store import DEFAULT_TRAINING_DIR, TrainingStore


DEFAULT_DEPLOYMENT_LEDGER_PATH = DEFAULT_TRAINING_DIR / "deployment_ledger.json"
DEPLOYMENT_POLICY_FILE = "deployment_policy.json"

ONBOARDING = "onboarding"
READY_FOR_ACTIVATION = "ready_for_activation"
ACTIVE = "active"
DEACTIVATED = "deactivated"
ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class DeploymentResult:
    accepted: bool
    message: str
    pharmacy: dict[str, Any] | None = None
    record: dict[str, Any] | None = None
    blockers: tuple[str, ...] = ()


class PharmacyDeploymentEngine:
    def __init__(
        self,
        *,
        ledger_path: str | Path | None = None,
        store: TrainingStore | None = None,
        reliability_engine: ProductionReliabilityEngine | None = None,
        pilot_engine: LivePharmacyPilotEngine | None = None,
        pharmacy_id: str = "default",
    ) -> None:
        self.ledger_path = Path(ledger_path or DEFAULT_DEPLOYMENT_LEDGER_PATH)
        self.store = store or TrainingStore(pharmacy_id=pharmacy_id)
        self.pharmacy_id = normalize_id(pharmacy_id or self.store.pharmacy_id or "default")
        self.reliability = reliability_engine or ProductionReliabilityEngine(
            ledger_path=self.store.training_dir / "reliability_ledger.json",
            store=self.store,
            pharmacy_id=self.pharmacy_id,
        )
        self.pilot = pilot_engine or LivePharmacyPilotEngine(
            ledger_path=self.store.training_dir / "live_pilot_ledger.json",
            store=self.store,
            reliability_engine=self.reliability,
            pharmacy_id=self.pharmacy_id,
        )

    def bootstrap_pharmacy_profile(
        self,
        *,
        pharmacy_name: str,
        owner_id: str,
        owner_phone: str | None = None,
        timezone_name: str = "Africa/Nairobi",
        country: str = "KE",
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        pharmacy.update(
            {
                "pharmacy_id": self.pharmacy_id,
                "status": ONBOARDING,
                "profile": {
                    "pharmacy_name": clean_text(pharmacy_name),
                    "owner_id": clean_text(owner_id),
                    "owner_phone": clean_text(owner_phone),
                    "timezone": clean_text(timezone_name) or "Africa/Nairobi",
                    "country": clean_text(country) or "KE",
                    "created_at": pharmacy.get("profile", {}).get("created_at") or current,
                    "updated_at": current,
                },
                "protections": locked_phase12_protections(),
            }
        )
        self._ensure_checklist(pharmacy)
        self._mark_checklist(pharmacy, "profile_bootstrapped", evidence={"pharmacy_name": pharmacy_name}, at=current)
        pharmacy.setdefault("owners", {})[owner_id] = {
            "owner_id": owner_id,
            "phone": owner_phone,
            "role": "owner",
            "created_at": current,
        }
        self._append_audit(pharmacy, "pharmacy_profile_bootstrapped", current, {"owner_id": owner_id})
        self._save(data)
        return DeploymentResult(True, f"Pharmacy profile bootstrapped for {self.pharmacy_id}.", pharmacy)

    def run_owner_setup_assistant(
        self,
        *,
        owner_id: str,
        display_name: str | None = None,
        contact_phone: str | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        owner = pharmacy.setdefault("owners", {}).setdefault(owner_id, {"owner_id": owner_id})
        owner.update(
            {
                "display_name": clean_text(display_name),
                "phone": clean_text(contact_phone) or owner.get("phone"),
                "setup_status": "complete",
                "updated_at": current,
            }
        )
        self._ensure_checklist(pharmacy)
        self._mark_checklist(pharmacy, "owner_setup", evidence={"owner_id": owner_id}, at=current)
        next_steps = self._pending_checklist_items(pharmacy)
        record = {"owner_id": owner_id, "next_steps": next_steps, "created_at": current}
        pharmacy.setdefault("owner_setup_runs", []).append(record)
        self._append_audit(pharmacy, "owner_setup_assistant_completed", current, {"owner_id": owner_id})
        self._save(data)
        return DeploymentResult(True, "Owner setup assistant completed.", pharmacy, record)

    def register_branch(
        self,
        *,
        branch_id: str,
        branch_name: str,
        location: str | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        clean_branch_id = normalize_id(branch_id)
        branch = {
            "branch_id": clean_branch_id,
            "branch_name": clean_text(branch_name),
            "location": clean_text(location),
            "status": "registered",
            "created_at": pharmacy.setdefault("branches", {}).get(clean_branch_id, {}).get("created_at") or current,
            "updated_at": current,
        }
        pharmacy["branches"][clean_branch_id] = branch
        self._ensure_checklist(pharmacy)
        self._mark_checklist(pharmacy, "branch_registered", evidence={"branch_id": clean_branch_id}, at=current)
        self._append_audit(pharmacy, "branch_registered", current, {"branch_id": clean_branch_id})
        self._save(data)
        return DeploymentResult(True, f"Branch {clean_branch_id} registered.", pharmacy, branch)

    def import_medicines(
        self,
        medicines: list[dict[str, Any]],
        *,
        source: str = "manual_import",
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        imported: list[dict[str, Any]] = []
        skipped: list[str] = []
        errors: list[str] = []
        medicine_store = pharmacy.setdefault("medicine_bootstrap", {})
        for index, item in enumerate(medicines, start=1):
            name = clean_text(item.get("name"))
            if not name:
                errors.append(f"row {index} missing name")
                continue
            key = normalize_key(name)
            if key in medicine_store:
                skipped.append(name)
                continue
            record = {
                "name": name,
                "canonical_key": key,
                "aliases": sorted({normalize_key(alias) for alias in item.get("aliases", []) if clean_text(alias)}),
                "form": clean_text(item.get("form")),
                "unit": clean_text(item.get("unit")),
                "opening_stock": safe_int(item.get("opening_stock")),
                "selling_price": safe_float(item.get("selling_price")),
                "source": source,
                "created_at": current,
            }
            medicine_store[key] = record
            imported.append(record)
        batch = {
            "id": f"medicine-import-{len(pharmacy.setdefault('medicine_imports', [])) + 1}",
            "source": source,
            "imported_count": len(imported),
            "skipped_duplicates": skipped,
            "errors": errors,
            "created_at": current,
        }
        pharmacy["medicine_imports"].append(batch)
        if imported:
            self._mark_checklist(pharmacy, "medicines_imported", evidence={"imported_count": len(imported)}, at=current)
        self._append_audit(
            pharmacy,
            "medicine_bootstrap_imported",
            current,
            {"imported_count": len(imported), "error_count": len(errors)},
        )
        self._save(data)
        return DeploymentResult(not errors, "Medicine bootstrap import recorded.", pharmacy, batch, tuple(errors))

    def enable_live_monitoring(
        self,
        *,
        channels: list[str] | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        record = {
            "enabled": True,
            "channels": channels or ["dashboard", "audit_log"],
            "last_checked_at": current,
        }
        pharmacy["monitoring"] = record
        self._mark_checklist(pharmacy, "monitoring_ready", evidence={"channels": record["channels"]}, at=current)
        self._append_audit(pharmacy, "live_monitoring_enabled", current, {"channels": record["channels"]})
        self._save(data)
        return DeploymentResult(True, "Live monitoring enabled.", pharmacy, record)

    def record_pilot_safety_validation(
        self,
        *,
        ready: bool,
        evidence: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        record = {
            "ready": bool(ready),
            "evidence": evidence or {},
            "validated_at": current,
        }
        pharmacy["pilot_validation"] = record
        if ready:
            self._mark_checklist(pharmacy, "pilot_safety_verified", evidence=record["evidence"], at=current)
        self._append_audit(pharmacy, "pilot_safety_validated", current, {"ready": ready})
        self._save(data)
        return DeploymentResult(True, "Pilot safety validation recorded.", pharmacy, record)

    def record_token_observation(
        self,
        *,
        source: str,
        known_flow: bool,
        tokens_used: int,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        token_monitoring = pharmacy.setdefault("token_monitoring", empty_token_monitoring())
        tokens = int(tokens_used)
        token_monitoring["total_tokens"] = int(token_monitoring.get("total_tokens") or 0) + tokens
        if known_flow:
            token_monitoring["known_flow_tokens"] = int(token_monitoring.get("known_flow_tokens") or 0) + tokens
        violation = known_flow and tokens > int(self.policy()["max_known_flow_tokens"])
        if violation:
            token_monitoring["known_flow_violations"] = int(token_monitoring.get("known_flow_violations") or 0) + 1
        record = {
            "source": source,
            "known_flow": bool(known_flow),
            "tokens_used": tokens,
            "violation": violation,
            "created_at": current,
        }
        token_monitoring.setdefault("events", []).append(record)
        self._append_audit(pharmacy, "deployment_token_observation_recorded", current, record)
        self._save(data)
        return DeploymentResult(True, "Token observation recorded.", pharmacy, record)

    def automate_onboarding_checklist(self, *, now: datetime | None = None) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        self._automate_checklist(pharmacy, at=current)
        self._append_audit(pharmacy, "onboarding_checklist_automated", current, {"pending": self._pending_checklist_items(pharmacy)})
        self._save(data)
        return DeploymentResult(True, "Onboarding checklist automated.", pharmacy, {"pending": self._pending_checklist_items(pharmacy)})

    def verify_reliability_protections(self, *, now: datetime | None = None) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        report = self.reliability.no_data_loss_report()
        ready = report.get("dead_letter", 0) == 0 and report.get("conflict", 0) == 0
        if ready:
            self._mark_checklist(pharmacy, "reliability_verified", evidence=report, at=current)
        self._append_audit(pharmacy, "deployment_reliability_verified", current, {"ready": ready, "report": report})
        self._save(data)
        return DeploymentResult(ready, "Reliability protections verified." if ready else "Reliability needs review.", pharmacy, report)

    def prepare_deployment_rollback(
        self,
        *,
        reason: str,
        requested_by: str | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        snapshot = {
            "id": f"deployment-rollback-{len(pharmacy.setdefault('rollback_points', [])) + 1}",
            "reason": reason,
            "requested_by": requested_by,
            "created_at": current,
            "status_before_rollback": pharmacy.get("status"),
            "profile": pharmacy.get("profile", {}),
            "branch_count": len(pharmacy.get("branches", {})),
            "medicine_count": len(pharmacy.get("medicine_bootstrap", {})),
            "checklist": pharmacy.get("checklist", {}),
            "reliability_report": self.reliability.no_data_loss_report(),
            "duplicate_prevention_supported": True,
            "grouped_confirmation_supported": True,
            "offline_recovery_supported": True,
            "pilot_safety_supported": True,
            "manual_restore_required": True,
        }
        pharmacy.setdefault("rollback_points", []).append(snapshot)
        self._mark_checklist(pharmacy, "rollback_ready", evidence={"rollback_id": snapshot["id"]}, at=current)
        self._append_audit(pharmacy, "deployment_rollback_prepared", current, {"rollback_id": snapshot["id"]})
        self._save(data)
        return DeploymentResult(True, "Deployment rollback point prepared.", pharmacy, snapshot)

    def execute_deployment_rollback(
        self,
        *,
        rollback_id: str,
        requested_by: str | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        rollback = next((item for item in pharmacy.get("rollback_points", []) if item.get("id") == rollback_id), None)
        if rollback is None:
            return DeploymentResult(False, f"Rollback point {rollback_id} was not found.", pharmacy)
        pharmacy["status"] = ROLLED_BACK
        pharmacy["activation"] = {"active": False, "rolled_back_at": current, "requested_by": requested_by}
        self._append_audit(
            pharmacy,
            "deployment_rolled_back",
            current,
            {"rollback_id": rollback_id, "requested_by": requested_by},
        )
        self._save(data)
        return DeploymentResult(True, "Deployment rolled back safely.", pharmacy, rollback)

    def record_onboarding_failure(
        self,
        *,
        checklist_item: str,
        description: str,
        severity: str = "medium",
        evidence: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        self._ensure_checklist(pharmacy)
        if checklist_item in pharmacy["checklist"]:
            pharmacy["checklist"][checklist_item]["status"] = "failed"
            pharmacy["checklist"][checklist_item]["evidence"] = evidence or {}
            pharmacy["checklist"][checklist_item]["updated_at"] = current
        ticket = self._append_support_ticket(
            pharmacy,
            issue_type="onboarding_failure",
            severity=severity,
            description=description,
            evidence={"checklist_item": checklist_item, **(evidence or {})},
            created_at=current,
        )
        rollback = {
            "id": f"deployment-rollback-{len(pharmacy.setdefault('rollback_points', [])) + 1}",
            "reason": f"Recover onboarding failure: {checklist_item}",
            "created_at": current,
            "status_before_rollback": pharmacy.get("status"),
            "support_ticket_id": ticket["id"],
            "reliability_report": self.reliability.no_data_loss_report(),
            "manual_restore_required": True,
        }
        pharmacy["rollback_points"].append(rollback)
        self._append_audit(
            pharmacy,
            "onboarding_failure_recorded",
            current,
            {"ticket_id": ticket["id"], "rollback_id": rollback["id"]},
        )
        self._save(data)
        return DeploymentResult(True, "Onboarding failure captured with recovery path.", pharmacy, {"ticket": ticket, "rollback": rollback})

    def open_support_ticket(
        self,
        *,
        issue_type: str,
        severity: str,
        description: str,
        evidence: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        ticket = self._append_support_ticket(
            pharmacy,
            issue_type=issue_type,
            severity=severity,
            description=description,
            evidence=evidence or {},
            created_at=current,
        )
        self._append_audit(pharmacy, "support_ticket_opened", current, {"ticket_id": ticket["id"]})
        self._save(data)
        return DeploymentResult(True, "Support ticket opened.", pharmacy, ticket)

    def resolve_support_ticket(
        self,
        ticket_id: str,
        *,
        resolution: str,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        for ticket in pharmacy.setdefault("support_tickets", []):
            if ticket.get("id") == ticket_id:
                ticket["status"] = "resolved"
                ticket["resolution"] = resolution
                ticket["resolved_at"] = current
                self._append_audit(pharmacy, "support_ticket_resolved", current, {"ticket_id": ticket_id})
                self._save(data)
                return DeploymentResult(True, "Support ticket resolved.", pharmacy, ticket)
        return DeploymentResult(False, f"Support ticket {ticket_id} was not found.", pharmacy)

    def optimize_onboarding_speed(self, *, now: datetime | None = None) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        pending = self._pending_checklist_items(pharmacy)
        total = len(self.policy()["required_checklist"])
        completed = total - len(pending)
        record = {
            "score": int(round((completed / total) * 100)) if total else 100,
            "next_step": pending[0] if pending else None,
            "remaining_steps": pending,
            "estimated_minutes_remaining": len(pending) * int(self.policy()["minutes_per_onboarding_step"]),
            "created_at": current,
        }
        pharmacy.setdefault("speed_optimizations", []).append(record)
        self._append_audit(pharmacy, "onboarding_speed_optimized", current, {"next_step": record["next_step"]})
        self._save(data)
        return DeploymentResult(True, "Onboarding speed plan generated.", pharmacy, record)

    def monitoring_dashboard(self) -> dict[str, Any]:
        pharmacy = self.current_pharmacy() or {}
        checklist = pharmacy.get("checklist", {})
        token_monitoring = pharmacy.get("token_monitoring", empty_token_monitoring())
        open_tickets = [
            ticket for ticket in pharmacy.get("support_tickets", []) if isinstance(ticket, dict) and ticket.get("status") == "open"
        ]
        return {
            "pharmacy_id": self.pharmacy_id,
            "status": pharmacy.get("status"),
            "activation": pharmacy.get("activation", {"active": False}),
            "checklist": checklist,
            "checklist_progress": checklist_progress(checklist),
            "reliability_report": self.reliability.no_data_loss_report(),
            "token_monitoring": token_monitoring,
            "open_support_tickets": open_tickets,
            "rollback_available": bool(pharmacy.get("rollback_points")),
            "deployment_score": self.deployment_score()["score"],
            "last_audit_event": pharmacy.get("audit", [])[-1] if pharmacy.get("audit") else None,
        }

    def deployment_score(self) -> dict[str, Any]:
        pharmacy = self.current_pharmacy() or {}
        policy = self.policy()
        score = 100
        penalties: list[str] = []
        checklist = pharmacy.get("checklist", {})
        for item in policy["required_checklist"]:
            if checklist.get(item, {}).get("status") != "passed":
                score -= int(policy["score_penalties"]["missing_checklist_item"])
                penalties.append(f"missing_{item}")
        token_violations = int(pharmacy.get("token_monitoring", {}).get("known_flow_violations") or 0)
        if token_violations:
            penalty = token_violations * int(policy["score_penalties"]["known_flow_token_violation"])
            score -= penalty
            penalties.append(f"known_flow_token_violation:-{penalty}")
        report = self.reliability.no_data_loss_report()
        if report.get("dead_letter", 0):
            score -= int(policy["score_penalties"]["reliability_issue"])
            penalties.append("dead_letter_sync")
        if report.get("conflict", 0):
            score -= int(policy["score_penalties"]["reliability_issue"])
            penalties.append("sync_conflict")
        for ticket in pharmacy.get("support_tickets", []):
            if not isinstance(ticket, dict) or ticket.get("status") != "open":
                continue
            severity = normalize_severity(ticket.get("severity"))
            if severity in {"critical", "high"}:
                penalty = int(policy["score_penalties"]["open_high_support_ticket"])
                score -= penalty
                penalties.append(f"open_{severity}_support_ticket:-{penalty}")
        return {"score": max(0, score), "penalties": penalties}

    def verify_deployment_readiness(
        self,
        *,
        mark_ready: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        self._automate_checklist(pharmacy, at=current)
        report = self.reliability.no_data_loss_report()
        if report.get("dead_letter", 0) == 0 and report.get("conflict", 0) == 0:
            self._mark_checklist(pharmacy, "reliability_verified", evidence=report, at=current)
        self._mark_checklist(pharmacy, "audit_ready", evidence={"audit_events": len(pharmacy.get("audit", []))}, at=current)
        score = self.deployment_score_from_pharmacy(pharmacy, report)
        blockers: list[str] = []
        for item in self.policy()["required_checklist"]:
            if pharmacy.get("checklist", {}).get(item, {}).get("status") != "passed":
                blockers.append(f"checklist:{item}")
        if int(pharmacy.get("token_monitoring", {}).get("known_flow_violations") or 0) > 0:
            blockers.append("known_flow_token_violation")
        if report.get("dead_letter", 0) or report.get("conflict", 0):
            blockers.append("reliability_review_required")
        if any(
            ticket.get("status") == "open" and normalize_severity(ticket.get("severity")) in {"critical", "high"}
            for ticket in pharmacy.get("support_tickets", [])
            if isinstance(ticket, dict)
        ):
            blockers.append("open_high_support_ticket")
        if int(score["score"]) < int(self.policy()["minimum_deployment_score"]):
            blockers.append("deployment_score_below_threshold")
        ready = not blockers
        validation = {
            "ready": ready,
            "blockers": blockers,
            "deployment_score": score["score"],
            "score_penalties": score["penalties"],
            "reliability_report": report,
            "validated_at": current,
        }
        pharmacy["readiness"] = validation
        self._append_audit(pharmacy, "deployment_readiness_verified", current, {"ready": ready, "blockers": blockers})
        if ready and mark_ready:
            pharmacy["status"] = READY_FOR_ACTIVATION
        self._save(data)
        return validation

    def activate_pharmacy(
        self,
        *,
        requested_by: str | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        validation = self.verify_deployment_readiness(mark_ready=True, now=now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        if not validation["ready"]:
            return DeploymentResult(False, "Deployment is not ready for activation.", pharmacy, validation, tuple(validation["blockers"]))
        record = {
            "active": True,
            "activated_at": current,
            "requested_by": requested_by,
            "deployment_score": validation["deployment_score"],
        }
        pharmacy["status"] = ACTIVE
        pharmacy["activation"] = record
        pharmacy.setdefault("activations", []).append(record)
        self._append_audit(pharmacy, "pharmacy_activated", current, {"requested_by": requested_by})
        self._save(data)
        return DeploymentResult(True, "Pharmacy activated.", pharmacy, record)

    def deactivate_pharmacy(
        self,
        *,
        reason: str,
        requested_by: str | None = None,
        now: datetime | None = None,
    ) -> DeploymentResult:
        current = utc_now(now)
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        record = {
            "active": False,
            "deactivated_at": current,
            "reason": reason,
            "requested_by": requested_by,
        }
        pharmacy["status"] = DEACTIVATED
        pharmacy["activation"] = record
        self._append_audit(pharmacy, "pharmacy_deactivated", current, {"reason": reason, "requested_by": requested_by})
        self._save(data)
        return DeploymentResult(True, "Pharmacy deactivated.", pharmacy, record)

    def deployment_score_from_pharmacy(
        self,
        pharmacy: dict[str, Any],
        reliability_report: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        policy = self.policy()
        score = 100
        penalties: list[str] = []
        checklist = pharmacy.get("checklist", {})
        for item in policy["required_checklist"]:
            if checklist.get(item, {}).get("status") != "passed":
                score -= int(policy["score_penalties"]["missing_checklist_item"])
                penalties.append(f"missing_{item}")
        token_violations = int(pharmacy.get("token_monitoring", {}).get("known_flow_violations") or 0)
        if token_violations:
            penalty = token_violations * int(policy["score_penalties"]["known_flow_token_violation"])
            score -= penalty
            penalties.append(f"known_flow_token_violation:-{penalty}")
        report = reliability_report or self.reliability.no_data_loss_report()
        if report.get("dead_letter", 0):
            penalty = int(policy["score_penalties"]["reliability_issue"])
            score -= penalty
            penalties.append(f"dead_letter_sync:-{penalty}")
        if report.get("conflict", 0):
            penalty = int(policy["score_penalties"]["reliability_issue"])
            score -= penalty
            penalties.append(f"sync_conflict:-{penalty}")
        for ticket in pharmacy.get("support_tickets", []):
            if not isinstance(ticket, dict) or ticket.get("status") != "open":
                continue
            severity = normalize_severity(ticket.get("severity"))
            if severity in {"critical", "high"}:
                penalty = int(policy["score_penalties"]["open_high_support_ticket"])
                score -= penalty
                penalties.append(f"open_{severity}_support_ticket:-{penalty}")
        return {"score": max(0, score), "penalties": penalties}

    def current_pharmacy(self) -> dict[str, Any] | None:
        data = self._load()
        pharmacy = self._pharmacy(data, self.pharmacy_id)
        return pharmacy if pharmacy else None

    def policy(self) -> dict[str, Any]:
        data = self.store.load_json(DEPLOYMENT_POLICY_FILE, default={})
        if not isinstance(data, dict):
            data = {}
        return {
            "required_checklist": [
                "profile_bootstrapped",
                "owner_setup",
                "branch_registered",
                "medicines_imported",
                "reliability_verified",
                "pilot_safety_verified",
                "rollback_ready",
                "monitoring_ready",
                "audit_ready",
            ],
            "minimum_deployment_score": 90,
            "max_known_flow_tokens": 0,
            "minutes_per_onboarding_step": 3,
            "score_penalties": {
                "missing_checklist_item": 8,
                "known_flow_token_violation": 30,
                "reliability_issue": 25,
                "open_high_support_ticket": 20,
            },
            **data,
        }

    def _automate_checklist(self, pharmacy: dict[str, Any], *, at: str) -> None:
        self._ensure_checklist(pharmacy)
        if pharmacy.get("profile"):
            self._mark_checklist(pharmacy, "profile_bootstrapped", at=at)
        if pharmacy.get("owners"):
            self._mark_checklist(pharmacy, "owner_setup", at=at)
        if pharmacy.get("branches"):
            self._mark_checklist(pharmacy, "branch_registered", at=at)
        if pharmacy.get("medicine_bootstrap"):
            self._mark_checklist(pharmacy, "medicines_imported", at=at)
        if pharmacy.get("pilot_validation", {}).get("ready") is True:
            self._mark_checklist(pharmacy, "pilot_safety_verified", at=at)
        if pharmacy.get("rollback_points"):
            self._mark_checklist(pharmacy, "rollback_ready", at=at)
        if pharmacy.get("monitoring", {}).get("enabled") is True:
            self._mark_checklist(pharmacy, "monitoring_ready", at=at)
        if pharmacy.get("audit"):
            self._mark_checklist(pharmacy, "audit_ready", at=at)

    def _pending_checklist_items(self, pharmacy: dict[str, Any]) -> list[str]:
        self._ensure_checklist(pharmacy)
        return [
            item
            for item in self.policy()["required_checklist"]
            if pharmacy.get("checklist", {}).get(item, {}).get("status") != "passed"
        ]

    def _append_support_ticket(
        self,
        pharmacy: dict[str, Any],
        *,
        issue_type: str,
        severity: str,
        description: str,
        evidence: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        ticket = {
            "id": f"support-{len(pharmacy.setdefault('support_tickets', [])) + 1}",
            "type": issue_type,
            "severity": normalize_severity(severity),
            "description": description,
            "evidence": evidence,
            "status": "open",
            "recoverable": True,
            "created_at": created_at,
        }
        pharmacy["support_tickets"].append(ticket)
        return ticket

    def _ensure_checklist(self, pharmacy: dict[str, Any]) -> None:
        checklist = pharmacy.setdefault("checklist", {})
        for item in self.policy()["required_checklist"]:
            checklist.setdefault(item, {"status": "pending", "evidence": {}, "updated_at": None})

    def _mark_checklist(
        self,
        pharmacy: dict[str, Any],
        item: str,
        *,
        evidence: dict[str, Any] | None = None,
        at: str,
    ) -> None:
        self._ensure_checklist(pharmacy)
        if item not in pharmacy["checklist"]:
            return
        pharmacy["checklist"][item] = {
            "status": "passed",
            "evidence": evidence or pharmacy["checklist"].get(item, {}).get("evidence", {}),
            "updated_at": at,
        }

    def _append_audit(self, pharmacy: dict[str, Any], action: str, at: str, details: dict[str, Any] | None = None) -> None:
        pharmacy.setdefault("audit", []).append(
            {
                "id": f"audit-{len(pharmacy.setdefault('audit', [])) + 1}",
                "action": action,
                "at": at,
                "details": details or {},
            }
        )

    def _pharmacy(self, data: dict[str, Any], pharmacy_id: str) -> dict[str, Any]:
        pharmacy = data.setdefault("pharmacies", {}).setdefault(pharmacy_id, {})
        pharmacy.setdefault("pharmacy_id", pharmacy_id)
        pharmacy.setdefault("status", "not_started")
        pharmacy.setdefault("profile", {})
        pharmacy.setdefault("owners", {})
        pharmacy.setdefault("branches", {})
        pharmacy.setdefault("medicine_bootstrap", {})
        pharmacy.setdefault("medicine_imports", [])
        pharmacy.setdefault("support_tickets", [])
        pharmacy.setdefault("rollback_points", [])
        pharmacy.setdefault("audit", [])
        pharmacy.setdefault("token_monitoring", empty_token_monitoring())
        pharmacy.setdefault("activation", {"active": False})
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


def locked_phase12_protections() -> dict[str, bool]:
    return {
        "phase2_11_regression_required": True,
        "zero_token_known_medicine_flows": True,
        "offline_reliability_protections": True,
        "rollback_recovery_protections": True,
        "pilot_safety_protections": True,
        "duplicate_prevention_guarantees": True,
        "grouped_confirmation_protections": True,
        "pharmacy_isolation_guarantees": True,
        "token_monitoring_protections": True,
        "recoverable_onboarding_failures": True,
        "fully_auditable_deployment_actions": True,
    }


def empty_token_monitoring() -> dict[str, Any]:
    return {
        "total_tokens": 0,
        "known_flow_tokens": 0,
        "known_flow_violations": 0,
        "events": [],
    }


def checklist_progress(checklist: dict[str, Any]) -> dict[str, int]:
    total = len(checklist)
    passed = sum(1 for item in checklist.values() if isinstance(item, dict) and item.get("status") == "passed")
    failed = sum(1 for item in checklist.values() if isinstance(item, dict) and item.get("status") == "failed")
    return {"total": total, "passed": passed, "failed": failed, "pending": max(0, total - passed - failed)}


def normalize_id(value: str | None) -> str:
    clean = clean_text(value).lower()
    clean = re.sub(r"[^a-z0-9]+", "_", clean).strip("_")
    return clean or "default"


def normalize_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_severity(value: Any) -> str:
    clean = str(value or "low").strip().lower()
    return clean if clean in {"critical", "high", "medium", "low"} else "low"


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def utc_now(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()
