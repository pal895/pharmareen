from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.deployment import clean_text, normalize_id, normalize_key
from app.provisioning import (
    AutonomousProvisioningEngine,
    validate_step1,
)


LIVE_TEST_NUMBER = "+254721149472"
REPLIT_OFFLINE_APP_PATH = "/offline_app/index.html"

ONBOARDING_PROMPT = (
    "Welcome to PharMareen setup. Please send: "
    "pharmacy name, owner name, branch name, location, and payment modes."
)


@dataclass(frozen=True)
class LiveRuntimeResult:
    reply: str
    status: str
    phone_number: str
    source: str
    pharmacy_id: str | None = None
    session_id: str | None = None
    admin_required: bool = False
    provisioned: bool = False
    token_safe: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "status": self.status,
            "phone_number": self.phone_number,
            "source": self.source,
            "pharmacy_id": self.pharmacy_id,
            "session_id": self.session_id,
            "admin_required": self.admin_required,
            "provisioned": self.provisioned,
            "token_safe": self.token_safe,
        }


class LiveRuntimeRouter:
    def __init__(
        self,
        *,
        intake_service_factory: Callable[[], Any],
        provisioning_engine: AutonomousProvisioningEngine | None = None,
        admin_numbers: list[str] | None = None,
        existing_pharmacy_numbers: list[str] | None = None,
        live_test_number: str = LIVE_TEST_NUMBER,
        onboarding_enabled: bool = True,
    ) -> None:
        self.intake_service_factory = intake_service_factory
        self.provisioning = provisioning_engine or AutonomousProvisioningEngine()
        self.admin_numbers = {normalize_phone(number) for number in (admin_numbers or []) if normalize_phone(number)}
        self.existing_pharmacy_numbers = {
            normalize_phone(number)
            for number in (existing_pharmacy_numbers or [])
            if normalize_phone(number)
        }
        self.live_test_number = normalize_phone(live_test_number) or LIVE_TEST_NUMBER
        self.onboarding_enabled = onboarding_enabled

    def handle_whatsapp_message(
        self,
        *,
        phone_number: str,
        text: str,
        source: str = "baileys",
        message_id: str | None = None,
    ) -> LiveRuntimeResult:
        phone = normalize_phone(phone_number)
        body = clean_text(text)
        if not phone:
            return LiveRuntimeResult("Missing sender phone number.", "rejected_missing_phone", phone, source)
        if not body:
            return LiveRuntimeResult("Please send a short text message.", "rejected_empty_message", phone, source)

        admin_command = parse_admin_command(body)
        if admin_command and phone in self.admin_numbers:
            return self.admin_review_unknown_session(
                session_id=admin_command["session_id"],
                action=admin_command["action"],
                admin_id=phone,
                source=source,
            )

        data = self.provisioning._load()
        pharmacy_id = data.setdefault("phone_index", {}).get(phone)
        if pharmacy_id:
            return self._process_existing_pharmacy_message(
                phone=phone,
                text=body,
                source=source,
                pharmacy_id=str(pharmacy_id),
            )

        if phone in self.existing_pharmacy_numbers:
            return self._process_existing_pharmacy_message(
                phone=phone,
                text=body,
                source=source,
                pharmacy_id=normalize_id("existing_live_pharmacy"),
            )

        if not self.onboarding_enabled:
            reply = "This number is not registered yet. Please contact the pharmacy owner/admin."
            return LiveRuntimeResult(reply, "unknown_onboarding_disabled", phone, source)

        session = open_unknown_session_for_phone(data, phone)
        if session is None:
            opened = self.provisioning.handle_unknown_number_message(
                phone_number=phone,
                message=body,
            )
            session = opened.record or {}
            return LiveRuntimeResult(
                f"{ONBOARDING_PROMPT}\n\nExample: Pharmacy: Zuri Chemist; Owner: Amina; Branch: Main; Location: Nairobi; Payments: cash, mpesa, credit",
                "unknown_onboarding_started",
                phone,
                source,
                session_id=str(session.get("session_id") or ""),
                admin_required=False,
            )

        return self._advance_unknown_onboarding(session, body, phone=phone, source=source)

    def admin_review_unknown_session(
        self,
        *,
        session_id: str,
        action: str,
        admin_id: str,
        source: str = "admin",
        corrections_requested: str | None = None,
    ) -> LiveRuntimeResult:
        result = self.provisioning.admin_review_unknown_session(
            session_id,
            action=action,
            admin_id=admin_id,
            corrections_requested=corrections_requested,
        )
        phone = normalize_phone((result.record or {}).get("phone_number")) if result.record else ""
        if result.accepted and result.pharmacy_id:
            gate = self.provisioning.activation_gate(result.pharmacy_id)
            if gate.get("decision") == "ALLOW":
                reply = f"Approved and provisioned {result.pharmacy_id}. Activation gate passed."
                status = "approved_provisioned"
            else:
                reply = f"Provisioned {result.pharmacy_id}, but activation is blocked: {', '.join(gate.get('blockers', []))}"
                status = "approved_activation_blocked"
            return LiveRuntimeResult(
                reply,
                status,
                phone,
                source,
                pharmacy_id=result.pharmacy_id,
                session_id=session_id,
                provisioned=True,
            )
        return LiveRuntimeResult(
            result.message,
            "admin_review_recorded" if result.accepted else "admin_review_failed",
            phone,
            source,
            session_id=session_id,
            admin_required=not result.accepted,
        )

    def _advance_unknown_onboarding(
        self,
        session: dict[str, Any],
        text: str,
        *,
        phone: str,
        source: str,
    ) -> LiveRuntimeResult:
        status = str(session.get("status") or "")
        session_id = str(session.get("session_id") or "")
        if status == "awaiting_admin_approval":
            return LiveRuntimeResult(
                admin_approval_reply(session_id),
                "awaiting_admin_approval",
                phone,
                source,
                session_id=session_id,
                admin_required=True,
            )
        if status == "paused":
            return LiveRuntimeResult(
                "Onboarding is paused for admin review.",
                "onboarding_paused",
                phone,
                source,
                session_id=session_id,
                admin_required=True,
            )
        if status == "rejected":
            return LiveRuntimeResult(
                "Onboarding was not approved. Please contact admin.",
                "onboarding_rejected",
                phone,
                source,
                session_id=session_id,
                admin_required=True,
            )
        if status == "approved_provisioned" and session.get("pharmacy_id"):
            return self._process_existing_pharmacy_message(
                phone=phone,
                text=text,
                source=source,
                pharmacy_id=str(session["pharmacy_id"]),
            )

        details = parse_onboarding_details(text, phone)
        errors = validate_step1(details)
        if errors:
            missing = ", ".join(error.split(":", 1)[1] for error in errors if error.startswith("missing:"))
            reply = f"I still need: {missing}. {ONBOARDING_PROMPT}"
            return LiveRuntimeResult(reply, "onboarding_needs_details", phone, source, session_id=session_id)

        saved = self.provisioning.submit_unknown_onboarding_info(session_id, details)
        if not saved.accepted:
            return LiveRuntimeResult(saved.message, "onboarding_save_failed", phone, source, session_id=session_id)

        return LiveRuntimeResult(
            admin_approval_reply(session_id),
            "awaiting_admin_approval",
            phone,
            source,
            session_id=session_id,
            admin_required=True,
        )

    def _process_existing_pharmacy_message(
        self,
        *,
        phone: str,
        text: str,
        source: str,
        pharmacy_id: str,
    ) -> LiveRuntimeResult:
        intake = self.intake_service_factory()
        reply = intake.process_text(
            text,
            actor_id=phone,
            owner_id=phone,
            actor_role="owner",
            source=source,
        )
        return LiveRuntimeResult(reply, "processed_existing_pharmacy", phone, source, pharmacy_id=pharmacy_id)


def parse_onboarding_details(text: str, phone_number: str) -> dict[str, Any]:
    details: dict[str, Any] = {"phone_number": normalize_phone(phone_number)}
    for segment in re.split(r"[\n;]+", text):
        if ":" in segment:
            raw_key, value = segment.split(":", 1)
        elif "=" in segment:
            raw_key, value = segment.split("=", 1)
        else:
            continue
        key = onboarding_field_for_key(raw_key)
        if key is not None:
            details[key] = clean_text(value)
    if "payment_modes" in details:
        details["payment_modes"] = [
            clean_text(item)
            for item in re.split(r"[,/|]+", str(details["payment_modes"]))
            if clean_text(item)
        ]
    return details


def onboarding_field_for_key(value: str) -> str | None:
    key = normalize_key(value)
    aliases = {
        "pharmacy": "pharmacy_name",
        "pharmacy name": "pharmacy_name",
        "chemist": "pharmacy_name",
        "owner": "owner_name",
        "owner name": "owner_name",
        "branch": "branch_name",
        "branch name": "branch_name",
        "location": "location",
        "area": "location",
        "payments": "payment_modes",
        "payment": "payment_modes",
        "payment modes": "payment_modes",
        "pay": "payment_modes",
    }
    return aliases.get(key)


def parse_admin_command(text: str) -> dict[str, str] | None:
    match = re.search(r"\b(approve|reject|pause)\s+(?:onboarding\s+)?([a-z0-9_+\-]+)", normalize_key(text))
    if not match:
        return None
    return {"action": match.group(1), "session_id": match.group(2)}


def admin_approval_reply(session_id: str) -> str:
    return (
        "Setup details received. Admin approval is required before activation. "
        f"Approval session: {session_id}. Admin command: approve onboarding {session_id}"
    )


def open_unknown_session_for_phone(data: dict[str, Any], phone_number: str) -> dict[str, Any] | None:
    for session in data.setdefault("unknown_sessions", {}).values():
        if not isinstance(session, dict):
            continue
        if normalize_phone(session.get("phone_number")) != phone_number:
            continue
        if session.get("status") in {
            "collecting",
            "awaiting_admin_approval",
            "corrections_requested",
            "paused",
            "rejected",
            "approved_provisioned",
        }:
            return session
    return None


def normalize_phone(value: Any) -> str:
    text = clean_text(value)
    text = re.sub(r"^whatsapp:", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", "", text)
    if text.startswith("00"):
        text = "+" + text[2:]
    return text


def split_phone_numbers(value: str | None) -> list[str]:
    if not value:
        return []
    return [normalize_phone(item) for item in re.split(r"[,;\s]+", value) if normalize_phone(item)]


def build_live_readiness_report(
    *,
    root_dir: Path,
    sheets_available: bool | None,
    settings_loaded: bool,
    settings_error: str | None = None,
) -> dict[str, Any]:
    offline_candidates = [
        root_dir / "static" / "offline_app" / "index.html",
        root_dir / "offline_app" / "index.html",
        root_dir / "local" / "index.html",
    ]
    baileys_candidates = [
        root_dir / "baileys",
        root_dir / "whatsapp-bridge",
        root_dir / "bridge",
        root_dir / "baileys-bridge.js",
        root_dir / "local_whatsapp_bridge.js",
        root_dir / "whatsapp-web-bridge.js",
        root_dir / "server.js",
        root_dir / "index.js",
    ]
    git_available = (root_dir / ".git").exists()
    replit_config_available = (root_dir / ".replit").exists() or (root_dir / "replit.nix").exists()
    offline_app_available = any(path.exists() for path in offline_candidates)
    baileys_available = any(path.exists() for path in baileys_candidates)
    blocked = []
    if not git_available:
        blocked.append("no_git_remote_available_for_replit_push")
    if not replit_config_available:
        blocked.append("no_replit_config_available_locally")
    if not baileys_available:
        blocked.append("baileys_bridge_source_not_present_locally")
    if not offline_app_available:
        blocked.append("offline_app_source_not_present_locally")
    if sheets_available is not True:
        blocked.append("google_sheets_not_confirmed_locally")
    if not settings_loaded:
        blocked.append("runtime_settings_not_fully_loaded")

    return {
        "phase": "Live Replit Push + Live Test Readiness",
        "status": "BLOCKED" if blocked else "PASS",
        "backend_boot": True,
        "debug_version": True,
        "git_available": git_available,
        "replit_config_available": replit_config_available,
        "baileys_confirmed": baileys_available,
        "offline_app_loads": offline_app_available,
        "google_sheets_connected": sheets_available is True,
        "settings_loaded": settings_loaded,
        "settings_error": settings_error,
        "onboarding_ready": True,
        "provisioning_ready": True,
        "admin_approval_ready": True,
        "deployment_activation_ready": True,
        "token_safety_known_flows_use_openai": False,
        "live_test_number": LIVE_TEST_NUMBER,
        "live_test_number_ready": True,
        "offline_app_path": REPLIT_OFFLINE_APP_PATH,
        "debug_version_path": "/debug/version",
        "blocked": blocked,
    }
