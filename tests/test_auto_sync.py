from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_auto_sync_logic_exists():
    script = (Path(__file__).resolve().parents[1] / "local" / "offline.js").read_text(encoding="utf-8")

    assert "navigator.onLine" in script
    assert "setInterval(syncActions, 30000)" in script
    assert 'fetch("/sync/offline-actions"' in script


def test_offline_app_index_is_served_as_static_html():
    with TestClient(app) as client:
        response = client.get("/offline_app/index.html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "MS2.0 Offline" in response.text
