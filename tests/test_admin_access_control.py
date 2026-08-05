from fastapi.testclient import TestClient

from app import main
from app.owner_auth import OwnerAuthService
from app.routes import admin as admin_routes
from app.config import Settings, get_settings


def test_admin_session_and_routes_fail_closed_without_configured_secret():
    main.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        PHARMAREEN_ADMIN_ACCESS_TOKEN="",
        GOOGLE_SERVICE_ACCOUNT_JSON="",
    )
    try:
        with TestClient(main.app) as client:
            session = client.get("/api/ms20/admin/session")
            admin_page = client.get("/admin/onboard")
    finally:
        main.app.dependency_overrides.pop(get_settings, None)

    assert session.status_code == 503
    assert session.json()["detail"] == "Admin access is not configured."
    assert admin_page.status_code == 503


def test_admin_session_rejects_wrong_token_and_returns_fixed_capabilities_for_valid_token():
    main.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        PHARMAREEN_ADMIN_ACCESS_TOKEN="ms20-test-admin-secret",
        PHARMAREEN_DEFAULT_PHARMACY_ID="test-pharmacy",
        GOOGLE_SERVICE_ACCOUNT_JSON="",
    )
    try:
        with TestClient(main.app) as client:
            missing = client.get("/api/ms20/admin/session")
            wrong = client.get(
                "/api/ms20/admin/session",
                headers={"Authorization": "Bearer wrong-secret"},
            )
            valid = client.get(
                "/api/ms20/admin/session",
                headers={"Authorization": "Bearer ms20-test-admin-secret"},
            )
            admin_page = client.get(
                "/admin/onboard",
                headers={"Authorization": "Bearer ms20-test-admin-secret"},
            )
    finally:
        main.app.dependency_overrides.pop(get_settings, None)

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert wrong.headers["www-authenticate"] == "Bearer"
    assert valid.status_code == 200
    assert valid.json() == {
        "authenticated": True,
        "actor_id": "admin_session",
        "role": "admin",
        "pharmacy_id": "test-pharmacy",
        "capabilities": [
            "pharmacy:create",
            "pharmacy:list",
            "pharmacy:read",
            "onboarding:review",
            "deployment:manage",
        ],
        "customer_flow": False,
    }
    assert admin_page.status_code == 200


def test_admin_activation_is_protected_bound_and_locally_rendered(monkeypatch):
    class PharmacyService:
        def get_pharmacy(self, pharmacy_id):
            if pharmacy_id != "test-pharmacy":
                return None
            return {
                "pharmacy_id": pharmacy_id,
                "pharmacy_name": "Afya Pharmacy",
                "owner_name": "Mary",
                "phone_number": "+254700000001",
                "active": "yes",
            }

    main.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        PHARMAREEN_ADMIN_ACCESS_TOKEN="ms20-test-admin-secret",
        GOOGLE_SERVICE_ACCOUNT_JSON="",
    )
    monkeypatch.setattr(admin_routes, "service", lambda: PharmacyService())
    monkeypatch.setattr(admin_routes, "owner_auth_service", OwnerAuthService())
    monkeypatch.setenv("PHARMAREEN_OWNER_ACTIVATION_PHARMACY_ID", "test-pharmacy")
    try:
        with TestClient(main.app, base_url="https://stage.ms20.test") as client:
            blocked = client.post("/admin/pharmacy/test-pharmacy/owner-activation")
            created = client.post(
                "/admin/pharmacy/test-pharmacy/owner-activation",
                headers={"Authorization": "Bearer ms20-test-admin-secret"},
            )
            outside = client.post(
                "/admin/pharmacy/other-pharmacy/owner-activation",
                headers={"Authorization": "Bearer ms20-test-admin-secret"},
            )
    finally:
        main.app.dependency_overrides.pop(get_settings, None)

    data = created.json()
    assert blocked.status_code == 401
    assert created.status_code == 200
    assert data["pharmacy_id"] == "test-pharmacy"
    assert data["activation_url"].startswith("https://stage.ms20.test/main-app/activate#token=")
    assert data["qr_data_uri"].startswith("data:image/png;base64,")
    assert outside.status_code == 403
