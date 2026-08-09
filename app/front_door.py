from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
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


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
