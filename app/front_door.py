from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class EntryState(StrEnum):
    AUTHENTICATION_REQUIRED = "authentication_required"
    STATE_CHECK_UNAVAILABLE = "state_check_unavailable"
    ESTABLISHED = "established"
    RECOVERY_OR_SETUP_REQUIRED = "recovery_or_setup_required"
    STAFF_INVITATION_REQUIRED = "staff_invitation_required"


class EntryKind(StrEnum):
    OWNER = "owner"
    NEW_PHARMACY = "new_pharmacy"
    STAFF_INVITATION = "staff_invitation"
    PHARMACY_REFERRAL = "pharmacy_referral"
    ACCOUNT_RECOVERY = "account_recovery"


FIXED_ROLES = frozenset({"owner", "manager", "staff", "pharmacist", "cashier"})
OWNER_ONLY_AUTHORITIES = frozenset({"billing", "loyalty_redemption", "staff_administration", "public_posting_control"})


@dataclass(frozen=True)
class FrontDoorDecision:
    state: EntryState
    pharmacy_id: str
    actor_id: str
    role: str
    operations_initialized: bool
    allow_onboarding: bool
    allow_recovery: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "ms20.front-door-decision.v1",
            "state": self.state,
            "pharmacy_id": self.pharmacy_id,
            "actor_id": self.actor_id,
            "role": self.role,
            "operations_initialized": self.operations_initialized,
            "allow_onboarding": self.allow_onboarding,
            "allow_recovery": self.allow_recovery,
            "reason": self.reason,
        }


def resolve_front_door(
    *,
    pharmacy_id: str,
    actor_id: str,
    role: str,
    authenticated: bool,
    durable_state_available: bool,
    operations_initialized: bool,
    entry_kind: EntryKind = EntryKind.OWNER,
    trusted_cached_established: bool = False,
    device_active: bool = True,
) -> FrontDoorDecision:
    """Return the single fail-closed entry decision used by every channel.

    Absence of operations data is deliberately not treated as proof that a
    pharmacy is new. An authenticated owner must explicitly choose recovery or
    new-pharmacy setup through the provisioning boundary; staff can only enter
    through an invitation for an existing tenant.
    """
    pharmacy_id = str(pharmacy_id or "").strip()
    actor_id = str(actor_id or "").strip()
    role = str(role or "").strip().lower()
    if not authenticated:
        return FrontDoorDecision(EntryState.AUTHENTICATION_REQUIRED, pharmacy_id, actor_id, role, False, False, False, "authenticate_first")
    if not pharmacy_id or not actor_id or role not in FIXED_ROLES:
        return FrontDoorDecision(EntryState.STATE_CHECK_UNAVAILABLE, pharmacy_id, actor_id, role, False, False, False, "invalid_tenant_actor_binding")
    if not device_active:
        return FrontDoorDecision(EntryState.AUTHENTICATION_REQUIRED, pharmacy_id, actor_id, role, False, False, False, "device_revoked")
    if not durable_state_available and trusted_cached_established:
        return FrontDoorDecision(EntryState.ESTABLISHED, pharmacy_id, actor_id, role, True, False, False, "trusted_offline_resume")
    if not durable_state_available:
        return FrontDoorDecision(EntryState.STATE_CHECK_UNAVAILABLE, pharmacy_id, actor_id, role, False, False, False, "durable_state_unavailable")
    if operations_initialized:
        return FrontDoorDecision(EntryState.ESTABLISHED, pharmacy_id, actor_id, role, True, False, False, "resume_established_pharmacy")
    if entry_kind == EntryKind.STAFF_INVITATION or role != "owner":
        return FrontDoorDecision(EntryState.STAFF_INVITATION_REQUIRED, pharmacy_id, actor_id, role, False, False, False, "staff_cannot_create_or_recover_pharmacy")
    return FrontDoorDecision(EntryState.RECOVERY_OR_SETUP_REQUIRED, pharmacy_id, actor_id, role, False, True, True, "owner_must_classify_empty_tenant")


class SignedEntryContext:
    """Short-lived, non-enumerable context shared by web, QR and link adapters."""

    def __init__(self, secret: str | bytes, *, ttl_seconds: int = 600):
        raw = secret.encode("utf-8") if isinstance(secret, str) else secret
        if len(raw) < 32:
            raise ValueError("Entry signing key must contain at least 32 bytes")
        self._secret = raw
        self._ttl = max(60, min(int(ttl_seconds), 1800))

    def issue(self, *, pharmacy_id: str, kind: EntryKind, nonce: str, now: int | None = None) -> str:
        issued = int(time.time() if now is None else now)
        payload = {"v": 1, "p": str(pharmacy_id).strip(), "k": kind, "n": str(nonce).strip(), "iat": issued, "exp": issued + self._ttl}
        if not payload["p"] or not payload["n"]:
            raise ValueError("Pharmacy and nonce are required")
        encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        signature = _b64(hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def verify(self, token: str, *, expected_kind: EntryKind | None = None, now: int | None = None) -> Mapping[str, Any]:
        try:
            encoded, supplied = str(token).split(".", 1)
            expected = _b64(hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest())
            if not hmac.compare_digest(supplied, expected):
                raise ValueError("Invalid entry context")
            payload = json.loads(_unb64(encoded))
        except Exception as exc:
            raise ValueError("Invalid entry context") from exc
        current = int(time.time() if now is None else now)
        if payload.get("v") != 1 or not payload.get("p") or not payload.get("n") or current >= int(payload.get("exp") or 0):
            raise ValueError("Expired or invalid entry context")
        if expected_kind is not None and payload.get("k") != expected_kind:
            raise ValueError("Entry context does not match this journey")
        return payload


def can_manage(authorities: set[str] | frozenset[str], role: str, capability: str) -> bool:
    role = str(role or "").strip().lower()
    if capability in OWNER_ONLY_AUTHORITIES:
        return role == "owner" or (role == "manager" and capability in authorities)
    return role in FIXED_ROLES and capability in authorities


class MemoryFrontDoorStore:
    def __init__(self, initial: dict[str, Any] | None = None):
        self._value = deepcopy(initial or {"version": 1, "community_counter": 0, "pharmacies": {}, "used_nonces": []})
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._value)

    def save(self, value: dict[str, Any]) -> None:
        with self._lock:
            self._value = deepcopy(value)


class FrontDoorRegistry:
    """Durable beginning-layer truth shared by all entry adapters.

    The injected store is responsible for production durability. This service
    owns tenant membership, invitations, devices, recovery transitions and the
    pharmacy-level identities consumed later by billing, Loyalty and Community.
    It intentionally does not implement those features' operational workflows.
    """

    def __init__(self, store: Any, signer: SignedEntryContext | None = None):
        self.store = store
        self.signer = signer
        self._lock = threading.RLock()

    def initialize_pharmacy(
        self,
        *,
        pharmacy_id: str,
        owner_id: str,
        owner_name: str,
        owner_phone_key: str,
        trusted_legacy_owner_ids: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        with self._lock:
            state = self.store.load()
            pharmacies = state.setdefault("pharmacies", {})
            existing = pharmacies.get(pharmacy_id)
            if existing:
                if existing.get("owner_id") != owner_id:
                    self._reconcile_legacy_owner(
                        existing,
                        owner_id=owner_id,
                        owner_phone_key=owner_phone_key,
                        trusted_legacy_owner_ids=trusted_legacy_owner_ids,
                    )
                    self.store.save(state)
                return deepcopy(existing)
            state["community_counter"] = int(state.get("community_counter") or 0) + 1
            community_number = state["community_counter"]
            now = int(time.time())
            pharmacy = {
                "pharmacy_id": pharmacy_id,
                "owner_id": owner_id,
                "entry_classification": "unresolved",
                "members": {owner_id: {"actor_id": owner_id, "display_name": owner_name, "role": "owner", "status": "active", "joined_at": now}},
                "invitations": {},
                "devices": {},
                "phone_key_digest": _digest(owner_phone_key),
                "community": {"community_id": f"{community_number:03d}", "pharmacy_identity": f"Impala Pharmacy {community_number:03d}", "posting_control": "owner"},
                "loyalty": {"wallet_id": _stable_id("wallet", pharmacy_id), "referral_code": _stable_id("refer", pharmacy_id)[:10].upper(), "pool_scope": "pharmacy", "balance": 0, "referred_by_pharmacy_id": None, "credited_event_keys": [], "contribution_actor_ids": []},
                "billing": {"authority_actor_ids": [owner_id], "active_seats": 1, "device_count_is_seat_count": False, "replacement_devices_add_seat": False, "subscription_status": "unqualified", "grace_status": "not_applicable"},
                "provisioning": {"status": "identity_ready", "failed_step": None, "resume_token_digest": None},
                "compliance": {"terms_version": None, "privacy_version": None, "owner_acceptance_at": None},
                "recovery": {"status": "ready", "sessions_recheck_required": False, "quick_pin_trust_recheck_required": False},
                "audit": [{"event": "front_door_initialized", "actor_id": owner_id, "at": now}],
            }
            pharmacies[pharmacy_id] = pharmacy
            self.store.save(state)
            return deepcopy(pharmacy)

    def issue_new_pharmacy_context(self, *, verified_phone_key: str, ttl_seconds: int = 900) -> str:
        """Issue a one-use setup context after a channel verifies the owner phone."""
        signer = self._require_signer()
        phone_key = str(verified_phone_key or "").strip()
        if not phone_key:
            raise ValueError("Verified owner identity is required")
        nonce = secrets.token_urlsafe(24)
        token = signer.issue(pharmacy_id="__new_pharmacy__", kind=EntryKind.NEW_PHARMACY, nonce=nonce)
        with self._lock:
            state = self.store.load()
            state.setdefault("pending_entries", {})[_digest(nonce)] = {
                "phone_key_digest": _digest(phone_key),
                "status": "active",
                "expires_at": int(time.time()) + min(max(ttl_seconds, 60), 1800),
            }
            self.store.save(state)
        return token

    def consume_new_pharmacy_context(self, token: str, *, phone_key: str) -> None:
        payload = self._require_signer().verify(token, expected_kind=EntryKind.NEW_PHARMACY)
        if payload.get("p") != "__new_pharmacy__":
            raise ValueError("New-pharmacy context is invalid")
        nonce_digest = _digest(str(payload["n"]))
        with self._lock:
            state = self.store.load()
            pending = state.setdefault("pending_entries", {}).get(nonce_digest)
            if (
                not pending
                or pending.get("status") != "active"
                or int(pending.get("expires_at") or 0) <= int(time.time())
                or pending.get("phone_key_digest") != _digest(phone_key)
                or nonce_digest in set(state.setdefault("used_nonces", []))
            ):
                raise ValueError("New-pharmacy context is unavailable")
            pending["status"] = "used"
            state["used_nonces"].append(nonce_digest)
            self.store.save(state)

    def issue_account_recovery_context(self, *, pharmacy_id: str, verified_phone_key: str, ttl_seconds: int = 600) -> str:
        signer = self._require_signer()
        if not pharmacy_id.strip() or not verified_phone_key.strip():
            raise ValueError("Verified recovery identity is required")
        nonce = secrets.token_urlsafe(24)
        token = signer.issue(pharmacy_id=pharmacy_id, kind=EntryKind.ACCOUNT_RECOVERY, nonce=nonce)
        with self._lock:
            state = self.store.load()
            if pharmacy_id not in state.get("pharmacies", {}):
                raise ValueError("Recovery pharmacy is unavailable")
            state.setdefault("pending_entries", {})[_digest(nonce)] = {"phone_key_digest": _digest(verified_phone_key), "status": "active", "kind": "account_recovery", "pharmacy_id": pharmacy_id, "expires_at": int(time.time()) + min(max(ttl_seconds, 60), 900)}
            self.store.save(state)
        return token

    def consume_account_recovery_context(self, token: str, *, phone_key: str, pharmacy_id: str) -> None:
        payload = self._require_signer().verify(token, expected_kind=EntryKind.ACCOUNT_RECOVERY)
        nonce_digest = _digest(str(payload["n"]))
        with self._lock:
            state = self.store.load()
            pending = state.setdefault("pending_entries", {}).get(nonce_digest)
            if (
                payload.get("p") != pharmacy_id
                or not pending
                or pending.get("kind") != "account_recovery"
                or pending.get("pharmacy_id") != pharmacy_id
                or pending.get("status") != "active"
                or int(pending.get("expires_at") or 0) <= int(time.time())
                or pending.get("phone_key_digest") != _digest(phone_key)
                or nonce_digest in set(state.setdefault("used_nonces", []))
            ):
                raise ValueError("Recovery context is unavailable")
            pending["status"] = "used"
            state["used_nonces"].append(nonce_digest)
            self.store.save(state)

    @staticmethod
    def _reconcile_legacy_owner(
        pharmacy: dict[str, Any],
        *,
        owner_id: str,
        owner_phone_key: str,
        trusted_legacy_owner_ids: tuple[str, ...],
    ) -> None:
        """Migrate only the exact pre-canonical phone-key owner representation."""
        previous = str(pharmacy.get("owner_id") or "")
        allowed = {str(value).strip() for value in trusted_legacy_owner_ids if str(value).strip()}
        members = pharmacy.get("members")
        previous_member = members.get(previous) if isinstance(members, dict) else None
        if (
            not previous
            or previous not in allowed
            or pharmacy.get("phone_key_digest") != _digest(owner_phone_key)
            or not isinstance(previous_member, dict)
            or previous_member.get("role") != "owner"
            or previous_member.get("status") != "active"
            or (owner_id in members and owner_id != previous)
        ):
            raise ValueError("Pharmacy owner mismatch")

        pharmacy["owner_id"] = owner_id
        member = members.pop(previous)
        member["actor_id"] = owner_id
        members[owner_id] = member
        for invitation in pharmacy.get("invitations", {}).values():
            if invitation.get("created_by") == previous:
                invitation["created_by"] = owner_id
        for device in pharmacy.get("devices", {}).values():
            if device.get("actor_id") == previous:
                device["actor_id"] = owner_id
        billing = pharmacy.get("billing", {})
        billing["authority_actor_ids"] = [owner_id if value == previous else value for value in billing.get("authority_actor_ids", [])]
        loyalty = pharmacy.get("loyalty", {})
        loyalty["contribution_actor_ids"] = [owner_id if value == previous else value for value in loyalty.get("contribution_actor_ids", [])]
        for event in pharmacy.get("audit", []):
            if event.get("actor_id") == previous:
                event["actor_id"] = owner_id
        pharmacy.setdefault("audit", []).append({"event": "owner_identity_canonicalized", "actor_id": owner_id, "details": {}, "at": int(time.time())})

    def issue_referral_context(self, pharmacy_id: str, *, owner_id: str) -> str:
        signer = self._require_signer()
        with self._lock:
            _, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            nonce = f"{pharmacy['loyalty']['referral_code']}:{secrets.token_urlsafe(16)}"
            return signer.issue(pharmacy_id=pharmacy_id, kind=EntryKind.PHARMACY_REFERRAL, nonce=nonce)

    def attribute_referral(self, token: str, *, new_pharmacy_id: str, new_owner_id: str) -> None:
        payload = self._require_signer().verify(token, expected_kind=EntryKind.PHARMACY_REFERRAL)
        with self._lock:
            state, new_pharmacy = self._owner_pharmacy(new_pharmacy_id, new_owner_id)
            referring_id = str(payload["p"])
            if referring_id == new_pharmacy_id or referring_id not in state["pharmacies"]:
                raise ValueError("Referral pharmacy is invalid")
            nonce_digest = _digest(str(payload["n"]))
            if nonce_digest in set(state.setdefault("used_nonces", [])) or new_pharmacy["loyalty"].get("referred_by_pharmacy_id"):
                raise ValueError("Referral was already attributed")
            new_pharmacy["loyalty"]["referred_by_pharmacy_id"] = referring_id
            state["used_nonces"].append(nonce_digest)
            self._audit(new_pharmacy, "referral_attributed", new_owner_id, {"referring_pharmacy_id": referring_id})
            self.store.save(state)

    def classify_empty_pharmacy(self, pharmacy_id: str, *, owner_id: str, classification: str) -> dict[str, Any]:
        if classification not in {"genuinely_new", "legacy_recovery"}:
            raise ValueError("Unsupported pharmacy classification")
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            current = pharmacy.get("entry_classification")
            if current not in {"unresolved", classification}:
                raise ValueError("Pharmacy classification is already fixed")
            pharmacy["entry_classification"] = classification
            self._audit(pharmacy, "entry_classified", owner_id, {"classification": classification})
            self.store.save(state)
            return deepcopy(pharmacy)

    def issue_invitation(self, pharmacy_id: str, *, owner_id: str, role: str, display_name: str, ttl_seconds: int = 600) -> str:
        signer = self._require_signer()
        role = role.strip().lower()
        if role not in FIXED_ROLES - {"owner"}:
            raise ValueError("Invitation role is not allowed")
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            nonce = secrets.token_urlsafe(24)
            token = signer.issue(pharmacy_id=pharmacy_id, kind=EntryKind.STAFF_INVITATION, nonce=nonce)
            pharmacy["invitations"][_digest(nonce)] = {"role": role, "display_name": display_name.strip(), "status": "active", "expires_at": int(time.time()) + min(max(ttl_seconds, 60), 1800), "created_by": owner_id}
            self._audit(pharmacy, "invitation_issued", owner_id, {"role": role})
            self.store.save(state)
            return token

    def accept_invitation(self, token: str, *, actor_id: str, verified_identity: bool, device_key: str | None = None) -> dict[str, Any]:
        if not verified_identity:
            raise ValueError("Verified staff identity is required")
        payload = self._require_signer().verify(token, expected_kind=EntryKind.STAFF_INVITATION)
        with self._lock:
            state = self.store.load()
            nonce_digest = _digest(str(payload["n"]))
            if nonce_digest in set(state.setdefault("used_nonces", [])):
                raise ValueError("Invitation was already used")
            pharmacy = state.setdefault("pharmacies", {}).get(payload["p"])
            invitation = (pharmacy or {}).setdefault("invitations", {}).get(nonce_digest)
            if not invitation or invitation.get("status") != "active" or int(invitation.get("expires_at") or 0) <= int(time.time()):
                raise ValueError("Invitation is unavailable")
            pharmacy["members"][actor_id] = {"actor_id": actor_id, "display_name": invitation["display_name"], "role": invitation["role"], "status": "active", "joined_at": int(time.time())}
            invitation["status"] = "accepted"
            state["used_nonces"].append(nonce_digest)
            pharmacy["billing"]["active_seats"] = self._active_seats(pharmacy)
            if device_key:
                self._bind_device(pharmacy, actor_id, device_key)
            self._audit(pharmacy, "invitation_accepted", actor_id, {"role": invitation["role"]})
            self.store.save(state)
            accepted = deepcopy(pharmacy["members"][actor_id])
            accepted["pharmacy_id"] = str(payload["p"])
            return accepted

    def revoke_invitation(self, pharmacy_id: str, *, owner_id: str, nonce: str) -> None:
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            invitation = pharmacy["invitations"].get(_digest(nonce))
            if not invitation or invitation.get("status") != "active":
                raise ValueError("Active invitation was not found")
            invitation["status"] = "revoked"
            self._audit(pharmacy, "invitation_revoked", owner_id, {})
            self.store.save(state)

    def bind_device(self, pharmacy_id: str, *, actor_id: str, device_key: str) -> dict[str, Any]:
        with self._lock:
            state, pharmacy = self._active_member_pharmacy(pharmacy_id, actor_id)
            device = self._bind_device(pharmacy, actor_id, device_key)
            self._audit(pharmacy, "device_bound", actor_id, {})
            self.store.save(state)
            return deepcopy(device)

    def revoke_device(self, pharmacy_id: str, *, owner_id: str, device_key: str) -> None:
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            device = pharmacy["devices"].get(_digest(device_key))
            if not device:
                raise ValueError("Device was not found")
            device["status"] = "revoked"
            device["revoked_at"] = int(time.time())
            self._audit(pharmacy, "device_revoked", owner_id, {"actor_id": device["actor_id"]})
            self.store.save(state)

    def remove_member(self, pharmacy_id: str, *, owner_id: str, actor_id: str) -> None:
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            member = pharmacy["members"].get(actor_id)
            if not member or member.get("role") == "owner":
                raise ValueError("Removable staff member was not found")
            member["status"] = "removed"
            for device in pharmacy["devices"].values():
                if device.get("actor_id") == actor_id:
                    device["status"] = "revoked"
            pharmacy["billing"]["active_seats"] = self._active_seats(pharmacy)
            self._audit(pharmacy, "member_removed", owner_id, {"actor_id": actor_id})
            self.store.save(state)

    def change_owner_phone(self, pharmacy_id: str, *, owner_id: str, new_phone_key: str, current_owner_verified: bool, new_phone_verified: bool) -> dict[str, Any]:
        if not current_owner_verified or not new_phone_verified:
            raise ValueError("Both current ownership and new phone must be verified")
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            pharmacy["phone_key_digest"] = _digest(new_phone_key)
            for device in pharmacy["devices"].values():
                device["status"] = "recheck_required"
            pharmacy["recovery"].update({"sessions_recheck_required": True, "quick_pin_trust_recheck_required": True})
            self._audit(pharmacy, "owner_phone_changed", owner_id, {})
            self.store.save(state)
            return {"revoke_sessions": True, "recheck_devices": True, "recheck_quick_pin": True}

    def complete_account_recovery(self, pharmacy_id: str, *, owner_id: str, verified_identity: bool) -> dict[str, bool]:
        if not verified_identity:
            raise ValueError("Verified production identity is required")
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            for device in pharmacy["devices"].values():
                device["status"] = "recheck_required"
            pharmacy["recovery"].update({"sessions_recheck_required": True, "quick_pin_trust_recheck_required": True, "last_completed_at": int(time.time())})
            self._audit(pharmacy, "account_recovered", owner_id, {})
            self.store.save(state)
            return {"revoke_sessions": True, "recheck_devices": True, "recheck_quick_pin": True}

    def record_provisioning_resume(self, pharmacy_id: str, *, owner_id: str, failed_step: str, resume_token: str) -> None:
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            pharmacy["provisioning"] = {"status": "resume_required", "failed_step": str(failed_step).strip(), "resume_token_digest": _digest(resume_token)}
            self._audit(pharmacy, "provisioning_resume_recorded", owner_id, {"failed_step": str(failed_step).strip()})
            self.store.save(state)

    def record_owner_acceptance(self, pharmacy_id: str, *, owner_id: str, terms_version: str, privacy_version: str) -> None:
        if not terms_version.strip() or not privacy_version.strip():
            raise ValueError("Terms and privacy versions are required")
        with self._lock:
            state, pharmacy = self._owner_pharmacy(pharmacy_id, owner_id)
            pharmacy["compliance"] = {"terms_version": terms_version.strip(), "privacy_version": privacy_version.strip(), "owner_acceptance_at": int(time.time())}
            self._audit(pharmacy, "owner_terms_accepted", owner_id, {"terms_version": terms_version.strip(), "privacy_version": privacy_version.strip()})
            self.store.save(state)

    def pharmacy_authorities(self, pharmacy_id: str, *, actor_id: str) -> dict[str, Any]:
        _, pharmacy = self._active_member_pharmacy(pharmacy_id, actor_id)
        member = pharmacy["members"][actor_id]
        return {"role": member["role"], "community": deepcopy(pharmacy["community"]), "loyalty": deepcopy(pharmacy["loyalty"]), "billing": deepcopy(pharmacy["billing"]), "may_redeem": member["role"] == "owner" or actor_id in pharmacy["billing"]["authority_actor_ids"], "may_post": member["role"] == "owner" or pharmacy["community"]["posting_control"] != "owner"}

    def _owner_pharmacy(self, pharmacy_id: str, owner_id: str):
        state, pharmacy = self._active_member_pharmacy(pharmacy_id, owner_id)
        if pharmacy.get("owner_id") != owner_id or pharmacy["members"][owner_id].get("role") != "owner":
            raise ValueError("Owner authority is required")
        return state, pharmacy

    def _require_signer(self) -> SignedEntryContext:
        if self.signer is None:
            raise RuntimeError("Signed entry adapters are not configured")
        return self.signer

    def _active_member_pharmacy(self, pharmacy_id: str, actor_id: str):
        state = self.store.load()
        pharmacy = state.setdefault("pharmacies", {}).get(pharmacy_id)
        member = (pharmacy or {}).setdefault("members", {}).get(actor_id)
        if not pharmacy or not member or member.get("status") != "active":
            raise ValueError("Active pharmacy membership is required")
        return state, pharmacy

    @staticmethod
    def _bind_device(pharmacy: dict[str, Any], actor_id: str, device_key: str) -> dict[str, Any]:
        digest = _digest(device_key)
        existing = pharmacy["devices"].get(digest)
        if existing and existing.get("actor_id") != actor_id:
            raise ValueError("Device is already bound to another actor")
        device = existing or {"device_digest": digest, "actor_id": actor_id, "created_at": int(time.time()), "quick_pin_trust": "disabled"}
        device.update({"status": "active", "last_active_at": int(time.time())})
        pharmacy["devices"][digest] = device
        return device

    @staticmethod
    def _active_seats(pharmacy: dict[str, Any]) -> int:
        return sum(1 for member in pharmacy["members"].values() if member.get("status") == "active")

    @staticmethod
    def _audit(pharmacy: dict[str, Any], event: str, actor_id: str, details: dict[str, Any]) -> None:
        pharmacy.setdefault("audit", []).append({"event": event, "actor_id": actor_id, "details": details, "at": int(time.time())})


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _digest(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _stable_id(namespace: str, pharmacy_id: str) -> str:
    return hashlib.sha256(f"ms20:{namespace}:{pharmacy_id}".encode("utf-8")).hexdigest()[:24]
