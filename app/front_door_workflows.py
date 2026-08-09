from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from copy import deepcopy
from typing import Any

from app.front_door import FIXED_ROLES, FrontDoorRegistry


def _digest(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _pin_hash(pin: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${derived.hex()}"


def _pin_matches(pin: str, stored: str) -> bool:
    try:
        _, rounds, salt, expected = stored.split("$", 3)
        actual = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


class FrontDoorWorkflowService:
    """Customer workflow layer over the durable, pharmacy-scoped front-door root."""

    def __init__(self, registry: FrontDoorRegistry, *, session_ttl_seconds: int = 900):
        self.registry = registry
        self.session_ttl_seconds = session_ttl_seconds

    def accept_staff_invitation(
        self,
        token: str,
        *,
        verified_identity: str,
        pin: str,
        device_key: str,
        now: int | None = None,
    ) -> dict[str, Any]:
        if len(pin) < 8 or not any(c.isalpha() for c in pin) or not any(c.isdigit() for c in pin):
            raise ValueError("Staff PIN must contain at least eight letters/numbers")
        identity_digest = _digest(verified_identity)
        actor_id = f"staff_{identity_digest[:24]}"
        member = self.registry.accept_invitation(token, actor_id=actor_id, verified_identity=True, device_key=device_key)
        with self.registry._lock:
            state, pharmacy = self.registry._active_member_pharmacy(member["pharmacy_id"], actor_id)
            pharmacy["members"][actor_id]["credential_hash"] = _pin_hash(pin)
            pharmacy["members"][actor_id]["identity_digest"] = identity_digest
            self.registry.store.save(state)
        raw_session = self._issue_session(pharmacy["pharmacy_id"], actor_id, device_key, now=now)
        return {"actor_id": actor_id, "role": member["role"], "session": raw_session, "pharmacy_id": pharmacy["pharmacy_id"]}

    def sign_in_staff(self, pharmacy_id: str, *, verified_identity: str, pin: str, device_key: str, now: int | None = None) -> str:
        identity_digest = _digest(verified_identity)
        actor_id = f"staff_{identity_digest[:24]}"
        with self.registry._lock:
            _, pharmacy = self.registry._active_member_pharmacy(pharmacy_id, actor_id)
            member = pharmacy["members"][actor_id]
            if member.get("identity_digest") != identity_digest or not _pin_matches(pin, member.get("credential_hash", "")):
                raise ValueError("Staff access is unavailable")
        return self._issue_session(pharmacy_id, actor_id, device_key, now=now)

    def authenticate_staff(self, raw_session: str, *, pharmacy_id: str, device_key: str, now: int | None = None) -> dict[str, Any]:
        current = int(time.time()) if now is None else now
        with self.registry._lock:
            state = self.registry.store.load()
            pharmacy = state.get("pharmacies", {}).get(pharmacy_id)
            session = (pharmacy or {}).get("sessions", {}).get(_digest(raw_session))
            device = (pharmacy or {}).get("devices", {}).get(_digest(device_key))
            if not session or session.get("revoked_at") or int(session.get("expires_at") or 0) <= current:
                raise ValueError("Staff session is unavailable")
            if not device or device.get("status") != "active" or device.get("actor_id") != session.get("actor_id"):
                raise ValueError("Staff device is unavailable")
            member = pharmacy.get("members", {}).get(session["actor_id"])
            if not member or member.get("status") != "active" or member.get("role") != session.get("role"):
                raise ValueError("Staff membership is unavailable")
            session["last_active_at"] = current
            device["last_active_at"] = current
            self.registry.store.save(state)
            return {"pharmacy_id": pharmacy_id, "actor_id": session["actor_id"], "role": session["role"], "display_name": member.get("display_name", "Staff")}

    def authenticate_staff_any(self, raw_session: str, *, device_key: str, now: int | None = None) -> dict[str, Any]:
        digest = _digest(raw_session)
        state = self.registry.store.load()
        matches = [pharmacy_id for pharmacy_id, pharmacy in state.get("pharmacies", {}).items() if digest in pharmacy.get("sessions", {})]
        if len(matches) != 1:
            raise ValueError("Staff session is unavailable")
        return self.authenticate_staff(raw_session, pharmacy_id=matches[0], device_key=device_key, now=now)

    def revoke_session(self, pharmacy_id: str, *, owner_id: str, session_digest: str) -> None:
        with self.registry._lock:
            state, pharmacy = self.registry._owner_pharmacy(pharmacy_id, owner_id)
            session = pharmacy.setdefault("sessions", {}).get(session_digest)
            if not session:
                raise ValueError("Session was not found")
            session["revoked_at"] = int(time.time())
            self.registry._audit(pharmacy, "session_revoked", owner_id, {"actor_id": session["actor_id"]})
            self.registry.store.save(state)

    def configure_quick_pin(self, pharmacy_id: str, *, actor_id: str, device_key: str, primary_verified: bool, quick_pin: str) -> None:
        if not primary_verified or len(quick_pin) != 4 or not quick_pin.isdigit():
            raise ValueError("Verified Primary PIN and a four-digit Quick PIN are required")
        with self.registry._lock:
            state, pharmacy = self.registry._active_member_pharmacy(pharmacy_id, actor_id)
            device = pharmacy.get("devices", {}).get(_digest(device_key))
            if not device or device.get("actor_id") != actor_id or device.get("status") != "active":
                raise ValueError("Active device is required")
            device.update({"quick_pin_hash": _pin_hash(quick_pin), "quick_pin_trust": "active", "quick_pin_failures": 0})
            self.registry.store.save(state)

    def credit_loyalty(self, pharmacy_id: str, *, actor_id: str, event_key: str, coins: int, reason: str) -> dict[str, Any]:
        if not event_key.strip() or not reason.strip() or coins <= 0 or coins > 100:
            raise ValueError("Bounded loyalty evidence is required")
        with self.registry._lock:
            state, pharmacy = self.registry._active_member_pharmacy(pharmacy_id, actor_id)
            loyalty = pharmacy["loyalty"]
            event_digest = _digest(event_key)
            if event_digest in loyalty.setdefault("credited_event_keys", []):
                return {"credited": False, "balance": int(loyalty.get("balance") or 0)}
            today = time.strftime("%Y-%m-%d", time.gmtime())
            awarded_today = sum(int(row["coins"]) for row in loyalty.setdefault("earning_history", []) if row["date"] == today)
            award = min(coins, max(0, 200 - awarded_today))
            if not award:
                return {"credited": False, "balance": int(loyalty.get("balance") or 0)}
            loyalty["credited_event_keys"].append(event_digest)
            loyalty["contribution_actor_ids"] = sorted(set(loyalty.get("contribution_actor_ids", [])) | {actor_id})
            loyalty["balance"] = int(loyalty.get("balance") or 0) + award
            loyalty["earning_history"].append({"event_digest": event_digest, "actor_id": actor_id, "coins": award, "reason": reason.strip(), "date": today})
            self.registry.store.save(state)
            return {"credited": True, "coins": award, "balance": loyalty["balance"]}

    def billing_summary(self, pharmacy_id: str, *, actor_id: str) -> dict[str, Any]:
        authorities = self.registry.pharmacy_authorities(pharmacy_id, actor_id=actor_id)
        billing = deepcopy(authorities["billing"])
        return {
            "active_seats": int(billing.get("active_seats") or 0),
            "device_count_is_seat_count": False,
            "replacement_devices_add_seat": False,
            "subscription_status": billing.get("subscription_status", "unqualified"),
            "grace_status": billing.get("grace_status", "not_applicable"),
            "package": billing.get("package"),
            "renewal_total": billing.get("renewal_total"),
            "commercially_qualified": bool(billing.get("commercially_qualified")),
            "may_redeem": authorities["may_redeem"],
        }

    def configure_billing(
        self,
        pharmacy_id: str,
        *,
        owner_id: str,
        package: str,
        included_seats: int,
        additional_seat_cost: int,
        renewal_total: int,
        coin_value: int,
        grace_days: int,
        provider_qualified: bool,
    ) -> dict[str, Any]:
        if not package.strip() or min(included_seats, additional_seat_cost, renewal_total, coin_value, grace_days) < 0:
            raise ValueError("Explicit non-negative billing terms are required")
        with self.registry._lock:
            state, pharmacy = self.registry._owner_pharmacy(pharmacy_id, owner_id)
            billing = pharmacy["billing"]
            billing.update({"package": package.strip(), "included_seats": included_seats, "additional_seat_cost": additional_seat_cost, "renewal_total": renewal_total, "coin_value": coin_value, "grace_days": grace_days, "commercially_qualified": bool(provider_qualified), "subscription_status": "active" if provider_qualified else "qualification_required", "grace_status": "not_applicable"})
            self.registry._audit(pharmacy, "billing_terms_configured", owner_id, {"provider_qualified": bool(provider_qualified)})
            self.registry.store.save(state)
        return self.billing_summary(pharmacy_id, actor_id=owner_id)

    def redeem_loyalty_for_renewal(self, pharmacy_id: str, *, actor_id: str, coins: int, idempotency_key: str) -> dict[str, Any]:
        if coins <= 0 or not idempotency_key.strip():
            raise ValueError("A positive bounded redemption is required")
        with self.registry._lock:
            state, pharmacy = self.registry._active_member_pharmacy(pharmacy_id, actor_id)
            authorities = self.registry.pharmacy_authorities(pharmacy_id, actor_id=actor_id)
            billing, loyalty = pharmacy["billing"], pharmacy["loyalty"]
            if not authorities["may_redeem"] or not billing.get("commercially_qualified"):
                raise ValueError("Qualified billing authority is required")
            digest = _digest(idempotency_key)
            existing = next((row for row in loyalty.setdefault("redemption_history", []) if row["idempotency_digest"] == digest), None)
            if existing:
                return {**deepcopy(existing), "duplicate": True}
            balance = int(loyalty.get("balance") or 0)
            renewal_total = int(billing.get("renewal_total") or 0)
            coin_value = int(billing.get("coin_value") or 0)
            used = min(coins, balance, renewal_total // coin_value if coin_value else 0)
            if used <= 0:
                raise ValueError("No redeemable renewal value is available")
            discount = used * coin_value
            row = {"idempotency_digest": digest, "actor_id": actor_id, "coins_used": used, "discount": discount, "remaining_payable": renewal_total - discount, "created_at": int(time.time())}
            loyalty["balance"] = balance - used
            loyalty["redemption_history"].append(row)
            self.registry.store.save(state)
            return {**deepcopy(row), "duplicate": False}

    def community_post(self, pharmacy_id: str, *, actor_id: str, text: str, kind: str = "post") -> dict[str, Any]:
        clean = " ".join(text.split())
        if kind not in {"post", "question"} or not clean or len(clean) > 1000:
            raise ValueError("A bounded pharmacy-community post is required")
        with self.registry._lock:
            state, pharmacy = self.registry._active_member_pharmacy(pharmacy_id, actor_id)
            member = pharmacy["members"][actor_id]
            if member.get("role") != "owner" and pharmacy["community"].get("posting_control") == "owner":
                raise ValueError("Owner posting approval is required")
            post = {"post_id": secrets.token_hex(12), "kind": kind, "text": clean, "actor_id": actor_id, "status": "visible", "appreciations": [], "comments": [], "reports": [], "created_at": int(time.time())}
            pharmacy["community"].setdefault("posts", []).append(post)
            self.registry.store.save(state)
            return deepcopy(post)

    def moderate_post(self, pharmacy_id: str, *, owner_id: str, post_id: str, action: str) -> None:
        if action not in {"restrict", "remove", "restore"}:
            raise ValueError("Unsupported moderation action")
        with self.registry._lock:
            state, pharmacy = self.registry._owner_pharmacy(pharmacy_id, owner_id)
            post = next((row for row in pharmacy["community"].get("posts", []) if row.get("post_id") == post_id), None)
            if not post:
                raise ValueError("Post was not found")
            post["status"] = {"restrict": "restricted", "remove": "removed", "restore": "visible"}[action]
            self.registry._audit(pharmacy, f"community_post_{action}", owner_id, {"post_id": post_id})
            self.registry.store.save(state)

    def community_interact(self, pharmacy_id: str, *, actor_id: str, post_id: str, action: str, text: str = "") -> dict[str, Any]:
        if action not in {"comment", "appreciate", "report"}:
            raise ValueError("Unsupported community interaction")
        clean = " ".join(text.split())
        if action in {"comment", "report"} and (not clean or len(clean) > 500):
            raise ValueError("A bounded explanation is required")
        with self.registry._lock:
            state, pharmacy = self.registry._active_member_pharmacy(pharmacy_id, actor_id)
            post = next((row for row in pharmacy["community"].get("posts", []) if row.get("post_id") == post_id and row.get("status") == "visible"), None)
            if not post:
                raise ValueError("Visible post was not found")
            if action == "appreciate":
                post["appreciations"] = sorted(set(post.get("appreciations", [])) | {actor_id})
            else:
                target = "comments" if action == "comment" else "reports"
                digest = _digest(f"{actor_id}:{clean}")
                if not any(row.get("digest") == digest for row in post.setdefault(target, [])):
                    post[target].append({"actor_id": actor_id, "text": clean, "digest": digest, "created_at": int(time.time())})
            self.registry.store.save(state)
            return deepcopy(post)

    def _issue_session(self, pharmacy_id: str, actor_id: str, device_key: str, *, now: int | None = None) -> str:
        current = int(time.time()) if now is None else now
        raw = secrets.token_urlsafe(32)
        with self.registry._lock:
            state, pharmacy = self.registry._active_member_pharmacy(pharmacy_id, actor_id)
            member = pharmacy["members"][actor_id]
            self.registry._bind_device(pharmacy, actor_id, device_key)
            pharmacy.setdefault("sessions", {})[_digest(raw)] = {"actor_id": actor_id, "role": member["role"], "device_digest": _digest(device_key), "created_at": current, "last_active_at": current, "expires_at": current + self.session_ttl_seconds, "revoked_at": None}
            self.registry.store.save(state)
        return raw
