import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import re

from app import main
from app import owner_auth as owner_auth_module
from app.config import Settings
from app.main import OWNER_SIGN_IN_HTML
from app.owner_auth import OWNER_CAPABILITIES, OwnerAuthService


OWNER = {
    "pharmacy_id": "pharmacy-a",
    "owner_name": "Mary",
    "phone_number": "+254700000001",
}


def begin(service: OwnerAuthService, delivered: list[tuple[str, str]], now: float = 100.0):
    return service.start_login(
        OWNER["phone_number"],
        find_owner=lambda phone: OWNER if phone.endswith("001") else None,
        deliver_code=lambda phone, code: delivered.append((phone, code)),
        now=now,
    )


def assert_http_error(status_code: int, call):
    with pytest.raises(HTTPException) as exc:
        call()
    assert exc.value.status_code == status_code


def test_unauthenticated_request_is_blocked():
    service = OwnerAuthService()
    assert_http_error(401, lambda: service.authenticate(None))


def test_authenticated_owner_is_bound_to_pharmacy_and_fixed_role():
    service = OwnerAuthService()
    delivered: list[tuple[str, str]] = []
    started = begin(service, delivered)
    token, session = service.verify_login(started["challenge_id"], delivered[0][1], now=101.0)
    actor = service.authenticate(token, pharmacy_id="pharmacy-a", allowed_roles={"owner"}, now=102.0)

    assert session.role == "owner"
    assert actor.pharmacy_id == "pharmacy-a"
    assert actor.role == "owner"
    assert "staff:invite" in OWNER_CAPABILITIES


def test_wrong_pharmacy_and_wrong_role_are_blocked():
    service = OwnerAuthService()
    delivered: list[tuple[str, str]] = []
    started = begin(service, delivered)
    token, _ = service.verify_login(started["challenge_id"], delivered[0][1], now=101.0)

    assert_http_error(403, lambda: service.authenticate(token, pharmacy_id="pharmacy-b", now=102.0))
    assert_http_error(403, lambda: service.authenticate(token, allowed_roles={"staff"}, now=102.0))


def test_expired_and_revoked_sessions_are_blocked():
    expiring = OwnerAuthService(session_ttl_seconds=10)
    delivered: list[tuple[str, str]] = []
    started = begin(expiring, delivered)
    token, _ = expiring.verify_login(started["challenge_id"], delivered[0][1], now=101.0)
    assert_http_error(401, lambda: expiring.authenticate(token, now=112.0))

    revocable = OwnerAuthService()
    delivered.clear()
    started = begin(revocable, delivered)
    token, _ = revocable.verify_login(started["challenge_id"], delivered[0][1], now=101.0)
    revocable.revoke(token)
    assert_http_error(401, lambda: revocable.authenticate(token, now=102.0))


def test_unknown_phone_is_not_enumerated_and_no_secret_uses_client_storage_or_ui():
    service = OwnerAuthService()
    delivered: list[tuple[str, str]] = []
    response = service.start_login(
        "+254700009999",
        find_owner=lambda _phone: None,
        deliver_code=lambda phone, code: delivered.append((phone, code)),
        now=100.0,
    )

    assert response["accepted"] is True
    assert delivered == []
    assert "localStorage" not in OWNER_SIGN_IN_HTML
    assert "sessionStorage" not in OWNER_SIGN_IN_HTML
    assert "PHARMAREEN_ADMIN_ACCESS_TOKEN" not in OWNER_SIGN_IN_HTML
    assert "ms20_owner_session" not in OWNER_SIGN_IN_HTML


def test_sensitive_login_code_is_hidden_from_public_outbox_and_debug(monkeypatch):
    main.offline_whatsapp_outbox.clear()
    main.offline_whatsapp_confirmation_history.clear()
    monkeypatch.setattr(main, "load_offline_confirmation_state", lambda: None)
    monkeypatch.setattr(main, "save_offline_confirmation_state", lambda: None)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(_env_file=None, MS20_BRIDGE_INTERNAL_TOKEN="bridge-only"),
    )
    main.queue_offline_whatsapp_confirmation(
        "+254700000001",
        "Your MS2.0 sign-in code is 123456.",
        sensitive=True,
    )

    public = main.offline_whatsapp_confirmations(limit=10, x_ms20_bridge_token=None)
    internal = main.offline_whatsapp_confirmations(limit=10, x_ms20_bridge_token="bridge-only")
    debug = main.debug_offline_confirmations()

    assert public["confirmations"] == []
    assert internal["confirmations"][0]["message"].endswith("123456.")
    assert debug["pending"][0]["message_preview"] == "[sensitive message hidden]"
    main.offline_whatsapp_outbox.clear()


def test_owner_facing_flow_sets_secure_http_only_cookie_and_allows_session(monkeypatch):
    delivered: list[str] = []

    class Registry:
        def find_by_phone(self, phone, active_only=True):
            return OWNER if str(phone).endswith("001") and active_only else None

    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    monkeypatch.setattr(
        main,
        "queue_offline_whatsapp_confirmation",
        lambda _phone, message, **_kwargs: delivered.append(message) or {"status": "queued"},
    )
    service = OwnerAuthService()
    monkeypatch.setattr(main, "owner_auth_service", service)
    monkeypatch.setattr(owner_auth_module, "owner_auth_service", service)

    with TestClient(main.app, base_url="https://ms20.test") as client:
        blocked = client.get("/api/ms20/auth/session")
        started = client.post("/api/ms20/auth/owner/start", json={"phone": OWNER["phone_number"]})
        code = re.search(r"\b(\d{6})\b", delivered[0]).group(1)
        verified = client.post(
            "/api/ms20/auth/owner/verify",
            json={"challenge_id": started.json()["challenge_id"], "code": code},
        )
        allowed = client.get("/api/ms20/auth/session")

    cookie = verified.headers["set-cookie"].lower()
    assert blocked.status_code == 401
    assert verified.status_code == 200
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie
    assert allowed.status_code == 200
    assert allowed.json()["role"] == "owner"
    assert allowed.json()["pharmacy_id"] == "pharmacy-a"
