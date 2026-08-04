from fastapi.testclient import TestClient

from app import main
from app.config import Settings, get_settings


def test_admin_session_and_routes_fail_closed_without_configured_secret():
    main.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        PHARMAREEN_ADMIN_ACCESS_TOKEN="",
        GOOGLE_SERVICE_ACCOUNT_JSON="",
    )
    try:
        with TestClient(main.app) as client:
            session = client.get("/api/ms20/auth/session")
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
            missing = client.get("/api/ms20/auth/session")
            wrong = client.get(
                "/api/ms20/auth/session",
                headers={"Authorization": "Bearer wrong-secret"},
            )
            valid = client.get(
                "/api/ms20/auth/session",
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
    }
    assert admin_page.status_code == 200
