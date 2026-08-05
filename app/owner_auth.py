from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import json
import os
from pathlib import Path
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

from fastapi import Cookie, HTTPException, status

from app.actor_context import ActorContext
from app.pharmacy_registry import registry_phone_key


OWNER_SESSION_COOKIE = "ms20_owner_session"
OWNER_CAPABILITIES = (
    "pharmacy:read",
    "catalog:manage",
    "transactions:manage",
    "reports:read",
    "staff:invite",
    "sessions:revoke",
)


@dataclass
class LoginChallenge:
    phone_key: str
    pharmacy_id: str
    owner_name: str
    code_digest: str
    expires_at: float
    attempts_left: int = 5


@dataclass
class OwnerSession:
    session_digest: str
    actor_id: str
    pharmacy_id: str
    role: str
    display_name: str
    expires_at: float
    revoked: bool = False


@dataclass
class ActivationInvitation:
    token_digest: str
    owner_id: str
    phone_key: str
    pharmacy_id: str
    pharmacy_name: str
    owner_name: str
    expires_at: float
    used_at: float = 0.0


@dataclass
class OwnerCredential:
    owner_id: str
    phone_key: str
    pharmacy_id: str
    pharmacy_name: str
    owner_name: str
    pin_hash: str
    failed_attempts: int = 0
    locked_until: float = 0.0


class OwnerAuthService:
    def __init__(self, *, challenge_ttl_seconds: int = 600, activation_ttl_seconds: int = 900, session_ttl_seconds: int = 900, state_path: str | Path | None = None):
        self.challenge_ttl_seconds = challenge_ttl_seconds
        self.activation_ttl_seconds = activation_ttl_seconds
        self.session_ttl_seconds = session_ttl_seconds
        self._challenges: dict[str, LoginChallenge] = {}
        self._sessions: dict[str, OwnerSession] = {}
        self._activations: dict[str, ActivationInvitation] = {}
        self._credentials: dict[str, OwnerCredential] = {}
        self._state_path = Path(state_path) if state_path else None
        self._state_loader: Callable[[], dict[str, Any]] | None = None
        self._state_saver: Callable[[dict[str, Any]], None] | None = None
        self._persistence_available = True
        self._lock = RLock()
        self._load_state()

    def configure_persistence(
        self,
        *,
        loader: Callable[[], dict[str, Any]],
        saver: Callable[[dict[str, Any]], None],
    ) -> None:
        """Switch to a shared durable store and refresh state from it."""
        with self._lock:
            data = loader()
            activations, credentials = self._decode_state(data)
            self._state_loader = loader
            self._state_saver = saver
            self._activations = activations
            self._credentials = credentials
            self._persistence_available = True

    def mark_persistence_unavailable(self) -> None:
        with self._lock:
            self._persistence_available = False

    def _require_persistence(self) -> None:
        if not self._persistence_available:
            raise HTTPException(status_code=503, detail="Owner access is temporarily unavailable.")

    def create_activation(self, owner: dict[str, str], *, now: float | None = None) -> tuple[str, ActivationInvitation]:
        self._require_persistence()
        current = time.time() if now is None else now
        pharmacy_id = str(owner.get("pharmacy_id") or "").strip()
        phone_key = registry_phone_key(owner.get("phone_number") or owner.get("phone"))
        if not pharmacy_id or not phone_key:
            raise HTTPException(status_code=400, detail="An active pharmacy owner is required.")
        raw_token = secrets.token_urlsafe(32)
        owner_id = str(owner.get("owner_id") or f"owner_{phone_key}")
        invitation = ActivationInvitation(
            token_digest=self._digest(raw_token), owner_id=owner_id, phone_key=phone_key,
            pharmacy_id=pharmacy_id, pharmacy_name=str(owner.get("pharmacy_name") or pharmacy_id),
            owner_name=str(owner.get("owner_name") or "Owner"), expires_at=current + self.activation_ttl_seconds,
        )
        with self._lock:
            self._refresh_persistent_state()
            if any(item.pharmacy_id == pharmacy_id for item in self._credentials.values()):
                raise HTTPException(status_code=409, detail="Owner access is already initialized.")
            self._activations[invitation.token_digest] = invitation
            self._save_state()
        return raw_token, invitation

    def pharmacy_has_owner(self, pharmacy_id: str) -> bool:
        self._require_persistence()
        wanted = str(pharmacy_id or "").strip()
        if not wanted:
            raise HTTPException(status_code=503, detail="Owner initialization is not configured.")
        with self._lock:
            self._refresh_persistent_state()
            return any(item.pharmacy_id == wanted for item in self._credentials.values())

    def pharmacy_owner_state(self, owner: dict[str, str]) -> str:
        """Return the canonical bootstrap state for one registry-bound pharmacy.

        An existing credential is valid only when both its pharmacy and normalized
        registered phone still match the active registry record. Conflicting or
        duplicate durable rows are never treated as either safe bootstrap or safe
        sign-in state.
        """
        self._require_persistence()
        pharmacy_id = str(owner.get("pharmacy_id") or "").strip()
        phone_key = registry_phone_key(owner.get("phone_number") or owner.get("phone"))
        if not pharmacy_id or not phone_key:
            raise HTTPException(status_code=503, detail="Owner initialization is not configured.")
        with self._lock:
            self._refresh_persistent_state()
            pharmacy_credentials = [
                item for item in self._credentials.values() if item.pharmacy_id == pharmacy_id
            ]
            if not pharmacy_credentials:
                return "uninitialized"
            if len(pharmacy_credentials) == 1 and pharmacy_credentials[0].phone_key == phone_key:
                return "initialized"
            raise HTTPException(
                status_code=503,
                detail="Owner access state does not match the active pharmacy registry.",
            )

    def initialize_first_owner(self, owner: dict[str, str], pin: str, *, now: float | None = None) -> tuple[str, OwnerSession]:
        """Create the sole bootstrap credential, only while this pharmacy is uninitialized."""
        self._require_persistence()
        current = time.time() if now is None else now
        self._validate_pin(pin)
        pharmacy_id = str(owner.get("pharmacy_id") or "").strip()
        phone_key = registry_phone_key(owner.get("phone_number") or owner.get("phone"))
        if not pharmacy_id or not phone_key:
            raise HTTPException(status_code=503, detail="Owner initialization is not configured.")
        with self._lock:
            self._refresh_persistent_state()
            if any(item.pharmacy_id == pharmacy_id for item in self._credentials.values()):
                raise HTTPException(status_code=409, detail="Owner access is already initialized.")
            credential = OwnerCredential(
                owner_id=str(owner.get("owner_id") or f"owner_{phone_key}"),
                phone_key=phone_key,
                pharmacy_id=pharmacy_id,
                pharmacy_name=str(owner.get("pharmacy_name") or pharmacy_id),
                owner_name=str(owner.get("owner_name") or "Owner"),
                pin_hash=self._hash_pin(pin),
            )
            previous = dict(self._credentials)
            self._credentials[phone_key] = credential
            try:
                self._save_state()
            except Exception:
                self._credentials = previous
                raise HTTPException(status_code=503, detail="Owner access is temporarily unavailable.")
            return self._issue_session(credential, now=current)

    def inspect_activation(self, raw_token: str, *, now: float | None = None) -> dict[str, str]:
        self._require_persistence()
        invitation = self._valid_activation(raw_token, now=now)
        return {"pharmacy_id": invitation.pharmacy_id, "pharmacy_name": invitation.pharmacy_name, "owner_name": invitation.owner_name, "role": "owner"}

    def activate(self, raw_token: str, pin: str, *, now: float | None = None) -> tuple[str, OwnerSession]:
        self._require_persistence()
        current = time.time() if now is None else now
        self._validate_pin(pin)
        with self._lock:
            invitation = self._valid_activation(raw_token, now=current)
            self._refresh_persistent_state()
            invitation = self._valid_activation(raw_token, now=current)
            if any(item.pharmacy_id == invitation.pharmacy_id for item in self._credentials.values()):
                raise HTTPException(status_code=409, detail="Owner access is already initialized.")
            credential = OwnerCredential(
                owner_id=invitation.owner_id, phone_key=invitation.phone_key,
                pharmacy_id=invitation.pharmacy_id, pharmacy_name=invitation.pharmacy_name,
                owner_name=invitation.owner_name, pin_hash=self._hash_pin(pin),
            )
            self._credentials[credential.phone_key] = credential
            invitation.used_at = current
            self._save_state()
            return self._issue_session(credential, now=current)

    def sign_in_with_pin(self, phone: str, pin: str, *, now: float | None = None) -> tuple[str, OwnerSession]:
        self._require_persistence()
        current = time.time() if now is None else now
        phone_key = registry_phone_key(phone)
        with self._lock:
            credential = self._credentials.get(phone_key)
            if not credential or credential.locked_until > current:
                raise self._unauthorized("The phone number or PIN is incorrect.")
            if not self._verify_pin(pin, credential.pin_hash):
                credential.failed_attempts += 1
                if credential.failed_attempts >= 5:
                    credential.locked_until = current + 900
                    credential.failed_attempts = 0
                self._save_state()
                raise self._unauthorized("The phone number or PIN is incorrect.")
            credential.failed_attempts = 0
            credential.locked_until = 0.0
            self._save_state()
            return self._issue_session(credential, now=current)

    def _valid_activation(self, raw_token: str, *, now: float | None = None) -> ActivationInvitation:
        current = time.time() if now is None else now
        invitation = self._activations.get(self._digest(raw_token))
        if not invitation or invitation.used_at or invitation.expires_at <= current:
            raise self._unauthorized("This activation invitation is invalid or expired.")
        return invitation

    def _issue_session(self, credential: OwnerCredential, *, now: float) -> tuple[str, OwnerSession]:
        token = secrets.token_urlsafe(32)
        session = OwnerSession(self._digest(token), credential.owner_id, credential.pharmacy_id, "owner", credential.owner_name, now + self.session_ttl_seconds)
        self._sessions[session.session_digest] = session
        return token, session

    @staticmethod
    def _validate_pin(pin: str) -> None:
        if len(pin) < 8 or not any(c.isdigit() for c in pin) or not any(c.isalpha() for c in pin):
            raise HTTPException(status_code=400, detail="Choose a PIN with at least 8 characters, including letters and numbers.")

    @staticmethod
    def _hash_pin(pin: str) -> str:
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 600_000)
        return f"pbkdf2_sha256$600000${salt.hex()}${derived.hex()}"

    @staticmethod
    def _verify_pin(pin: str, stored: str) -> bool:
        try:
            _, rounds, salt_hex, digest_hex = stored.split("$", 3)
            actual = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
            return hmac.compare_digest(actual, digest_hex)
        except (TypeError, ValueError):
            return False

    def _load_state(self) -> None:
        try:
            if self._state_path and self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
            else:
                return
            self._activations, self._credentials = self._decode_state(data)
        except Exception:
            self._activations, self._credentials = {}, {}

    @staticmethod
    def _decode_state(data: dict[str, Any]) -> tuple[dict[str, ActivationInvitation], dict[str, OwnerCredential]]:
        activations = {k: ActivationInvitation(**v) for k, v in data.get("activations", {}).items()}
        credentials = {k: OwnerCredential(**v) for k, v in data.get("credentials", {}).items()}
        return activations, credentials

    def _save_state(self) -> None:
        payload = {
            "activations": {k: vars(v) for k, v in self._activations.items()},
            "credentials": {k: vars(v) for k, v in self._credentials.items()},
        }
        if self._state_saver:
            self._state_saver(payload)
            return
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(self._state_path)

    def _refresh_persistent_state(self) -> None:
        if not self._state_loader:
            return
        activations, credentials = self._decode_state(self._state_loader())
        self._activations = activations
        self._credentials = credentials

    def start_login(
        self,
        phone: str,
        *,
        find_owner: Callable[[str], dict[str, str] | None],
        deliver_code: Callable[[str, str], None],
        now: float | None = None,
    ) -> dict[str, object]:
        current = time.time() if now is None else now
        phone_key = registry_phone_key(phone)
        record = find_owner(phone) if phone_key else None
        if record and str(record.get("pharmacy_id") or ""):
            code = f"{secrets.randbelow(1_000_000):06d}"
            challenge_id = secrets.token_urlsafe(24)
            challenge = LoginChallenge(
                phone_key=phone_key,
                pharmacy_id=str(record["pharmacy_id"]),
                owner_name=str(record.get("owner_name") or "Owner"),
                code_digest=self._digest(code),
                expires_at=current + self.challenge_ttl_seconds,
            )
            with self._lock:
                self._challenges[challenge_id] = challenge
            deliver_code(phone, code)
            return {"accepted": True, "challenge_id": challenge_id, "expires_in": self.challenge_ttl_seconds}
        # Keep the response shape generic so registry membership cannot be enumerated.
        return {"accepted": True, "challenge_id": secrets.token_urlsafe(24), "expires_in": self.challenge_ttl_seconds}

    def verify_login(self, challenge_id: str, code: str, *, now: float | None = None) -> tuple[str, OwnerSession]:
        current = time.time() if now is None else now
        with self._lock:
            challenge = self._challenges.get(str(challenge_id or ""))
            if not challenge or challenge.expires_at <= current or challenge.attempts_left <= 0:
                raise self._unauthorized("The sign-in code is invalid or expired.")
            if not hmac.compare_digest(challenge.code_digest, self._digest(code)):
                challenge.attempts_left -= 1
                raise self._unauthorized("The sign-in code is invalid or expired.")
            self._challenges.pop(challenge_id, None)
            token = secrets.token_urlsafe(32)
            session = OwnerSession(
                session_digest=self._digest(token),
                actor_id=f"owner_{challenge.phone_key}",
                pharmacy_id=challenge.pharmacy_id,
                role="owner",
                display_name=challenge.owner_name,
                expires_at=current + self.session_ttl_seconds,
            )
            self._sessions[session.session_digest] = session
            return token, session

    def authenticate(
        self,
        token: str | None,
        *,
        pharmacy_id: str | None = None,
        allowed_roles: set[str] | None = None,
        now: float | None = None,
    ) -> ActorContext:
        current = time.time() if now is None else now
        digest = self._digest(token) if token else ""
        with self._lock:
            session = self._sessions.get(digest)
            if not session or session.revoked or session.expires_at <= current:
                raise self._unauthorized("Owner sign-in required.")
            if pharmacy_id and session.pharmacy_id != pharmacy_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This session cannot access that pharmacy.")
            if allowed_roles is not None and session.role not in allowed_roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This role cannot perform that action.")
            return ActorContext(
                pharmacy_id=session.pharmacy_id,
                actor_id=session.actor_id,
                role=session.role,
                source="secure_cookie",
                display_name=session.display_name,
            )

    def revoke(self, token: str | None) -> None:
        digest = self._digest(token) if token else ""
        with self._lock:
            session = self._sessions.get(digest)
            if session:
                session.revoked = True

    @staticmethod
    def _digest(value: str | None) -> str:
        return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _unauthorized(detail: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Session"},
        )


owner_auth_service = OwnerAuthService(state_path=os.getenv("PHARMAREEN_OWNER_AUTH_STORE", "data/owner_auth.json"))


def require_owner_actor(ms20_owner_session: str | None = Cookie(default=None)) -> ActorContext:
    return owner_auth_service.authenticate(ms20_owner_session)
