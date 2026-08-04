from fastapi.testclient import TestClient

from app import main


class FakeSheetStore:
    is_available = True

    def __init__(self):
        self.rows = []

    def find_offline_sync_action(self, action_id):
        return next((row for row in reversed(self.rows) if row.get("action_id") == action_id), None)

    def append_offline_sync_log(self, row):
        self.rows.append(dict(row))


class UnavailableSheetStore:
    is_available = False


def test_connection_test_writes_once_without_medicine_data(monkeypatch):
    store = FakeSheetStore()
    monkeypatch.setattr(main, "get_sheet_store", lambda: store)
    monkeypatch.setattr(main, "live_pharmacy_id", lambda: "pharmacy-one")
    client = TestClient(main.app)
    body = {"action_id": "ms20-connection-test-001", "pharmacy_id": "pharmacy-one"}

    first = client.post("/api/ms20/sync/connection-test", json=body).json()
    second = client.post("/api/ms20/sync/connection-test", json=body).json()

    assert first["status"] == "saved"
    assert second["status"] == "already_saved"
    assert len(store.rows) == 1
    assert store.rows[0]["action_type"] == "connection_test"
    assert store.rows[0]["drug_name"] == ""
    assert store.rows[0]["quantity"] == ""


def test_connection_test_blocks_other_pharmacy(monkeypatch):
    store = FakeSheetStore()
    monkeypatch.setattr(main, "get_sheet_store", lambda: store)
    monkeypatch.setattr(main, "live_pharmacy_id", lambda: "pharmacy-one")
    response = TestClient(main.app).post(
        "/api/ms20/sync/connection-test",
        json={"action_id": "ms20-connection-test-002", "pharmacy_id": "pharmacy-two"},
    ).json()
    assert response["status"] == "error"
    assert store.rows == []


def test_connection_test_binds_omitted_pharmacy_to_live_configuration(monkeypatch):
    store = FakeSheetStore()
    monkeypatch.setattr(main, "get_sheet_store", lambda: store)
    monkeypatch.setattr(main, "live_pharmacy_id", lambda: "pharmacy-one")

    response = TestClient(main.app).post(
        "/api/ms20/sync/connection-test",
        json={"action_id": "ms20-connection-test-003"},
    ).json()

    assert response["status"] == "saved"
    assert response["pharmacy_id"] == "pharmacy_one"
    assert len(store.rows) == 1
    assert store.rows[0]["source"] == "ms20_main_app:pharmacy_one"


def test_connection_test_waits_without_write_when_sheets_are_unavailable(monkeypatch):
    monkeypatch.setattr(main, "get_sheet_store", lambda: UnavailableSheetStore())
    monkeypatch.setattr(main, "live_pharmacy_id", lambda: "pharmacy-one")

    response = TestClient(main.app).post(
        "/api/ms20/sync/connection-test",
        json={"action_id": "ms20-connection-test-004"},
    ).json()

    assert response == {
        "status": "waiting",
        "message": "Google Sheets is not ready. Nothing was changed.",
    }
