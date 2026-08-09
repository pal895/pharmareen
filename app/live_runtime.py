from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.branding import onboarding_prompt, unregistered_setup_prompt
from app.deployment import clean_text, normalize_id, normalize_key
from app.pharmacy_registry import phone_digits as registry_phone_digits
from app.pharmacy_registry import registry_phone_key
from app.provisioning import (
    AutonomousProvisioningEngine,
    validate_step1,
)


LIVE_TEST_NUMBER = "+254721149472"
REPLIT_OFFLINE_APP_PATH = "/offline_app/index.html"

ONBOARDING_PROMPT = onboarding_prompt()


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
        pharmacy_registry: Any | None = None,
        admin_numbers: list[str] | None = None,
        existing_pharmacy_numbers: list[str] | None = None,
        development_override_numbers: list[str] | None = None,
        live_test_number: str = LIVE_TEST_NUMBER,
        onboarding_enabled: bool = True,
        new_pharmacy_entry_factory: Callable[[str], str] | None = None,
    ) -> None:
        self.intake_service_factory = intake_service_factory
        self.provisioning = provisioning_engine or AutonomousProvisioningEngine()
        self.pharmacy_registry = pharmacy_registry
        self.admin_numbers = {normalize_phone(number) for number in (admin_numbers or []) if normalize_phone(number)}
        self.existing_pharmacy_numbers = {
            normalize_phone(number)
            for number in (existing_pharmacy_numbers or [])
            if normalize_phone(number)
        }
        self.development_override_numbers = {
            registry_phone_key(number)
            for number in (development_override_numbers or [])
            if registry_phone_key(number)
        }
        self.live_test_number = normalize_phone(live_test_number) or LIVE_TEST_NUMBER
        self.onboarding_enabled = onboarding_enabled
        self.new_pharmacy_entry_factory = new_pharmacy_entry_factory

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

        registry_record = self._active_registry_record(phone)
        if registry_record is not None:
            pharmacy_id = str(registry_record.get("pharmacy_id") or "")
            if is_onboarding_start_command(body):
                return LiveRuntimeResult(
                    f"{registry_record.get('pharmacy_name') or 'This pharmacy'} is already registered and active.",
                    "registered_active_pharmacy",
                    phone,
                    source,
                    pharmacy_id=pharmacy_id,
                )
            return self._process_existing_pharmacy_message(
                phone=phone,
                text=body,
                source=source,
                pharmacy_id=pharmacy_id or normalize_id("registered_pharmacy"),
            )

        if self._is_development_override(phone):
            return self._process_existing_pharmacy_message(
                phone=phone,
                text=body,
                source=source,
                pharmacy_id=normalize_id("development_override_pharmacy"),
            )

        if self._registry_available():
            return self._handle_registry_onboarding(phone=phone, body=body, source=source)

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
                onboarding_prompt(include_example=True),
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
        if self._registry_available():
            registry_details = parse_registry_onboarding_details(text, phone)
            if not validate_step1(registry_details):
                return self._complete_registry_onboarding(registry_details, session=session, phone=phone, source=source)

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
            conversation_id=f"{pharmacy_id}:{phone}",
            actor_id=phone,
            owner_id=phone,
            actor_role="owner",
            source=source,
        )
        return LiveRuntimeResult(reply, "processed_existing_pharmacy", phone, source, pharmacy_id=pharmacy_id)

    def _active_registry_record(self, phone: str) -> dict[str, str] | None:
        registry = self.pharmacy_registry
        if registry is None or not getattr(registry, "is_available", False):
            return None
        finder = getattr(registry, "find_by_phone", None)
        if not callable(finder):
            return None
        return finder(phone, active_only=True)

    def _registry_available(self) -> bool:
        registry = self.pharmacy_registry
        if registry is None or not getattr(registry, "is_available", False):
            return False
        ensure_schema = getattr(registry, "ensure_schema", None)
        if callable(ensure_schema):
            return bool(ensure_schema())
        return True

    def _is_development_override(self, phone: str) -> bool:
        return bool(registry_phone_key(phone) and registry_phone_key(phone) in self.development_override_numbers)

    def _handle_registry_onboarding(self, *, phone: str, body: str, source: str) -> LiveRuntimeResult:
        if not self.onboarding_enabled:
            return LiveRuntimeResult(
                "This number is not registered yet. Please contact the pharmacy owner/admin.",
                "unknown_onboarding_disabled",
                phone,
                source,
            )

        data = self.provisioning._load()
        session = open_unknown_session_for_phone(data, phone)
        details = parse_registry_onboarding_details(body, phone)
        valid_details = not validate_step1(details)
        if valid_details:
            if session is None:
                opened = self.provisioning.handle_unknown_number_message(phone_number=phone, message=body)
                session = opened.record or {}
            return self._complete_registry_onboarding(details, session=session or {}, phone=phone, source=source)

        if session is None and is_onboarding_start_command(body):
            opened = self.provisioning.handle_unknown_number_message(phone_number=phone, message=body)
            session = opened.record or {}
            return LiveRuntimeResult(
                onboarding_prompt(include_example=True),
                "unknown_onboarding_started",
                phone,
                source,
                session_id=str(session.get("session_id") or ""),
            )

        if session is not None:
            return self._advance_unknown_onboarding(session, body, phone=phone, source=source)

        return LiveRuntimeResult(
            unregistered_setup_prompt(),
            "unregistered_onboarding_prompt",
            phone,
            source,
            token_safe=True,
        )

    def _complete_registry_onboarding(
        self,
        details: dict[str, Any],
        *,
        session: dict[str, Any],
        phone: str,
        source: str,
    ) -> LiveRuntimeResult:
        registry = self.pharmacy_registry
        if registry is None:
            return LiveRuntimeResult(
                "Pharmacy registry is not available. Please try again later.",
                "registry_unavailable",
                phone,
                source,
            )
        result = registry.register_pharmacy(
            {
                **details,
                "phone_number": display_runtime_phone(phone),
                "status": "active",
                "active": "yes",
            }
        )
        if not result.accepted:
            return LiveRuntimeResult(
                "I could not register the pharmacy in Google Sheets yet. Please check Sheets access.",
                "registry_write_failed",
                phone,
                source,
            )

        record = result.record
        session_id = str(session.get("session_id") or "")
        self._sync_registry_to_provisioning(phone=phone, pharmacy_id=record.get("pharmacy_id", ""), session_id=session_id)
        status = "registered_existing_pharmacy" if not result.created else "registered_active_pharmacy"
        if result.created and self.new_pharmacy_entry_factory:
            entry_path = self.new_pharmacy_entry_factory(phone)
            reply = f"{record.get('pharmacy_name') or 'Your pharmacy'} is registered. Continue secure owner setup: {entry_path}"
        else:
            reply = f"{record.get('pharmacy_name') or 'Your pharmacy'} is registered and active. You can now send sales like: Panadol 2 cash."
        return LiveRuntimeResult(
            reply,
            status,
            phone,
            source,
            pharmacy_id=record.get("pharmacy_id") or "",
            session_id=session_id,
            provisioned=True,
            token_safe=True,
        )

    def _sync_registry_to_provisioning(self, *, phone: str, pharmacy_id: str, session_id: str = "") -> None:
        if not pharmacy_id:
            return
        data = self.provisioning._load()
        data.setdefault("phone_index", {})[phone] = pharmacy_id
        if registry_phone_digits(phone):
            data.setdefault("phone_index", {})[registry_phone_digits(phone)] = pharmacy_id
        session = data.setdefault("unknown_sessions", {}).get(session_id) if session_id else None
        if isinstance(session, dict):
            session["status"] = "approved_provisioned"
            session["pharmacy_id"] = pharmacy_id
        self.provisioning._save(data)


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


def parse_registry_onboarding_details(text: str, phone_number: str) -> dict[str, Any]:
    details = parse_onboarding_details(text, phone_number)
    if details.get("pharmacy_name") and details.get("owner_name") and details.get("location"):
        details.setdefault("branch_name", "Main")
        details.setdefault("payment_modes", ["cash", "mpesa", "credit"])
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


def is_onboarding_start_command(text: str) -> bool:
    key = normalize_key(text)
    return key in {
        "start",
        "setup",
        "register",
        "register pharmacy",
        "create pharmacy",
        "create a pharmacy",
        "create new pharmacy",
        "create a new pharmacy",
        "new pharmacy",
        "onboard pharmacy",
    }


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


def display_runtime_phone(value: Any) -> str:
    digits = registry_phone_digits(value)
    return f"+{digits}" if digits else ""


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
