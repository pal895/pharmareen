from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException, status

from app.actor_context import ActorContext
from app.config import Settings, get_settings


ADMIN_CAPABILITIES = (
    "pharmacy:create",
    "pharmacy:list",
    "pharmacy:read",
    "onboarding:review",
    "deployment:manage",
)


def authenticate_admin(
    settings: Settings,
    authorization: str | None,
) -> ActorContext:
    expected_token = str(settings.admin_access_token or "").strip()
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin access is not configured.",
        )

    scheme, _, supplied_token = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return ActorContext(
        pharmacy_id=settings.pharmareen_default_pharmacy_id or "platform",
        actor_id="admin_session",
        role="admin",
        source="bearer",
        display_name="MS2.0 administrator",
    )


def require_admin_actor(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> ActorContext:
    return authenticate_admin(settings, authorization)
