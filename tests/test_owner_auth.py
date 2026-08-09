import hashlib
import hmac
import json
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import re
from pathlib import Path

from app import main
from app import owner_auth as owner_auth_module
from app.config import Settings
from app.actor_context import ActorContext
from app.main import (
    OWNER_ACTIVATION_CLIENT_ACTIONS,
    OWNER_ACTIVATION_HTML,
    OWNER_FIRST_SETUP_HTML,
    OWNER_SIGN_IN_CLIENT_ACTIONS,
    OWNER_SIGN_IN_HTML,
)
from app.owner_auth import OWNER_CAPABILITIES, OWNER_SESSION_COOKIE, OwnerAuthService
from app.services.owner_auth_persistence import GoogleSheetsOwnerAuthStateStore, owner_auth_sheet_id


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


def test_authenticated_session_survives_process_handoff_and_shared_revocation():
    durable = {}

    def load():
        return json.loads(json.dumps(durable))

    def save(payload):
        durable.clear()
        durable.update(json.loads(json.dumps(payload)))

    first = OwnerAuthService()
    first.configure_persistence(loader=load, saver=save)
    first.initialize_first_owner(OWNER, "Owner1234", now=100.0)
    token, session = first.sign_in_with_pin(OWNER["phone_number"], "Owner1234", now=101.0)

    replacement = OwnerAuthService()
    replacement.configure_persistence(loader=load, saver=save)
    actor = replacement.authenticate(token, pharmacy_id=session.pharmacy_id, now=102.0)
    assert actor.actor_id == session.actor_id

    replacement.revoke(token)
    assert_http_error(401, lambda: first.authenticate(token, now=103.0))


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


def test_owner_activation_and_repeat_sign_in_remain_within_three_client_actions():
    assert OWNER_ACTIVATION_CLIENT_ACTIONS == (
        "Open MS2.0 for the uninitialized pharmacy.",
        "Confirm the pharmacy and create the private PIN.",
        "Enter the Main App.",
    )
    assert OWNER_SIGN_IN_CLIENT_ACTIONS == (
        "Open MS2.0.",
        "Confirm the provisioned owner identity and enter the private PIN.",
        "Enter the Main App.",
    )
    assert len(OWNER_ACTIVATION_CLIENT_ACTIONS) <= 3
    assert len(OWNER_SIGN_IN_CLIENT_ACTIONS) <= 3
    assert 'location.replace("/main-app/")' in OWNER_ACTIVATION_HTML
    assert 'window.location.assign("/main-app/")' in OWNER_SIGN_IN_HTML
    assert 'location.replace("/main-app/")' in OWNER_FIRST_SETUP_HTML
    for customer_html in (OWNER_ACTIVATION_HTML, OWNER_FIRST_SETUP_HTML, OWNER_SIGN_IN_HTML):
        assert "ADMIN_ACCESS_TOKEN" not in customer_html
        assert "Authorization" not in customer_html


def test_first_owner_pin_guidance_and_visibility_are_safe_and_inline():
    assert "Use at least 8 characters with letters and numbers" in OWNER_FIRST_SETUP_HTML
    assert "Choose something you can remember" in OWNER_FIRST_SETUP_HTML
    assert OWNER_FIRST_SETUP_HTML.count('type="button" data-pin-toggle=') == 2
    assert 'input.type=show?"text":"password"' in OWNER_FIRST_SETUP_HTML
    assert "localStorage" not in OWNER_FIRST_SETUP_HTML
    assert "sessionStorage" not in OWNER_FIRST_SETUP_HTML
    assert "location.search" not in OWNER_FIRST_SETUP_HTML
    assert 'body:JSON.stringify({pin})' in OWNER_FIRST_SETUP_HTML
    assert "The PINs do not match. Enter the same PIN twice." in OWNER_FIRST_SETUP_HTML


def test_post_authentication_operations_setup_is_not_mislabeled_as_owner_setup():
    app_source = Path("ms20-main-app/src/app.js").read_text(encoding="utf-8")
    assert 'return "Operations setup needed"' in app_source
    assert "Owner access is ready. Add business details and medicines to begin." in app_source


def test_authenticated_operations_bootstrap_resumes_durable_existing_pharmacy(monkeypatch):
    class Store:
        is_available = True

        def list_pharmacy_catalog_records(self, pharmacy_id):
            assert pharmacy_id == "pharmacy-a"
            return [{"name": "Ibuprofen", "stockLeft": 13, "sellingPrice": 18}]

    main.app.dependency_overrides[main.require_owner_actor] = lambda: ActorContext(
        pharmacy_id="pharmacy-a", actor_id="owner-a", role="owner"
    )
    monkeypatch.setattr(main, "first_owner_registry_record", lambda _request: {
        **OWNER, "pharmacy_name": "Zuri Chemist", "branch": "Main", "location": "Nairobi"
    })
    monkeypatch.setattr(main, "get_sheet_store", lambda: Store())
    try:
        with TestClient(main.app, base_url="https://ms20.test") as client:
            response = client.get("/api/ms20/operations/bootstrap")
    finally:
        main.app.dependency_overrides.pop(main.require_owner_actor, None)
    assert response.status_code == 200
    assert response.json()["operations_initialized"] is True
    assert response.json()["pharmacy"]["name"] == "Zuri Chemist"
    assert response.json()["catalog"] == [{"name": "Ibuprofen", "stockLeft": 13, "sellingPrice": 18}]


def test_operations_resume_is_tenant_scoped_and_does_not_reopen_setup_from_blank_browser_memory():
    app_source = Path("ms20-main-app/src/app.js").read_text(encoding="utf-8")
    assert 'fetch("/api/ms20/operations/bootstrap"' in app_source
    assert "payload.operations_initialized" in app_source
    assert 'removeCardsByType(["OnboardingCard", "CatalogOnboardingCard", "OperationsStateUnavailableCard"])' in app_source
    assert "setupStorageKey()" in app_source and "catalogStorageKey()" in app_source
    assert 'state.operationsBootstrap = { status: "unavailable"' in app_source


def test_authenticated_legacy_workspace_migrates_once_to_durable_operations_state(monkeypatch):
    saved = []

    class Store:
        is_available = True

        def get_ms20_operations_state(self, pharmacy_id):
            assert pharmacy_id == "pharmacy-a"
            return None

        def save_ms20_operations_state(self, pharmacy_id, profile, catalog):
            saved.append((pharmacy_id, profile, catalog))
            return {"initialized": True, "catalog": catalog}

    main.app.dependency_overrides[main.require_owner_actor] = lambda: ActorContext(
        pharmacy_id="pharmacy-a", actor_id="owner-a", role="owner"
    )
    monkeypatch.setattr(main, "first_owner_registry_record", lambda _request: {
        **OWNER, "pharmacy_name": "Zuri Chemist", "owner_name": "Pal", "location": "Nairobi"
    })
    monkeypatch.setattr(main, "get_sheet_store", lambda: Store())
    try:
        with TestClient(main.app, base_url="https://ms20.test") as client:
            response = client.post("/api/ms20/operations/migrate-legacy", json={
                "catalog": [{"name": "Ibuprofen", "stockLeft": 13}]
            })
    finally:
        main.app.dependency_overrides.pop(main.require_owner_actor, None)
    assert response.status_code == 200
    assert response.json()["operations_initialized"] is True
    assert response.json()["catalog"][0]["name"] == "Ibuprofen"
    assert saved[0][0] == "pharmacy-a"
    assert saved[0][1]["name"] == "Zuri Chemist"


def test_legacy_workspace_migration_requires_completed_catalog_and_is_frontend_gated():
    app_source = Path("ms20-main-app/src/app.js").read_text(encoding="utf-8")
    assert "payload.legacy_migration_allowed && legacySetupComplete() && legacyCatalog.length > 0" in app_source
    assert 'fetch("/api/ms20/operations/migrate-legacy"' in app_source
    assert "safeLocalStorage()?.removeItem(SETUP_KEY)" in app_source
    assert "safeLocalStorage()?.removeItem(CATALOG_KEY)" in app_source


def test_legacy_inventory_csv_preserves_blanks_and_rejects_duplicates():
    headers = ",".join(main.LEGACY_INVENTORY_HEADERS)
    rows = main.legacy_inventory_catalog((headers + "\nIbuprofen,200 mg,tablet,tablet,18,,13,,,,,\n").encode())
    assert rows == [{"name":"Ibuprofen","strength":"200 mg","forms":["tablet"],"units":["tablet"],"sellingPrice":18.0,"costPrice":None,"stockLeft":13.0,"supplier":"","barcode":"","batches":[],"shelf":""}]
    with pytest.raises(ValueError, match="unique"):
        main.legacy_inventory_catalog((headers + "\nIbuprofen,,tablet,tablet,,,,,,,,\nIbuprofen,,tablet,tablet,,,,,,,,\n").encode())


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


def test_activation_is_bound_hashed_single_use_and_persistent():
    path = Path("tests/.owner-auth-state-test.json")
    path.unlink(missing_ok=True)
    service = OwnerAuthService(state_path=path, activation_ttl_seconds=10)
    raw, invitation = service.create_activation({**OWNER, "pharmacy_name": "Afya Pharmacy"}, now=100)

    assert raw not in path.read_text(encoding="utf-8")
    assert invitation.pharmacy_id == OWNER["pharmacy_id"]
    assert service.inspect_activation(raw, now=101)["owner_name"] == "Mary"
    token, session = service.activate(raw, "Owner1234", now=102)
    assert session.pharmacy_id == "pharmacy-a"
    assert service.authenticate(token, now=103).role == "owner"
    assert_http_error(401, lambda: service.inspect_activation(raw, now=104))
    stored = path.read_text(encoding="utf-8")
    assert raw not in stored
    assert "Owner1234" not in stored
    assert "pbkdf2_sha256$600000$" in stored
    path.unlink(missing_ok=True)


def test_activation_rejects_changed_unknown_expired_and_weak_pin():
    service = OwnerAuthService(activation_ttl_seconds=10)
    raw, _ = service.create_activation(OWNER, now=100)
    assert_http_error(401, lambda: service.inspect_activation(raw + "changed", now=101))
    assert_http_error(401, lambda: service.inspect_activation("unknown", now=101))
    assert_http_error(401, lambda: service.inspect_activation(raw, now=111))
    raw, _ = service.create_activation(OWNER, now=200)
    assert_http_error(400, lambda: service.activate(raw, "1234", now=201))


def test_first_owner_bootstrap_is_pharmacy_bound_single_use_and_persistent():
    path = Path("tests/.owner-bootstrap-state-test.json")
    path.unlink(missing_ok=True)
    service = OwnerAuthService(state_path=path)
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy"}

    legacy_invitation, _ = service.create_activation(owner, now=99)
    assert service.pharmacy_has_owner("pharmacy-a") is False
    token, session = service.initialize_first_owner(owner, "Owner1234", now=100)

    assert session.pharmacy_id == "pharmacy-a"
    assert service.authenticate(token, pharmacy_id="pharmacy-a", now=101).role == "owner"
    assert service.pharmacy_has_owner("pharmacy-a") is True
    assert "Owner1234" not in path.read_text(encoding="utf-8")
    assert_http_error(409, lambda: service.initialize_first_owner(owner, "Another1234", now=102))
    assert_http_error(409, lambda: service.activate(legacy_invitation, "Another1234", now=102))
    assert_http_error(409, lambda: service.create_activation(owner, now=102))

    reloaded = OwnerAuthService(state_path=path)
    assert reloaded.pharmacy_has_owner("pharmacy-a") is True
    assert_http_error(409, lambda: reloaded.initialize_first_owner(owner, "Another1234", now=103))
    path.unlink(missing_ok=True)


def test_owner_state_requires_exact_single_registry_binding():
    service = OwnerAuthService()
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy"}
    assert service.pharmacy_owner_state(owner) == "uninitialized"
    service.initialize_first_owner(owner, "Owner1234", now=100)
    assert service.pharmacy_owner_state(owner) == "initialized"
    changed_phone = {**owner, "phone_number": "+254722222222", "phone": "+254722222222"}
    assert_http_error(503, lambda: service.pharmacy_owner_state(changed_phone))


def test_first_owner_bootstrap_page_switches_permanently_to_sign_in(monkeypatch):
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy", "active": "yes", "status": "active"}

    class Registry:
        def find_by_id(self, pharmacy_id, active_only=True):
            return owner if pharmacy_id == "pharmacy-a" and active_only else None

    path = Path("tests/.owner-bootstrap-route-state-test.json")
    path.unlink(missing_ok=True)
    service = OwnerAuthService(state_path=path)
    monkeypatch.setenv("PHARMAREEN_DEFAULT_PHARMACY_ID", "pharmacy-a")
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    monkeypatch.setattr(main, "owner_auth_service", service)
    monkeypatch.setattr(owner_auth_module, "owner_auth_service", service)

    with TestClient(main.app, base_url="https://ms20.test") as client:
        first_page = client.get("/main-app/sign-in")
        status_before = client.get("/api/ms20/auth/owner/bootstrap")
        activated = client.post("/api/ms20/auth/owner/bootstrap", json={"pin": "Owner1234", "phone": "+254711111111", "pharmacy_id": "pharmacy-b"})
        status_after = client.get("/api/ms20/auth/owner/bootstrap")
        second_attempt = client.post("/api/ms20/auth/owner/bootstrap", json={"pin": "Another1234"})
        repeat_page = client.get("/main-app/sign-in")

    assert "Activate first owner" in first_page.text
    assert status_before.json()["requires_initialization"] is True
    assert activated.status_code == 200
    assert activated.json()["pharmacy_id"] == "pharmacy-a"
    assert status_after.json() == {"requires_initialization": False}
    assert second_attempt.status_code == 409
    assert "Owner sign in" in repeat_page.text
    assert "Registered phone ending 0001" in repeat_page.text
    assert 'id="phone"' not in repeat_page.text
    assert OWNER["phone_number"] not in first_page.text
    assert "pharmacy-b" not in activated.text
    path.unlink(missing_ok=True)


def test_single_active_registry_pharmacy_is_bound_without_per_tenant_environment(monkeypatch):
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy", "active": "yes", "status": "active"}

    class Registry:
        def list_records(self):
            return [owner]

    monkeypatch.delenv("PHARMAREEN_DEFAULT_PHARMACY_ID", raising=False)
    monkeypatch.setattr(main, "owner_auth_service", OwnerAuthService())
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    with TestClient(main.app, base_url="https://pharmareen--test.replit.app") as client:
        response = client.get("/api/ms20/auth/owner/bootstrap")

    assert response.status_code == 200
    assert response.json()["requires_initialization"] is True


def test_ambiguous_registry_without_trusted_route_fails_closed(monkeypatch):
    class Registry:
        def list_records(self):
            return [
                {**OWNER, "active": "yes", "status": "active"},
                {**OWNER, "pharmacy_id": "pharmacy-b", "phone": "+254722222222", "phone_number": "+254722222222", "active": "yes", "status": "active"},
            ]

    monkeypatch.delenv("PHARMAREEN_DEFAULT_PHARMACY_ID", raising=False)
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    with TestClient(main.app, base_url="https://ms20.test", raise_server_exceptions=False) as client:
        response = client.get("/api/ms20/auth/owner/bootstrap")

    assert response.status_code == 503


def test_production_gateway_binding_is_request_scoped_and_signed(monkeypatch):
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy", "active": "yes", "status": "active"}

    class Registry:
        def find_by_id(self, pharmacy_id, active_only=True):
            return owner if pharmacy_id == "pharmacy-a" and active_only else None

    now = 1_800_000_000
    key = "platform-routing-key-for-test"
    signature = hmac.new(key.encode(), f"pharmacy-a:{now}".encode(), hashlib.sha256).hexdigest()
    monkeypatch.delenv("PHARMAREEN_DEFAULT_PHARMACY_ID", raising=False)
    monkeypatch.setattr(main, "owner_auth_service", OwnerAuthService())
    monkeypatch.setenv("PHARMAREEN_TENANT_ROUTING_KEY", key)
    monkeypatch.setattr(main.time, "time", lambda: now)
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    headers = {
        "x-pharmareen-pharmacy-id": "pharmacy-a",
        "x-pharmareen-routing-timestamp": str(now),
        "x-pharmareen-routing-signature": signature,
    }
    with TestClient(main.app, base_url="https://app.pharmareen.example", raise_server_exceptions=False) as client:
        allowed = client.get("/api/ms20/auth/owner/bootstrap", headers=headers)
        rejected = client.get("/api/ms20/auth/owner/bootstrap", headers={**headers, "x-pharmareen-pharmacy-id": "pharmacy-b"})

    assert allowed.status_code == 200
    assert rejected.status_code == 503


def test_main_app_entry_routes_from_canonical_owner_state(monkeypatch):
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy", "active": "yes", "status": "active"}

    class Registry:
        def find_by_id(self, pharmacy_id, active_only=True):
            return owner if pharmacy_id == "pharmacy-a" and active_only else None

    path = Path("tests/.owner-entry-route-state-test.json")
    path.unlink(missing_ok=True)
    service = OwnerAuthService(state_path=path)
    monkeypatch.setenv("PHARMAREEN_DEFAULT_PHARMACY_ID", "pharmacy-a")
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    monkeypatch.setattr(main, "owner_auth_service", service)

    with TestClient(main.app, base_url="https://ms20.test", follow_redirects=False) as client:
        first_entry = client.get("/main-app/")
        first_page = client.get(first_entry.headers["location"])
        token, _ = service.initialize_first_owner(owner, "Owner1234")
        returning_entry = client.get("/main-app/")
        returning_page = client.get(returning_entry.headers["location"])
        client.cookies.set(OWNER_SESSION_COOKIE, token)
        authenticated_entry = client.get("/main-app/")

    assert first_entry.status_code == 307 and first_entry.headers["location"] == "/main-app/sign-in"
    assert "Activate first owner" in first_page.text
    assert returning_entry.status_code == 307 and returning_entry.headers["location"] == "/main-app/sign-in"
    assert "Owner sign in" in returning_page.text
    assert authenticated_entry.status_code == 200
    assert "MS2.0" in authenticated_entry.text
    path.unlink(missing_ok=True)


def test_main_app_entry_fails_closed_for_mismatched_owner_state(monkeypatch):
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy", "active": "yes", "status": "active"}
    changed = {**owner, "phone": "+254722222222", "phone_number": "+254722222222"}

    class Registry:
        def find_by_id(self, pharmacy_id, active_only=True):
            return changed if pharmacy_id == "pharmacy-a" and active_only else None

    service = OwnerAuthService()
    service.initialize_first_owner(owner, "Owner1234")
    monkeypatch.setenv("PHARMAREEN_DEFAULT_PHARMACY_ID", "pharmacy-a")
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    monkeypatch.setattr(main, "owner_auth_service", service)
    with TestClient(main.app, base_url="https://ms20.test", raise_server_exceptions=False) as client:
        response = client.get("/main-app/")

    assert response.status_code == 503


def test_home_conversation_guidance_wraps_instead_of_truncating():
    styles = (Path("ms20-main-app/src/styles.css")).read_text(encoding="utf-8")
    rule = styles.split(".conversation-copy span {", 1)[1].split("}", 1)[0]
    assert "white-space: normal" in rule
    assert "text-overflow: clip" in rule
    assert "text-overflow: ellipsis" not in rule


def test_pin_sign_in_and_lockout_are_fail_closed():
    service = OwnerAuthService()
    raw, _ = service.create_activation(OWNER, now=100)
    service.activate(raw, "Owner1234", now=101)
    assert_http_error(401, lambda: service.sign_in_with_pin(OWNER["phone_number"], "Wrong1234", now=102))
    for second in range(103, 107):
        assert_http_error(401, lambda second=second: service.sign_in_with_pin(OWNER["phone_number"], "Wrong1234", now=second))
    assert_http_error(401, lambda: service.sign_in_with_pin(OWNER["phone_number"], "Owner1234", now=107))
    token, session = service.sign_in_with_pin(OWNER["phone_number"], "Owner1234", now=1008)
    assert service.authenticate(token, pharmacy_id=session.pharmacy_id, now=1009).role == "owner"


def test_activation_and_pin_routes_set_secure_cookie_without_client_secrets(monkeypatch):
    service = OwnerAuthService()
    raw, _ = service.create_activation({**OWNER, "pharmacy_name": "Afya Pharmacy"}, now=100)
    monkeypatch.setattr(main, "owner_auth_service", service)
    monkeypatch.setattr(owner_auth_module, "owner_auth_service", service)
    monkeypatch.setattr(owner_auth_module.time, "time", lambda: 101)
    monkeypatch.setattr(main, "first_owner_registry_record", lambda _request: OWNER)
    with TestClient(main.app, base_url="https://ms20.test") as client:
        inspected = client.post("/api/ms20/auth/owner/activation/inspect", json={"token": raw})
        activated = client.post("/api/ms20/auth/owner/activation/complete", json={"token": raw, "pin": "Owner1234"})
        client.post("/api/ms20/auth/logout")
        signed_in = client.post("/api/ms20/auth/owner/pin", json={"phone": "+254799999999", "pin": "Owner1234"})
        session = client.get("/api/ms20/auth/session")
    assert inspected.json() == {"pharmacy_id": "pharmacy-a", "pharmacy_name": "Afya Pharmacy", "owner_name": "Mary", "role": "owner"}
    for response in (activated, signed_in):
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
        assert raw not in response.text and "Owner1234" not in response.text
    assert session.json()["authenticated"] is True
    assert "localStorage" not in OWNER_ACTIVATION_HTML and "sessionStorage" not in OWNER_ACTIVATION_HTML
    assert "ms20_owner_session" not in OWNER_ACTIVATION_HTML


def test_repeat_sign_in_uses_trusted_tenant_owner_phone_and_pin_only():
    assert 'id="phone"' not in OWNER_SIGN_IN_HTML
    assert "Your phone number is already registered. Enter your private Owner PIN." in OWNER_SIGN_IN_HTML
    assert "{{OWNER_IDENTITY}}" in OWNER_SIGN_IN_HTML
    assert 'JSON.stringify({pin})' in OWNER_SIGN_IN_HTML
    assert 'JSON.stringify({phone,pin})' not in OWNER_SIGN_IN_HTML
    assert 'id="pin-toggle"' in OWNER_SIGN_IN_HTML


def test_owner_auth_fails_closed_when_durable_store_is_unavailable():
    service = OwnerAuthService()
    service.mark_persistence_unavailable()
    assert_http_error(503, lambda: service.create_activation(OWNER))
    assert_http_error(503, lambda: service.sign_in_with_pin(OWNER["phone_number"], "Owner1234"))


def test_sign_in_page_does_not_mask_configuration_or_store_failure(monkeypatch):
    service = OwnerAuthService()
    service.mark_persistence_unavailable()
    owner = {**OWNER, "pharmacy_name": "Afya Pharmacy", "active": "yes", "status": "active"}

    class Registry:
        def find_by_id(self, pharmacy_id, active_only=True):
            return owner if pharmacy_id == "pharmacy-a" and active_only else None

    monkeypatch.setenv("PHARMAREEN_DEFAULT_PHARMACY_ID", "pharmacy-a")
    monkeypatch.setattr(main, "get_pharmacy_registry", lambda: Registry())
    monkeypatch.setattr(main, "owner_auth_service", service)
    with TestClient(main.app, base_url="https://ms20.test", raise_server_exceptions=False) as client:
        response = client.get("/main-app/sign-in")

    assert response.status_code == 503
    assert "Owner sign in" not in response.text
    assert "Activate first owner" not in response.text


def test_configured_persistence_receives_only_digests_and_hashes():
    saved: list[dict] = []
    durable: dict = {"activations": {}, "credentials": {}}

    def save(payload):
        durable.clear()
        durable.update(payload)
        saved.append(payload)

    service = OwnerAuthService()
    service.configure_persistence(loader=lambda: durable, saver=save)
    raw, _ = service.create_activation(OWNER, now=100)
    service.activate(raw, "Owner1234", now=101)
    serialized = repr(saved)
    assert raw not in serialized
    assert "Owner1234" not in serialized
    assert "pbkdf2_sha256$600000$" in serialized


def test_owner_auth_store_uses_platform_admin_or_existing_registry_workbook(monkeypatch):
    registry_settings = Settings(
        GOOGLE_SHEET_ID="registry-workbook",
        GOOGLE_SERVICE_ACCOUNT_JSON="unused.json",
    )
    assert owner_auth_sheet_id(registry_settings) == "registry-workbook"

    admin_settings = Settings(
        GOOGLE_SHEET_ID="registry-workbook",
        PHARMAREEN_ADMIN_SHEET_ID="platform-admin-workbook",
        GOOGLE_SERVICE_ACCOUNT_JSON="unused.json",
    )
    assert owner_auth_sheet_id(admin_settings) == "platform-admin-workbook"

    opened: list[str] = []

    class Client:
        def open_by_key(self, sheet_id):
            opened.append(sheet_id)
            return object()

    store = GoogleSheetsOwnerAuthStateStore(registry_settings)
    monkeypatch.setattr(store._onboarding, "_gspread_client", lambda: Client())
    store._spreadsheet()
    assert opened == ["registry-workbook"]


def test_durable_store_load_failure_is_not_treated_as_empty_valid_state():
    service = OwnerAuthService()
    with pytest.raises(RuntimeError, match="workbook unavailable"):
        service.configure_persistence(
            loader=lambda: (_ for _ in ()).throw(RuntimeError("workbook unavailable")),
            saver=lambda _payload: None,
        )


def test_operations_bootstrap_never_leaves_onboarding_visible_when_state_is_unavailable_or_unresolved():
    app_source = (Path(__file__).resolve().parents[1] / "ms20-main-app" / "src" / "app.js").read_text(encoding="utf-8")
    assert 'removeCardsByType(["OnboardingCard", "CatalogOnboardingCard"]);' in app_source
    assert 'state.operationsBootstrap?.state === "recovery_or_setup_required"' in app_source
    assert 'return "Pharmacy state unavailable"' in app_source
    assert "Only a genuinely new pharmacy starts setup." in app_source
