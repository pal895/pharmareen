from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from threading import RLock
from typing import Callable

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


class OwnerAuthService:
    def __init__(self, *, challenge_ttl_seconds: int = 600, session_ttl_seconds: int = 900):
        self.challenge_ttl_seconds = challenge_ttl_seconds
        self.session_ttl_seconds = session_ttl_seconds
        self._challenges: dict[str, LoginChallenge] = {}
        self._sessions: dict[str, OwnerSession] = {}
        self._lock = RLock()

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


owner_auth_service = OwnerAuthService()


def require_owner_actor(ms20_owner_session: str | None = Cookie(default=None)) -> ActorContext:
    return owner_auth_service.authenticate(ms20_owner_session)
